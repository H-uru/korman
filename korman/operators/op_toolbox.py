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


class PlasmaConvertLayerOpacitiesOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "texture.plasma_convert_layer_opacities"
    bl_label = "Convert Layer Opacities"
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


class PlasmaConvertPlasmaObjectOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "object.plasma_convert_plasma_objects"
    bl_label = "Convert Plasma Objects"
    bl_description = "Converts PyPRP objects to Plasma Objects"

    def execute(self, context):
        # We will loop through all the objects and enable Plasma Object on every object that
        # is either inserted into a valid page using the old-style text properties or is lacking
        # a page property. Unfortunately, unless we start bundling some YAML interpreter, we cannot
        # use the old AlcScript schtuff.
        pages = { i.seq_suffix: i.name for i in context.scene.world.plasma_age.pages }
        for i in bpy.data.objects:
            pageid = i.game.properties.get("page_num", None)
            if pageid is None:
                i.plasma_object.enabled = True
                continue

            page_name = pages.get(pageid.value, None)
            if page_name is None:
                # a common hack to prevent exporting in PyPRP was to set page_num == -1,
                # so don't warn about that.
                if pageid.value != -1:
                    print("Object '{}' in page_num '{}', which is not available :/".format(i.name, pageid.value))
            else:
                i.plasma_object.enabled = True
                i.plasma_object.page = page_name
        return {"FINISHED"}


class PlasmaEnablePlasmaObjectOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "object.plasma_enable_all_objects"
    bl_label = "Enable All Plasma Objects"
    bl_description = "Marks all Objects as Plasma Objects for exporting"

    def execute(self, context):
        for i in bpy.data.objects:
            i.plasma_object.enabled = True
        return {"FINISHED"}


class PlasmaEnableTexturesOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "texture.plasma_enable_all_textures"
    bl_label = "Enable All Textures"
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
