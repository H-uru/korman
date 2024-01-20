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
from PyHSPlasma import *

from .node_core import PlasmaNodeBase, PlasmaNodeSocketBase
from ..properties.modifiers.avatar import sitting_approach_flags
from ..exporter.explosions import ExportError

class PlasmaSittingBehaviorNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "AVATAR"
    bl_idname = "PlasmaSittingBehaviorNode"
    bl_label = "Sitting Behavior"
    bl_width_default = 120

    pl_attrib = {"ptAttribActivator", "ptAttribActivatorList", "ptAttribNamedActivator"}

    approach = EnumProperty(name="Approach",
                            description="Directions an avatar can approach the seat from",
                            items=sitting_approach_flags,
                            default={"kApproachFront", "kApproachLeft", "kApproachRight"},
                            options={"ENUM_FLAG"})

    input_sockets: dict[str, dict[str, str]] = {
        "condition": {
            "text": "Condition",
            "type": "PlasmaConditionSocket",
        },
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "satisfies": {
            "text": "Satisfies",
            "type": "PlasmaConditionSocket",
            "valid_link_sockets": {"PlasmaConditionSocket", "PlasmaPythonFileNodeSocket"},
        },
    }

    def draw_buttons(self, context, layout):
        col = layout.column()
        col.label("Approach:")
        col.prop(self, "approach")

    def draw_buttons_ext(self, context, layout):
        layout.prop_menu_enum(self, "approach")

    def get_key(self, exporter, so):
        return self._find_create_key(plSittingModifier, exporter, so=so)

    def export(self, exporter, bo, so):
        sitmod = self._find_create_object(plSittingModifier, exporter, so=so)
        for flag in self.approach:
            sitmod.miscFlags |= getattr(plSittingModifier, flag)
        for i in self.find_outputs("satisfies"):
            if i is not None:
                sitmod.addNotifyKey(i.get_key(exporter, so))
            else:
                exporter.report.warn(f"'{i.bl_idname}' Node '{i.name}' doesn't expose a key. It won't be triggered by '{self.name}'!")

    @property
    def requires_actor(self):
        return True


class PlasmaAnimStageAdvanceSocketIn(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.412, 0.2, 0.055, 1.0)

    auto_advance = BoolProperty(name="Advance to Next Stage",
                                description="Automatically advance to the next stage when the animation completes instead of halting",
                                default=True)

    def draw_content(self, context, layout, node, text):
        if not self.is_linked:
            layout.prop(self, "auto_advance")
        else:
            if self.links[0].from_node.stage_id is not None:
                layout.label("{} {}".format(text, self.links[0].from_node.stage_id))
            else:
                layout.label(text)


class PlasmaAnimStageRegressSocketIn(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.412, 0.2, 0.055, 1.0)

    auto_regress = BoolProperty(name="Regress to Previous Stage",
                                description="Automatically regress to the previous stage when the animation completes instead of halting",
                                default=True)

    def draw_content(self, context, layout, node, text):
        if not self.is_linked:
            layout.prop(self, "auto_regress")
        else:
            if self.links[0].from_node.stage_id is not None:
                layout.label("{} {}".format(text, self.links[0].from_node.stage_id))
            else:
                layout.label(text)


class PlasmaAnimStageOrderSocketOut(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.412, 0.2, 0.055, 1.0)


anim_play_flags = [("kPlayNone", "None", "Play stage only when directed by a message"),
                   ("kPlayKey", "Keyboard", "Play stage when the user presses the forward/backward key"),
                   ("kPlayAuto", "Automatic", "Play stage automatically")]
anim_stage_adv_flags = [("kAdvanceNone", "None", "Advance to the next stage only when directed by a message"),
                        ("kAdvanceOnMove", "Movement", "Advance to the next stage when the user presses a movement key"),
                        ("kAdvanceAuto", "Automatic", "Advance to the next stage automatically when this one completes"),
                        ("kAdvanceOnAnyKey", "Any Keypress", "Advance to the next stage when the user presses any key")]
