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
import itertools

class NodeOperator:
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class SelectFileOperator(NodeOperator, bpy.types.Operator):
    bl_idname = "file.plasma_file_picker"
    bl_label = "Select"

    filter_glob = StringProperty(options={"HIDDEN"})
    filepath = StringProperty(subtype="FILE_PATH")
    filename = StringProperty(options={"HIDDEN"})

    data_path = StringProperty(options={"HIDDEN"})
    filepath_property = StringProperty(description="Name of property to store filepath in", options={"HIDDEN"})
    filename_property = StringProperty(description="Name of property to store filename in", options={"HIDDEN"})

    def execute(self, context):
        dest = eval(self.data_path)
        if self.filepath_property:
            setattr(dest, self.filepath_property, self.filepath)
        if self.filename_property:
            setattr(dest, self.filename_property, self.filename)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PlPyAttributeNodeOperator(NodeOperator, bpy.types.Operator):
    bl_idname = "node.plasma_attributes_to_node"
    bl_label = "R"
    bl_options = {"INTERNAL"}

    python_path = StringProperty(subtype="FILE_PATH")
    node_path = StringProperty()

    def execute(self, context):
        from ..plasma_attributes import get_attributes
        attribs = get_attributes(self.python_path)

        node = eval(self.node_path)
        node_attrib_map = node.attribute_map
        node_attribs = node.attributes

        # Remove any that p00fed
        for cached in node.attributes:
            if cached.attribute_id not in attribs:
                node_attribs.remove(cached)

        # Update or create
        for idx, attrib in attribs.items():
            cached = node_attrib_map.get(idx, None)
            if cached is None:
                cached = node_attribs.add()
            cached.attribute_id = idx
            cached.attribute_type = attrib["type"]
            cached.attribute_name = attrib["name"]
            cached.attribute_description = attrib["desc"]
            default = attrib.get("default", None)
            if default is not None and cached.is_simple_value:
                cached.simple_value = default

        # Manually cause the node to update its inputs
        node.update()
        return {"FINISHED"}
