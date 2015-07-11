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
from bpy.props import *
from ..helpers import *

def _fetch_lamp_objects():
    for obj in bpy.data.objects:
        if obj.type == "LAMP":
            yield obj

class _LightingOperator:
    def __init__(self):
        self._old_lightgroups = {}

    @classmethod
    def poll(cls, context):
        if context.object is not None:
            return context.scene.render.engine == "PLASMA_GAME"

    def _apply_render_settings(self, render, toggle):
        toggle.track(render, "use_textures", False)
        toggle.track(render, "use_shadows", True)
        toggle.track(render, "use_envmaps", False)
        toggle.track(render, "use_raytrace", True)
        toggle.track(render, "bake_type", "FULL")
        toggle.track(render, "use_bake_clear", True)

    def _generate_lightgroups(self, mesh, user_lg=None):
        """Makes a new light group for the baking process that excludes all Plasma RT lamps"""
        shouldibake = (user_lg and user_lg.objects)

        for material in mesh.materials:
            if material is None:
                # material is not assigned to this material... (why is this even a thing?)
                continue

            lg = material.light_group
            self._old_lightgroups[material] = lg

            if user_lg is None:
                # TODO: faux-lightgroup caching for the entire export process. you dig?
                if not lg or len(lg.objects) == 0:
                    source = _fetch_lamp_objects()
                else:
                    source = lg.objects
                dest = bpy.data.groups.new("_LIGHTMAPGEN_{}".format(material.name))

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

    def _pop_lightgroups(self):
        for material, lg in self._old_lightgroups.items():
            _fake = material.light_group
            if _fake is not None and _fake.name.startswith("_LIGHTMAPGEN"):
                for i in _fake.objects:
                    _fake.objects.unlink(i)
                _fake.user_clear()
                bpy.data.groups.remove(_fake)
            material.light_group = lg
        self._old_lightgroups.clear()


class LightmapAutobakeOperator(_LightingOperator, bpy.types.Operator):
    bl_idname = "object.plasma_lightmap_autobake"
    bl_label = "Bake Lightmap"
    bl_options = {"INTERNAL"}

    light_group = StringProperty(name="Light Group")
    force = BoolProperty(name="Force Lightmap Generation", default=False)

    def __init__(self):
        super().__init__()

    def _associate_image_with_uvtex(self, uvtex, im):
        # Associate the image with all the new UVs
        # NOTE: no toggle here because it's the artist's problem if they are looking at our
        #       super swagalicious LIGHTMAPGEN uvtexture...
        for i in uvtex.data:
            i.image = im

    def _get_base_uvtex(self, mesh, modifier):
        if modifier.uv_map:
            return mesh.uv_textures[modifier.uv_map]
        for i in mesh.uv_textures:
            if i.name != "LIGHTMAPGEN":
                return i
        return None

    def execute(self, context):
        obj = context.active_object
        mesh = obj.data
        modifier = obj.plasma_modifiers.lightmap
        uv_textures = mesh.uv_textures

        with GoodNeighbor() as toggle:
            # We need to ensure that we bake onto the "BlahObject_LIGHTMAPGEN" image
            data_images = bpy.data.images
            im_name = "{}_LIGHTMAPGEN.png".format(obj.name)
            size = modifier.resolution

            im = data_images.get(im_name)
            if im is None:
                im = data_images.new(im_name, width=size, height=size)
            elif im.size[0] != size:
                # Force delete and recreate the image because the size is out of date
                im.user_clear()
                data_images.remove(im)
                im = data_images.new(im_name, width=size, height=size)
            elif not (context.scene.world.plasma_age.regenerate_lightmaps or self.force):
                # we have a lightmap that matches our specs, so what gives???
                # this baking process is one slow thing. only do it if the user wants us to!
                return {"CANCELLED"}

            # If there is a cached LIGHTMAPGEN uvtexture, nuke it
            uvtex = uv_textures.get("LIGHTMAPGEN", None)
            if uvtex is not None:
                uv_textures.remove(uvtex)

            # Make sure the object can be baked to. NOTE this also makes sure we can enter edit mode
            # TROLLING LOL LOL LOL
            ensure_object_can_bake(obj, toggle)

            # Because the way Blender tracks active UV layers is massively stupid...
            og_uv_map = uv_textures.active

            # Originally, we used the lightmap unpack UV operator to make our UV texture, however,
            # this tended to create sharp edges. There was already a discussion about this on the
            # Guild of Writers forum, so I'm implementing a code version of dendwaler's process,
            # as detailed here: http://forum.guildofwriters.org/viewtopic.php?p=62572#p62572
            uv_base = self._get_base_uvtex(mesh, modifier)
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
            for i in uv_textures:
                value = i.name == "LIGHTMAPGEN"
                i.active = value
                i.active_render = value

            # Bake settings
            render = context.scene.render
            toggle.track(render, "use_bake_to_vertex_color", False)
            self._apply_render_settings(render, toggle)

            # Now, we *finally* bake the lightmap...
            try:
                light_group = bpy.data.groups[self.light_group] if self.light_group else None
                if self._generate_lightgroups(mesh, light_group):
                    bpy.ops.object.bake_image()
                    im.pack(as_png=True)
                self._pop_lightgroups()
            finally:
                for i, uv_tex in enumerate(uv_textures):
                    # once this executes the og_uv_map is apparently no longer in the UVTextures :/
                    # search by name to find the REAL uv texture that we need.
                    if uv_tex.name == og_uv_map.name:
                        uv_textures.active = uv_tex
                        uv_textures.active_index = i
                        break

        # Done!
        return {"FINISHED"}


class LightmapAutobakePreviewOperator(_LightingOperator, bpy.types.Operator):
    bl_idname = "object.plasma_lightmap_preview"
    bl_label = "Preview Lightmap"
    bl_options = {"INTERNAL"}

    light_group = StringProperty(name="Light Group")

    def __init__(self):
        super().__init__()

    def execute(self, context):
        bpy.ops.object.plasma_lightmap_autobake(light_group=self.light_group, force=True)

        tex = bpy.data.textures.get("LIGHTMAPGEN_PREVIEW")
        if tex is None:
            tex = bpy.data.textures.new("LIGHTMAPGEN_PREVIEW", "IMAGE")
        tex.extension = "CLIP"
        tex.image = bpy.data.images["{}_LIGHTMAPGEN.png".format(context.active_object.name)]

        return {"FINISHED"}


class VertexColorLightingOperator(_LightingOperator, bpy.types.Operator):
    bl_idname = "object.plasma_vertexlight_autobake"
    bl_label = "Bake Vertex Color Lighting"
    bl_options = {"INTERNAL"}

    def __init__(self):
        super().__init__()

    def execute(self, context):
        with GoodNeighbor() as toggle:
            obj = context.active_object
            mesh = obj.data
            vcols = mesh.vertex_colors

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

            # Bake settings
            render = context.scene.render
            toggle.track(render, "use_bake_to_vertex_color", True)
            self._apply_render_settings(render, toggle)

            # Really and truly make sure we can bake...
            ensure_object_can_bake(obj, toggle)

            # Bake
            if self._generate_lightgroups(mesh):
                bpy.ops.object.bake_image()
            self._pop_lightgroups()

        # And done!
        return {"FINISHED"}
