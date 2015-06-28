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

from .node_core import PlasmaNodeBase, PlasmaNodeSocketBase

class PlasmaSittingBehaviorNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "AVATAR"
    bl_idname = "PlasmaSittingBehaviorNode"
    bl_label = "Sitting Behavior"
    bl_default_width = 100

    approach = EnumProperty(name="Approach",
                            description="Directions an avatar can approach the seat from",
                            items=[("kApproachFront", "Front", "Approach from the font"),
                                   ("kApproachLeft", "Left", "Approach from the left"),
                                   ("kApproachRight", "Right", "Approach from the right"),
                                   ("kApproachRear", "Rear", "Approach from the rear guard")],
                            default={"kApproachFront", "kApproachLeft", "kApproachRight"},
                            options={"ENUM_FLAG"})

    def init(self, context):
        self.inputs.new("PlasmaConditionSocket", "Condition", "condition")
        # This makes me determined to create and release a whoopee cushion age...
        self.outputs.new("PlasmaConditionSocket", "Satisfies", "satisfies")

    def draw_buttons(self, context, layout):
        col = layout.column()
        col.label("Approach:")
        col.prop(self, "approach")

    def draw_buttons_ext(self, context, layout):
        layout.prop_menu_enum(self, "approach")

    def get_key(self, exporter, tree, so):
        return exporter.mgr.find_create_key(plSittingModifier, name=self.create_key_name(tree), so=so)

    def export(self, exporter, tree, bo, so):
        sitmod = self.get_key(exporter, tree, so).object
        for flag in self.approach:
            sitmod.miscFlags |= getattr(plSittingModifier, flag)
        for key in self.find_outputs("satisfies"):
            if key is not None:
                sitmod.addNotifyKey(key)
            else:
                exporter.report.warn(" '{}' Node '{}' doesn't expose a key. It won't be triggered by '{}'!".format(i.bl_idname, i.name, self.name), indent=3)
