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

from contextlib import contextmanager
import itertools

from ..exporter.etlight import LightBaker
from ..helpers import UiHelper
from ..korlib import ConsoleToggler

class _LightingOperator:
    @contextmanager
    def _oven(self, context):
        if context.scene.world is not None:
            verbose = context.scene.world.plasma_age.verbose
            console = context.scene.world.plasma_age.show_console
        else:
            verbose = False
            console = True
        with UiHelper(context), ConsoleToggler(console), LightBaker(verbose=verbose) as oven:
            yield oven

    @classmethod
    def poll(cls, context):
        if context.mode != "OBJECT":
            return False
        if context.object is not None:
            return context.scene.render.engine == "PLASMA_GAME"


class LightmapAutobakePreviewOperator(_LightingOperator, bpy.types.Operator):
    bl_idname = "object.plasma_lightmap_preview"
    bl_label = "Preview Lightmap"
    bl_description = "Preview Lighting"
    bl_options = {"INTERNAL"}

    final = BoolProperty(name="Use this lightmap for export")

    def __init__(self):
        super().__init__()

    def execute(self, context):
        with self._oven(context) as bake:
            if not self.final:
                bake.lightmap_name = "{}_LIGHTMAPGEN_PREVIEW.png"
                bake.lightmap_uvtex_name = "LIGHTMAPGEN_PREVIEW"
            bake.force = True
            bake.retain_lightmap_uvtex = self.final
            if not bake.bake_static_lighting([context.object,]):
                self.report({"WARNING"}, "No valid lights found to bake.")
                return {"FINISHED"}

        lightmap_mod = context.object.plasma_modifiers.lightmap
        if lightmap_mod.bake_lightmap:
            tex = bpy.data.textures.get("LIGHTMAPGEN_PREVIEW")
            if tex is None:
                tex = bpy.data.textures.new("LIGHTMAPGEN_PREVIEW", "IMAGE")
            tex.extension = "CLIP"
            image = bake.get_lightmap(context.object)
            tex.image = image
            if self.final:
                lightmap_mod.image = image
        else:
            for i in context.object.data.vertex_colors:
                i.active = i.name == bake.vcol_layer_name

        return {"FINISHED"}


class LightmapBakeMultiOperator(_LightingOperator, bpy.types.Operator):
    bl_idname = "object.plasma_lightmap_bake"
    bl_label = "Bake Lighting"
    bl_description = "Bake scene lighting to object(s)"

    bake_selection = BoolProperty(name="Bake Selection",
                                  description="Bake only the selected objects (else all objects)",
                                  options=set())

    def __init__(self):
        super().__init__()

    def execute(self, context):
        all_objects = context.selected_objects if self.bake_selection else context.scene.objects
        filtered_objects = [i for i in all_objects if i.type == "MESH" and i.plasma_object.enabled]

        with self._oven(context) as bake:
            bake.force = True
            if not bake.bake_static_lighting(filtered_objects):
                self.report({"WARNING"}, "Nothing was baked.")
                return {"FINISHED"}

        for i in filtered_objects:
            lightmap_mod = i.plasma_modifiers.lightmap
            if lightmap_mod.bake_lightmap:
                lightmap_mod.image = bake.get_lightmap(i)

        return {"FINISHED"}


class LightmapClearMultiOperator(_LightingOperator, bpy.types.Operator):
    bl_idname = "object.plasma_lightmap_clear"
    bl_label = "Clear Lighting"
    bl_description = "Clear baked lighting"

    clear_selection = BoolProperty(name="Clear Selection",
                                   description="Clear only the selected objects (else all objects)",
                                   options=set())

    def __init__(self):
        super().__init__()

    def _iter_lightmaps(self, objects):
        yield from filter(lambda x: x.type == "MESH" and x.plasma_modifiers.lightmap.bake_lightmap, objects)

    def _iter_vcols(self, objects):
        yield from filter(lambda x: x.type == "MESH" and not x.plasma_modifiers.lightmap.bake_lightmap, objects)

    def execute(self, context):
        all_objects = context.selected_objects if self.clear_selection else context.scene.objects

        for i in self._iter_lightmaps(all_objects):
            i.plasma_modifiers.lightmap.image = None

        for i in self._iter_vcols(all_objects):
            vcols = i.data.vertex_colors
            col_layer = vcols.get("autocolor")
            if col_layer is not None:
                vcols.remove(col_layer)
        return {"FINISHED"}


@bpy.app.handlers.persistent
def _toss_garbage(scene):
    """Removes all LIGHTMAPGEN and autocolor garbage before saving"""
    bpy_data = bpy.data
    tex = bpy_data.textures.get("LIGHTMAPGEN_PREVIEW")
    if tex is not None:
        bpy_data.textures.remove(tex)

    for i in bpy_data.images:
        if i.name.endswith("_LIGHTMAPGEN_PREVIEW.png"):
            bpy_data.images.remove(i)
    for i in bpy_data.meshes:
        uvtex = i.uv_textures.get("LIGHTMAPGEN_PREVIEW")
        if uvtex is not None:
            i.uv_textures.remove(uvtex)

# collects light baking garbage
bpy.app.handlers.save_pre.append(_toss_garbage)
