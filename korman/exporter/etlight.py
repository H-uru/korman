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
from bpy.app.handlers import persistent

from .mesh import _VERTEX_COLOR_LAYERS
from ..helpers import *

_NUM_RENDER_LAYERS = 20

class LightBaker:
    """ExportTime Lighting"""

    def __init__(self):
        self._lightgroups = {}
        self._uvtexs = {}

    def _apply_render_settings(self, toggle):
        render = bpy.context.scene.render
        toggle.track(render, "use_textures", False)
        toggle.track(render, "use_shadows", True)
        toggle.track(render, "use_envmaps", False)
        toggle.track(render, "use_raytrace", True)
        toggle.track(render, "bake_type", "FULL")
        toggle.track(render, "use_bake_clear", True)

    def _associate_image_with_uvtex(self, uvtex, im):
        # Associate the image with all the new UVs
        # NOTE: no toggle here because it's the artist's problem if they are looking at our
        #       super swagalicious LIGHTMAPGEN uvtexture...
        for i in uvtex.data:
            i.image = im

    def _bake_lightmaps(self, objs, layers, toggle):
        scene = bpy.context.scene
        scene.layers = layers
        toggle.track(scene.render, "use_bake_to_vertex_color", False)
        self._select_only(objs)
        bpy.ops.object.bake_image()

    def _bake_vcols(self, objs, toggle):
        bpy.context.scene.layers = (True,) * _NUM_RENDER_LAYERS
        toggle.track(bpy.context.scene.render, "use_bake_to_vertex_color", True)
        self._select_only(objs)
        bpy.ops.object.bake_image()

    def bake_static_lighting(self, objs):
        """Bakes all static lighting for Plasma geometry"""

        print("\nBaking Static Lighting...")
        bake = self._harvest_bakable_objects(objs)

        with GoodNeighbor() as toggle:
            try:
                # reduce the amount of indentation
                self._bake_static_lighting(bake, toggle)
            finally:
                # this stuff has been observed to be problematic with GoodNeighbor
                self._pop_lightgroups()
                self._restore_uvtexs()

    def _bake_static_lighting(self, bake, toggle):
        # Step 0.9: Make all layers visible.
        #           This prevents context operators from phailing.
        bpy.context.scene.layers = (True,) * _NUM_RENDER_LAYERS

        # Step 1: Prepare... Apply UVs, etc, etc, etc
        for key, value in bake.copy().items():
            if key[0] == "lightmap":
                for i in value:
                    if not self._prep_for_lightmap(i, toggle):
                        bake[key].remove(i)
            elif key[0] == "vcol":
                for i in value:
                    if not self._prep_for_vcols(i, toggle):
                        bake[key].remove(i)
            else:
                raise RuntimeError(key[0])

        # Step 2: BAKE!
        self._apply_render_settings(toggle)
        for key, value in bake.items():
            if not value:
                continue

            if key[0] == "lightmap":
                print("    {} Lightmap(s) [H:{:X}]".format(len(value), hash(key)))
                self._bake_lightmaps(value, key[1:], toggle)
            elif key[0] == "vcol":
                print("    {} Crap Light(s)".format(len(value)))
                self._bake_vcols(value, toggle)
            else:
                raise RuntimeError(key[0])

    def _generate_lightgroup(self, mesh, user_lg=None):
        """Makes a new light group for the baking process that excludes all Plasma RT lamps"""

        if user_lg is not None:
            user_lg = bpy.data.groups.get(user_lg)
        shouldibake = (user_lg and user_lg.objects)

        for material in mesh.materials:
            if material is None:
                # material is not assigned to this material... (why is this even a thing?)
                continue

            # Already done it?
            name = material.name
            lg = material.light_group
            if name in self._lightgroups:
                # No, this is not Pythonic, but bpy_prop_collection is always "True",
                # even when empty. Sigh.
                return bool(len(lg.objects))
            else:
                self._lightgroups[name] = lg

            if user_lg is None:
                if not lg or len(lg.objects) == 0:
                    source = [i for i in bpy.data.objects if i.type == "LAMP"]
                else:
                    source = lg.objects
                dest = bpy.data.groups.new("_LIGHTMAPGEN_{}".format(name))

                # Only use non-RT lights
                for obj in source:
                    if obj.plasma_object.enabled:
                        continue
                    dest.objects.link(obj)
                    shouldibake = True
            else:
                dest = user_lg
            material.light_group = dest
        return shouldibake

    def _get_lightmap_uvtex(self, mesh, modifier):
        if modifier.uv_map:
            return mesh.uv_textures[modifier.uv_map]
        for i in mesh.uv_textures:
            if i.name != "LIGHTMAPGEN":
                return i
        return None

    def _harvest_bakable_objects(self, objs):
        # The goal here is to minimize the calls to bake_image, so we are going to collect everything
        # that needs to be baked and sort it out by configuration.
        bake = { ("vcol",): [] }
        for i in objs:
            if i.type != "MESH":
                continue

            mods = i.plasma_modifiers
            if mods.lightmap.enabled:
                key = ("lightmap",) + tuple(mods.lightmap.render_layers)
                if key in bake:
                    bake[key].append(i)
                else:
                    bake[key] = [i,]
            elif not mods.water_basic.enabled:
                vcols = i.data.vertex_colors
                for j in _VERTEX_COLOR_LAYERS:
                    if j in vcols:
                        break
                else:
                    bake[("vcol",)].append(i)
        return bake

    def _pop_lightgroups(self):
        for mat_name, lg in self._lightgroups.items():
            material = bpy.data.materials[mat_name]
            _fake = material.light_group
            if _fake is not None and _fake.name.startswith("_LIGHTMAPGEN"):
                for i in _fake.objects:
                    _fake.objects.unlink(i)
                _fake.user_clear()
                bpy.data.groups.remove(_fake)
            material.light_group = lg
        self._lightgroups.clear()

    def _prep_for_lightmap(self, bo, toggle):
        mesh = bo.data
        modifier = bo.plasma_modifiers.lightmap
        uv_textures = mesh.uv_textures

        # Create a special light group for baking
        if not self._generate_lightgroup(mesh, modifier.light_group):
            return False

        # We need to ensure that we bake onto the "BlahObject_LIGHTMAPGEN" image
        data_images = bpy.data.images
        im_name = "{}_LIGHTMAPGEN.png".format(bo.name)
        size = modifier.resolution

        im = data_images.get(im_name)
        if im is None:
            im = data_images.new(im_name, width=size, height=size)
        elif im.size[0] != size:
            # Force delete and recreate the image because the size is out of date
            im.user_clear()
            data_images.remove(im)
            im = data_images.new(im_name, width=size, height=size)

        # If there is a cached LIGHTMAPGEN uvtexture, nuke it
        uvtex = uv_textures.get("LIGHTMAPGEN", None)
        if uvtex is not None:
            uv_textures.remove(uvtex)

        # Make sure the object can be baked to. NOTE this also makes sure we can enter edit mode
        # TROLLING LOL LOL LOL
        toggle.track(bo, "hide", False)
        toggle.track(bo, "hide_render", False)
        toggle.track(bo, "hide_select", False)

        # Because the way Blender tracks active UV layers is massively stupid...
        self._uvtexs[mesh.name] = uv_textures.active.name

        # We must make this the active object before touching any operators
        bpy.context.scene.objects.active = bo

        # Originally, we used the lightmap unpack UV operator to make our UV texture, however,
        # this tended to create sharp edges. There was already a discussion about this on the
        # Guild of Writers forum, so I'm implementing a code version of dendwaler's process,
        # as detailed here: https://forum.guildofwriters.org/viewtopic.php?p=62572#p62572
        uv_base = self._get_lightmap_uvtex(mesh, modifier)
        if uv_base is not None:
            uv_textures.active = uv_base
            # this will copy the UVs to the new UV texture
            uvtex = uv_textures.new("LIGHTMAPGEN")
            uv_textures.active = uvtex
            self._associate_image_with_uvtex(uvtex, im)
            # here we go...
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.average_islands_scale()
            bpy.ops.uv.pack_islands()
        else:
            # same thread, see Sirius's suggestion RE smart unwrap. this seems to yield good
            # results in my tests. it will be good enough for quick exports.
            uvtex = uv_textures.new("LIGHTMAPGEN")
            self._associate_image_with_uvtex(uvtex, im)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project()
        bpy.ops.object.mode_set(mode="OBJECT")

        # Now, set the new LIGHTMAPGEN uv layer as what we want to render to...
        # NOTE that this will need to be reset by us to what the user had previously
        # Not using toggle.track due to observed oddities
        for i in uv_textures:
            value = i.name == "LIGHTMAPGEN"
            i.active = value
            i.active_render = value

        # Indicate we should bake
        return True

    def _prep_for_vcols(self, bo, toggle):
        mesh = bo.data
        vcols = mesh.vertex_colors

        # Create a special light group for baking
        if not self._generate_lightgroup(mesh):
            return False

        # Make sure the object can be baked to. NOTE this also makes sure we can enter edit mode
        # TROLLING LOL LOL LOL
        toggle.track(bo, "hide", False)
        toggle.track(bo, "hide_render", False)
        toggle.track(bo, "hide_select", False)

        # I have heard tale of some moar "No valid image to bake to" boogs if there is a really
        # old copy of the autocolor layer on the mesh. Nuke it.
        autocolor = vcols.get("autocolor")
        if autocolor is not None:
            vcols.remove(autocolor)
        autocolor = vcols.new("autocolor")
        toggle.track(vcols, "active", autocolor)

        # Mark "autocolor" as our active render layer
        for vcol_layer in mesh.vertex_colors:
            autocol = vcol_layer.name == "autocolor"
            toggle.track(vcol_layer, "active_render", autocol)
            toggle.track(vcol_layer, "active", autocol)
        mesh.update()

        # Indicate we should bake
        return True

    def _restore_uvtexs(self):
        for mesh_name, uvtex_name in self._uvtexs.items():
            mesh = bpy.data.meshes[mesh_name]
            for i in mesh.uv_textures:
                i.active = uvtex_name == i.name
            mesh.uv_textures.active = mesh.uv_textures[uvtex_name]

    def _select_only(self, objs):
        if isinstance(objs, bpy.types.Object):
            for i in bpy.data.objects:
                i.select = i == objs
        else:
            for i in bpy.data.objects:
                i.select = i in objs

@persistent
def _toss_garbage(scene):
    """Removes all LIGHTMAPGEN and autocolor garbage before saving"""
    for i in bpy.data.images:
        if i.name.endswith("_LIGHTMAPGEN.png"):
            i.user_clear()
            bpy.data.images.remove(i)
    for i in bpy.data.meshes:
        for uv_tex in i.uv_textures:
            if uv_tex.name == "LIGHTMAPGEN":
                i.uv_textures.remove(uv_tex)
        for vcol in i.vertex_colors:
            if vcol.name == "autocolor":
                i.vertex_colors.remove(vcol)

# collects light baking garbage
bpy.app.handlers.save_pre.append(_toss_garbage)
