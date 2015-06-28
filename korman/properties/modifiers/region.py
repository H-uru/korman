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
from .physics import bounds_types

footstep_surface_ids = {
    "dirt": 0,
    # 1 = NULL
    "puddle": 2,
    # 3 = tile (NULL in MOUL)
    "metal": 4,
    "woodbridge": 5,
    "rope": 6,
    "grass": 7,
    # 8 = NULL
    "woodfloor": 9,
    "rug": 10,
    "stone": 11,
    # 12 = NULL
    # 13 = metal ladder (dupe of metal)
    "woodladder": 14,
    "water": 15,
    # 16 = maintainer's glass (NULL in PotS)
    # 17 = maintainer's metal grating (NULL in PotS)
    # 18 = swimming (why would you want this?)
}

footstep_surfaces = [("dirt", "Dirt", "Dirt"),
                     ("grass", "Grass", "Grass"),
                     ("metal", "Metal", "Metal Catwalk"),
                     ("puddle", "Puddle", "Shallow Water"),
                     ("rope", "Rope", "Rope Ladder"),
                     ("rug", "Rug", "Carpet Rug"),
                     ("stone", "Stone", "Stone Tile"),
                     ("water", "Water", "Deep Water"),
                     ("woodbridge", "Wood Bridge", "Wood Bridge"),
                     ("woodfloor", "Wood Floor", "Wood Floor"),
                     ("woodladder", "Wood Ladder", "Wood Ladder")]

class PlasmaFootstepRegion(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "footstep"

    bl_category = "Region"
    bl_label = "Footstep"
    bl_description = "Footstep Region"

    surface = EnumProperty(name="Surface",
                           description="What kind of surface are we walking on?",
                           items=footstep_surfaces,
                           default="stone")
    bounds = EnumProperty(name="Region Bounds",
                          description="Physical object's bounds",
                          items=bounds_types,
                          default="hull")


    def created(self, obj):
        self.display_name = "{}_FootRgn".format(obj.name)

    def export(self, exporter, bo, so):
        # Generate the logic nodes now
        self.logicwiz(bo)

        # Now, export the node tree
        self.node_tree.export(exporter, bo, so)

    def logicwiz(self, bo):
        tree = self.node_tree
        nodes = tree.nodes
        nodes.clear()

        # Region Sensor
        volsens = nodes.new("PlasmaVolumeSensorNode")
        volsens.name = "RegionSensor"
        volsens.region = bo.name
        volsens.bounds = self.bounds
        volsens.find_input_socket("enter").allow = True
        volsens.find_input_socket("exit").allow = True

        # Responder
        respmod = nodes.new("PlasmaResponderNode")
        respmod.name = "Resp"
        respmod.link_input(tree, volsens, "satisfies", "condition")
        respstate = nodes.new("PlasmaResponderStateNode")
        respstate.link_input(tree, respmod, "states", "condition")
        respstate.default_state = True
        respcmd = nodes.new("PlasmaResponderCommandNode")
        respcmd.link_input(tree, respstate, "cmds", "whodoneit")

        # ArmatureEffectStateMsg
        msg = nodes.new("PlasmaFootstepSoundMsgNode")
        msg.link_input(tree, respcmd, "msg", "sender")
        msg.surface = self.surface


class PlasmaPanicLinkRegion(PlasmaModifierProperties):
    pl_id = "paniclink"

    bl_category = "Region"
    bl_label = "Panic Link"
    bl_description = "Panic Link Region"

    play_anim = BoolProperty(name="Play Animation",
                             description="Play the link-out animation when panic linking",
                             default=True)
    exact_bounds = BoolProperty(name="Exact Bounds",
                                description="Use exact (triangle mesh) bounds -- only use if your mesh is not convex",
                                default=False)

    def created(self, obj):
        self.display_name = "{}_PanicLinkRgn".format(obj.name)

    def export(self, exporter, bo, so):
        # Generate the base physical object
        if self.exact_bounds:
            bounds = "trimesh"
        else:
            bounds = "hull"
        simIface, physical = exporter.physics.generate_physical(bo, so, bounds, self.display_name)

        # Now setup the region detector properties
        physical.memberGroup = plSimDefs.kGroupDetector
        physical.reportGroup = 1 << plSimDefs.kGroupAvatar

        # Finally, the panic link region proper
        reg = exporter.mgr.add_object(plPanicLinkRegion, name=self.display_name, so=so)
        reg.playLinkOutAnim = self.play_anim

    @property
    def requires_actor(self):
        return True
