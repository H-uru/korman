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

class NodeOperator:
    def get_node_tree(self, context):
        space = context.space_data
        if space.type != "NODE_EDITOR":
            raise RuntimeError("Operator '{}' should only be used in the node editor".format(self.bl_idname))
        return space.node_tree

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class ResponderStateAddOperator(NodeOperator, bpy.types.Operator):
    bl_idname = "node.plasma_add_responder_state"
    bl_label = "Add Responder State Socket"

    node_name = StringProperty(name="Node's name", options={"HIDDEN"})

    def execute(self, context):
        tree = self.get_node_tree(context)
        tree.nodes[self.node_name].add_state_input()
        return {"FINISHED"}


class ResponderStateRemoveOperator(NodeOperator, bpy.types.Operator):
    bl_idname = "node.plasma_remove_responder_state"
    bl_label = "Remove Responder State Socket"

    node_name = StringProperty(name="Node's name", options={"HIDDEN"})
    socket_name = StringProperty(name="Socket name to remove", options={"HIDDEN"})

    def execute(self, context):
        tree = self.get_node_tree(context)
        node = tree.nodes[self.node_name]
        socket = node.inputs[self.socket_name]
        node.inputs.remove(socket)
        return {"FINISHED"}
