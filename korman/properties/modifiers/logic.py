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

import bmesh
import bpy
from bpy.props import *
import mathutils
from PyHSPlasma import *

from ...addon_prefs import game_versions
from .base import PlasmaModifierProperties, PlasmaModifierLogicWiz
from ...exporter import ExportError, utils
from ... import idprops

class PlasmaVersionedNodeTree(idprops.IDPropMixin, bpy.types.PropertyGroup):
    version = EnumProperty(name="Version",
                           description="Plasma versions this node tree exports under",
                           items=game_versions,
                           options={"ENUM_FLAG"},
                           default=set(list(zip(*game_versions))[0]))
    node_tree = PointerProperty(name="Node Tree",
                                description="Node Tree to export",
                                type=bpy.types.NodeTree)

    @classmethod
    def _idprop_mapping(cls):
        return {"node_tree": "node_tree_name"}

    def _idprop_sources(self):
        return {"node_tree_name": bpy.data.node_groups}


class PlasmaAdvancedLogic(PlasmaModifierProperties):
    pl_id = "advanced_logic"

    bl_category = "Logic"
    bl_label = "Advanced"
    bl_description = "Plasma Logic Nodes"
    bl_icon = "NODETREE"

    logic_groups = CollectionProperty(type=PlasmaVersionedNodeTree)
    active_group_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        version = exporter.mgr.getVer()
        for i in self.logic_groups:
            our_versions = [globals()[j] for j in i.version]
            if version in our_versions:
                if i.node_tree is None:
                    raise ExportError("'{}': Advanced Logic is missing a node tree for '{}'".format(bo.name, i.name))

                # Defer node tree export until all trees are harvested.
                exporter.want_node_trees[i.node_tree.name].add((bo, so))

    def harvest_actors(self):
        actors = set()
        for i in self.logic_groups:
            if i.node_tree is not None:
                actors.update(i.node_tree.harvest_actors())
        return actors

    @property
    def requires_actor(self):
        return any((i.node_tree.requires_actor for i in self.logic_groups if i.node_tree))


class PlasmaSpawnPoint(PlasmaModifierProperties):
    pl_id = "spawnpoint"

    bl_category = "Logic"
    bl_label = "Spawn Point"
    bl_description = "Point at which avatars link into the Age"
    bl_object_types = {"EMPTY"}

    def export(self, exporter, bo, so):
        # Not much to this modifier... It's basically a flag that tells the engine, "hey, this is a
        # place the avatar can show up." Nice to have a simple one to get started with.
        spawn = exporter.mgr.add_object(pl=plSpawnModifier, so=so, name=self.key_name)

    @property
    def requires_actor(self):
        return True


class PlasmaMaintainersMarker(PlasmaModifierProperties):
    pl_id = "maintainersmarker"

    bl_category = "Logic"
    bl_label = "Maintainer's Marker"
    bl_description = "Designates an object as the D'ni coordinate origin point of the Age."
    bl_icon = "OUTLINER_DATA_EMPTY"

    calibration = EnumProperty(name="Calibration",
                               description="State of repair for the Marker",
                               items=[
                                  ("kBroken", "Broken",
                                   "A marker which reports scrambled coordinates to the KI."),
                                  ("kRepaired", "Repaired",
                                   "A marker which reports blank coordinates to the KI."),
                                  ("kCalibrated", "Calibrated",
                                   "A marker which reports accurate coordinates to the KI.")
                               ])

    def export(self, exporter, bo, so):
        maintmark = exporter.mgr.add_object(pl=plMaintainersMarkerModifier, so=so, name=self.key_name)
        maintmark.calibration = getattr(plMaintainersMarkerModifier, self.calibration)

    @property
    def requires_actor(self):
        return True


telescope_pfm = {
    "filename": "xTelescope.py",
    "attribs": (
        { 'id':  1, 'type': "ptAttribActivator", 'name': "Activate" },
        { 'id':  2, 'type': "ptAttribSceneobject", 'name': "Camera" },
        { 'id':  3, 'type': "ptAttribBehavior", 'name': "Behavior" },
        { 'id':  4, 'type': "ptAttribString", 'name': "Vignette" },
    )
}


