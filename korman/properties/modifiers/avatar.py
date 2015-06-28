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

from .base import PlasmaModifierProperties, PlasmaModifierLogicWiz
from ...exporter.explosions import ExportError
from ...helpers import find_modifier

sitting_approach_flags = [("kApproachFront", "Front", "Approach from the font"),
                          ("kApproachLeft", "Left", "Approach from the left"),
                          ("kApproachRight", "Right", "Approach from the right"),
                          ("kApproachRear", "Rear", "Approach from the rear guard")]

class PlasmaSittingBehavior(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "sittingmod"

    bl_category = "Avatar"
    bl_label = "Sitting Behavior"
    bl_description = "Avatar sitting position"

    approach = EnumProperty(name="Approach",
                            description="Directions an avatar can approach the seat from",
                            items=sitting_approach_flags,
                            default={"kApproachFront", "kApproachLeft", "kApproachRight"},
                            options={"ENUM_FLAG"})

    clickable_obj = StringProperty(name="Clickable",
                                   description="Object that defines the clickable area")
    region_obj = StringProperty(name="Region",
                                description="Object that defines the region mesh")

    facing_enabled = BoolProperty(name="Avatar Facing",
                                  description="The avatar must be facing the clickable's Y-axis",
                                  default=True)
    facing_degrees = IntProperty(name="Tolerance",
                                 description="How far away we will tolerate the avatar facing the clickable",
                                 min=-180, max=180, default=45)

    def created(self, obj):
        self.display_name = "{}_SitBeh".format(obj.name)

    def export(self, exporter, bo, so):
        # The user absolutely MUST specify a clickable or this won't export worth crap.
        clickable_obj = bpy.data.objects.get(self.clickable_obj, None)
        if clickable_obj is None:
            raise ExportError("'{}': Sitting Behavior's clickable object is invalid")

        # Generate the logic nodes now
        self.logicwiz(bo)

        # Now, export the node tree
        self.node_tree.export(exporter, bo, so)

    def logicwiz(self, bo):
        tree = self.node_tree
        nodes = tree.nodes
        nodes.clear()

        # Sitting Modifier
        sittingmod = nodes.new("PlasmaSittingBehaviorNode")
        sittingmod.approach = self.approach
        sittingmod.name = "SittingBeh"

        # Clickable
        clickable = nodes.new("PlasmaClickableNode")
        clickable.link_output(tree, sittingmod, "satisfies", "condition")
        clickable.clickable = self.clickable_obj
        clickable.bounds = find_modifier(self.clickable_obj, "collision").bounds

        # Avatar Region (optional)
        region_phys = find_modifier(self.region_obj, "collision")
        if region_phys is not None:
            region = nodes.new("PlasmaClickableRegionNode")
            region.link_output(tree, clickable, "satisfies", "region")
            region.name = "ClickableAvRegion"
            region.region = self.region_obj
            region.bounds = region_phys.bounds

        # Facing Target (optional)
        if self.facing_enabled:
            facing = nodes.new("PlasmaFacingTargetNode")
            facing.link_output(tree, clickable, "satisfies", "facing")
            facing.name = "FacingClickable"
            facing.directional = True
            facing.tolerance = self.facing_degrees
        else:
            # this socket must be explicitly disabled, otherwise it automatically generates a default
            # facing target conditional for us. isn't that nice?
            clickable.find_input_socket("facing").allow_simple = False
