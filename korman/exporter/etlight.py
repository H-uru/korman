#    This file is part of Korman.
#
#    Korman is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Korman is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Korman.  If not, see <http://www.gnu.org/licenses/>.

import bpy

from contextlib import contextmanager
import itertools

from .explosions import *
from .logger import ExportProgressLogger, ExportVerboseLogger
from .mesh import _MeshManager, _VERTEX_COLOR_LAYERS
from ..helpers import *

_NUM_RENDER_LAYERS = 20

class LightBaker:
    """ExportTime Lighting"""

    def __init__(self, *, mesh=None, report=None, verbose=False):
        self._lightgroups = {}
        if report is None:
            self._report = ExportVerboseLogger() if verbose else ExportProgressLogger()
            self.add_progress_steps(self._report, True)
            self._report.progress_start("BAKING LIGHTING")
            self._own_report = True
        else:
            self._report = report
            self._own_report = False

        # This used to be the base class, but due to the need to access the export state
        # which may be stored in the exporter's mesh manager, we've changed from is-a to has-a
        # semantics. Sorry for this confusion!
        self._mesh = _MeshManager(self._report) if mesh is None else mesh

        self.vcol_layer_name = "autocolor"
        self.lightmap_name = "{}_LIGHTMAPGEN.png"
        self.lightmap_uvtex_name = "LIGHTMAPGEN"
        self.retain_lightmap_uvtex = True
        self.force = False
        self._lightmap_images = {}
        self._uvtexs = {}
        self._active_vcols = {}

    def __del__(self):
        if self._own_report:
            self._report.progress_end()

    def __enter__(self):
        self._mesh.__enter__()
        return self

    def __exit__(self, *exc_info):
        self._mesh.__exit__(*exc_info)

    @staticmethod
    def add_progress_steps(report, add_base=False):
        if add_base:
            _MeshManager.add_progress_presteps(report)
        report.progress_add_step("Searching for Bahro")
        report.progress_add_step("Baking Static Lighting")

    def _apply_render_settings(self, toggle, vcols):
        render = bpy.context.scene.render

        # Remember, lightmaps carefully control the enabled textures such that light
        # can be cast through transparent materials. See diatribe in lightmap prep.
        toggle.track(render, "use_textures", not vcols)
        toggle.track(render, "use_shadows", True)
        toggle.track(render, "use_envmaps", True)
        toggle.track(render, "use_raytrace", True)
        toggle.track(render, "bake_type", "FULL")
        toggle.track(render, "use_bake_clear", True)
        toggle.track(render, "use_bake_to_vertex_color", vcols)

    def _associate_image_with_uvtex(self, uvtex, im):
        # Associate the image with all the new UVs
        # NOTE: no toggle here because it's the artist's problem if they are looking at our
        #       super swagalicious LIGHTMAPGEN uvtexture...
        for i in uvtex.data:
            i.image = im

    def _bake_lightmaps(self, objs, layers):
        with GoodNeighbor() as toggle:
            scene = bpy.context.scene
            scene.layers = layers
            self._apply_render_settings(toggle, False)
            self._select_only(objs, toggle)
            bpy.ops.object.bake_image()
            self._pack_lightmaps(objs)

    def _bake_vcols(self, objs, layers):
        with GoodNeighbor() as toggle:
            bpy.context.scene.layers = layers
            self._apply_render_settings(toggle, True)
            self._select_only(objs, toggle)
            bpy.ops.object.bake_image()

    def bake_static_lighting(self, objs):
        """Bakes all static lighting for Plasma geometry"""

        self._report.msg("\nBaking Static Lighting...")

        with GoodNeighbor() as toggle:
            try:
                # reduce the amount of indentation
                bake = self._harvest_bakable_objects(objs, toggle)
                result = self._bake_static_lighting(bake, toggle)
            finally:
                # this stuff has been observed to be problematic with GoodNeighbor
                self._pop_lightgroups()
                self._restore_uvtexs()
                self._restore_vcols()
                if not self.retain_lightmap_uvtex:
                    self._remove_stale_uvtexes(bake)
            return result

    def _bake_static_lighting(self, bake, toggle):
        inc_progress = self._report.progress_increment

        # Lightmap passes are expensive, so we will warn about any passes that seem
        # particularly wasteful.
        try:
            largest_pass = max((len(value) for key, value in bake.items() if key[0] != "vcol"))
        except ValueError:
            largest_pass = 0

        # Step 0.9: Make all layers visible.
        #           This prevents context operators from phailing.
        bpy.context.scene.layers = (True,) * _NUM_RENDER_LAYERS

        # Step 1: Prepare... Apply UVs, etc, etc, etc
        self._report.progress_advance()
        self._report.progress_range = len(bake)
        self._report.msg("Preparing to bake...", indent=1)
        for key, value in bake.items():
            if key[0] == "lightmap":
                for i in range(len(value)-1, -1, -1):
                    obj = value[i]
                    if not self._prep_for_lightmap(obj, toggle):
                        self._report.msg("Lightmap '{}' will not be baked -- no applicable lights",
                                         obj.name, indent=2)
                        value.pop(i)
            elif key[0] == "vcol":
                for i in range(len(value)-1, -1, -1):
                    obj = value[i]
                    if not self._prep_for_vcols(obj, toggle):
                        if self._has_valid_material(obj):
                            self._report.msg("VCols '{}' will not be baked -- no applicable lights",
                                             obj.name, indent=2)
                        value.pop(i)
            else:
                raise RuntimeError(key[0])
            inc_progress()
        self._report.msg("    ...")

        # Step 2: BAKE!
        self._report.progress_advance()
        self._report.progress_range = len(bake)
        for key, value in bake.items():
            if value:
                if key[0] == "lightmap":
                    num_objs = len(value)
                    self._report.msg("{} Lightmap(s) [H:{:X}]", num_objs, hash(key[1:]), indent=1)
                    if largest_pass > 1 and num_objs < round(largest_pass * 0.02):
                        pass_names = set((i.plasma_modifiers.lightmap.bake_pass_name for i in value))
                        pass_msg = ", ".join(pass_names)
                        self._report.warn("Small lightmap bake pass! Bake Pass(es): {}".format(pass_msg), indent=2)
                    self._bake_lightmaps(value, key[1:])
                elif key[0] == "vcol":
                    self._report.msg("{} Vertex Color(s) [H:{:X}]", len(value), hash(key[1:]), indent=1)
                    self._bake_vcols(value, key[1:])
                    self._fix_vertex_colors(value)
                else:
                    raise RuntimeError(key[0])
            inc_progress()

        # Return how many thingos we baked
        return sum(map(len, bake.values()))

    def _fix_vertex_colors(self, blender_objects):
        # Blender's lightmapper has a bug which allows vertices to "self-occlude" when shared between
        # two faces. See here https://forum.guildofwriters.org/viewtopic.php?f=9&t=6576&p=68939
        # What we're doing here is an improved version of the algorithm in the previous link.
        # For each loop, we find all other loops in the mesh sharing the same vertex, which aren't
        # separated by a sharp edge. We then take the brightest color out of all those loops, and
        # assign it back to the base loop.
        # "Sharp edges" include edges manually tagged as sharp by the user, or part of a non-smooth
        # face, or edges for which the face angle is superior to the mesh's auto-smooth threshold.
        # (If the object has an edge split modifier, well, screw you!)
        for bo in blender_objects:
            mesh = bo.data
            bm = bmesh.new()
            bm.from_mesh(mesh)

            light_vcol = bm.loops.layers.color.get(self.vcol_layer_name)

            # If no vertex color is found, then baking either failed (error raised by oven)
            # or is turned off. Either way, bail out.
            if light_vcol is None:
                bm.free()
                del bm
                continue

            bm.faces.ensure_lookup_table()

            for face in bm.faces:
                for loop in face.loops:
                    vert = loop.vert
                    max_color = loop[light_vcol]
                    if not face.smooth:
                        # Face is sharp, so we can't smooth anything.
                        continue
                    # Now that we have a loop and its vertex, find all edges the vertex connects to.
                    for edge in vert.link_edges:
                        if len(edge.link_faces) != 2:
                            # Either a border edge, or an abomination.
                            continue
                        if not edge.smooth or (mesh.use_auto_smooth and
                                               edge.calc_face_angle() > mesh.auto_smooth_angle):
                            # Sharp edge. Don't care.
                            continue
                        if face in edge.link_faces:
                            # Alright, this edge is connected to our loop AND our face.
                            # Now for the Fun Stuff(c)... First, actually get ahold of the other
                            # face (the one we're connected to via this edge).
                            other_face = next(f for f in edge.link_faces if f != face)
                            # Now get ahold of the loop sharing our vertex on the OTHER SIDE
                            # of that damnable edge...
                            other_loop = next(loop for loop in other_face.loops if loop.vert == vert)
                            other_color = other_loop[light_vcol]
                            # Phew ! Good, now just pick whichever color has the highest average value
                            if sum(max_color) / 3 < sum(other_color) / 3:
                                max_color = other_color
                    # Assign our hard-earned color back
                    loop[light_vcol] = max_color

            bm.to_mesh(mesh)
            bm.free()
            del bm

    def _generate_lightgroup(self, bo, user_lg=None):
        """Makes a new light group for the baking process that excludes all Plasma RT lamps"""
        shouldibake = (user_lg is not None and bool(user_lg.objects))
        mesh = bo.data

        for material in mesh.materials:
            if material is None:
                # material is not assigned to this material... (why is this even a thing?)
                continue

            # Already done it?
            lg, mat_name = material.light_group, material.name
            if mat_name not in self._lightgroups:
                self._lightgroups[mat_name] = lg

            if not user_lg:
                if not lg or bool(lg.objects) is False:
                    source = [i for i in bpy.context.scene.objects if i.type == "LAMP"]
                else:
                    source = lg.objects
                dest = bpy.data.groups.new("_LIGHTMAPGEN_{}_{}".format(bo.name, mat_name))

                # Rules:
                # 1) No animated lights, period.
                # 2) If we accept runtime lighting, no Plasma Objects
                rtl_mod = bo.plasma_modifiers.lighting
                for obj in source:
                    if obj.plasma_object.has_animation_data:
                        continue
                    if rtl_mod.rt_lights and obj.plasma_object.enabled:
                        continue
                    dest.objects.link(obj)
                    shouldibake = True
            else:
                # The aforementioned rules do not apply. You better hope you know WTF you are
                # doing. I'm not going to help!
                dest = user_lg
            material.light_group = dest
        return shouldibake

    def get_lightmap(self, bo):
        return self._lightmap_images.get(bo.name)

    def get_lightmap_name(self, bo):
        return self.lightmap_name.format(bo.name)

    def _has_valid_material(self, bo):
        for material in bo.data.materials:
            if material is not None:
                return True
        return False

    def _harvest_bakable_objects(self, objs, toggle):
        # The goal here is to minimize the calls to bake_image, so we are going to collect everything
        # that needs to be baked and sort it out by configuration.
        default_layers = tuple((True,) * _NUM_RENDER_LAYERS)
        bake, bake_passes = {}, bpy.context.scene.plasma_scene.bake_passes
        bake_vcol = bake.setdefault(("vcol",) + default_layers, [])

        def lightmap_bake_required(obj) -> bool:
            mod = obj.plasma_modifiers.lightmap
            if mod.bake_lightmap:
                if self.force:
                    return True
                if mod.image is not None:
                    uv_texture_names = frozenset((i.name for i in obj.data.uv_textures))
                    if self.lightmap_uvtex_name in uv_texture_names:
                        self._report.msg("'{}': Skipping due to valid lightmap override", obj.name, indent=1)
                    else:
                        self._report.warn("'{}': Have lightmap, but regenerating UVs", obj.name, indent=1)
                        self._prep_for_lightmap_uvs(obj, mod.image, toggle)
                    return False
                return True
            return False

        def vcol_bake_required(obj) -> bool:
            if obj.plasma_modifiers.lightmap.bake_lightmap:
                return False
            vcol_layer_names = frozenset((vcol_layer.name.lower() for vcol_layer in obj.data.vertex_colors))
            manual_layer_names = _VERTEX_COLOR_LAYERS & vcol_layer_names
            if manual_layer_names:
                self._report.msg("'{}': Skipping due to valid manual vertex color layer(s): '{}'", obj.name, manual_layer_names.pop(), indent=1)
                return False
            if self.force:
                return True
            if self.vcol_layer_name.lower() in vcol_layer_names:
                self._report.msg("'{}': Skipping due to valid matching vertex color layer(s): '{}'", obj.name, self.vcol_layer_name, indent=1)
                return False
            return True

        for i in filter(lambda x: x.type == "MESH" and bool(x.data.materials), objs):
            mods = i.plasma_modifiers
            lightmap_mod = mods.lightmap
            if lightmap_mod.enabled:
                if lightmap_mod.bake_pass_name:
                    bake_pass = bake_passes.get(lightmap_mod.bake_pass_name, None)
                    if bake_pass is None:
                        raise ExportError("Bake Lighting '{}': Could not find pass '{}'".format(i.name, lightmap_mod.bake_pass_name))
                    lm_layers = tuple(bake_pass.render_layers)
                else:
                    lm_layers = default_layers

                # In order for Blender to be able to bake this properly, at least one of the
                # layers this object is on must be selected. We will sanity check this now.
                obj_layers = tuple(i.layers)
                lm_active_layers = set((i for i, value in enumerate(lm_layers) if value))
                obj_active_layers = set((i for i, value in enumerate(obj_layers) if value))
                if not lm_active_layers & obj_active_layers:
                    raise ExportError("Bake Lighting '{}': At least one layer the object is on must be selected".format(i.name))

                if lightmap_bake_required(i) is False and vcol_bake_required(i) is False:
                    continue

                method = "lightmap" if lightmap_mod.bake_lightmap else "vcol"
                key = (method,) + lm_layers
                bake_pass = bake.setdefault(key, [])
                bake_pass.append(i)
                self._report.msg("'{}': Bake to {}", i.name, method, indent=1)
            elif mods.lighting.preshade and vcol_bake_required(i):
                self._report.msg("'{}': Bake to vcol (crappy)", i.name, indent=1)
                bake_vcol.append(i)
        return bake

    def _pack_lightmaps(self, objs):
        for bo in objs:
            im = self.get_lightmap(bo)
            if im is not None and im.is_dirty:
                im.pack(as_png=True)

    def _pop_lightgroups(self):
        materials = bpy.data.materials
        for mat_name, lg in self._lightgroups.items():
            materials[mat_name].light_group = lg
        self._lightgroups.clear()

        groups = bpy.data.groups
        for i in groups:
            if i.name.startswith("_LIGHTMAPGEN_"):
                bpy.data.groups.remove(i)

    def _prep_for_lightmap(self, bo, toggle):
        mesh = bo.data
        modifier = bo.plasma_modifiers.lightmap
        uv_textures = mesh.uv_textures

        # Previously, we told Blender to just ignore textures althogether when baking
        # VCols or lightmaps. This is easy, but it prevents us from doing tricks like
        # using the "Receive Transparent" option, which allows for light to be cast
        # through sections of materials that are transparent. Therefore, on objects
        # that are lightmapped, we will disable all the texture slots...
        # Due to our batching, however, materials that are transparent cannot be lightmapped.
        for material in (i for i in mesh.materials if i is not None):
            if material.use_transparency:
                raise ExportError("'{}': Cannot lightmap material '{}' because it is transparnt".format(bo.name, material.name))
            for slot in (j for j in material.texture_slots if j is not None):
                toggle.track(slot, "use", False)

        # Create a special light group for baking
        if not self._generate_lightgroup(bo, modifier.lights):
            return False

        # We need to ensure that we bake onto the "BlahObject_LIGHTMAPGEN" image
        data_images = bpy.data.images
        im_name = self.get_lightmap_name(bo)
        size = modifier.resolution

        im = data_images.get(im_name)
        if im is None:
            im = data_images.new(im_name, width=size, height=size)
        elif im.size[0] != size:
            # Force delete and recreate the image because the size is out of date
            data_images.remove(im)
            im = data_images.new(im_name, width=size, height=size)
        self._lightmap_images[bo.name] = im

        self._prep_for_lightmap_uvs(bo, im, toggle)

        # Now, set the new LIGHTMAPGEN uv layer as what we want to render to...
        # NOTE that this will need to be reset by us to what the user had previously
        # Not using toggle.track due to observed oddities
        for i in uv_textures:
            value = i.name == self.lightmap_uvtex_name
            i.active = value
            i.active_render = value

        # Indicate we should bake
        return True

    def _prep_for_lightmap_uvs(self, bo, image, toggle):
        mesh = bo.data
        modifier = bo.plasma_modifiers.lightmap
        uv_textures = mesh.uv_textures

        # If there is a cached LIGHTMAPGEN uvtexture, nuke it
        uvtex = uv_textures.get(self.lightmap_uvtex_name, None)
        if uvtex is not None:
            uv_textures.remove(uvtex)

        # Make sure we can enter Edit Mode(TM)
        toggle.track(bo, "hide", False)

        # Because the way Blender tracks active UV layers is massively stupid...
        if uv_textures.active is not None:
            self._uvtexs[mesh.name] = uv_textures.active.name

        # We must make this the active object before touching any operators
        bpy.context.scene.objects.active = bo

        # Originally, we used the lightmap unpack UV operator to make our UV texture, however,
        # this tended to create sharp edges. There was already a discussion about this on the
        # Guild of Writers forum, so I'm implementing a code version of dendwaler's process,
        # as detailed here: https://forum.guildofwriters.org/viewtopic.php?p=62572#p62572
        # This has been amended with Sirius's observations in GH-265 about forced uv map
        # packing. Namely, don't do it unless modifiers make us.
        uv_base = uv_textures.get(modifier.uv_map) if modifier.uv_map else None
        if uv_base is not None:
            uv_textures.active = uv_base

            # this will copy the UVs to the new UV texture
            uvtex = uv_textures.new(self.lightmap_uvtex_name)
            uv_textures.active = uvtex

            # if the artist hid any UVs, they will not be baked to... fix this now
            with self._set_mode("EDIT"):
                bpy.ops.uv.reveal()
            self._associate_image_with_uvtex(uv_textures.active, image)

            # Meshes with modifiers need to have islands packed to prevent generated vertices
            # from sharing UVs. Sigh.
            if self._mesh.is_collapsed(bo):
                # Danger: uv_base.name -> UnicodeDecodeError (wtf? another blender bug?)
                self._report.warn("'{}': packing islands in UV Texture '{}' due to modifier collapse",
                                  bo.name, modifier.uv_map, indent=2)
                with self._set_mode("EDIT"):
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.uv.select_all(action="SELECT")
                    bpy.ops.uv.pack_islands(margin=0.01)
        else:
            # same thread, see Sirius's suggestion RE smart unwrap. this seems to yield good
            # results in my tests. it will be good enough for quick exports.
            uvtex = uv_textures.new(self.lightmap_uvtex_name)
            uv_textures.active = uvtex
            self._associate_image_with_uvtex(uvtex, image)
            with self._set_mode("EDIT"):
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.smart_project(island_margin=0.05)

    def _prep_for_vcols(self, bo, toggle):
        mesh = bo.data
        modifier = bo.plasma_modifiers.lightmap
        vcols = mesh.vertex_colors

        # Create a special light group for baking
        user_lg = modifier.lights if modifier.enabled else None
        if not self._generate_lightgroup(bo, user_lg):
            return False

        vcol_layer_name = self.vcol_layer_name
        autocolor = vcols.get(vcol_layer_name)
        needs_vcol_layer = autocolor is None
        if needs_vcol_layer:
            autocolor = vcols.new(vcol_layer_name)

        self._active_vcols[mesh] = (
            next(i for i, vc in enumerate(mesh.vertex_colors) if vc.active),
            next(i for i, vc in enumerate(mesh.vertex_colors) if vc.active_render),
        )
        # Mark "autocolor" as our active render layer
        for vcol_layer in mesh.vertex_colors:
            autocol = vcol_layer.name == vcol_layer_name
            vcol_layer.active_render = autocol
            vcol_layer.active = autocol
        mesh.update()

        # Vertex colors are sort of ephemeral, so if we have an exit stack, we want to
        # terminate this layer when the exporter is done. But, this is not an unconditional
        # nukage. If we're in the lightmap operators, we clearly want this to persist for
        # future exports as an optimization. We won't reach this point if there is already an
        # autocolor layer (gulp).
        if not self.force and needs_vcol_layer:
            self._mesh.context_stack.enter_context(TemporaryObject(vcol_layer.name, lambda layer_name: vcols.remove(vcols[layer_name])))

        # Indicate we should bake
        return True

    def _remove_stale_uvtexes(self, bake):
        lightmap_iter = itertools.chain.from_iterable((value for key, value in bake.items() if key[0] == "lightmap"))
        for bo in lightmap_iter:
            uv_textures = bo.data.uv_textures
            uvtex = uv_textures.get(self.lightmap_uvtex_name, None)
            if uvtex is not None:
                uv_textures.remove(uvtex)

    def _restore_uvtexs(self):
        for mesh_name, uvtex_name in self._uvtexs.items():
            mesh = bpy.data.meshes[mesh_name]
            for i in mesh.uv_textures:
                i.active = uvtex_name == i.name
            mesh.uv_textures.active = mesh.uv_textures[uvtex_name]

    def _restore_vcols(self):
        for mesh, (vcol_index, vcol_render_index) in self._active_vcols.items():
            mesh.vertex_colors[vcol_index].active = True
            mesh.vertex_colors[vcol_render_index].active_render = True

    def _select_only(self, objs, toggle):
        if isinstance(objs, bpy.types.Object):
            toggle.track(objs, "hide_render", False)
            for i in bpy.data.objects:
                if i == objs:
                    # prevents proper baking to texture
                    for mat in (j for j in i.data.materials if j is not None):
                        toggle.track(mat, "use_vertex_color_paint", False)
                    i.select = True
                else:
                    i.select = False

                if isinstance(i.data, bpy.types.Mesh) and not self._has_valid_material(i):
                    toggle.track(i, "hide_render", True)
        else:
            for i in bpy.data.objects:
                value = i in objs
                if value:
                    # prevents proper baking to texture
                    for mat in (j for j in i.data.materials if j is not None):
                        toggle.track(mat, "use_vertex_color_paint", False)
                    toggle.track(i, "hide_render", False)
                elif isinstance(i.data, bpy.types.Mesh) and not self._has_valid_material(i):
                    toggle.track(i, "hide_render", True)
                i.select = value

    @contextmanager
    def _set_mode(self, mode):
        bpy.ops.object.mode_set(mode=mode)
        try:
            yield
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
