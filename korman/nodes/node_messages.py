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


class PlasmaMessageNode(PlasmaNodeBase):
    @property
    def has_callbacks(self):
        """This message has callbacks that can be waited on by a Responder"""
        return False


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
    drivable = BoolProperty(name="Drivable",
                            description="Player retains control of the avatar during the OneShot",
                            default=False)
    reversable = BoolProperty(name="Reversable",
                              description="Player can reverse the OneShot",
                              default=False)

    def init(self, context):
        self.inputs.new("PlasmaOneShotMsgSocket", "Sender", "sender")

    def convert_message(self, exporter, tree, so, respKey, wait):
        msg = plOneShotMsg()
        msg.addReceiver(self.get_key(exporter, tree, so))
        cb = self.find_input_socket("sender")
        if cb.marker:
            msg.addCallback(cb.marker, respKey, wait)
        return msg

    def draw_buttons(self, context, layout):
        layout.prop(self, "animation", text="Anim")
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
        cb = self.find_input_socket("sender")
        return bool(cb.marker)


class PlasmaOneShotMsgSocket(PlasmaMessageSocketBase, bpy.types.NodeSocket):
    marker = StringProperty(name="Marker",
                            description="Name of the marker specifying the time to send a callback message")

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.prop(self, "marker")
        else:
            layout.label(text)


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

    def convert_message(self, exporter, tree, so, respKey, wait):
        msg = plArmatureEffectStateMsg()
        msg.surface = footstep_surface_ids[self.surface]
        return msg
