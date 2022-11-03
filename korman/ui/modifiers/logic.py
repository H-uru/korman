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

def clothing(modifier, layout, context):
    layout.prop(modifier, "clickable_object")
    layout.prop(modifier, "clickable_region")

    if modifier.clickable_object and modifier.clickable_region:
        layout.separator()
        layout.label(text="Clothing Item Details:")
        split = layout.split()
        col = split.column()
        col.prop(modifier, "clothing_sdl")
        col.prop(modifier, "clothing_chance")
        col.prop(modifier, "clothing_female")
        col.prop(modifier, "clothing_male")

        layout.separator()
        layout.label(text="Default Clothing Color(s):")
        split = layout.split()
        col = split.column()
        col.prop(modifier, "clothing_tint2on")

        col = split.column()
        col.prop(modifier, "clothing_hair")

        split = layout.split()
        col = split.column()
        col.prop(modifier, "clothing_tint1")

        col = split.column()
        col.enabled = modifier.clothing_tint2on is True
        col.prop(modifier, "clothing_tint2")

        layout.separator()
        layout.label(text="Visibility:")
        split = layout.split()
        col = split.column()
        col.prop(modifier, "clothing_show")

        col = split.column()
        col.prop(modifier, "clothing_stayvis")
