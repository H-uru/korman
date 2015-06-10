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
from PyHSPlasma import *
import uuid

from .node_core import *

class PlasmaResponderNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderNode"
    bl_label = "Responder"

    def init(self, context):
        self.inputs.new("PlasmaRespTriggerSocket", "Trigger", "whodoneit")
        self.outputs.new("PlasmaRespStateSocket", "States", "states")

    def get_key(self, exporter, tree, so):
        return exporter.mgr.find_create_key(plResponderModifier, name=self.create_key_name(tree), so=so)

    def export(self, exporter, tree, bo, so):
        responder = self.get_key(exporter, tree, so).object
        if not bo.plasma_net.manual_sdl:
            responder.setExclude("Responder")

        class ResponderStateMgr:
            def __init__(self, respNode, respMod):
                self.states = []
                self.parent = respNode
                self.responder = respMod

            def get_state(self, node):
                for idx, (theNode, theState) in enumerate(self.states):
                    if theNode == node:
                        return (idx, theState)
                state = plResponderModifier_State()
                self.states.append((node, state))
                return (len(self.states) - 1, state)

            def save(self):
                resp = self.responder
                resp.clearStates()
                for node, state in self.states:
                    resp.addState(state)

        # Convert the Responder states
        stateMgr = ResponderStateMgr(self, responder)
        for stateNode in self.find_outputs("states", "PlasmaResponderStateNode"):
            stateNode.convert_state(exporter, stateMgr)
        stateMgr.save()


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

    def convert_state(self, exporter, stateMgr):
        idx, state = stateMgr.get_state(self)

        # No sanity checking here. Hopefully nothing crazy has happened in the UI.
        if self.default_state:
            stateMgr.responder.curState = idx

        # Where do we go from heah?
        toStateNode = self.find_output("gotostate", "PlasmaResponderStateNode")
        if toStateNode is None:
            state.switchToState = idx
        else:
            toIdx, toState = stateMgr.get_state(toStateNode)
            state.switchToState = toIdx

        class CommandMgr:
            def __init__(self):
                self.commands = []
                self.waits = {}

            def add_command(self, node):
                cmd = type("ResponderCommand", (), {"msg": None, "waitOn": -1})
                self.commands.append((node, cmd))
                return (len(self.commands) - 1, cmd)

            def add_wait(self, parentCmd):
                try:
                    idx = self.commands.index(parentCmd)
                except ValueError:
                    # The parent command didn't export for some reason... Probably no message.
                    # So, wait on nothing!
                    return -1
                else:
                    wait = len(self.waits)
                    self.waits[wait] = idx
                    return idx

            def save(self, state):
                for node, cmd in self.commands:
                    # Amusing, PyHSPlasma doesn't actually want a plResponderModifier_Cmd
                    # Meh, I'll let this one slide.
                    state.addCommand(cmd.msg, cmd.waitOn)
                state.numCallbacks = len(self.waits)
                state.waitToCmd = self.waits

        # Convert the commands
        commands = CommandMgr()
        for i in self.find_outputs("cmds", "PlasmaResponderCommandNode"):
            # slight optimization--commands attached to states can't wait on other commands
            # namely because it's impossible to wait on a command that doesn't exist...
            i.convert_command(exporter, stateMgr.responder, commands, True)
        commands.save(state)


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

    def convert_command(self, exporter, responder, commandMgr, forceNoWait=False):
        # If this command has no message, there is no need to export it...
        msgNode = self.find_output("msg")
        if msgNode is not None:
            idx, command = commandMgr.add_command(self)

            # If the thingthatdoneit is another command, we need to register a wait.
            # We could hack and assume the parent is idx-1, but that won't work if the parent has many
            # child commands. Le whoops!
            if not forceNoWait:
                parentCmd = self.find_input("whodoneit", "PlasmaResponderCommandNode")
                if parentCmd is not None:
                    command.waitOn = commandMgr.add_wait(parentCmd)

            # Finally, convert our message...
            msg = msgNode.convert_message(exporter)
            self._finalize_message(exporter, responder, msg)

            # If we have child commands, we need to make sure that we support chaining this message as a callback
            # If not, we'll export our children and tell them to not actually wait on us.
            haveChildren = self.find_output("trigger", "PlasmaResponderCommandNode") is not None
            if haveChildren:
                nowait = not self._add_msg_callback(exporter, responder, msg)
            command.msg = msg
        else:
            nowait = True

        # Export any child commands
        for i in self.find_outputs("trigger", "PlasmaResponderCommandNode"):
            i.convert_command(exporter, responder, commandMgr, nowait)

    _bcast_flags = {
        plArmatureEffectStateMsg: (plMessage.kPropagateToModifiers | plMessage.kNetPropagate),
    }

    def _finalize_message(self, exporter, responder, msg):
        msg.sender = responder.key

        # BCast Flags are pretty common...
        _cls = msg.__class__
        if _cls in self._bcast_flags:
            msg.BCastFlags = self._bcast_flags[_cls]
        msg.BCastFlags |= plMessage.kLocalPropagate

    def _add_msg_callback(self, exporter, responder, msg):
        """Prepares a given message to be a callback to the responder"""
        # We do not support callback messages ATM
        return False


class PlasmaRespCommandSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.451, 0.0, 0.263, 1.0)

