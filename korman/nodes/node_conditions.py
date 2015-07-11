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
import math
from PyHSPlasma import *

from .node_core import PlasmaNodeBase, PlasmaNodeSocketBase
from ..properties.modifiers.physics import bounds_types

class PlasmaClickableNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaClickableNode"
    bl_label = "Clickable"
    bl_width_default = 160

    clickable = StringProperty(name="Clickable",
                               description="Mesh that is clickable")
    bounds = EnumProperty(name="Bounds",
                          description="Clickable's bounds (NOTE: only used if your clickable is not a collider)",
                          items=bounds_types,
                          default="hull")

    def init(self, context):
        self.inputs.new("PlasmaClickableRegionSocket", "Avatar Inside Region", "region")
        self.inputs.new("PlasmaFacingTargetSocket", "Avatar Facing Target", "facing")
        self.outputs.new("PlasmaConditionSocket", "Satisfies", "satisfies")

    def draw_buttons(self, context, layout):
        layout.prop_search(self, "clickable", bpy.data, "objects", icon="MESH_DATA")
        layout.prop(self, "bounds")

    def export(self, exporter, tree, parent_bo, parent_so):
        # First: look up the clickable mesh. if it is not specified, then it's this BO.
        # We do this because we might be exporting from a BO that is not actually the clickable object.
        # Case: sitting modifier (exports from sit position empty)
        if self.clickable:
            clickable_bo = bpy.data.objects.get(self.clickable, None)
            if clickable_bo is None:
                self.raise_error("invalid Clickable object: '{}'".format(self.clickable), tree)
            clickable_so = exporter.mgr.find_create_object(plSceneObject, bl=clickable_bo)
        else:
            clickable_bo = parent_bo
            clickable_so = parent_so

        name = self.create_key_name(tree)
        interface = exporter.mgr.find_create_key(plInterfaceInfoModifier, name=name, so=clickable_so).object
        logicmod = exporter.mgr.find_create_key(plLogicModifier, name=name, so=clickable_so)
        interface.addIntfKey(logicmod)
        # Matches data seen in Cyan's PRPs...
        interface.addIntfKey(logicmod)
        logicmod = logicmod.object

        # Try to figure out the appropriate bounds type for the clickable....
        phys_mod = clickable_bo.plasma_modifiers.collision
        bounds = phys_mod.bounds if phys_mod.enabled else self.bounds

        # The actual physical object that does the cursor LOS
        made_the_phys = (clickable_so.sim is None)
        phys_name = "{}_ClickableLOS".format(clickable_bo.name)
        simIface, physical = exporter.physics.generate_physical(clickable_bo, clickable_so, bounds, phys_name)
        simIface.setProperty(plSimulationInterface.kPinned, True)
        physical.setProperty(plSimulationInterface.kPinned, True)
        if made_the_phys:
            # we assume that the collision modifier will do this if they want it to be intangible
            physical.memberGroup = plSimDefs.kGroupLOSOnly
        if physical.mass == 0.0:
            physical.mass = 1.0
        physical.LOSDBs |= plSimDefs.kLOSDBUIItems

        # Picking Detector -- detect when the physical is clicked
        detector = exporter.mgr.find_create_key(plPickingDetector, name=name, so=clickable_so).object
        detector.addReceiver(logicmod.key)

        # Clickable
        activator = exporter.mgr.find_create_key(plActivatorConditionalObject, name=name, so=clickable_so).object
        activator.addActivator(detector.key)
        logicmod.addCondition(activator.key)
        logicmod.setLogicFlag(plLogicModifier.kLocalElement, True)
        logicmod.cursor = plCursorChangeMsg.kCursorPoised
        logicmod.notify = self.generate_notify_msg(exporter, tree, parent_so, "satisfies")

        # If we have a region attached, let it convert.
        region = self.find_input("region", "PlasmaClickableRegionNode")
        if region is not None:
            region.convert_subcondition(exporter, tree, clickable_bo, clickable_so, logicmod)

        # Hand things off to the FaceTarget socket which does things nicely for us
        face_target = self.find_input_socket("facing")
        face_target.convert_subcondition(exporter, tree, clickable_bo, clickable_so, logicmod)

    def harvest_actors(self):
        return (self.clickable,)


class PlasmaClickableRegionNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaClickableRegionNode"
    bl_label = "Clickable Region Settings"
    bl_width_default = 200

    region = StringProperty(name="Region",
                            description="Object that defines the region mesh")
    bounds = EnumProperty(name="Bounds",
                          description="Physical object's bounds (NOTE: only used if your clickable is not a collider)",
                          items=bounds_types,
                          default="hull")

    def init(self, context):
        self.outputs.new("PlasmaClickableRegionSocket", "Satisfies", "satisfies")

    def draw_buttons(self, context, layout):
        layout.prop_search(self, "region", bpy.data, "objects", icon="MESH_DATA")
        layout.prop(self, "bounds")

    def convert_subcondition(self, exporter, tree, parent_bo, parent_so, logicmod):
        # REMEMBER: parent_so doesn't have to be the actual region scene object...
        region_bo = bpy.data.objects.get(self.region, None)
        if region_bo is None:
            self.raise_error("invalid Region object: '{}'".format(self.region), tree)
        region_so = exporter.mgr.find_create_key(plSceneObject, bl=region_bo).object

        # Try to figure out the appropriate bounds type for the region....
        phys_mod = region_bo.plasma_modifiers.collision
        bounds = phys_mod.bounds if phys_mod.enabled else self.bounds

        # Our physical is a detector and it only detects avatars...
        phys_name = "{}_ClickableAvRegion".format(region_bo.name)
        simIface, physical = exporter.physics.generate_physical(region_bo, region_so, bounds, phys_name)
        physical.memberGroup = plSimDefs.kGroupDetector
        physical.reportGroup |= 1 << plSimDefs.kGroupAvatar

        # I'm glad this crazy mess made sense to someone at Cyan...
        # ObjectInVolumeDetector can notify multiple logic mods. This implies we could share this
        # one detector for many unrelated logic mods. However, LogicMods and Conditions appear to
        # assume they pwn each other... so we need a unique detector. This detector must be attached
        # as a modifier to the region's SO however.
        name = self.create_key_name(tree)
        detector_key = exporter.mgr.find_create_key(plObjectInVolumeDetector, name=name, so=region_so)
        detector = detector_key.object
        detector.addReceiver(logicmod.key)
        detector.type = plObjectInVolumeDetector.kTypeAny

        # Now, the conditional object. At this point, these seem very silly. At least it's not a plModifier.
        # All they really do is hold a satisfied boolean...
        objinbox_key = exporter.mgr.find_create_key(plObjectInBoxConditionalObject, name=name, so=parent_so)
        objinbox_key.object.satisfied = True
        logicmod.addCondition(objinbox_key)


class PlasmaClickableRegionSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.412, 0.0, 0.055, 1.0)


class PlasmaConditionSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.188, 0.086, 0.349, 1.0)


class PlasmaFacingTargetNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaFacingTargetNode"
    bl_label = "Facing Target"

    directional = BoolProperty(name="Directional",
                               description="TODO",
                               default=True)
    tolerance = IntProperty(name="Degrees",
                            description="How far away from the target the avatar can turn (in degrees)",
                            min=-180, max=180, default=45)

    def init(self, context):
        self.outputs.new("PlasmaFacingTargetSocket", "Satisfies", "satisfies")

    def draw_buttons(self, context, layout):
        layout.prop(self, "directional")
        layout.prop(self, "tolerance")


class PlasmaFacingTargetSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.0, 0.267, 0.247, 1.0)

    allow_simple = BoolProperty(name="Facing Target",
                           description="Avatar must be facing the target object",
                           default=True)

    def draw(self, context, layout, node, text):
        if self.simple_mode:
            layout.prop(self, "allow_simple", text="")
        layout.label(text)

    def convert_subcondition(self, exporter, tree, bo, so, logicmod):
        assert not self.is_output
        if not self.enable_condition:
            return

        # First, gather the schtuff from the appropriate blah blah blah
        if self.simple_mode:
            directional = True
            tolerance = 45
            name = "{}_SimpleFacing".format(self.node.create_key_name(tree))
        elif self.is_linked:
            node = self.links[0].from_node
            directional = node.directional
            tolerance = node.tolerance
            name = node.create_key_name(tree)
        else:
            # This is a programmer failure, so we need a traceback.
            raise RuntimeError("Tried to export an unused PlasmaFacingTargetSocket")

        facing_key = exporter.mgr.find_create_key(plFacingConditionalObject, name=name, so=so)
        facing = facing_key.object
        facing.directional = directional
        facing.satisfied = True
        facing.tolerance = math.radians(tolerance)
        logicmod.addCondition(facing_key)

    @property
    def enable_condition(self):
        return ((self.simple_mode and self.allow_simple) or self.is_linked)

    @property
    def simple_mode(self):
        """Simple mode allows a user to click a button on input sockets to automatically generate a
           Facing Target condition"""
        return (not self.is_linked and not self.is_output)


class PlasmaVolumeReportNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "CONDITIONS"
    bl_idname = "PlasmaVoumeReportNode"
    bl_label = "Region Trigger Settings"

    report_when = EnumProperty(name="When",
                               description="When the region should trigger",
                               items=[("each", "Each Event", "The region will trigger on every enter/exit"),
                                      ("first", "First Event", "The region will trigger on the first event only"),
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
        layout.prop_search(self, "region", bpy.data, "objects", icon="MESH_DATA")
        layout.prop(self, "bounds")

    def export(self, exporter, tree, bo, so):
        interface = exporter.mgr.add_object(plInterfaceInfoModifier, name=self.create_key_name(tree), so=so)

        # Region Enters
        enter_simple = self.find_input_socket("enter").allow
        enter_settings = self.find_input("enter", "PlasmaVolumeReportNode")
        if enter_simple or enter_settings is not None:
            key = self._export_volume_event(exporter, tree, bo, so, plVolumeSensorConditionalObject.kTypeEnter, enter_settings)
            interface.addIntfKey(key)

        # Region Exits
        exit_simple = self.find_input_socket("exit").allow
        exit_settings = self.find_input("exit", "PlasmaVolumeReportNode")
        if exit_simple or exit_settings is not None:
            key = self._export_volume_event(exporter, tree, bo, so, plVolumeSensorConditionalObject.kTypeExit, exit_settings)
            interface.addIntfKey(key)

        # Don't forget to export the physical object itself!
        # [trollface.jpg]
        phys_bo = bpy.data.objects.get(self.region, None)
        if phys_bo is None:
            self.raise_error("invalid Region object: '{}'".format(self.region), tree)
        simIface, physical = exporter.physics.generate_physical(phys_bo, so, self.bounds, "{}_VolumeSensor".format(bo.name))

        physical.memberGroup = plSimDefs.kGroupDetector
        if "avatar" in self.report_on:
            physical.reportGroup |= 1 << plSimDefs.kGroupAvatar
        if "dynamics" in self.report_on:
            physical.reportGroup |= 1 << plSimDefs.kGroupDynamic

    def _export_volume_event(self, exporter, tree, bo, so, event, settings):
        if event == plVolumeSensorConditionalObject.kTypeEnter:
            suffix = "Enter"
        else:
            suffix = "Exit"

        theName = "{}_{}_{}".format(tree.name, self.name, suffix)
        print("        [LogicModifier '{}']".format(theName))
        logicKey = exporter.mgr.find_create_key(plLogicModifier, name=theName, so=so)
        logicmod = logicKey.object
        logicmod.setLogicFlag(plLogicModifier.kMultiTrigger, True)
        logicmod.notify = self.generate_notify_msg(exporter, tree, so, "satisfies")

        # Now, the detector objects
        print("        [ObjectInVolumeDetector '{}']".format(theName))
        detKey = exporter.mgr.find_create_key(plObjectInVolumeDetector, name=theName, so=so)
        det = detKey.object

        print("        [VolumeSensorConditionalObject '{}']".format(theName))
        volKey = exporter.mgr.find_create_key(plVolumeSensorConditionalObject, name=theName, so=so)
        volsens = volKey.object

        volsens.type = event
        if settings is not None:
            if settings.report_when == "first":
                volsens.first = True
            elif settings.report_when == "threshold":
                volsens.trigNum = settings.threshold

        # There appears to be a mandatory order for these keys...
        det.addReceiver(volKey)
        det.addReceiver(logicKey)

        # End mandatory order
        logicmod.addCondition(volKey)
        return logicKey


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
