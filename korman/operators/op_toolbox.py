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

class ToolboxOperator:
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class PlasmaEnablePlasmaObjectOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "object.plasma_enable_all_objects"
    bl_label = "Plasma Objects"
    bl_description = "Marks all Objects as Plasma Objects for exporting"

    def execute(self, context):
        for i in bpy.data.objects:
            i.plasma_object.enabled = True
        return {"FINISHED"}


class PlasmaEnableTexturesOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "texture.plasma_enable_all_textures"
    bl_label = "Textures"
    bl_description = "Ensures that all Textures are enabled"

    def execute(self, context):
        for mesh in bpy.data.meshes:
            for material in mesh.materials:
                if material is None:
                    continue

                for slot in material.texture_slots:
                    if slot is None:
                        continue
                    slot.use = True
        return {"FINISHED"}

class PlasmaConvertLayerOpacitiesOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "texture.plasma_convert_layer_opacities"
    bl_label = "Layer Opacities"
    bl_description = "Convert layer opacities from diffuse color factor"

    def execute(self, context):
        for mesh in bpy.data.meshes:
            for material in mesh.materials:
                if material is None:
                    continue

                for slot in material.texture_slots:
                    if slot is None:
                        continue

                    slot.texture.plasma_layer.opacity = slot.diffuse_color_factor * 100
                    slot.diffuse_color_factor = 1.0
        return {"FINISHED"}
