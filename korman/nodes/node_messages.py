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

from .node_core import *
from ..properties.modifiers.region import footstep_surfaces, footstep_surface_ids
from ..exporter import ExportError

class PlasmaMessageSocketBase(PlasmaNodeSocketBase):
    bl_color = (0.004, 0.282, 0.349, 1.0)
class PlasmaMessageSocket(PlasmaMessageSocketBase, bpy.types.NodeSocket):
    pass


class PlasmaMessageNode(PlasmaNodeVariableInput):
    @property
    def has_callbacks(self):
        """This message has callbacks that can be waited on by a Responder"""
        return False

    def init(self, context):
        self.inputs.new("PlasmaMessageSocket", "Sender", "sender")

    def update(self):
        self.ensure_sockets("PlasmaMessageSocket", "Sender", "sender")


class PlasmaAnimCmdMsgNode(PlasmaMessageNode, bpy.types.Node):
    bl_category = "MSG"
    bl_idname = "PlasmaAnimCmdMsgNode"
    bl_label = "Animation Command"
    bl_width_default = 190

    anim_type = EnumProperty(name="Type",
                             description="Animation type to affect",
                             items=[("OBJECT", "Object", "Mesh Action"),
                                    ("TEXTURE", "Texture", "Texture Action")],
                             default="OBJECT")
    object_name = StringProperty(name="Object",
                                 description="Target object name")
    material_name = StringProperty(name="Material",
                                   description="Target material name")
    texture_name = StringProperty(name="Texture",
                                  description="Target texture slot name")

    go_to = EnumProperty(name="Go To",
                         description="Where should the animation start?",
                         items=[("kGoToBegin", "Beginning", "The beginning"),
                                ("kGoToLoopBegin", "Loop Beginning", "The beginning of the active loop"),
                                ("CURRENT", "(Don't Change)", "The current position"),
                                ("kGoToEnd", "Ending", "The end"),
                                ("kGoToLoopEnd", "Loop Ending", "The end of the active loop")],
                         default="CURRENT")
    action = EnumProperty(name="Action",
                          description="What do you want the animation to do?",
                          items=[("kContinue", "Play", "Plays the animation"),
                                 ("kPlayToPercent", "Play to Percent", "Plays the animation until a given percent is complete"),
                                 ("kPlayToTime", "Play to Frame", "Plays the animation up to a given frame number"),
                                 ("kStop", "Stop", "Stops the animation",),
                                 ("kToggleState", "Toggle", "Toggles between Play and Stop"),
                                 ("CURRENT", "(Don't Change)", "Don't change the animation's playing state")],
                          default="CURRENT")
    play_direction = EnumProperty(name="Direction",
                                  description="Which direction do you want to play from?",
                                  items=[("kSetForwards", "Forward", "Play forwards"),
                                         ("kSetBackwards", "Backwards", "Play backwards"),
                                         ("CURRENT", "(Don't Change)", "Don't change the  play direction")],
                                  default="CURRENT")
    play_to_percent = IntProperty(name="Play To",
                                  description="Percentage at which to stop the animation",
                                  subtype="PERCENTAGE",
                                  min=0, max=100, default=50)
    play_to_frame = IntProperty(name="Play To",
                                  description="Frame at which to stop the animation",
                                  min=0)

    def _set_loop_name(self, context):
        """Updates loop_begin and loop_end when the loop name is changed"""
        pass

    looping = EnumProperty(name="Looping",
                           description="Is the animation looping?",
                           items=[("kSetLooping", "Yes", "The animation is looping",),
                                  ("CURRENT", "(Don't Change)", "Don't change the loop status"),
                                  ("kSetUnLooping", "No", "The animation is NOT looping")],
                           default="CURRENT")
    loop_name = StringProperty(name="Active Loop",
                               description="Name of the active loop",
                               update=_set_loop_name)
    loop_begin = IntProperty(name="Loop Begin",
                             description="Frame number at which the loop begins",
                             min=0)
    loop_end = IntProperty(name="Loop End",
                           description="Frame number at which the loop ends",
                           min=0)

    event = EnumProperty(name="Callback",
                         description="Event upon which to callback the Responder",
                         items=[("kEnd", "End", "When the action ends"),
                                ("NONE", "(None)", "Don't notify the Responder at all"),
                                ("kStop", "Stop", "When the action is stopped by a message")],
                         default="kEnd")

    def draw_buttons(self, context, layout):
        layout.prop(self, "anim_type")
        if self.anim_type == "OBJECT":
            layout.prop_search(self, "object_name", bpy.data, "objects")
        else:
            layout.prop_search(self, "material_name", bpy.data, "materials")
            material = bpy.data.materials.get(self.material_name, None)
            if material is not None:
                layout.prop_search(self, "texture_name", material, "texture_slots")

        layout.prop(self, "go_to")
        layout.prop(self, "action")
        layout.prop(self, "play_direction")
        if self.action == "kPlayToPercent":
            layout.prop(self, "play_to_percent")
        elif self.action == "kPlayToTime":
            layout.prop(self, "play_to_frame")

        layout.prop(self, "looping")
        col = layout.column()
        col.enabled = self.looping != "CURRENT"
        if self.anim_type != "OBJECT":
            loops = None
        else:
            obj = bpy.data.objects.get(self.object_name, None)
            loops = None if obj is None else obj.plasma_modifiers.animation_loop
        if loops is not None and loops.enabled:
            layout.prop_search(self, "loop_name", loops, "loops", icon="PMARKER_ACT")
        else:
            layout.prop(self, "loop_begin")
            layout.prop(self, "loop_end")

        layout.prop(self, "event")

    def convert_callback_message(self, exporter, tree, so, msg, target, wait):
        cb = plEventCallbackMsg()
        cb.addReceiver(target)
        cb.event = globals()[self.event]
        cb.user = wait
        msg.addCallback(cb)

    def convert_message(self, exporter, tree, so):
        msg = plAnimCmdMsg()

        # We're either sending this off to an AGMasterMod or a LayerAnim
        if self.anim_type == "OBJECT":
            obj = bpy.data.objects.get(self.object_name, None)
            if obj is None:
                self.raise_error("invalid object: '{}'".format(self.object_name), tree)
            anim = obj.plasma_modifiers.animation
            if not anim.enabled:
                self.raise_error("invalid animation", tree)
            target = exporter.mgr.find_create_key(plAGMasterMod, bl=obj, name=anim.display_name)
        else:
            material = bpy.data.materials.get(self.material_name, None)
            if material is None:
                self.raise_error("invalid material: '{}'".format(self.material_name), tree)
            tex_slot = material.texture_slots.get(self.texture_name, None)
            if tex_slot is None:
                self.raise_error("invalid texture: '{}'".format(self.texture_name), tree)
            name = "{}_{}_LayerAnim".format(self.material_name, self.texture_name)
            target = exporter.mgr.find_create_key(plLayerAnimation, name=name, so=so)
        if target is None:
            raise RuntimeError()
        msg.addReceiver(target)

        # Check the enum properties to see what commands we need to add
        for prop in (self.go_to, self.action, self.play_direction, self.looping):
            cmd = getattr(plAnimCmdMsg, prop, None)
            if cmd is not None:
                msg.setCmd(cmd, True)

        # Easier part starts here???
        fps = bpy.context.scene.render.fps
        if self.action == "kPlayToPercent":
            msg.time = self.play_to_percent
        elif self.action == "kPlayToTime":
            msg.time = self.play_to_frame / fps

        # Implicit s better than explicit, I guess...
        if self.loop_begin != self.loop_end:
            # NOTE: loop name is not used in the engine AFAICT
            msg.setCmd(plAnimCmdMsg.kSetLoopBegin, True)
            msg.setCmd(plAnimCmdMsg.kSetLoopEnd, True)
            msg.loopBegin = self.loop_begin / fps
            msg.loopEnd = self.loop_end / fps

        # Whew, this was crazy
        return msg

    @property
    def has_callbacks(self):
        return self.event != "NONE"


