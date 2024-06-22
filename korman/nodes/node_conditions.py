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
import math
from PyHSPlasma import *
from typing import *

from .. import enum_props
from .node_core import *
from .. import idprops

class PlasmaClickableNode(idprops.IDPropObjectMixin, PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaClickableNode"
    bl_label = "Clickable"
    bl_width_default = 160

    # These are the Python attributes we can fill in
    pl_attrib = {"ptAttribActivator", "ptAttribActivatorList", "ptAttribNamedActivator"}

    clickable_object = PointerProperty(name="Clickable",
                                       description="Mesh object that is clickable",
                                       type=bpy.types.Object,
                                       poll=idprops.poll_mesh_objects)

    bounds = enum_props.bounds(
        "clickable_object", store_on_collider=False,
        name="Bounds",
        description="Clickable's bounds (NOTE: only used if your clickable is not a collider)",
        default="hull"
    )

    input_sockets: dict[str, Any] = {
        "region": {
            "text": "Avatar Inside Region",
            "type": "PlasmaClickableRegionSocket",
        },
        "facing": {
            "text": "Avatar Facing Target",
            "type": "PlasmaFacingTargetSocket",
        },
        "message": {
            "text": "Message",
            "type": "PlasmaEnableMessageSocket",
            "spawn_empty": True,
        },
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "satisfies": {
            "text": "Satisfies",
            "type": "PlasmaConditionSocket",
            "valid_link_sockets": {"PlasmaConditionSocket", "PlasmaPythonFileNodeSocket"},
        },
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "clickable_object", icon="MESH_DATA")
        layout.prop(self, "bounds")

    def export(self, exporter, parent_bo, parent_so):
        clickable_bo, clickable_so = self._get_objects(exporter, parent_so)
        if clickable_bo is None:
            clickable_bo = parent_bo

        interface = self._find_create_object(plInterfaceInfoModifier, exporter, bl=clickable_bo, so=clickable_so)
        logicmod = self._find_create_key(plLogicModifier, exporter, bl=clickable_bo, so=clickable_so)
        interface.addIntfKey(logicmod)
        # Matches data seen in Cyan's PRPs...
        interface.addIntfKey(logicmod)
        logicmod = logicmod.object

        # If we receive an enable message, this is a one-shot type deal that needs to be disabled
        # while the attached responder is running.
        if self.find_input("message", "PlasmaEnableMsgNode") is not None:
            logicmod.setLogicFlag(plLogicModifier.kOneShot, True)

        # Try to figure out the appropriate bounds type for the clickable....
        phys_mod = clickable_bo.plasma_modifiers.collision
        bounds = phys_mod.bounds if phys_mod.enabled else self.bounds

        # The actual physical object that does the cursor LOS
        exporter.physics.generate_physical(clickable_bo, clickable_so, bounds=bounds,
                                           member_group="kGroupLOSOnly",
                                           properties=["kPinned"],
                                           losdbs=["kLOSDBUIItems"])

        # Picking Detector -- detect when the physical is clicked
        detector = self._find_create_object(plPickingDetector, exporter, bl=clickable_bo, so=clickable_so)
        detector.addReceiver(logicmod.key)

        # Clickable
        activator = self._find_create_object(plActivatorConditionalObject, exporter, bl=clickable_bo, so=clickable_so)
        activator.addActivator(detector.key)
        logicmod.addCondition(activator.key)
        logicmod.setLogicFlag(plLogicModifier.kLocalElement, True)
        logicmod.cursor = plCursorChangeMsg.kCursorPoised
        logicmod.notify = self.generate_notify_msg(exporter, parent_so, "satisfies")

        # If we have a region attached, let it convert.
        region = self.find_input("region", "PlasmaClickableRegionNode")
        if region is not None:
            region.convert_subcondition(exporter, clickable_bo, clickable_so, logicmod)

        # Hand things off to the FaceTarget socket which does things nicely for us
        face_target = self.find_input_socket("facing")
        face_target.convert_subcondition(exporter, clickable_bo, clickable_so, logicmod)

    @property
    def export_once(self):
        return self.clickable_object is not None

    def get_key(self, exporter, parent_so):
        # careful... we really make lots of keys...
        clickable_bo, clickable_so = self._get_objects(exporter, parent_so)
        key = self._find_create_key(plLogicModifier, exporter, bl=clickable_bo, so=clickable_so)
        return key

    def _get_objects(self, exporter, parent_so):
        # First: look up the clickable mesh. if it is not specified, then it's this BO.
        # We do this because we might be exporting from a BO that is not actually the clickable object.
        # Case: sitting modifier (exports from sit position empty)
        if self.clickable_object:
            clickable_so = exporter.mgr.find_create_object(plSceneObject, bl=self.clickable_object)
            return (self.clickable_object, clickable_so)
        else:
            return (None, parent_so)

    def harvest_actors(self):
        if self.clickable_object:
            yield self.clickable_object.name

    @property
    def requires_actor(self):
        return self.clickable_object is None

    @classmethod
    def _idprop_mapping(cls):
        return {"clickable_object": "clickable"}


class PlasmaClickableRegionNode(idprops.IDPropObjectMixin, PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaClickableRegionNode"
    bl_label = "Clickable Region Settings"
    bl_width_default = 200

    region_object = PointerProperty(name="Region",
                                    description="Object that defines the region mesh",
                                    type=bpy.types.Object,
                                    poll=idprops.poll_mesh_objects)
    bounds = enum_props.bounds(
        "region_object", store_on_collider=False,
        name="Bounds",
        description="Physical object's bounds (NOTE: only used if your clickable is not a collider)",
        default="hull"
    )

    output_sockets = {
        "satisfies": {
            "text": "Satisfies",
            "type": "PlasmaClickableRegionSocket",
        },
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "region_object", icon="MESH_DATA")
        layout.alert = self.bounds == "trimesh"
        layout.prop(self, "bounds")
        layout.alert = False

    def convert_subcondition(self, exporter, parent_bo, parent_so, logicmod):
        # REMEMBER: parent_so doesn't have to be the actual region scene object...
        region_bo = self.region_object
        if region_bo is None:
            self.raise_error("invalid Region")
        region_so = exporter.mgr.find_create_object(plSceneObject, bl=region_bo)

        # Try to figure out the appropriate bounds type for the region....
        phys_mod = region_bo.plasma_modifiers.collision
        bounds = phys_mod.bounds if phys_mod.enabled else self.bounds

        # Our physical is a detector and it only detects avatars...
        exporter.physics.generate_physical(region_bo, region_so, bounds=bounds,
                                           member_group="kGroupDetector",
                                           report_groups=["kGroupAvatar"])

        # I'm glad this crazy mess made sense to someone at Cyan...
        # ObjectInVolumeDetector can notify multiple logic mods. This implies we could share this
        # one detector for many unrelated logic mods. However, LogicMods and Conditions appear to
        # assume they pwn each other... so we need a unique detector. This detector must be attached
        # as a modifier to the region's SO however.
        detector = self._find_create_object(plObjectInVolumeDetector, exporter, bl=region_bo, so=region_so)
        detector.addReceiver(logicmod.key)
        detector.type = plObjectInVolumeDetector.kTypeAny

        # Now, the conditional object. At this point, these seem very silly. At least it's not a plModifier.
        # All they really do is hold a satisfied boolean...
        objinbox_key = self._find_create_key(plObjectInBoxConditionalObject, exporter, bl=region_bo, so=parent_so)
        objinbox_key.object.satisfied = True
        logicmod.addCondition(objinbox_key)

    @classmethod
    def _idprop_mapping(cls):
        return {"region_object": "region"}


class PlasmaClickableRegionSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.412, 0.0, 0.055, 1.0)


class PlasmaConditionSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.188, 0.086, 0.349, 1.0)


class PlasmaFacingTargetNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaFacingTargetNode"
    bl_label = "Facing Target"
    bl_width_default = 200

    def _get_directional(self) -> bool:
        output_node = self.find_output("satisfies")
        if output_node is not None and output_node.bl_idname == "PlasmaVolumeSensorNode":
            return True
        return self.directional

    def _set_directional(self, value: bool):
        self.directional = value

    # Volume Sensors use view ortientation testing, so if we're connected to a volume sensor node,
    # then we need to indicate that in the UI.
    directional = BoolProperty(default=False, options={"HIDDEN"})
    directional_ui = BoolProperty(name="Directional",
                                  description="Use the object's orientation for facing tests",
                                  get=_get_directional, set=_set_directional)

    def _get_moving_forward(self) -> bool:
        output_node = self.find_output("satisfies")
        if output_node is not None and output_node.bl_idname != "PlasmaVolumeSensorNode":
            return False
        return self.moving_forward

    def _set_moving_forward(self, value: bool):
        self.moving_forward = value

    # Only volume sensors allow the moving forward setting, so show this as disabled for connections
    # that are not volume sensors.
    moving_forward = BoolProperty(options={"HIDDEN"})
    moving_forward_ui = BoolProperty(name="Forward Motion",
                                     description="The player must be moving forward (eg walking) for the condition to trigger",
                                     get=_get_moving_forward, set=_set_moving_forward)

    def _get_tolerance(self) -> float:
        return math.radians(self.tolerance)

    def _set_tolerance(self, value: float) -> None:
        self.tolerance = math.degrees(value)

    # Legacy storage property... this exists as the storage for the tolerance value to prevent
    # breaking old blend files. NOTE: This property is stored in degrees.
    tolerance = FloatProperty(min=-180.0, max=180.0, default=45.0, options={"HIDDEN"})

    # New property for usage in the UI. NOTE: This property is stored in radians.
    tolerance_ui = FloatProperty(name="Tolerance",
                                 description="How far away from the target the avatar can turn",
                                 min=-180.0, max=180.0, precision=0,
                                 get=_get_tolerance, set=_set_tolerance,
                                 subtype="ANGLE", options=set())

    output_sockets: dict[str, dict[str, Any]] = {
        "satisfies": {
            "text": "Satisfies",
            "type": "PlasmaFacingTargetSocket",
            "link_limit": 1,
        },
    }

    def _draw_sub_prop(self, layout, prop_name, *, active=True, sidebar=False, **kwargs):
        sub = layout.row() if sidebar else layout.column()
        sub.enabled = active
        sub.prop(self, prop_name, **kwargs)

    def _draw(self, layout, *, sidebar):
        output_node = self.find_output("satisfies")
        is_regular_condition = output_node is None or output_node.bl_idname != "PlasmaVolumeSensorNode"
        is_volume_sensor = output_node is None or output_node.bl_idname == "PlasmaVolumeSensorNode"

        sub = layout if sidebar else layout.split()
        self._draw_sub_prop(sub, "directional_ui", active=is_regular_condition)
        self._draw_sub_prop(sub, "moving_forward_ui", active=is_volume_sensor, text="Moving")
        layout.prop(self, "tolerance_ui")

    def draw_buttons(self, context, layout):
        self._draw(layout, sidebar=False)

    def draw_buttons_ext(self, context, layout):
        self._draw(layout, sidebar=True)


class PlasmaFacingTargetSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.0, 0.267, 0.247, 1.0)

    allow_simple = BoolProperty(name="Facing Target",
                           description="Avatar must be facing the target object",
                           default=True)

    def draw_content(self, context, layout, node, text):
        if self.simple_mode:
            layout.prop(self, "allow_simple", text="")
        layout.label(text)

    def convert_subcondition(self, exporter, bo, so, logicmod: Union[plLogicModifier, plObjectInVolumeAndFacingDetector]):
        assert not self.is_output
        if not self.enable_condition:
            return

        # First, gather the schtuff from the appropriate blah blah blah
        if self.simple_mode:
            node = self.node
            directional = False
            moving_forward = False
            tolerance = math.cos(math.radians(45.0))
        elif self.is_linked:
            node = self.links[0].from_node
            directional = node.directional
            moving_forward = node.moving_forward
            tolerance = math.cos(math.radians(node.tolerance))
        else:
            # This is a programmer failure, so we need a traceback.
            raise RuntimeError("Tried to export an unused PlasmaFacingTargetSocket")

        if isinstance(logicmod, plLogicModifier):
            facing_key = node._find_create_key(plFacingConditionalObject, exporter, bl=bo, so=so)
            facing = facing_key.object
            facing.directional = directional
            facing.satisfied = True
            facing.tolerance = tolerance
            logicmod.addCondition(facing_key)
        elif isinstance(logicmod, plObjectInVolumeAndFacingDetector):
            logicmod.facingTolerance = tolerance
            logicmod.needWalkingForward = moving_forward
        else:
            raise ValueError("logicmod")

    @property
    def enable_condition(self):
        return self.enabled and ((self.simple_mode and self.allow_simple) or self.is_linked)

    @property
    def simple_mode(self):
        """Simple mode allows a user to click a button on input sockets to automatically generate a
           Facing Target condition"""
        return (not self.is_linked and not self.is_output)


class PlasmaVolumeReportNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaVolumeReportNode"
    bl_label = "Region Trigger Settings"

    report_when = EnumProperty(name="When",
                               description="When the region should trigger",
                               items=[("each", "Each Event", "The region will trigger on every enter/exit"),
                                      ("first", "First Event", "The region will trigger on the first event only"),
                                      ("count", "Population", "When the region has a certain number of objects inside it")])
    threshold = IntProperty(name="Threshold",
                    description="How many objects should be in the region for it to trigger",
                    min=0)

    output_sockets: dict[str, dict[str, Any]] = {
        "settings": {
            "text": "Trigger Settings",
            "type": "PlasmaVolumeSettingsSocketOut",
            "valid_link_sockets": {"PlasmaVolumeSettingsSocketIn"},
        },
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "report_when")
        if self.report_when == "count":
            row = layout.row()
            row.label("Threshold: ")
            row.prop(self, "threshold", text="")


class PlasmaVolumeSensorNode(idprops.IDPropObjectMixin, PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaVolumeSensorNode"
    bl_label = "Region Sensor"
    bl_width_default = 190

    def _update_report_on(self, context):
        # Facing target properties only make sense if we trigger on avatars being present
        # in the region. Furthermore, the engine explicitly disallows other physicals triggering
        # the region sensor if the facing condition is enabled. So, remove the facing option if
        # avatars are not selected or if dynamics are selected. NOTE: The socket is hidden
        # when it is disabled.
        include_avatars = "kGroupAvatar" in self.report_on
        include_physicals = "kGroupDynamic" in self.report_on
        self.find_input_socket("facing").enabled = include_avatars and not include_physicals

    # These are the Python attributes we can fill in
    pl_attrib = {"ptAttribActivator", "ptAttribActivatorList", "ptAttribNamedActivator"}

    # Region Mesh
    region_object = PointerProperty(name="Region",
                                    description="Object that defines the region mesh",
                                    type=bpy.types.Object,
                                    poll=idprops.poll_mesh_objects)
    bounds = enum_props.bounds(
        "region_object", store_on_collider=False,
        name="Bounds",
        description="Physical object's bounds"
    )

    # Detector Properties
    report_on = EnumProperty(name="Triggerers",
                             description="What triggers this region?",
                             options={"ANIMATABLE", "ENUM_FLAG"},
                             items=[("kGroupAvatar", "Avatars", "Avatars trigger this region"),
                                    ("kGroupDynamic", "Dynamics", "Any non-avatar dynamic physical object (eg kickables)")],
                             default={"kGroupAvatar"},
                             update=_update_report_on)

    input_sockets: dict[str, dict[str, Any]] = {
        "facing": {
            "text": "Avatar Facing Target",
            "type": "PlasmaFacingTargetSocket",
        },
        "enter": {
            "text": "Trigger on Enter",
            "type": "PlasmaVolumeSettingsSocketIn",
            "valid_link_sockets": {"PlasmaVolumeSettingsSocketOut"},
        },
        "exit": {
            "text": "Trigger on Exit",
            "type": "PlasmaVolumeSettingsSocketIn",
            "valid_link_sockets": {"PlasmaVolumeSettingsSocketOut"},
        },
        "message": {
            "text": "Message",
            "type": "PlasmaEnableMessageSocket",
            "spawn_empty": True,
        },
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "satisfies": {
            "text": "Satisfies",
            "type": "PlasmaConditionSocket",
            "valid_link_sockets": {"PlasmaConditionSocket", "PlasmaPythonFileNodeSocket"},
        },
    }

    def init(self, context):
        # The default value for the facing socket is a bit silly for this node type.
        # Reset it to False.
        self.find_input_socket("facing").allow_simple = False

    def draw_buttons(self, context, layout):
        layout.prop(self, "report_on")

        # Okay, if they changed the name of the ObData, that's THEIR problem...
        layout.prop(self, "region_object", icon="MESH_DATA")
        layout.alert = self.bounds == "trimesh"
        layout.prop(self, "bounds")
        layout.alert = False

    def get_key(self, exporter, parent_so):
        bo = self.region_object
        if bo is None:
            self.raise_error("Region cannot be empty")
        so = exporter.mgr.find_create_object(plSceneObject, bl=bo)
        rgn_enter, rgn_exit = None, None
        parent_key = parent_so.key

        if self.report_enters:
            rgn_enter = self._find_create_key(plLogicModifier, exporter, suffix="Enter", bl=bo, so=so)
        if self.report_exits:
            rgn_exit = self._find_create_key(plLogicModifier, exporter, suffix="Exit", bl=bo, so=so)

        if rgn_enter is None:
            return rgn_exit
        elif rgn_exit is None:
            return rgn_enter
        else:
            # !!! ... !!!
            # Sorry
            #     -- Hoikas
            # !!! ... !!!
            return (rgn_enter, rgn_exit)

    def export(self, exporter, bo, parent_so):
        region_bo = self.region_object
        if region_bo is None:
            self.raise_error("Region cannot be empty")

        region_so = exporter.mgr.find_create_object(plSceneObject, bl=region_bo)
        interface = self._find_create_object(plInterfaceInfoModifier, exporter, bl=region_bo, so=region_so)

        # Region Enters
        enter_simple = self.find_input_socket("enter").allow
        enter_settings = self.find_input("enter", "PlasmaVolumeReportNode")
        if enter_simple or enter_settings is not None:
            key = self._export_volume_event(exporter, region_bo, region_so, parent_so, plVolumeSensorConditionalObject.kTypeEnter, enter_settings)
            interface.addIntfKey(key)

        # Region Exits
        exit_simple = self.find_input_socket("exit").allow
        exit_settings = self.find_input("exit", "PlasmaVolumeReportNode")
        if exit_simple or exit_settings is not None:
            key = self._export_volume_event(exporter, region_bo, region_so, parent_so, plVolumeSensorConditionalObject.kTypeExit, exit_settings)
            interface.addIntfKey(key)

        # Don't forget to export the physical object itself!
        exporter.physics.generate_physical(region_bo, region_so, bounds=self.bounds,
                                           member_group="kGroupDetector",
                                           report_groups=self.report_on)

    def _export_volume_event(self, exporter, region_bo, region_so, parent_so, event, settings):
        if event == plVolumeSensorConditionalObject.kTypeEnter:
            suffix = "Enter"
        else:
            suffix = "Exit"

        logicKey = self._find_create_key(plLogicModifier, exporter, suffix=suffix, bl=region_bo, so=region_so)
        logicmod = logicKey.object
        logicmod.setLogicFlag(plLogicModifier.kMultiTrigger, True)
        logicmod.notify = self.generate_notify_msg(exporter, parent_so, "satisfies")

        # Now, the detector objects
        facing_socket: PlasmaFacingTargetSocket = self.find_input_socket("facing")
        if facing_socket.enable_condition:
            det = self._find_create_object(plObjectInVolumeAndFacingDetector, exporter, suffix=suffix, bl=region_bo, so=region_so)
            facing_socket.convert_subcondition(exporter, region_bo, region_so, det)
        else:
            det = self._find_create_object(plObjectInVolumeDetector, exporter, suffix=suffix, bl=region_bo, so=region_so)

        volKey = self._find_create_key(plVolumeSensorConditionalObject, exporter, suffix=suffix, bl=region_bo, so=region_so)
        volsens = volKey.object

        volsens.type = event
        if settings is not None:
            if settings.report_when == "first":
                volsens.first = True
            elif settings.report_when == "count":
                volsens.trigNum = settings.threshold

        # There appears to be a mandatory order for these keys...
        det.addReceiver(volKey)
        det.addReceiver(logicKey)

        # End mandatory order
        logicmod.addCondition(volKey)
        return logicKey

    @property
    def export_once(self):
        return True

    def harvest_actors(self):
        if self.region_object and self.find_input_socket("facing").enable_condition:
            yield self.region_object.name

    @classmethod
    def _idprop_mapping(cls):
        return {"region_object": "region"}

    @property
    def report_enters(self):
        return (self.find_input_socket("enter").allow or
                self.find_input("enter", "PlasmaVolumeReportNode") is not None)

    @property
    def report_exits(self):
        return (self.find_input_socket("exit").allow or
                self.find_input("exit", "PlasmaVolumeReportNode") is not None)


class PlasmaVolumeSettingsSocket(PlasmaNodeSocketBase):
    bl_color = (43.1, 24.7, 0.0, 1.0)


class PlasmaVolumeSettingsSocketIn(PlasmaVolumeSettingsSocket, bpy.types.NodeSocket):
    allow = BoolProperty()

    def draw_content(self, context, layout, node, text):
        if not self.is_linked:
            layout.prop(self, "allow", text="")
        layout.label(text)


class PlasmaVolumeSettingsSocketOut(PlasmaVolumeSettingsSocket, bpy.types.NodeSocket):
    pass
