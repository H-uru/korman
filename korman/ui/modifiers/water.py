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

def water_basic(modifier, layout, context):
    layout.prop_search(modifier, "wind_object_name", bpy.data, "objects")

    row = layout.row()
    row.prop(modifier, "wind_speed")
    layout.separator()

    split = layout.split()
    col = split.column()
    col.prop(modifier, "specular_tint")
    col.prop(modifier, "specular_alpha", text="Alpha")

    col.label("Specular:")
    col.prop(modifier, "specular_start", text="Start")
    col.prop(modifier, "specular_end", text="End")

    col.label("Misc:")
    col.prop(modifier, "noise")
    col.prop(modifier, "ripple_scale")

    col = split.column()
    col.label("Opacity:")
    col.prop(modifier, "zero_opacity", text="Start")
    col.prop(modifier, "depth_opacity", text="End")

    col.label("Reflection:")
    col.prop(modifier, "zero_reflection", text="Start")
    col.prop(modifier, "depth_reflection", text="End")

    col.label("Wave:")
    col.prop(modifier, "zero_wave", text="Start")
    col.prop(modifier, "depth_wave", text="End")

def _wavestate(modifier, layout, context):
    split = layout.split()
    col = split.column()
    col.label("Size:")
    col.prop(modifier, "min_length")
    col.prop(modifier, "max_length")
    col.prop(modifier, "amplitude")

    col = split.column()
    col.label("Behavior:")
    col.prop(modifier, "chop")
    col.prop(modifier, "angle_dev")

water_geostate = _wavestate
water_texstate = _wavestate

class ShoreListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.prop(item, "display_name", emboss=False, text="", icon="MOD_WAVE")


def water_shore(modifier, layout, context):
    row = layout.row()
    row.template_list("ShoreListUI", "shores", modifier, "shores", modifier, "active_shore_index",
                      rows=2, maxrows=3)
    col = row.column(align=True)
    op = col.operator("object.plasma_modifier_collection_add", icon="ZOOMIN", text="")
    op.modifier = modifier.pl_id
    op.collection = "shores"
    op.name_prefix = "Shore"
    op.name_prop = "display_name"
    op = col.operator("object.plasma_modifier_collection_remove", icon="ZOOMOUT", text="")
    op.modifier = modifier.pl_id
    op.collection = "shores"
    op.index = modifier.active_shore_index

    # Display the active shore
    if modifier.shores:
        shore = modifier.shores[modifier.active_shore_index]
        layout.prop_search(shore, "object_name", bpy.data, "objects", icon="MESH_DATA")

    split = layout.split()
    col = split.column()
    col.label("Basic:")
    col.prop(modifier, "shore_tint")
    col.prop(modifier, "shore_opacity")
    col.prop(modifier, "wispiness")

    col = split.column()
    col.label("Advanced:")
    col.prop(modifier, "period")
    col.prop(modifier, "finger")
    col.prop(modifier, "edge_opacity")
    col.prop(modifier, "edge_radius")
