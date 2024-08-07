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

from __future__ import annotations

import bpy

from typing import *

if TYPE_CHECKING:
    from ...properties.modifiers.logic import *

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

def spawnpoint(modifier: PlasmaSpawnPoint, layout, context):
    layout.label(text="Avatar faces negative Y.")
    layout.separator()

    col = layout.column()
    col.prop(modifier, "entry_camera", icon="CAMERA_DATA")
    sub = col.row()
    sub.active = modifier.entry_camera is not None
    sub.prop(modifier, "exit_region", icon="MESH_DATA")
    sub = col.row()
    sub.active = modifier.entry_camera is not None and modifier.exit_region is not None
    sub.prop(modifier, "bounds_type")

def maintainersmarker(modifier, layout, context):
    layout.label(text="Positive Y is North, positive Z is up.")
    layout.prop(modifier, "calibration")

def sdl_showhide(modifier: PlasmaSDLShowHide, layout, context):
    if not context.scene.world.plasma_age.age_sdl:
        layout.label("This modifier requires Age Global SDL!", icon="ERROR")
        return

    valid_variable = modifier.sdl_variable.strip()
    layout.alert = not valid_variable
    layout.prop(modifier, "sdl_variable")
    if not valid_variable:
        layout.label("A valid SDL variable is required!", icon="ERROR")
    layout.alert = False
    layout.prop(modifier, "variable_type")
    layout.separator()

    def setup_collection_operator(op):
        op.context = "object"
        op.group_path = modifier.path_from_id()
        op.collection_prop = "int_states"
        op.index_prop = ""

    if modifier.variable_type == "bool":
        layout.prop(modifier, "bool_state")
    elif modifier.variable_type == "int":
        layout.label("Show when SDL variable is:")
        sub = layout.column_flow()
        for i, state in enumerate(modifier.int_states):
            row = sub.row(align=True)
            row.prop(state, "value", text="Value")
            op = row.operator("ui.plasma_collection_remove", icon="ZOOMOUT", text="")
            setup_collection_operator(op)
            op.manual_index = i

        op = layout.operator("ui.plasma_collection_add", icon="ZOOMIN", text="Add State Value")
        setup_collection_operator(op)
    else:
        raise RuntimeError()

def telescope(modifier, layout, context):
    layout.prop(modifier, "clickable_region")
    layout.prop(modifier, "seek_target_object", icon="EMPTY_DATA")
    layout.alert = modifier.camera_object is None
    layout.prop(modifier, "camera_object", icon="CAMERA_DATA")
