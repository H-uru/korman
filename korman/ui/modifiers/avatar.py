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

from ...helpers import find_modifier

def sittingmod(modifier, layout, context):
    layout.row().prop(modifier, "approach")

    col = layout.column()
    col.prop_search(modifier, "clickable_obj", bpy.data, "objects", icon="MESH_DATA")
    clickable = find_modifier(modifier.clickable_obj, "collision")
    if clickable is not None:
        col.prop(clickable, "bounds")

    col = layout.column()
    col.prop_search(modifier, "region_obj", bpy.data, "objects", icon="MESH_DATA")
    region = find_modifier(modifier.region_obj, "collision")
    if region is not None:
        col.prop(region, "bounds")

    split = layout.split()
    split.column().prop(modifier, "facing_enabled")
    col = split.column()
    col.enabled = modifier.facing_enabled
    col.prop(modifier, "facing_degrees")
