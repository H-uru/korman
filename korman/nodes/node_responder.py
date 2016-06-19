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
from collections import OrderedDict
import inspect
from PyHSPlasma import *
import uuid

from .node_core import *

class PlasmaResponderNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderNode"
    bl_label = "Responder"
    bl_width_default = 145

    # These are the Python attributes we can fill in
    pl_attrib = {"ptAttribResponder", "ptAttribResponderList", "ptAttribNamedResponder"}

    detect_trigger = BoolProperty(name="Detect Trigger",
                                  description="When notified, trigger the Responder",
                                  default=True)
    detect_untrigger = BoolProperty(name="Detect UnTrigger",
                                    description="When notified, untrigger the Responder",
                                    default=False)
    no_ff_sounds = BoolProperty(name="Don't F-Fwd Sounds",
                                description="When fast-forwarding, play sound effects",
                                default=False)

    input_sockets = OrderedDict([
        ("condition", {
            "text": "Condition",
            "type": "PlasmaConditionSocket",
            "spawn_empty": True,
        }),
    ])

    output_sockets = OrderedDict([
        ("keyref", {
            "text": "References",
            "type": "PlasmaPythonReferenceNodeSocket",
            "valid_link_nodes": {"PlasmaPythonFileNode"},
        }),
        ("states", {
            "text": "States",
            "type": "PlasmaRespStateSocket",
        }),
    ])

    def draw_buttons(self, context, layout):
        layout.prop(self, "detect_trigger")
        layout.prop(self, "detect_untrigger")
        layout.prop(self, "no_ff_sounds")

    def get_key(self, exporter, so):
        return exporter.mgr.find_create_key(plResponderModifier, name=self.key_name, so=so)

    def export(self, exporter, bo, so):
        responder = self.get_key(exporter, so).object
        if not bo.plasma_net.manual_sdl:
            responder.setExclude("Responder")

        if self.detect_trigger:
            responder.flags |= plResponderModifier.kDetectTrigger
        if self.detect_untrigger:
            responder.flags |= plResponderModifier.kDetectUnTrigger
        if self.no_ff_sounds:
            responder.flags |= plResponderModifier.kSkipFFSound

        class ResponderStateMgr:
            def __init__(self, respNode, respMod):
                self.states = []
                self.parent = respNode
                self.responder = respMod

            def get_state(self, node):
                for idx, (theNode, theState) in enumerate(self.states):
                    if theNode == node:
                        return (idx, theState, True)
                state = plResponderModifier_State()
                self.states.append((node, state))
                return (len(self.states) - 1, state, False)

            def save(self):
                resp = self.responder
                resp.clearStates()
                for node, state in self.states:
                    resp.addState(state)

        # Convert the Responder states
        stateMgr = ResponderStateMgr(self, responder)
        for stateNode in self.find_outputs("states", "PlasmaResponderStateNode"):
            stateNode.convert_state(exporter, so, stateMgr)
        stateMgr.save()


class PlasmaResponderStateNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderStateNode"
    bl_label = "Responder State"

    default_state = BoolProperty(name="Default State",
                                 description="This state is the responder's default",
                                 default=False)

    input_sockets = OrderedDict([
        ("condition", {
            "text": "Condition",
            "type": "PlasmaRespStateSocket",
            "spawn_empty": True,
        }),
    ])

    output_sockets = OrderedDict([
        ("cmds", {
            "text": "Commands",
            "type": "PlasmaRespCommandSocket",
        }),
        ("gotostate", {
            "link_limit": 1,
            "text": "Trigger",
            "type": "PlasmaRespStateSocket",
        }),
    ])

    def draw_buttons(self, context, layout):
        layout.prop(self, "default_state")

    def convert_state(self, exporter, so, stateMgr):
        idx, state, converted = stateMgr.get_state(self)

        # No sanity checking here. Hopefully nothing crazy has happened in the UI.
        if self.default_state:
            stateMgr.responder.curState = idx

        # Where do we go from heah?
        toStateNode = self.find_output("gotostate", "PlasmaResponderStateNode")
        if toStateNode is None:
            state.switchToState = idx
        else:
            toIdx, toState, converted = stateMgr.get_state(toStateNode)
            state.switchToState = toIdx
            if not converted:
                toStateNode.convert_state(exporter, so, stateMgr)

        class CommandMgr:
            def __init__(self):
                self.commands = []
                self.waits = {}

            def add_command(self, node, waitOn):
                cmd = type("ResponderCommand", (), {"msg": None, "waitOn": waitOn})
                self.commands.append((node, cmd))
                return (len(self.commands) - 1, cmd)

            def add_wait(self, parentIdx):
                wait = len(self.waits)
                self.waits[wait] = parentIdx
                return wait

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
            i.convert_command(exporter, so, stateMgr.responder, commands)
        commands.save(state)

    def update(self):
        super().update()

        # Check to see if we're the default state
        if not self.default_state:
            inputs = list(self.find_input_sockets("condition", "PlasmaResponderNode"))
            if len(inputs) == 1:
                self.default_state = True


class PlasmaRespStateSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.388, 0.78, 0.388, 1.0)


class PlasmaResponderCommandNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderCommandNode"
    bl_label = "Responder Command"

    input_sockets = OrderedDict([
        ("whodoneit", {
            "text": "Condition",
            "type": "PlasmaRespCommandSocket",
        }),
    ])

    output_sockets = OrderedDict([
        ("msg", {
            "link_limit": 1,
            "text": "Message",
            "type": "PlasmaMessageSocket",
        }),
        ("trigger", {
            "text": "Trigger",
            "type": "PlasmaRespCommandSocket",
        }),
        ("reenable", {
            "text": "Local Reenable",
            "type": "PlasmaEnableMessageSocket",
        }),
    ])

    def convert_command(self, exporter, so, responder, commandMgr, waitOn=-1):
        def prepare_message(exporter, so, responder, commandMgr, waitOn, msg):
            idx, command = commandMgr.add_command(self, waitOn)
            if msg.sender is None:
                msg.sender = responder.key
            msg.BCastFlags |= plMessage.kLocalPropagate
            command.msg = msg
            return (idx, command)

        # If this command has no message, there is no need to export it...
        msgNode = self.find_output("msg")
        if msgNode is not None:
            # HACK: Some message nodes may need to sneakily send multiple messages. So, convert_message
            # is therefore now a generator. We will ASSume that the first message generated is the
            # primary msg that we should use for callbacks, if applicable
            if inspect.isgeneratorfunction(msgNode.convert_message):
                messages = tuple(msgNode.convert_message(exporter, so))
                msg = messages[0]
                for i in messages[1:]:
                    prepare_message(exporter, so, responder, commandMgr, waitOn, i)
            else:
                msg = msgNode.convert_message(exporter, so)
            idx, command = prepare_message(exporter, so, responder, commandMgr, waitOn, msg)

            # If we have child commands, we need to make sure that we support chaining this message as a callback
            # If not, we'll export our children and tell them to not actually wait on us.
            haveChildren = self.find_output("trigger", "PlasmaResponderCommandNode") is not None
            if haveChildren and msgNode.has_callbacks:
                childWaitOn = commandMgr.add_wait(idx)
                msgNode.convert_callback_message(exporter, so, msg, responder.key, childWaitOn)
            else:
                childWaitOn = waitOn
        else:
            childWaitOn = waitOn

        # If they linked us back to a condition or something that exports a LogicModifier, that
        # means we need to reenable it here... NOTE: it would be incredibly stupid to do this
        # if we're not waiting on anything to complete
        if childWaitOn != -1:
            for child in self.find_outputs("reenable"):
                key = child.get_key(exporter, so)
                if key is None:
                    continue
                logicmod = key.object
                if not isinstance(logicmod, plLogicModifier):
                    continue
                logicmod.setLogicFlag(plLogicModifier.kOneShot, True)

                # Yep, this is an entirely new ResponderCommand that sends a plEnableMsg
                enableMsg = plEnableMsg()
                enableMsg.addReceiver(key)
                enableMsg.sender = responder.key
                enableMsg.BCastFlags |= plMessage.kLocalPropagate
                enableMsg.setCmd(plEnableMsg.kEnable, True)
                logicCmdIdx, logicCmd = commandMgr.add_command(self, childWaitOn)
                logicCmd.msg = enableMsg

        # Export any child commands
        for i in self.find_outputs("trigger", "PlasmaResponderCommandNode"):
            i.convert_command(exporter, so, responder, commandMgr, childWaitOn)


class PlasmaRespCommandSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.451, 0.0, 0.263, 1.0)
