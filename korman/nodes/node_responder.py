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
from .node_deprecated import PlasmaVersionedNode

class PlasmaResponderNode(PlasmaVersionedNode, bpy.types.Node):
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
    default_state = IntProperty(name="Default State Index",
                                options=set())

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
        ("state_refs", {
            "text": "State",
            "type": "PlasmaRespStateRefSocket",
            "valid_link_nodes": "PlasmaResponderStateNode",
            "valid_link_sockets": "PlasmaRespStateRefSocket",
            "link_limit": 1,
            "spawn_empty": True,
        }),

        # This version of the states socket has been deprecated.
        # We need to be able to track 1 socket -> 1 state to manage
        # responder state IDs
        ("states", {
            "text": "States",
            "type": "PlasmaRespStateSocket",
            "hidden": True,
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
        responder.curState = self.default_state

        class ResponderStateMgr:
            def __init__(self, respNode, respMod):
                self.states = []
                self.parent = respNode
                self.responder = respMod
                self.has_pfm = respNode.find_output("keyref") is not None

            def convert_states(self, exporter, so):
                # This could implicitly export more states...
                i = 0
                while i < len(self.states):
                    node, state = self.states[i]
                    node.convert_state(exporter, so, state, i, self)
                    i += 1

                resp = self.responder
                resp.clearStates()
                for node, state in self.states:
                    resp.addState(state)

            def get_state(self, node):
                for idx, (theNode, theState) in enumerate(self.states):
                    if theNode == node:
                        return (idx, theState)
                state = plResponderModifier_State()
                self.states.append((node, state))
                return (len(self.states) - 1, state)

            def register_state(self, node):
                self.states.append((node, plResponderModifier_State()))

        # Convert the Responder states
        stateMgr = ResponderStateMgr(self, responder)
        for stateNode in self.find_outputs("state_refs", "PlasmaResponderStateNode"):
            stateMgr.register_state(stateNode)
        stateMgr.convert_states(exporter, so)

    def upgrade(self):
        # In version 1 responder nodes, responder states could be linked to the responder
        # or to subsequent responder state nodes and be exported. The problem with this
        # is that to use responder states in Python attributes, we need to be able to
        # inform the user as to what the ID of the responder state will be.
        # Version 2 make it slightly more mandatory that states be linked to a responder
        # and will display the ID of each state linked to the responder. Any states only
        # linked to other states will be converted at the end of the list.
        if self.version == 1:
            states = set()
            def _link_states(state):
                if state in states:
                    return
                states.add(state)
                self.link_output(state, "state_refs", "resp")
                goto = state.find_output("gotostate")
                if goto is not None:
                    _link_states(goto)
            for i in self.find_outputs("states"):
                _link_states(i)
            self.unlink_outputs("states", "socket deprecated (upgrade complete)")
            self.version = 2


class PlasmaResponderStateNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderStateNode"
    bl_label = "Responder State"

    def _get_default_state(self):
        resp_node = self.find_input("resp")
        if resp_node is not None:
            try:
                state_idx = next((idx for idx, node in enumerate(resp_node.find_outputs("state_refs")) if node == self))
            except StopIteration:
                return False
            else:
                return resp_node.default_state == state_idx
        return False
    def _set_default_state(self, value):
        if value:
            resp_node = self.find_input("resp")
            if resp_node is not None:
                try:
                    state_idx = next((idx for idx, node in enumerate(resp_node.find_outputs("state_refs")) if node == self))
                except StopIteration:
                    self._whine("unable to set default state on responder")
                else:
                    resp_node.default_state = state_idx

    default_state = BoolProperty(name="Default State",
                                 description="This state is the responder's default",
                                 get=_get_default_state,
                                 set=_set_default_state,
                                 options=set())

    input_sockets = OrderedDict([
        ("condition", {
            "text": "Triggers State",
            "type": "PlasmaRespStateSocket",
            "spawn_empty": True,
        }),
        ("resp", {
            "text": "Responder",
            "type": "PlasmaRespStateRefSocket",
            "valid_link_nodes": "PlasmaResponderNode",
            "valid_link_sockets": "PlasmaRespStateRefSocket",
        }),
    ])

    output_sockets = OrderedDict([
        # This socket has been deprecated.
        ("cmds", {
            "text": "Commands",
            "type": "PlasmaRespCommandSocket",
            "hidden": True,
        }),

        # These sockets are valid.
        ("msgs", {
            "text": "Send Message",
            "type": "PlasmaMessageSocket",
            "valid_link_sockets": "PlasmaMessageSocket",
        }),
        ("gotostate", {
            "link_limit": 1,
            "text": "Triggers State",
            "type": "PlasmaRespStateSocket",
        }),
    ])

    def draw_buttons(self, context, layout):
        layout.active = self.find_input("resp") is not None
        layout.prop(self, "default_state")

    def convert_state(self, exporter, so, state, idx, stateMgr):
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
        for i in self.find_outputs("msgs"):
            # slight optimization--commands attached to states can't wait on other commands
            # namely because it's impossible to wait on a command that doesn't exist...
            self._generate_command(exporter, so, stateMgr.responder, commands, i)
        commands.save(state)

        # If the responder is linked to a PythonFile node, we need to automatically generate
        # the callback message command node...
        # YES! This SHOULD indeed be below the command manager save :)
        if stateMgr.has_pfm:
            pfmNotify = plNotifyMsg()
            pfmNotify.BCastFlags |= plMessage.kLocalPropagate
            pfmNotify.sender = stateMgr.responder.key
            pfmNotify.state = 1.0
            pfmNotify.addEvent(proCallbackEventData())

            # This command needs to send at the end of the state, so after all waits
            # have elapsed. Since waits are serial, we can just take the highest.
            lastWait = len(commands.waits) - 1 if commands.waits else -1
            state.addCommand(pfmNotify, lastWait)

    def _generate_command(self, exporter, so, responder, commandMgr, msgNode, waitOn=-1):
        def prepare_message(exporter, so, responder, commandMgr, waitOn, msg):
            idx, command = commandMgr.add_command(self, waitOn)
            if msg.sender is None:
                msg.sender = responder.key
            msg.BCastFlags |= plMessage.kLocalPropagate
            command.msg = msg
            return (idx, command)

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

        if msgNode.has_callbacks:
            childWaitOn = commandMgr.add_wait(idx)
            msgNode.convert_callback_message(exporter, so, msg, responder.key, childWaitOn)
        else:
            childWaitOn = waitOn

        # Export any linked callback messages
        for i in msgNode.find_outputs("msgs"):
            self._generate_command(exporter, so, responder, commandMgr, i, childWaitOn)


class PlasmaRespStateSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.388, 0.78, 0.388, 1.0)


class PlasmaRespStateRefSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (1.00, 0.980, 0.322, 1.0)

    def draw(self, context, layout, node, text):
        if isinstance(node, PlasmaResponderNode):
            try:
                idx = next((idx for idx, socket in enumerate(node.find_output_sockets("state_refs")) if socket == self))
            except StopIteration:
                layout.label(text)
            else:
                layout.label("State (ID: {})".format(idx))
        else:
            layout.label(text)
