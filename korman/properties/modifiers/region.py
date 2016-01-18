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

from ...exporter import ExportError
from ...helpers import TemporaryObject

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
        respmod.link_input(volsens, "satisfies", "condition")
        respstate = nodes.new("PlasmaResponderStateNode")
        respstate.link_input(respmod, "states", "condition")
        respstate.default_state = True
        respcmd = nodes.new("PlasmaResponderCommandNode")
        respcmd.link_input(respstate, "cmds", "whodoneit")

        # ArmatureEffectStateMsg
        msg = nodes.new("PlasmaFootstepSoundMsgNode")
        msg.link_input(respcmd, "msg", "sender")
        msg.surface = self.surface

    @property
    def key_name(self):
        return "{}_FootRgn".format(self.id_data.name)


class PlasmaPanicLinkRegion(PlasmaModifierProperties):
    pl_id = "paniclink"

    bl_category = "Region"
    bl_label = "Panic Link"
    bl_description = "Panic Link Region"

    play_anim = BoolProperty(name="Play Animation",
                             description="Play the link-out animation when panic linking",
                             default=True)

    def export(self, exporter, bo, so):
        phys_mod = bo.plasma_modifiers.collision
        simIface, physical = exporter.physics.generate_physical(bo, so, phys_mod.bounds, self.key_name)

        # Now setup the region detector properties
        physical.memberGroup = plSimDefs.kGroupDetector
        physical.reportGroup = 1 << plSimDefs.kGroupAvatar

        # Finally, the panic link region proper
        reg = exporter.mgr.add_object(plPanicLinkRegion, name=self.key_name, so=so)
        reg.playLinkOutAnim = self.play_anim

    @property
    def key_name(self):
        return "{}_PanicLinkRgn".format(self.id_data.name)

    @property
    def requires_actor(self):
        return True


class PlasmaSoftVolume(PlasmaModifierProperties):
    pl_id = "softvolume"

    bl_category = "Region"
    bl_label = "Soft Volume"
    bl_description = "Soft-Boundary Region"

    # Advanced
    use_nodes = BoolProperty(name="Use Nodes",
                             description="Make this a node-based Soft Volume",
                             default=False)
    node_tree_name = StringProperty(name="Node Tree",
                                    description="Node Tree detailing soft volume logic")

    # Basic
    invert = BoolProperty(name="Invert",
                          description="Invert the soft region")
    inside_strength = IntProperty(name="Inside", description="Strength inside the region",
                                  subtype="PERCENTAGE", default=100, min=0, max=100)
    outside_strength = IntProperty(name="Outside", description="Strength outside the region",
                                   subtype="PERCENTAGE", default=0, min=0, max=100)
    soft_distance = FloatProperty(name="Distance", description="Soft Distance",
                                  default=0.0, min=0.0, max=500.0)

    def _apply_settings(self, sv):
        sv.insideStrength = self.inside_strength / 100.0
        sv.outsideStrength = self.outside_strength / 100.0

    def get_key(self, exporter, so=None):
        """Fetches the key appropriate for this Soft Volume"""
        if so is None:
            so = exporter.mgr.find_create_object(plSceneObject, bl=self.id_data)

        if self.use_nodes:
            output = self.node_tree.find_output("PlasmaSoftVolumeOutputNode")
            if output is None:
                raise ExportError("SoftVolume '{}' Node Tree '{}' has no output node!".format(self.key_name, self.node_tree))
            return output.get_key(exporter, so)
        else:
            pClass = plSoftVolumeInvert if self.invert else plSoftVolumeSimple
            return exporter.mgr.find_create_key(pClass, bl=self.id_data, so=so)

    def export(self, exporter, bo, so):
        if self.use_nodes:
            self._export_sv_nodes(exporter, bo, so)
        else:
            self._export_convex_region(exporter, bo, so)

    def _export_convex_region(self, exporter, bo, so):
        if bo.type != "MESH":
            raise ExportError("SoftVolume '{}': Simple SoftVolumes can only be meshes!".format(bo.name))

        # Grab the SoftVolume KO
        sv = self.get_key(exporter, so).object
        self._apply_settings(sv)

        # If "invert" was checked, we got a SoftVolumeInvert, but we need to make a Simple for the
        # region data to be exported into..
        if isinstance(sv, plSoftVolumeInvert):
            svSimple = exporter.mgr.find_create_object(plSoftVolumeSimple, bl=bo, so=so)
            self._apply_settings(svSimple)
            sv.addSubVolume(svSimple.key)
            sv = svSimple
        sv.softDist = self.soft_distance

        # Initialize the plVolumeIsect. Currently, we only support convex isects. If you want parallel
        # isects from empties, be my guest...
        with TemporaryObject(bo.to_mesh(bpy.context.scene, True, "RENDER", calc_tessface=False), bpy.data.meshes.remove) as mesh:
            mesh.transform(bo.matrix_world)

            isect = plConvexIsect()
            for i in mesh.vertices:
                isect.addPlane(hsVector3(*i.normal), hsVector3(*i.co))
            sv.volume = isect

    def _export_sv_nodes(self, exporter, bo, so):
        if self.node_tree_name not in exporter.node_trees_exported:
            exporter.node_trees_exported.add(self.node_tree_name)
            self.node_tree.export(exporter, bo, so)

    @property
    def node_tree(self):
        tree = bpy.data.node_groups.get(self.node_tree_name, None)
        if tree is None:
            raise ExportError("SoftVolume '{}': Node Tree '{}' does not exist!".format(self.key_name, self.node_tree_name))
        return tree
