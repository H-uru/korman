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

class PlasmaMessageSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.004, 0.282, 0.349, 1.0)


class PlasmaFootstepSoundMsgNode(PlasmaNodeBase, bpy.types.Node):
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

    def convert_message(self, exporter):
        msg = plArmatureEffectStateMsg()
        msg.surface = footstep_surface_ids[self.surface]
        return msg
