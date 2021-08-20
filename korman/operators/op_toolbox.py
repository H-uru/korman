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
import pickle
import itertools

class ToolboxOperator:
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class PageSearchOperator(ToolboxOperator):
    _pages_ref_hack = []

    @property
    def desired_page(self):
        result = pickle.loads(self.page.encode())
        PageSearchOperator._pages_ref_hack.clear()
        return result

    def _get_pages(self, context):
        # WTF? Pickle, you ask??? Apparently Blender changes the output if we return an empty string,
        # making it impossible to select the default page... Ugh.
        page_defns = context.scene.world.plasma_age.pages
        pages = [(pickle.dumps(i.name, 0).decode(), i.name, "") for i in page_defns]

        # Ensure an entry exists for the default page
        manual_default_page = next((i.name for i in page_defns if i.seq_suffix == 0), None)
        if not manual_default_page:
            pages.append((pickle.dumps("", 0).decode(), "Default", "Default Page"))

        # Have to hold a reference to this numb-skullery so Blender won't crash.
        PageSearchOperator._pages_ref_hack = pages
        return pages

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    @classmethod
    def poll(cls, context):
        return super().poll(context) and context.scene.world is not None


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


class PlasmaMovePageObjectsOperator(PageSearchOperator, bpy.types.Operator):
    bl_idname = "object.plasma_move_selection_to_page"
    bl_label = "Move Selection to Page"
    bl_description = "Moves all selected objects to a new page"
    bl_property = "page"

    page = EnumProperty(name="Page",
                        description= "Page whose objects should be selected",
                        items=PageSearchOperator._get_pages,
                        options=set())

    def execute(self, context):
        desired_page = self.desired_page
        for i in context.selected_objects:
            i.plasma_object.page = desired_page
        return {"FINISHED"}


class PlasmaSelectPageObjectsOperator(PageSearchOperator, bpy.types.Operator):
    bl_idname = "object.plasma_select_page_objects"
    bl_label = "Select Objects in Page"
    bl_description = "Selects all objects in a specific page"
    bl_property = "page"

    page = EnumProperty(name="Page",
                        description= "Page whose objects should be selected",
                        items=PageSearchOperator._get_pages,
                        options=set())

    def execute(self, context):
        desired_page = self.desired_page
        for i in context.scene.objects:
            i.select = i.plasma_object.page == desired_page
        return {"FINISHED"}


class PlasmaToggleAllPlasmaObjectsOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "object.plasma_toggle_all_objects"
    bl_label = "Toggle All Plasma Objects"
    bl_description = "Changes the state of all Plasma Objects"

    enable = BoolProperty(name="Enable", description="Enable Plasma Object")

    def execute(self, context):
        for i in bpy.data.objects:
            i.plasma_object.enabled = self.enable
        return {"FINISHED"}

        
class PlasmaToggleDoubleSidedOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "mat.plasma_toggle_double_sided"
    bl_label = "Toggle All Double Sided"
    bl_description = "Toggles all materials to be double sided"
    
    enable = BoolProperty(name="Enable", description="Enable Double Sided")
    
    def execute(self, context):
        enable = self.enable
        for mat in bpy.data.materials:
            mat.plasma_mat.plasma_double_sided = enable
        return {"FINISHED"}


class PlasmaToggleDoubleSidedSelectOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "mat.plasma_toggle_double_sided_selected"
    bl_label = "Toggle Selected Double Sided"
    bl_description = "Toggles selected meshes' material(s) double sided value"
    
    @classmethod
    def poll(cls, context):
        return super().poll(context) and hasattr(bpy.context, "selected_objects")

    def execute(self, context):
        mat_list = [i.data for i in context.selected_objects if i.type == "MATERIAL"]
        enable = not all((mat.plasma_mat.plasma_double_sided for mat in mat_list))
        for mat in mat_list:
            mat.plasma_mat.plasma_double_sided = enable
        return {"FINISHED"}


class PlasmaToggleEnvironmentMapsOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "texture.plasma_toggle_environment_maps"
    bl_label = "Toggle Environment Maps"
    bl_description = "Changes the state of all Environment Maps"

    enable = BoolProperty(name="Enable", description="Enable Environment Maps")

    def execute(self, context):
        enable = self.enable
        for material in bpy.data.materials:
            for slot in material.texture_slots:
                if slot is None:
                    continue
                if slot.texture.type == "ENVIRONMENT_MAP":
                    slot.use = enable
        return {"FINISHED"}


class PlasmaTogglePlasmaObjectsOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "object.plasma_toggle_selected_objects"
    bl_label = "Toggle Plasma Objects"
    bl_description = "Toggles the Plasma Object status of a selection"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and hasattr(bpy.context, "selected_objects")

    def execute(self, context):
        enable = not all((i.plasma_object.enabled for i in bpy.context.selected_objects))
        for i in context.selected_objects:
            i.plasma_object.enabled = enable
        return {"FINISHED"}


class PlasmaToggleSoundExportOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "object.plasma_toggle_sound_export"
    bl_label = "Toggle Sound Export"
    bl_description = "Toggles the Export function of all sound emitters' files"
    
    enable = BoolProperty(name="Enable", description="Sound Export Enable")
    
    def execute(self, context):
        enable = self.enable
        for i in bpy.data.objects:
            if i.plasma_modifiers.soundemit is None:
                continue
            for sound in i.plasma_modifiers.soundemit.sounds:
                sound.package = enable
        return {"FINISHED"}


class PlasmaToggleSoundExportSelectedOperator(ToolboxOperator, bpy.types.Operator):
    bl_idname = "object.plasma_toggle_sound_export_selected"
    bl_label = "Toggle Selected Sound Export"
    bl_description = "Toggles the Export function of selected sound emitters' files."
    
    @classmethod
    def poll(cls, context):
        return super().poll(context) and hasattr(bpy.context, "selected_objects")
    
    def execute(self, context):
        enable = not all((i.package for i in itertools.chain.from_iterable(i.plasma_modifiers.soundemit.sounds for i in bpy.context.selected_objects)))
        for i in context.selected_objects:
            if i.plasma_modifiers.soundemit is None:
                continue
            for sound in i.plasma_modifiers.soundemit.sounds:
                sound.package = enable
        return {"FINISHED"}
