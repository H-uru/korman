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
from ..helpers import GoodNeighbor

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

    def _generate_lightgroups(self, mesh, user_lg=None):
        """Makes a new light group for the baking process that excludes all Plasma RT lamps"""
        shouldibake = (user_lg and user_lg.objects)

        for material in mesh.materials:
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
            if _fake is not None:
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

    def __init__(self):
        super().__init__()

    def execute(self, context):
        with GoodNeighbor() as toggle:
            # We need to ensure that we bake onto the "BlahObject_LIGHTMAPGEN" image
            obj = context.active_object
            data_images = bpy.data.images
            im_name = "{}_LIGHTMAPGEN".format(obj.name)
            size = obj.plasma_modifiers.lightmap.resolution

            im = data_images.get(im_name)
            if im is None:
                im = data_images.new(im_name, width=size, height=size)
            elif im.size != (size, size):
                # Force delete and recreate the image because the size is out of date
                im.user_clear()
                data_images.remove(im)
                im = data_images.new(im_name, width=size, height=size)
    
            # This just wraps Blender's internal lightmap UV whatchacallit...
            # We want to ensure that we use the UV Layer "LIGHTMAPGEN" and fetch the size from
            #     the lightmap modifier. What fun...
            mesh = context.active_object.data
            mesh.update()
    
            # Search for LIGHTMAPGEN
            for uvtex in mesh.uv_textures:
                if uvtex.name == "LIGHTMAPGEN":
                    toggle.track(mesh.uv_textures, "active", uvtex)
                    toggle.track(uvtex, "active_render", True)
                    break
                else:
                    toggle.track(uvtex, "active_render", False)
            else:
                # Gotta make it
                uvtex = mesh.uv_textures.new("LIGHTMAPGEN")
                toggle.track(mesh.uv_textures, "active", uvtex)
                toggle.track(uvtex, "active_render", True)
    
            # Now, enter edit mode on this mesh and unwrap.
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.lightmap_pack(PREF_CONTEXT="ALL_FACES", PREF_IMG_PX_SIZE=size)
            bpy.ops.object.mode_set(mode="OBJECT")
    
            # Associate the image with all the new UVs
            # NOTE: no toggle here because it's the artist's problem if they are looking at our
            #       super swagalicious LIGHTMAPGEN uvtexture...
            for i in mesh.uv_textures.active.data:
                i.image = im
    
            # Bake settings
            render = context.scene.render
            toggle.track(render, "use_bake_to_vertex_color", False)
            self._apply_render_settings(render, toggle)

            # Now, we *finally* bake the lightmap...
            light_group = bpy.data.groups[self.light_group] if self.light_group else None
            if self._generate_lightgroups(mesh, light_group):
                bpy.ops.object.bake_image()
                im.pack(as_png=True)
            self._pop_lightgroups()

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
        bpy.ops.object.plasma_lightmap_autobake(light_group=self.light_group)

        tex = bpy.data.textures.get("LIGHTMAPGEN_PREVIEW")
        if tex is None:
            tex = bpy.data.textures.new("LIGHTMAPGEN_PREVIEW", "IMAGE")
        tex.extension = "CLIP"
        tex.image = bpy.data.images["{}_LIGHTMAPGEN".format(context.active_object.name)]

        return {"FINISHED"}


class VertexColorLightingOperator(_LightingOperator, bpy.types.Operator):
    bl_idname = "object.plasma_vertexlight_autobake"
    bl_label = "Bake Vertex Color Lighting"
    bl_options = {"INTERNAL"}

    def __init__(self):
        super().__init__()

    def execute(self, context):
        with GoodNeighbor() as toggle:
            mesh = context.active_object.data
            mesh.update()

            # Find the "autocolor" vertex color layer
            autocolor = mesh.vertex_colors.get("autocolor")
            if autocolor is None:
                mesh.vertex_colors.new("autocolor")
            toggle.track(mesh.vertex_colors, "active", autocolor)

            # Mark "autocolor" as our active render layer
            for vcol_layer in mesh.vertex_colors:
                autocol = vcol_layer.name == "autocolor"
                toggle.track(vcol_layer, "active_render", autocol)

            # Bake settings
            render = context.scene.render
            toggle.track(render, "use_bake_to_vertex_color", True)
            self._apply_render_settings(render, toggle)

            # Bake
            if self._generate_lightgroups(mesh):
                bpy.ops.object.bake_image()
            self._pop_lightgroups()

        # And done!
        return {"FINISHED"}
