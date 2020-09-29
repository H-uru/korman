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
import itertools

class ToolboxPanel:
    bl_category = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    @classmethod
    def poll(cls, context):
        return context.object and context.scene.render.engine == "PLASMA_GAME"


class PlasmaToolboxPanel(ToolboxPanel, bpy.types.Panel):
    bl_context = "objectmode"
    bl_label = "Plasma"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label("Plasma Objects:")
        enable_all = col.operator("object.plasma_toggle_all_objects", icon="OBJECT_DATA", text="Enable All")
        enable_all.enable = True
        all_plasma_objects = all((i.plasma_object.enabled for i in bpy.context.selected_objects))
        col.operator("object.plasma_toggle_selected_objects", icon="VIEW3D", text="Disable Selection" if all_plasma_objects else "Enable Selection")
        disable_all = col.operator("object.plasma_toggle_all_objects", icon="OBJECT_DATA", text="Disable All")
        disable_all.enable = False

        col.label("Plasma Pages:")
        col.operator("object.plasma_move_selection_to_page", icon="BOOKMARKS", text="Move to Page")
        col.operator("object.plasma_select_page_objects", icon="RESTRICT_SELECT_OFF", text="Select Objects")
        
        col.label("Package Sounds:")
        col.operator("object.plasma_toggle_sound_export", icon="MUTE_IPO_OFF", text="Enable All").enable = True
        all_sounds_export = all((i.package for i in itertools.chain.from_iterable(i.plasma_modifiers.soundemit.sounds for i in bpy.context.selected_objects if i.plasma_modifiers.soundemit.enabled)))
        col.operator("object.plasma_toggle_sound_export_selected", icon="OUTLINER_OB_SPEAKER", text="Disable Selection" if all_sounds_export else "Enable Selection")
        col.operator("object.plasma_toggle_sound_export", icon="MUTE_IPO_ON", text="Disable All").enable = False

        col.label("Textures:")
        col.operator("texture.plasma_enable_all_textures", icon="TEXTURE", text="Enable All")
        col.operator("texture.plasma_toggle_environment_maps", icon="IMAGE_RGB", text="Enable All EnvMaps").enable = True
        col.operator("texture.plasma_toggle_environment_maps", icon="IMAGE_RGB_ALPHA", text="Disable All EnvMaps").enable = False

        # Double Sided Operators
        col.label("Double Sided:")
        col.operator("mesh.plasma_toggle_double_sided", icon="MESH_DATA", text="Disable All").enable = False
        all_double_sided = all((i.data.show_double_sided for i in bpy.context.selected_objects if i.type == "MESH"))
        col.operator("mesh.plasma_toggle_double_sided_selected", icon="BORDER_RECT", text="Disable Selection" if all_double_sided else "Enable Selection")

        col.label("Convert:")
        col.operator("object.plasma_convert_plasma_objects", icon="OBJECT_DATA", text="Plasma Objects")
        col.operator("texture.plasma_convert_layer_opacities", icon="IMAGE_RGB_ALPHA", text="Layer Opacities")
