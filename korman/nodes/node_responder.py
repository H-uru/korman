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

from __future__ import annotations

import bpy
from bpy.props import *
from typing import *
import inspect
from PyHSPlasma import *

from ..helpers import run_once, TemporaryObject
from .node_core import *
from .node_deprecated import PlasmaVersionedNode

class _ResponderState(NamedTuple):
    node: PlasmaResponderStateNode
    state: plResponderModifier_State


class _ResponderStateMgr:
    def __init__(self, respNode: PlasmaNodeBase, respMod: plResponderModifier):
        self.states: List[_ResponderState] = []
        self.parent = respNode
        self.responder = respMod

    def convert_states(self, exporter: Exporter, so: plSceneObject):
        # This could implicitly export more states...
        i = 0
        while i < len(self.states):
            node, state = self.states[i]
            node.convert_state(exporter, so, state, i, self)
            i += 1

        if not self.states:
            self.parent.raise_error("No states converted by Responder node")

        resp = self.responder
        resp.clearStates()
        for node, state in self.states:
            resp.addState(state)

    def get_state(self, node) -> Tuple[int, plResponderModifier_State]:
        for idx, (theNode, theState) in enumerate(self.states):
            if theNode == node:
                return (idx, theState)
        state = plResponderModifier_State()
        self.states.append(_ResponderState(node, state))
        return (len(self.states) - 1, state)

    def register_state(self, node):
        self.states.append(_ResponderState(node, plResponderModifier_State()))


class PlasmaResponderNodeBase(PlasmaNodeBase):
    # These are the Python attributes we can fill in
    pl_attrib = {"ptAttribResponder", "ptAttribResponderList", "ptAttribNamedResponder"}

    def create_responder(
        self,
        exporter: Exporter,
        bo: bpy.types.Object,
        so: plSceneObject
    ) -> plResponderModifier:
        responder = self.get_key(exporter, so).object

        # Ensure there is not already a Responder that matches this name in the PRP
        # if we are a named responder. This will be a very rare error - the responder must
        # be linked to a ptAttribNamedResponder for this to trigger.
        if self.is_named_responder and responder.states:
            self.raise_error(f"A Responder named '{self.name}' has already been exported to this page.")
        if not bo.plasma_net.manual_sdl:
            responder.setExclude("Responder")

        return responder

    def get_key(self, exporter, so) -> plKey[plResponderModifier]:
        return self._find_create_key(plResponderModifier, exporter, so=so)

    def get_key_name(self, single, suffix=None, bl=None, so=None) -> str:
        # If we're connected to a ptAttribNamedResponder, then we need to use our exact
        # name in the node tree. This introduces potential collisions, so named responders
        # are opt-in behavior.
        if self.is_named_responder:
            return self.name
        else:
            return super().get_key_name(single, suffix, bl, so)

    @property
    def export_once(self):
        # What exactly is a reused responder? All the messages are directed, after all...
        return True

    @property
    def is_named_responder(self) -> bool:
        # Check to see if any of the Python attributes that we're linked to are ptAttribNamedResponder.
        # We'll need to navigate from our keyref output socket (PFM socket) to the PFM attribute
        # socket and test the `attribute_type` for all links.
        return any(
            (i.to_socket.attribute_type == "ptAttribNamedResponder"
             for i in self.find_output_socket("keyref").links)
        )