anim_stage_rgr_flags = [("kAdvanceNone", "None", "Regress to the previous stage only when directed by a message"),
                        ("kAdvanceOnMove", "Movement", "Regress to the previous stage when the user presses a movement key"),
                        ("kAdvanceAuto", "Automatic", "Regress to the previous stage automatically when this one completes"),
                        ("kAdvanceOnAnyKey", "Any Keypress", "Regress to the previous stage when the user presses any key")]


class PlasmaAnimStageSettingsSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.412, 0.0, 0.055, 1.0)


class PlasmaAnimStageSettingsNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "AVATAR"
    bl_idname = "PlasmaAnimStageSettingsNode"
    bl_label = "Animation Stage Settings"
    bl_width_default = 325

    forward = EnumProperty(name="Forward",
                           description="Selects which events cause this stage to play forward",
                           items=anim_play_flags,
                           default="kPlayNone")
    backward = EnumProperty(name="Backward",
                           description="Selects which events cause this stage to play backward",
                           items=anim_play_flags,
                           default="kPlayNone")
    stage_advance = EnumProperty(name="Stage Advance",
                                 description="Selects which events cause this stage to advance to the next stage",
                                 items=anim_stage_adv_flags,
                                 default="kAdvanceNone")
    stage_regress = EnumProperty(name="Stage Regress",
                                 description="Selects which events cause this stage to regress to the previous stage",
                                 items=anim_stage_rgr_flags,
                                 default="kAdvanceNone")

    notify_on = EnumProperty(name="Notify",
                             description="Which events should send notifications",
                             items=[
                                ("kNotifyEnter", "Enter",
                                "Send notification when animation first begins to play"),
                                ("kNotifyLoop", "Loop",
                                "Send notification when animation starts a loop"),
                                ("kNotifyAdvance", "Advance",
                                "Send notification when animation is advanced"),
                                ("kNotifyRegress", "Regress",
                                "Send notification when animation is regressed")
                             ],
                             default={"kNotifyEnter"},
                             options={"ENUM_FLAG"})

    input_sockets: dict[str, dict[str, Any]] = {
        "advance_to": {
            "text": "Advance to Stage",
            "type": "PlasmaAnimStageAdvanceSocketIn",
            "valid_link_nodes": "PlasmaAnimStageNode",
            "valid_link_sockets": "PlasmaAnimStageOrderSocketOut",
            "link_limit": 1,
        },
        "regress_to": {
            "text": "Regress to Stage",
            "type": "PlasmaAnimStageRegressSocketIn",
            "valid_link_nodes": "PlasmaAnimStageNode",
            "valid_link_sockets": "PlasmaAnimStageOrderSocketOut",
            "link_limit": 1,
        },
    }

    output_sockets: dict[str, dict[str, str]] = {
        "stage": {
            "text": "Stage",
            "type": "PlasmaAnimStageSettingsSocket",
            "valid_link_nodes": "PlasmaAnimStageNode",
            "valid_link_sockets": "PlasmaAnimStageSettingsSocket",
        },
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "forward")
        layout.prop(self, "backward")
        layout.prop(self, "stage_advance")
        layout.prop(self, "stage_regress")
        layout.separator()

        layout.label("Notify On:")
        row = layout.row()
        row.prop(self, "notify_on")
        layout.separator()


class PlasmaAnimStageNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "AVATAR"
    bl_idname = "PlasmaAnimStageNode"
    bl_label = "Animation Stage"
    bl_width_default = 325

    pl_attrib = ("ptAttribAnimation")

    anim_name = StringProperty(name="Animation Name",
                               description="Name of animation to play")

    loop_option = EnumProperty(name="Looping",
                               description="Loop options for animation playback",
                               items=[("kDontLoop", "Don't Loop", "Don't loop the animation"),
                                      ("kLoop", "Loop", "Loop the animation a finite number of times"),
                                      ("kLoopForever", "Loop Forever", "Continue playing animation indefinitely")],
                               default="kDontLoop")
    num_loops = IntProperty(name="Num Loops",
                            description="Number of times to loop animation",
                            default=0)

    input_sockets: dict[str, dict[str, Any]] = {
        "stage_settings": {
            "text": "Stage Settings",
            "type": "PlasmaAnimStageSettingsSocket",
            "valid_link_nodes": "PlasmaAnimStageSettingsNode",
            "valid_link_sockets": "PlasmaAnimStageSettingsSocket",
            "link_limit": 1,
        },
    }

    output_sockets: dict[str, Any] = {
        "stage": {
            "text": "Behavior",
            "type": "PlasmaAnimStageRefSocket",
            "valid_link_nodes": "PlasmaMultiStageBehaviorNode",
            "valid_link_sockets": "PlasmaAnimStageRefSocket",
        },
        "stage_reference": {
            "text": "Stage Progression",
            "type": "PlasmaAnimStageOrderSocketOut",
            "valid_link_nodes": "PlasmaAnimStageSettingsNode",
            "valid_link_sockets": {"PlasmaAnimStageAdvanceSocketIn", "PlasmaAnimStageRegressSocketIn"} ,
        },
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "anim_name")

        row = layout.row()
        row.prop(self, "loop_option")
        if self.loop_option == "kLoop":
            row = layout.row()
            row.prop(self, "num_loops")

    @property
    def stage_id(self):
        idx = None
        stage_socket = self.find_output_socket("stage")
        if stage_socket.is_linked:
            msbmod = stage_socket.links[0].to_node
            idx = next((idx for idx, socket in enumerate(msbmod.find_input_sockets("stage_refs")) if socket.is_linked and socket.links[0].from_node == self))
        return idx


class PlasmaBehaviorSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.348, 0.186, 0.349, 1.0)


class PlasmaMultiStageBehaviorNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "AVATAR"
    bl_idname = "PlasmaMultiStageBehaviorNode"
    bl_label = "Multistage Behavior"
    bl_width_default = 200

    pl_attrib = ("ptAttribBehavior")

    freeze_phys = BoolProperty(name="Freeze Physical",
                              description="Freeze physical at end",
                              default=False)
    reverse_control = BoolProperty(name="Reverse Controls",
                              description="Reverse forward/back controls at end",
                              default=False)

    input_sockets: dict[str, Any] = {
        "seek_target": {
            "text": "Seek Target",
            "type": "PlasmaSeekTargetSocketIn",
            "valid_link_sockets": "PlasmaSeekTargetSocketOut",
        },
        "stage_refs": {
            "text": "Stage",
            "type": "PlasmaAnimStageRefSocket",
            "valid_link_nodes": "PlasmaAnimStageNode",
            "valid_link_sockets": "PlasmaAnimStageRefSocket",
            "link_limit": 1,
            "spawn_empty": True,
        },
        "condition": {
            "text": "Triggered By",
            "type": "PlasmaConditionSocket",
            "spawn_empty": True,
        },
    }

    output_sockets: dict[str, Any] = {
        "hosts": {
            "text": "Host Script",
            "type": "PlasmaBehaviorSocket",
            "valid_link_nodes": "PlasmaPythonFileNode",
            "spawn_empty": True,
        },
        "satisfies": {
            "text": "Trigger",
            "type": "PlasmaConditionSocket",
        }
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "freeze_phys")
        layout.prop(self, "reverse_control")

    def get_key(self, exporter, so):
        seek_socket = self.find_input_socket("seek_target")

        if seek_socket.is_linked:
            seek_target = seek_socket.links[0].from_node.target
            if seek_target is not None:
                seek_object = exporter.mgr.find_create_object(plSceneObject, bl=seek_target)
            else:
                self.raise_error("MultiStage Behavior's seek point object is invalid")
        else:
            seek_object = so

        return self._find_create_key(plMultistageBehMod, exporter, so=seek_object)

    def export(self, exporter, bo, so):
        seek_socket = self.find_input_socket("seek_target")
        msbmod = self.get_key(exporter, so).object

        msbmod.smartSeek = True if seek_socket.is_linked or seek_socket.auto_target else False
        msbmod.freezePhys = self.freeze_phys
        msbmod.reverseFBControlsOnRelease = self.reverse_control

        for stage in self.find_inputs("stage_refs"):
            animstage = plAnimStage()
            animstage.animName = stage.anim_name
            if stage.loop_option == "kLoopForever":
                animstage.loops = -1
            elif stage.loop_option == "kLoop":
                animstage.loops = stage.num_loops

            # Harvest additional AnimStage Settings, if available
            settings = stage.find_input("stage_settings")
            if settings:
                animstage.forwardType = getattr(plAnimStage, settings.forward)
                animstage.backType =getattr(plAnimStage, settings.backward)
                animstage.advanceType = getattr(plAnimStage, settings.stage_advance)
                animstage.regressType = getattr(plAnimStage, settings.stage_regress)
                for flag in settings.notify_on:
                    animstage.notify |= getattr(plAnimStage, flag)

                advance_to = settings.find_input_socket("advance_to")
                if advance_to.is_linked:
                    # Auto-Advance to specific stage
                    animstage.advanceTo = advance_to.links[0].from_node.stage_id
                elif advance_to.auto_advance:
                    # Auto-Advance
                    animstage.advanceTo = None
                else:
                    # Don't Auto-Advance, just stop!
                    animstage.advanceTo = -1

                regress_to = settings.find_input_socket("regress_to")
                if regress_to.is_linked:
                    # Auto-Regress to specific stage
                    animstage.regressTo = regress_to.links[0].from_node.stage_id
                elif regress_to.auto_regress:
                    # Auto-Regress
                    animstage.regressTo = None
                else:
                    # Don't Auto-Regress, just stop!
                    animstage.regressTo = -1

            msbmod.addStage(animstage)

        receivers = ((i, i.get_key(exporter, so)) for i in self.find_outputs("satisfies"))
        for node, key in receivers:
            if key is not None:
                msbmod.addReceiver(key)
            else:
                exporter.report.warn("'{}' Node '{}' doesn't expose a key. It won't be triggered by '{}'!",
                                     node.bl_idname, node.name, self.name)

    @property
    def requires_actor(self):
        return not self.find_input_socket("seek_target").is_linked

    @property
    def export_once(self):
        return self.find_input_socket("seek_target").is_linked

    def harvest_actors(self):
        seek_socket = self.find_input_socket("seek_target")
        if seek_socket.is_linked and seek_socket.links[0].from_node.target is not None:
            yield seek_socket.links[0].from_node.target.name


class PlasmaAnimStageRefSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.188, 0.186, 0.349, 1.0)

    def draw_content(self, context, layout, node, text):
        if isinstance(node, PlasmaMultiStageBehaviorNode):
            try:
                idx = next((idx for idx, socket in enumerate(node.find_input_sockets("stage_refs")) if socket == self))
            except StopIteration:
                layout.label(text)
            else:
                layout.label("Stage (ID: {})".format(idx))
        else:
            layout.label(text)


class PlasmaSeekTargetSocketIn(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.180, 0.350, 0.180, 1.0)
    auto_target = BoolProperty(name="Auto Smart Seek",
                               description="Smart Seek causes the avatar to seek to the provided position before starting the behavior ('auto' will use the current object as the seek point)",
                               default=False)

    def draw_content(self, context, layout, node, text):
        if not self.is_linked:
            layout.prop(self, "auto_target")
        else:
            target = self.links[0].from_node.target
            if target:
                layout.label("Smart Seek Target: {}".format(target.name))
            else:
                layout.label("Smart Seek Target")


class PlasmaSeekTargetSocketOut(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.180, 0.350, 0.180, 1.0)


class PlasmaSeekTargetNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "AVATAR"
    bl_idname = "PlasmaSeekTargetNode"
    bl_label = "Seek Target"
    bl_width_default = 200

    target = PointerProperty(name="Position",
                             description="Object defining the Seek Point's position",
                             type=bpy.types.Object)

    output_sockets: dict[str, Any] = {
        "seekers": {
            "text": "Seekers",
            "type": "PlasmaSeekTargetSocketOut",
            "valid_link_nodes": {"PlasmaMultiStageBehaviorNode", "PlasmaOneShotMsgNode"},
            "valid_link_sockets": {"PlasmaSeekTargetSocketIn"},
        },
    }

    def draw_buttons(self, context, layout):
        col = layout.column()
        col.prop(self, "target", icon="EMPTY_DATA")
