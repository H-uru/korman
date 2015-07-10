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

class LogicListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.prop(item, "name", emboss=False, text="", icon="NODETREE")

def advanced_logic(modifier, layout, context):
    row = layout.row()
    row.template_list("LogicListUI", "logic_groups", modifier, "logic_groups", modifier, "active_group_index",
                      rows=2, maxrows=3)
    col = row.column(align=True)
    op = col.operator("object.plasma_modifier_collection_add", icon="ZOOMIN", text="")
    op.modifier = modifier.pl_id
    op.collection = "logic_groups"
    op.name_prefix = "Logic"
    op.name_prop = "name"
    op = col.operator("object.plasma_modifier_collection_remove", icon="ZOOMOUT", text="")
    op.modifier = modifier.pl_id
    op.collection = "logic_groups"
    op.index = modifier.active_group_index

    # Modify the loop points
    if modifier.logic_groups:
        logic = modifier.logic_groups[modifier.active_group_index]
        row = layout.row()
        row.prop_menu_enum(logic, "version")
        row.prop_search(logic, "node_tree_name", bpy.data, "node_groups", icon="NODETREE", text="")

def spawnpoint(modifier, layout, context):
    layout.label(text="Avatar faces negative Y.")

def maintainersmarker(modifier, layout, context):
    layout.label(text="Positive Y is North, positive Z is up.")
    layout.prop(modifier, "calibration")