class PlasmaTelescope(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id="telescope"

    bl_category = "Logic"
    bl_label = "Telescope"
    bl_description = "Set up clickable mesh as a telescope."
    bl_icon = "VISIBLE_IPO_ON"

    clickable_region = PointerProperty(name="Region",
                                    description="Region inside which the avatar must stand to be able to use the telescope (optional).",
                                    type=bpy.types.Object,
                                    poll=idprops.poll_mesh_objects)
    seek_target_object = PointerProperty(name="Seek Point",
                                         description="Empty object representing the position/orientation of the player when using the telescope.",
                                         type=bpy.types.Object,
                                         poll=idprops.poll_empty_objects)
    camera_object = PointerProperty(name="Camera",
                                    description="Camera used when viewing through telescope.",
                                    type=bpy.types.Object,
                                    poll=idprops.poll_camera_objects)

    def sanity_check(self, exporter):
        if self.camera_object is None:
            raise ExportError(f"'{self.id_data.name}': Telescopes must specify a camera!")

    def pre_export(self, exporter, bo):
        # Generate a six-foot cube region if none was provided.
        if self.clickable_region is None:
            self.clickable_region = yield utils.create_cube_region(
                f"{self.key_name}_Telescope_ClkRgn", 6.0,
                bo
            )

        # Generate the logic nodes
        yield self.convert_logic(bo)

    def logicwiz(self, bo, tree):
        nodes = tree.nodes

        # Create Python Node
        telescopepynode = self._create_python_file_node(tree, telescope_pfm["filename"], telescope_pfm["attribs"])

        # Clickable
        telescopeclick = nodes.new("PlasmaClickableNode")
        telescopeclick.value = bo
        for i in telescopeclick.inputs:
            i.allow_simple = False
        telescopeclick.link_output(telescopepynode, "satisfies", "Activate")

        # Region
        telescoperegion = nodes.new("PlasmaClickableRegionNode")
        telescoperegion.region_object = self.clickable_region
        telescoperegion.link_output(telescopeclick, "satisfies", "region")

        # Telescope Camera
        telescopecam = nodes.new("PlasmaAttribObjectNode")
        telescopecam.target_object = self.camera_object
        telescopecam.link_output(telescopepynode, "pfm", "Camera")

        # Now for the tricky MSB!
        telescopemsb = nodes.new("PlasmaMultiStageBehaviorNode")
        telescopemsb.link_output(telescopepynode, "hosts", "Behavior")

        # OneShot
        telescopeoneshot = nodes.new("PlasmaSeekTargetNode")
        telescopeoneshot.target = self.seek_target_object if self.seek_target_object else bo
        telescopeoneshot.link_output(telescopemsb, "seekers", "seek_target")

        # Anim Stage 1 (Grab)
        telescopestageone = nodes.new("PlasmaAnimStageNode")
        telescopestageone.anim_name = "GlobalScopeGrab"
        telescopestageone.loop_option = "kLoop"
        telescopestageone.num_loops = 0
        telescopestageone.link_output(telescopemsb, "stage", "stage_refs")
        # Settings
        telescopestageoneops = nodes.new("PlasmaAnimStageSettingsNode")
        telescopestageoneops.forward = "kPlayAuto"
        telescopestageoneops.stage_advance = "kAdvanceAuto"
        telescopestageoneops.notify_on = {"kNotifyAdvance"}
        telescopestageoneops.link_output(telescopestageone, "stage", "stage_settings")

        # Anim Stage 2 (Hold)
        telescopestagetwo = nodes.new("PlasmaAnimStageNode")
        telescopestagetwo.anim_name = "GlobalScopeHold"
        telescopestagetwo.loop_option = "kLoop"
        telescopestagetwo.num_loops = -1
        telescopestagetwo.link_output(telescopemsb, "stage", "stage_refs")
        # Settings
        telescopestagetwoops = nodes.new("PlasmaAnimStageSettingsNode")
        telescopestagetwoops.forward = "kPlayAuto"
        telescopestagetwoops.notify_on = set()
        telescopestagetwoops.link_output(telescopestagetwo, "stage", "stage_settings")

        # Anim Stage 3 (Release)
        telescopestagethree = nodes.new("PlasmaAnimStageNode")
        telescopestagethree.anim_name = "GlobalScopeRelease"
        telescopestagethree.loop_option = "kLoop"
        telescopestagethree.num_loops = 0
        telescopestagethree.link_output(telescopemsb, "stage", "stage_refs")
        # Settings
        telescopestagethreeops = nodes.new("PlasmaAnimStageSettingsNode")
        telescopestagethreeops.forward = "kPlayAuto"
        telescopestagethreeops.stage_advance = "kAdvanceAuto"
        telescopestagethreeops.notify_on = set()
        telescopestagethreeops.link_output(telescopestagethree, "stage", "stage_settings")

        telescopename = nodes.new("PlasmaAttribStringNode")
        telescopename.value = "telescope"
        telescopename.link_output(telescopepynode, "pfm", "Vignette")
