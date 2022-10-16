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

from .. import ui_list

class LogicListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if item.node_tree:
            # Using layout.prop on the pointer prevents clicking on the item O.o
            layout.label(item.node_tree.name, icon="NODETREE")
        else:
            layout.label("[Empty]")


def advanced_logic(modifier, layout, context):
    ui_list.draw_modifier_list(layout, "LogicListUI", modifier, "logic_groups",
                               "active_group_index", rows=2, maxrows=3)

    # Modify the logic groups
    if modifier.logic_groups:
        logic = modifier.logic_groups[modifier.active_group_index]
        layout.row().prop_menu_enum(logic, "version")
        layout.prop(logic, "node_tree", icon="NODETREE")

def spawnpoint(modifier, layout, context):
    layout.label(text="Avatar faces negative Y.")

def maintainersmarker(modifier, layout, context):
    layout.label(text="Positive Y is North, positive Z is up.")
    layout.prop(modifier, "calibration")

def imager(modifier, layout, context):
    layout.prop(modifier, "imager_object")

    split = layout.split()
    col = split.column()
    col.enabled = modifier.imager_object is not None
    col.prop(modifier, "imager_material")

    col = split.column()
    col.enabled = modifier.imager_material is not None
    col.prop(modifier, "imager_texture")

    if modifier.imager_material and modifier.imager_texture:
        layout.separator()
        layout.prop(modifier, "imager_name")
        layout.prop(modifier, "imager_type")
        if modifier.imager_type == "POSTABLE":
            layout.separator()
            layout.prop(modifier, "imager_region")
            split = layout.split()
            col = split.column()
            col.prop(modifier, "imager_time")
            col.prop(modifier, "imager_maximum")

            col = split.column()
            col.prop(modifier, "imager_membersonly")
            col.prop(modifier, "imager_pellets")

            layout.separator()
            layout.label(text="For Clue Imager:")
            layout.prop(modifier, "imager_clueobject")
            if modifier.imager_clueobject:
                split = layout.split()
                col = split.column()
                col.prop(modifier, "imager_cluetime")

                col = split.column()
                col.prop(modifier, "imager_randomtime")
