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
import uuid

from .node_core import *

class PlasmaResponderNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderNode"
    bl_label = "Responder"

    def init(self, context):
        self.inputs.new("PlasmaRespTriggerSocket", "Trigger", "whodoneit")
        self.outputs.new("PlasmaRespStateSocket", "States", "states")


class PlasmaResponderStateNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderStateNode"
    bl_label = "Responder State"

    def init(self, context):
        self.inputs.new("PlasmaRespStateSocket", "Condition", "whodoneit")
        self.outputs.new("PlasmaRespCommandSocket", "Commands", "cmds")
        self.outputs.new("PlasmaRespStateSocket", "Trigger", "gotostate").link_limit = 1


class PlasmaRespStateSocketBase(PlasmaNodeSocketBase):
    bl_color = (0.388, 0.78, 0.388, 1.0)


class PlasmaRespStateSocket(PlasmaRespStateSocketBase, bpy.types.NodeSocket):
    default_state = BoolProperty(name="Default State",
                                 description="This state is the Responder's default",
                                 default=False)

    def draw(self, context, layout, node, text):
        # If this is a RespoderState node and the parent is a Responder, offer the user the
        # ability to make this the default state.
        if self.is_linked and not self.is_output:
            # Before we do anything, see if we need to do a delayed update...
            if node.bl_idname == "PlasmaResponderStateNode":
                parent = node.find_input("whodoneit", "PlasmaResponderNode")
                if parent is not None:
                    layout.prop(self, "default_state")
                    return

        # Still here? Draw the text.
        layout.label(text)


class PlasmaResponderStateListNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderStateListNode"
    bl_label = "Responder State List"

    def add_state_input(self):
        self.inputs.new("PlasmaRespStateListSocket", str(uuid.uuid4()))

    def init(self, context):
        # Inputs will be added by the user
        self.outputs.new("PlasmaRespStateSocket", "Go To State", "gotostate")

    def draw_buttons(self, context, layout):
        # This will allow us to add input states on the fly.
        # Caveat: We're only showing this operator in the properties because we need the node
        #         to be active in the operator...
        op = layout.operator("node.plasma_add_responder_state", text="Add State", icon="ZOOMIN")
        op.node_name = self.name


class PlasmaRespStateListSocket(PlasmaRespStateSocketBase, bpy.types.NodeSocket):
    def draw(self, context, layout, node, text):
        # We'll allow them to delete all their inputs if they want to be stupid...
        props = layout.operator("node.plasma_remove_responder_state", text="", icon="X")
        props.node_name = node.name
        props.socket_name = self.name


class PlasmaResponderCommandNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderCommandNode"
    bl_label = "Responder Command"

    def init(self, context):
        self.inputs.new("PlasmaRespCommandSocket", "Condition", "whodoneit")
        self.outputs.new("PlasmaMessageSocket", "Message", "msg")
        self.outputs.new("PlasmaRespCommandSocket", "Trigger", "trigger")


class PlasmaRespCommandSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.451, 0.0, 0.263, 1.0)

