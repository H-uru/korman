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

from .node_core import PlasmaNodeBase, PlasmaNodeSocketBase
from ..properties.modifiers.physics import bounds_types

class PlasmaConditionSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.188, 0.086, 0.349, 1.0)


class PlasmaVolumeReportNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaVoumeReportNode"
    bl_label = "Region Trigger Settings"

    report_when = EnumProperty(name="When",
                               description="When the region should trigger",
                               items=[("each", "Each Event", "The region will trigger on every enter/exit"),
                                      ("count", "Population", "When the region has a certain number of objects inside it")])
    threshold = IntProperty(name="Threshold",
                    description="How many objects should be in the region for it to trigger",
                    min=1)

    def init(self, context):
        self.outputs.new("PlasmaVolumeSettingsSocketOut", "Trigger Settings")

    def draw_buttons(self, context, layout):
        layout.prop(self, "report_when")
        if self.report_when == "count":
            row = layout.row()
            row.label("Threshold: ")
            row.prop(self, "threshold", text="")


class PlasmaVolumeSensorNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaVolumeSensorNode"
    bl_label = "Region Sensor"
    bl_width_default = 190

    # Region Mesh
    region = StringProperty(name="Region",
                            description="Object that defines the region mesh")
    bounds = EnumProperty(name="Bounds",
                          description="Physical object's bounds",
                          items=bounds_types)

    # Detector Properties
    report_on = EnumProperty(name="Triggerers",
                             description="What triggers this region?",
                             options={"ANIMATABLE", "ENUM_FLAG"},
                             items=[("avatar", "Avatars", "Avatars trigger this region"),
                                    ("dynamics", "Dynamics", "Any non-avatar dynamic physical object (eg kickables)")],
                             default={"avatar"})

    def init(self, context):
        self.inputs.new("PlasmaVolumeSettingsSocketIn", "Trigger on Enter", "enter")
        self.inputs.new("PlasmaVolumeSettingsSocketIn", "Trigger on Exit", "exit")
        self.outputs.new("PlasmaConditionSocket", "Satisfies", "satisfies")

    def draw_buttons(self, context, layout):
        layout.prop(self, "report_on")

        # Okay, if they changed the name of the ObData, that's THEIR problem...
        layout.prop_search(self, "region", bpy.data, "meshes", icon="MESH_DATA")
        layout.prop(self, "bounds")


class PlasmaVolumeSettingsSocket(PlasmaNodeSocketBase):
    bl_color = (43.1, 24.7, 0.0, 1.0)


class PlasmaVolumeSettingsSocketIn(PlasmaVolumeSettingsSocket, bpy.types.NodeSocket):
    allow = BoolProperty()

    def draw(self, context, layout, node, text):
        if not self.is_linked:
            layout.prop(self, "allow", text="")
        layout.label(text)


class PlasmaVolumeSettingsSocketOut(PlasmaVolumeSettingsSocket, bpy.types.NodeSocket):
    pass
