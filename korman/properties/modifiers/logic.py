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
from PyHSPlasma import *
from typing import *

if TYPE_CHECKING:
    from ...exporter import Exporter
    from ...nodes.node_conditions import *
    from ...nodes.node_messages import *
    from ...nodes.node_responder import *

from typing import *

if TYPE_CHECKING:
    from ...exporter import Exporter

from ...addon_prefs import game_versions
from .base import PlasmaModifierProperties, PlasmaModifierLogicWiz
from ... import enum_props
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
    pl_page_types = {"gui", "room"}

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


class PlasmaSpawnPoint(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "spawnpoint"

    bl_category = "Logic"
    bl_label = "Spawn Point"
    bl_description = "Point at which avatars link into the Age"
    bl_object_types = {"EMPTY"}

    entry_camera = PointerProperty(
        name="Entry Camera",
        description="Camera to use when the player spawns at this location",
        type=bpy.types.Object,
        poll=idprops.poll_camera_objects
    )

    exit_region = PointerProperty(
        name="Exit Region",
        description="Pop the camera when the player exits this region",
        type=bpy.types.Object,
        poll=idprops.poll_mesh_objects
    )

    bounds_type = enum_props.bounds(
        "exit_region",
        name="Bounds",
        description="",
        default="hull"
    )

    def pre_export(self, exporter: Exporter, bo: bpy.types.Object) -> None:
        if self.entry_camera is None:
            return

        if self.exit_region is None:
            self.exit_region = yield utils.create_box_region(
                f"{self.key_name}_ExitRgn", (2.0, 2.0, 6.0),
                bo, utils.RegionOrigin.bottom
            )

        yield self.convert_logic(bo)

    def logicwiz(self, bo, tree):
        pfm_node = self._create_standard_python_file_node(tree, "xEntryCam.py")

        volume_sensor: PlasmaVolumeSensorNode = tree.nodes.new("PlasmaVolumeSensorNode")
        volume_sensor.find_input_socket("enter").allow = True
        volume_sensor.find_input_socket("exit").allow = True
        volume_sensor.region_object = self.exit_region
        volume_sensor.bounds = self.bounds_type
        volume_sensor.link_output(pfm_node, "satisfies", "actRegionSensor")

        self._create_python_attribute(
            pfm_node,
            "camera",
            target_object=self.entry_camera
        )


    def export(self, exporter, bo, so):
        exporter.mgr.add_object(pl=plSpawnModifier, so=so, name=self.key_name)

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


class PlasmaSDLIntState(bpy.types.PropertyGroup):
    value: int = IntProperty(
        name="State Value",
        description="The object is shown when the SDL variable is set to this value",
        min=0,
        soft_max=255,
        options=set()
    )


class PlasmaSDLShowHide(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "sdl_showhide"
    pl_page_types = {"gui", "room"}

    bl_category = "Logic"
    bl_label = "SDL Show/Hide"
    bl_description = "Show/Hide an object based on an SDL Variable"
    bl_object_types = {"MESH", "FONT"}
    bl_icon = "VISIBLE_IPO_OFF"

    sdl_variable: str = StringProperty(
        name="SDL Variable",
        description="Name of the SDL variable that controls visibility",
        options=set()
    )
    variable_type: str = EnumProperty(
        name="Type",
        description="Data type of the SDL variable",
        items=[
            ("bool", "Boolean", "A boolean, used to represent simple on/off for a single state"),
            ("int", "Integer", "An integer, used to represent multiple state combinations"),
        ],
        options=set()
    )

    int_states = CollectionProperty(type=PlasmaSDLIntState)
    bool_state: bool = BoolProperty(
        name="Show When True",
        description="If checked, show this object when the SDL Variable is TRUE. If not, hide it when TRUE.",
        default=True,
        options=set()
    )

    def created(self):
        # Ensure at least one SDL int state is precreated for ease of use.
        # REMEMBER: Blender's "sequences" don't do truthiness correctly...
        if len(self.int_states) == 0:
            self.int_states.add()

    def sanity_check(self, exporter: Exporter):
        if not exporter.age_sdl:
            raise ExportError(f"'{self.id_data.name}': Age Global SDL is required for the SDL Show/Hide modifier!")
        if not self.sdl_variable.strip():
            raise ExportError(f"'{self.id_data.name}': A valid SDL variable is required for the SDL Show/Hide modifier!")

    def logicwiz(self, bo, tree):
        if self.variable_type == "bool":
            pfm_node = self._create_standard_python_file_node(tree, "xAgeSDLBoolShowHide.py")
            self._create_python_attribute(pfm_node, "sdlName", value=self.sdl_variable)
            self._create_python_attribute(pfm_node, "showOnTrue", value=self.bool_state)
        elif self.variable_type == "int":
            pfm_node = self._create_standard_python_file_node(tree, "xAgeSDLIntShowHide.py")
            self._create_python_attribute(pfm_node, "stringVarName", value=self.sdl_variable)
            self._create_python_attribute(pfm_node, "stringShowStates", value=",".join(self._states))
        else:
            raise RuntimeError()

    @property
    def key_name(self):
        if self.variable_type == "bool":
            return f"cPythBoolShowHide_{self.sdl_variable}_{self.bool_state:d}"
        elif self.variable_type == "int":
            return f"cPythIntShowHide_{self.sdl_variable}_{'-'.join(self._states)}"

    @property
    def _states(self) -> Iterable[str]:
        """Returns a sorted, deduplicated iterable of the integer (converted to strings) states we should be visible in."""
        return (str(i) for i in sorted(frozenset((i.value for i in self.int_states))))


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
        telescopepynode = self._create_standard_python_file_node(tree, "xTelescope.py")

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
