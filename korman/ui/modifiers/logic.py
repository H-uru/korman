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

def advanced_logic(modifier, layout, context):
    layout.prop_search(modifier, "tree_name", bpy.data, "node_groups", icon="NODETREE")

def spawnpoint(modifier, layout, context):
    layout.label(text="The Y axis indicates the direction the avatar is facing.")

def maintainersmarker(modifier, layout, context):
    layout.label(text="Positive Y is North, positive Z is up.")
    layout.prop(modifier, "calibration")