class PlasmaOneShotMsgNode(PlasmaMessageNode, bpy.types.Node):
    bl_category = "MSG"
    bl_idname = "PlasmaOneShotMsgNode"
    bl_label = "One Shot"
    bl_width_default = 210

    pos = StringProperty(name="Position",
                         description="Object defining the OneShot position")
    seek = EnumProperty(name="Seek",
                        description="How the avatar should approach the OneShot position",
                        items=[("SMART", "Smart Seek", "Let the engine figure out the best path"),
                               ("DUMB", "Seek", "Shuffle to the OneShot position"),
                               ("NONE", "Warp", "Warp the avatar to the OneShot position")],
                        default="SMART")

    animation = StringProperty(name="Animation",
                               description="Name of the animation the avatar should execute")
    marker = StringProperty(name="Marker",
                                     description="Name of the marker specifying when to notify the Responder")
    drivable = BoolProperty(name="Drivable",
                            description="Player retains control of the avatar during the OneShot",
                            default=False)
    reversable = BoolProperty(name="Reversable",
                              description="Player can reverse the OneShot",
                              default=False)

    def convert_callback_message(self, exporter, tree, so, msg, target, wait):
        msg.addCallback(self.marker, target, wait)

    def convert_message(self, exporter, tree, so):
        msg = plOneShotMsg()
        msg.addReceiver(self.get_key(exporter, tree, so))
        return msg

    def draw_buttons(self, context, layout):
        layout.prop(self, "animation", text="Anim")
        layout.prop(self, "marker")
        row = layout.row()
        row.prop(self, "drivable")
        row.prop(self, "reversable")
        layout.prop_search(self, "pos", bpy.data, "objects", icon="EMPTY_DATA")
        layout.prop(self, "seek")

    def export(self, exporter, tree, bo, so):
        oneshotmod = self.get_key(exporter, tree, so).object
        oneshotmod.animName = self.animation
        oneshotmod.drivable = self.drivable
        oneshotmod.reversable = self.reversable
        oneshotmod.smartSeek = self.seek == "SMART"
        oneshotmod.noSeek = self.seek == "NONE"
        oneshotmod.seekDuration = 1.0

    def get_key(self, exporter, tree, so):
        name = self.create_key_name(tree)
        if self.pos:
            bo = bpy.data.objects.get(self.pos, None)
            if bo is None:
                raise ExportError("Node '{}' in '{}' specifies an invalid Position Empty".format(self.name, tree.name))
            pos_so = exporter.mgr.find_create_object(plSceneObject, bl=bo)
            return exporter.mgr.find_create_key(plOneShotMod, name=name, so=pos_so)
        else:
            return exporter.mgr.find_create_key(plOneShotMod, name=name, so=so)

    @property
    def has_callbacks(self):
        return bool(self.marker)


class PlasmaOneShotCallbackSocket(PlasmaMessageSocketBase, bpy.types.NodeSocket):
    marker = StringProperty(name="Marker",
                            description="Marker specifying the time at which to send a callback to this Responder")

    def draw(self, context, layout, node, text):
        layout.prop(self, "marker")


class PlasmaFootstepSoundMsgNode(PlasmaMessageNode, bpy.types.Node):
    bl_category = "MSG"
    bl_idname = "PlasmaFootstepSoundMsgNode"
    bl_label = "Footstep Sound"

    surface = EnumProperty(name="Surface",
                           description="What kind of surface are we walking on?",
                           items=footstep_surfaces,
                           default="stone")

    def init(self, context):
        self.inputs.new("PlasmaMessageSocket", "Sender", "sender")

    def draw_buttons(self, context, layout):
        layout.prop(self, "surface")

    def convert_message(self, exporter, tree, so):
        msg = plArmatureEffectStateMsg()
        msg.surface = footstep_surface_ids[self.surface]
        return msg
