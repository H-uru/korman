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


class PlasmaResponderStateNode(PlasmaNodeVariableInput, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderStateNode"
    bl_label = "Responder State"

    default_state = BoolProperty(name="Default State",
                                 description="This state is the responder's default",
                                 default=False)

    def init(self, context):
        self.outputs.new("PlasmaRespCommandSocket", "Commands", "cmds")
        self.outputs.new("PlasmaRespStateSocket", "Trigger", "gotostate").link_limit = 1

    def draw_buttons(self, context, layout):
        # This actually draws nothing, but it makes sure we have at least one empty input slot
        # We need this because it's possible that multiple OTHER states can call us
        self.ensure_sockets("PlasmaRespStateSocket", "Condition")

        # Now draw a prop
        layout.prop(self, "default_state")


class PlasmaRespStateSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.388, 0.78, 0.388, 1.0)


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

