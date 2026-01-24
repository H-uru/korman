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
from typing import *
from PyHSPlasma import *

from .. import enum_props
from ..exporter import Exporter
from .node_core import *
from .. import idprops

class PlasmaChangeSDLNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaChangeSDLNode"
    bl_label = "Change SDL"
    bl_width_default = 200

    input_sockets: dict[str, dict[str, Any]] = {
        "condition": {
            "text": "Condition",
            "type": "PlasmaConditionSocket",
            "spawn_empty": True,
        },
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "variable": {
            "text": "SDL",
            "type": "PlasmaSDLTriggereeSocket",
        }
    }

    action = EnumProperty(
        name="Action",
        items=[
            ("TOGGLE", "Toggle Boolean", "Toggle a boolean SDL variable"),
            ("SET_BOOL", "Set Boolean", "Set the boolean value of an SDL Variable"),
            ("SET_INT", "Set Integer", "Set the integer value of an SDL Variable"),
            ("INC_INT", "Increment Integer", "Increment the integer value of an SDL Variable"),
            ("DEC_INT", "Decrement Integer", "Decrement the integer value of an SDL Variable"),
        ],
        options=set()
    )

    value_int = IntProperty(
        name="Value",
        options=set()
    )

    def _get_bool(self) -> bool:
        return self.value_int != 0
    def _set_bool(self, value: bool) -> None:
        if self.value_int == 0 and value:
            self.value_int = 1
        if self.value_int != 0 and not value:
            self.value_int = 0

    value_bool = BoolProperty(
        name="Value",
        description="If checked, the value of the SDL Variable is true",
        get=_get_bool,
        set=_set_bool,
        options=set()
    )

    count_behavior = EnumProperty(
        name="Behavior",
        description="",
        items=[
            ("UNBOUNDED", "[None]", "Don't use bounds for the SDL value"),
            ("CLAMP", "Clamp", "Clamp the SDL value to the range provided"),
            ("LOOP", "Loop", "Loop the SDL value within the range provided"),
        ]
    )

    min_value = IntProperty(
        name="Min",
        description="Minimum value of the SDL variable",
        default=0,
        options=set()
    )
    max_value = IntProperty(
        name="Max",
        description="Maximum value of the SDL variable",
        default=10,
        options=set()
    )

    tag_string = StringProperty(
        name="Extra Info",
        description="Tag string sent along as extra info for the SDL variable change",
        options=set()
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "action")
        if self.action == "SET_BOOL":
            layout.prop(self, "value_bool")
        elif self.action == "SET_INT":
            layout.prop(self, "value_int")
        elif self.action in {"INC_INT", "DEC_INT"}:
            layout.prop(self, "count_behavior")
            if self.count_behavior != "UNBOUNDED":
                row = layout.row(align=True)
                row.alert = self.min_value >= self.max_value
                row.prop(self, "min_value")
                row.prop(self, "max_value")
        elif self.action == "TOGGLE":
            pass
        else:
            raise ValueError(self.action)

        layout.prop(self, "tag_string")

    def get_key(self, exporter: Exporter, so: plSceneObject) -> plKey[plPythonFileMod]:
        return self._find_create_key(plPythonFileMod, exporter, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        variable_node = self.find_output("variable")
        if variable_node is None:
            self.raise_error("Must be connected to an SDL Variable")

        # While we could technically use a thunk to simplify this, unfortunately, plAACO won't
        # pass through the details about which avatar did the deed. xAgeSDLBoolToggle uses the
        # anti-pattern `if PtFindAvatar(events) == PtGetLocalAvatar()` to detect if a notification
        # is local. So, we'll connect the PFM directly to the host LogicMod.
        logic_keys = [i.get_key(exporter, so) for i in self.find_inputs("condition")]
        logic_keys_iter = (i for i in logic_keys if i is not None)
        if not any(logic_keys):
            self.raise_error("Must be connected to valid conditions!")

        pfm = self._find_create_object(plPythonFileMod, exporter, so=so)
        if self.action == "TOGGLE":
            pfm.filename = "xAgeSDLBoolToggle"
            for i in logic_keys_iter:
                self._add_py_parameter(pfm, 1, plPythonParameter.kActivator, i)
            self._add_py_parameter(pfm, 2, plPythonParameter.kString, variable_node.variable_name)
            if self.tag_string:
                self._add_py_parameter(pfm, 5, plPythonParameter.kString, self.tag_string)
        elif self.action == "SET_BOOL":
            pfm.filename = "xAgeSDLBoolSet"
            for i in logic_keys_iter:
                self._add_py_parameter(pfm, 1, plPythonParameter.kActivator, i)
            self._add_py_parameter(pfm, 2, plPythonParameter.kString, variable_node.variable_name)
            self._add_py_parameter(pfm, 7, plPythonParameter.kInt, self.value_int)
            if self.tag_string:
                self._add_py_parameter(pfm, 8, plPythonParameter.kString, self.tag_string)
        elif self.action in {"INC_INT", "DEC_INT", "SET_INT"}:
            pfm.filename = "xAgeSDLIntChange"
            for i in logic_keys_iter:
                self._add_py_parameter(pfm, 1, plPythonParameter.kActivator, i)
            self._add_py_parameter(pfm, 2, plPythonParameter.kString, variable_node.variable_name)
            self._add_py_parameter(pfm, 3, plPythonParameter.kBoolean, self.action == "INC_INT")
            self._add_py_parameter(pfm, 4, plPythonParameter.kBoolean, self.action == "DEC_INT")
            if self.action != "SET_INT":
                # The xAgeSDLIntChange script doesn't really have an "unbounded" mode. But,
                # we can fake it by passing in the min/max values of the underlying signed
                # 32-bit integer store.
                if self.count_behavior == "UNBOUNDED":
                    min_value, max_value = 0x80000000, 0x7FFFFFFF
                else:
                    min_value = min(self.min_value, self.max_value)
                    max_value = max(self.min_value, self.max_value)
                if min_value == max_value:
                    self.raise_error("Minimum and maximum values must not be the same!")
                self._add_py_parameter(pfm, 5, plPythonParameter.kInt, min_value)
                self._add_py_parameter(pfm, 6, plPythonParameter.kInt, max_value)
                self._add_py_parameter(pfm, 7, plPythonParameter.kBoolean, self.count_behavior == "LOOP")
            if self.tag_string:
                self._add_py_parameter(pfm, 8, plPythonParameter.kString, self.tag_string)
            if self.action == "SET_INT":
                self._add_py_parameter(pfm, 9, plPythonParameter.kInt, self.value_int)
        else:
            raise ValueError(self.action)

    @property
    def export_once(self):
        return True


class PlasmaExcludeRegionNode(idprops.IDPropObjectMixin, PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaExcludeRegionNode"
    bl_label = "Exclude Region"
    bl_width_default = 195

    # ohey, this can be a Python attribute
    pl_attrib = {"ptAttribExcludeRegion"}

    region_object = PointerProperty(name="Region",
                                    description="Region object's name",
                                    type=bpy.types.Object,
                                    poll=idprops.poll_mesh_objects)
    bounds = enum_props.bounds(
        "region_object",
        name="Bounds",
        description="Region bounds"
    )
    block_cameras = BoolProperty(
        name="Block Cameras",
        description="The region blocks cameras when it has been cleared"
    )

    input_sockets:dict[str, dict[str, Any]] = {
        "safe_point": {
            "type": "PlasmaExcludeSafePointSocket",
            "text": "Safe Point",
            "spawn_empty": True,
            # This never links to anything...
            "valid_link_sockets": frozenset(),
        },
        "msg": {
            "type": "PlasmaExcludeMessageSocket",
            "text": "Message",
            "spawn_empty": True,
        },
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "keyref": {
            "text": "References",
            "type": "PlasmaPythonReferenceNodeSocket",
            "valid_link_nodes": {"PlasmaPythonFileNode"},
        },
    }

    def draw_buttons(self, context, layout):
        layout.prop(self, "region_object", icon="MESH_DATA")
        layout.prop(self, "bounds")
        layout.prop(self, "block_cameras")

    def get_key(self, exporter, parent_so):
        if self.region_object is None:
            self.raise_error("Region must be set")
        return self._find_create_key(plExcludeRegionModifier, exporter, bl=self.region_object)

    def harvest_actors(self):
        return (i.safepoint.name for i in self.find_input_sockets("safe_points") if i.safepoint is not None)

    def export(self, exporter, bo, parent_so):
        excludergn = self.get_key(exporter, parent_so).object
        excludergn.setFlag(plExcludeRegionModifier.kBlockCameras, self.block_cameras)
        region_so = exporter.mgr.find_create_object(plSceneObject, bl=self.region_object)

        # Safe points
        for i in self.find_input_sockets("safe_point"):
            safept = i.safepoint_object
            if safept:
                excludergn.addSafePoint(exporter.mgr.find_create_key(plSceneObject, bl=safept))

        # Ensure the region is exported
        if exporter.mgr.getVer() <= pvPots:
            member_group = "kGroupDetector"
            collide_groups = ["kGroupDynamic"]
        else:
            member_group = "kGroupStatic"
            collide_groups = []
        exporter.physics.generate_physical(self.region_object, region_so, bounds=self.bounds,
                                           properties=["kPinned"],
                                           losdbs=["kLOSDBUIBlockers"],
                                           member_group=member_group,
                                           collide_groups=collide_groups)

    @property
    def export_once(self):
        return True

    @classmethod
    def _idprop_mapping(cls):
        return {"region_object": "region"}


class PlasmaExcludeSafePointSocket(idprops.IDPropObjectMixin, PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.0, 0.0, 0.0, 0.0)

    safepoint_object = PointerProperty(name="Safe Point",
                                       description="A point outside of this exclude region to move the avatar to",
                                       type=bpy.types.Object)

    def draw(self, context, layout, node, text):
        layout.prop(self, "safepoint_object", icon="EMPTY_DATA")

    @classmethod
    def _idprop_mapping(cls):
        return {"safepoint_object": "safepoint_name"}

    @property
    def is_used(self):
        return self.safepoint_object is not None


class PlasmaExcludeMessageSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.467, 0.576, 0.424, 1.0)


class PlasmaSDLSocketBase:
    bl_color = (0.18, 0.55, 0.34, 1.0)


class PlasmaSDLTriggererSocket(PlasmaSDLSocketBase, PlasmaNodeSocketBase, bpy.types.NodeSocket): pass
class PlasmaSDLTriggereeSocket(PlasmaSDLSocketBase, PlasmaNodeSocketBase, bpy.types.NodeSocket): pass


class PlasmaSDLVariableNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaSDLVariableNode"
    bl_label = "SDL Variable"
    bl_width_default = 200

    input_sockets: dict[str, dict[str, Any]] = {
        "condition": {
            "text": "Changed By",
            "type": "PlasmaSDLTriggereeSocket",
        }
    }

    output_sockets: dict[str, dict[str, Any]] = {
        "satisfies": {
            "text": "Triggers",
            "type": "PlasmaSDLTriggererSocket",
        }
    }

    variable_name = StringProperty(
        name="Variable",
        description="Name of an SDL Variable",
        options=set()
    )

    def draw_buttons(self, context, layout: bpy.types.UILayout):
        layout.alert = not self.variable_name.strip()
        layout.prop(self, "variable_name")