class PlasmaBasicResponderNode(PlasmaVersionedNode, PlasmaResponderNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaBasicResponderNode"
    bl_label = "Basic Responder"

    input_sockets: dict[str, dict[str, Any]] = {
        "condition": {
            "text": "Condition",
            "type": "PlasmaConditionSocket",
            "spawn_empty": True,
        },
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "keyref": {
            "text": "Host Script",
            "type": "PlasmaPythonReferenceNodeSocket",
            "valid_link_nodes": {"PlasmaPythonFileNode"},
        },
        "msgs": {
            "text": "Send Message",
            "type": "PlasmaMessageSocket",
            "valid_link_sockets": "PlasmaMessageSocket",
        },
        # This socket only exists to make the code safe. It will never be seen by the user.
        "state_refs": {
            "text": "State",
            "type": "PlasmaRespStateRefSocket",
            "valid_link_nodes": "PlasmaResponderStateNode",
            "valid_link_sockets": "PlasmaRespStateRefSocket",
            "hidden": True,
            "link_limit": 1,
        },
    }

    def export(self, exporter, bo, so):
        # This node exists to simplify the creation of Responders even further. The old Responder
        # node is very close to what Plasma does under the hood and what PlasmaMax exposes. I
        # removed the "command" node in version 2 of that node, but, really, most responders just
        # need to send some messages when they are triggered with a notify of state==1.0. That's
        # what our goal is. Not worrying about Responder states, switch to, when to fire, etc.
        responder = self.create_responder(exporter, bo, so)
        responder.flags |= plResponderModifier.kDetectTrigger

        # This is a bit of a hack, but it allows us to reuse the existing well-tested Responder
        # export code and not have to write a new code path. We're going to sneakily create a
        # Responder State node for our only state and link our messages to it. Then link the state
        # node to ourselves, just in case the export code ever cares. Then, we can just fire the
        # old export code.
        nodes = self.id_data.nodes
        with TemporaryObject(nodes.new("PlasmaResponderStateNode"), nodes.remove) as state_node:
            self.link_output(state_node, "state_refs", "resp")
            for i in self.find_outputs("msgs"):
                state_node.link_output(i, "msgs", "sender")

            stateMgr = _ResponderStateMgr(self, responder)
            stateMgr.register_state(state_node)
            stateMgr.convert_states(exporter, so)


class PlasmaResponderNode(PlasmaVersionedNode, PlasmaResponderNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaResponderNode"
    bl_label = "Responder"
    bl_width_default = 145

    detect_trigger = BoolProperty(
        name="Detect Trigger",
        description="When a trigger notification (state == 1.0) is received, run the Responder",
        default=True,
        options=set()
        )
    detect_untrigger = BoolProperty(
        name="Detect UnTrigger",
        description="When an untrigger notification (state == 0.0) is received, run the Responder",
        options=set()
    )
    no_ff_sounds = BoolProperty(
        name="Don't F-Fwd Sounds",
        description="When fast-forwarding, play sound effects",
        default=False,
        options=set()
    )
    default_state = IntProperty(
        name="Default State Index",
        options=set()
    )

    input_sockets: dict[str, dict[str, Any]] = {
        "condition": {
            "text": "Condition",
            "type": "PlasmaConditionSocket",
            "spawn_empty": True,
        },
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "keyref": {
            "text": "Host Script",
            "type": "PlasmaPythonReferenceNodeSocket",
            "valid_link_nodes": {"PlasmaPythonFileNode"},
        },
        "state_refs": {
            "text": "State",
            "type": "PlasmaRespStateRefSocket",
            "valid_link_nodes": "PlasmaResponderStateNode",
            "valid_link_sockets": "PlasmaRespStateRefSocket",
            "link_limit": 1,
            "spawn_empty": True,
        },

        # This version of the states socket has been deprecated.
        # We need to be able to track 1 socket -> 1 state to manage
        # responder state IDs
        "states": {
            "text": "States",
            "type": "PlasmaRespStateSocket",
            "hidden": True,
        }
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "detect_trigger")
        layout.prop(self, "detect_untrigger")
        layout.prop(self, "no_ff_sounds")

    def export(self, exporter, bo, so):
        responder = self.create_responder(exporter, bo, so)
        if self.detect_trigger:
            responder.flags |= plResponderModifier.kDetectTrigger
        if self.detect_untrigger:
            responder.flags |= plResponderModifier.kDetectUnTrigger
        if self.no_ff_sounds:
            responder.flags |= plResponderModifier.kSkipFFSound
        responder.curState = self.default_state

        # Convert the Responder states
        stateMgr = _ResponderStateMgr(self, responder)
        for stateNode in self.find_outputs("state_refs", "PlasmaResponderStateNode"):
            stateMgr.register_state(stateNode)
        stateMgr.convert_states(exporter, so)

    @property
    def latest_version(self):
        return 2

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


class PlasmaResponderStateNode(PlasmaVersionedNode, bpy.types.Node):
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

    export_auto_notify_value = BoolProperty(options={"HIDDEN"})
    def _get_auto_notify(self):
        if not self.allow_auto_notify:
            return False
        return self.export_auto_notify_value
    def _set_auto_notify(self, value: bool) -> None:
        self.export_auto_notify_value = value
    export_auto_notify = BoolProperty(
        name="Auto Notify",
        description="When this state completes, automatically send a notification to whoever triggered the Responder",
        get=_get_auto_notify,
        set=_set_auto_notify,
        options=set()
    )

    input_sockets: dict[str, Any] = {
        "condition": {
            "text": "Triggers State",
            "type": "PlasmaRespStateSocket",
            "spawn_empty": True,
        },
        "resp": {
            "text": "Responder",
            "type": "PlasmaRespStateRefSocket",
            "valid_link_sockets": "PlasmaRespStateRefSocket",
        },
    }

    output_sockets = {
        # This socket has been deprecated.
        # While this is deprecated I might as well also convert it.
        "cmds": {
            "text": "Commands",
            "type": "PlasmaRespCommandSocket",
            "hidden": True,
        },
        # These ones are valid.
        "msgs": {
            "text": "Send Message",
            "type": "PlasmaMessageSocket",
            "valid_link_sockets": "PlasmaMessageSocket",
        },
        "gotostate": {
            "link_limit": 1,
            "text": "Triggers State",
            "type": "PlasmaRespStateSocket",
        },
    }

    @property
    def allow_auto_notify(self):
        resp_node = self.find_input("resp")
        if resp_node is None:
            return False
        if resp_node.find_output("keyref") is None:
            return False
        if self.has_notify:
            return False
        return True

    def draw_buttons(self, context, layout):
        row = layout.row()
        row.active = self.find_input("resp") is not None
        row.prop(self, "default_state")
        row = layout.row()
        row.active = self.allow_auto_notify
        row.prop(self, "export_auto_notify")

    def convert_state(
        self,
        exporter: Exporter,
        so: plSceneObject,
        state: plResponderModifier_State,
        idx: int,
        stateMgr: _ResponderStateMgr
    ):
        # Where do we go from heah?
        toStateNode = self.find_output("gotostate", "PlasmaResponderStateNode")
        if toStateNode is None:
            state.switchToState = idx
        else:
            toIdx, toState = stateMgr.get_state(toStateNode)
            state.switchToState = toIdx

        class CommandMgr:
            def __init__(self, respMod: plResponderModifier, state: plResponderModifier_State):
                self.commands = []
                self.responder = respMod
                self._state = state
                self.waits = {}
                self.waitable_nodes = []

            def __enter__(self):
                return self

            def __exit__(self, type, value, traceback):
                self.save()

            def add_command(self, node, waitOn):
                cmd = type("ResponderCommand", (), {"msg": None, "waitOn": waitOn})
                self.commands.append((node, cmd))
                return (len(self.commands) - 1, cmd)

            def add_wait(self, parentIdx):
                wait = len(self.waits)
                self.waits[wait] = parentIdx
                return wait

            def add_waitable_node(self, node):
                self.waitable_nodes.append(node)

            def ensure_last_wait(self, exporter, so):
                if self.waitable_nodes:
                    return self.find_create_wait(exporter, so, self.waitable_nodes[-1])
                return -1

            def find_create_wait(self, exporter, so, node):
                i, cmd = next(((i, cmd) for i, cmd in enumerate(self.commands) if cmd[0] == node))
                wait = next((key for key, value in self.waits.items() if value == i), None)
                if wait is None:
                    wait = self.add_wait(i)
                    node.convert_callback_message(exporter, so, cmd[1].msg, self.responder.key, wait)
                return wait

            @run_once
            def save(self):
                for node, cmd in self.commands:
                    # Amusing, PyHSPlasma doesn't actually want a plResponderModifier_Cmd
                    # Meh, I'll let this one slide.
                    self._state.addCommand(cmd.msg, cmd.waitOn)
                self._state.numCallbacks = len(self.waits)
                self._state.waitToCmd = self.waits

        # Convert the commands
        with CommandMgr(stateMgr.responder, state) as commands:
            for i in self._get_child_messages():
                # slight optimization--commands attached to states can't wait on other commands
                # namely because it's impossible to wait on a command that doesn't exist...
                self._generate_command(exporter, so, stateMgr.responder, commands, i)

            # Korman would originally notify any attached PFM by default at the end of the Responder
            # state. In PlasmaMax, the "Notify Triggerer" is a manual option, and most Responders
            # actually don't do this. So, in the interest of removing cruft and better exposing
            # our behavior, only do this if the old behavior is explicitly requested.
            if self.export_auto_notify:
                # The last waitable message node may or may not have child nodes attached to it.
                # Imaging a responder that sends only one animation command message, for example.
                # That means a wait will not be set up for that command due to no child linkage.
                # However, the PFM notification below expects a wait for stuff like that.
                lastWait = commands.ensure_last_wait(exporter, so)

                # This commits the responder commands to the responder. Needs to happen before we
                # add the PFM notification directly to the responder. This would normally happen
                # when the context manager exits, but we're going to force it to happen now,
                # and only now.
                commands.save()

                # Manually insert the callback event notify message command. It would have been nice
                # to spawn the node to allow code deduplication, but the structure of the old code
                # means this pattern is nicer.
                cbEvent = proCallbackEventData()
                cbEvent.callbackEventType = 1
                pfmNotify = plNotifyMsg()
                pfmNotify.sender = stateMgr.responder.key
                pfmNotify.state = 1.0
                pfmNotify.addEvent(cbEvent)
                state.addCommand(pfmNotify, lastWait)

    def _generate_command(self, exporter, so, responder, commandMgr, msgNode, waitOn=-1):
        def prepare_message(exporter, so, responder, commandMgr, waitOn, msg):
            idx, command = commandMgr.add_command(msgNode, waitOn)
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
            commandMgr.add_waitable_node(msgNode)
            if msgNode.has_linked_callbacks:
                # Only one "branch" of a Responder is allowed to have callbacks. That is to say
                # that if we have a message that sends two other messages on completion, only one
                # of those two messages can have messages sent after it completes. Plasma doesn't
                # have a concept of sending a batch of messages and waiting on them. It's a serial
                # send-wait, send-wait. So, overriding the waitOn we were initially given is fine.
                waitOn = commandMgr.add_wait(idx)
                msgNode.convert_callback_message(exporter, so, msg, responder.key, waitOn)

        # Export any linked callback messages
        for i in self._get_child_messages(msgNode):
            self._generate_command(exporter, so, responder, commandMgr, i, waitOn)

    def _get_child_messages(self, node=None):
        """Returns a list of the message nodes sent by `node`. The list is sorted such that any
           messages with callbacks are last in the list, allowing proper wait generation.
        """
        if node is None:
            node = self
        return sorted(node.find_outputs("msgs"), key=lambda x: bool(x.has_callbacks and x.has_linked_callbacks))

    @property
    def has_notify(self):
        def check_for_notify(node):
            for i in node.find_outputs("msgs"):
                yield i.is_notify
                yield from check_for_notify(i)
        return any(check_for_notify(self))

    @property
    def latest_version(self):
        return 2

    def upgrade(self):
        # In Version 2 of the node, the automatic notification of attached PFMs has been turned off
        # by default. To ensure esoteric node trees don't suddenly break, any nodes that have
        # attached PFMs will default to this functionality being ON after upgrading. New nodes
        # will default to OFF.
        if self.version == 1:
            # Just directly set the value if auto notification is allowed. Otherwise, leave it
            # at the default value.
            if self.allow_auto_notify:
                self.export_auto_notify_value = True
            self.version = 2


class PlasmaRespStateSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.388, 0.78, 0.388, 1.0)


class PlasmaRespStateRefSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (1.00, 0.980, 0.322, 1.0)

    def draw_content(self, context, layout, node, text):
        if isinstance(node, PlasmaResponderNode):
            try:
                idx = next((idx for idx, socket in enumerate(node.find_output_sockets("state_refs")) if socket == self))
            except StopIteration:
                layout.label(text)
            else:
                layout.label("State (ID: {})".format(idx))
        else:
            layout.label(text)
