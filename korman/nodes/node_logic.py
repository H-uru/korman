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
from collections import OrderedDict
from PyHSPlasma import *

from .node_core import *
from ..properties.modifiers.physics import bounds_types, bounds_type_index

class PlasmaExcludeRegionNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "LOGIC"
    bl_idname = "PlasmaExcludeRegionNode"
    bl_label = "Exclude Region"
    bl_width_default = 195

    # ohey, this can be a Python attribute
    pl_attribs = {"ptAttribExcludeRegion"}

    def _get_bounds(self):
        bo = bpy.data.objects.get(self.region, None)
        if bo is not None:
            return bounds_type_index(bo.plasma_modifiers.collision.bounds)
        return bounds_type_index("hull")
    def _set_bounds(self, value):
        bo = bpy.data.objects.get(self.region, None)
        if bo is not None:
            bo.plasma_modifiers.collision.bounds = value

    region = StringProperty(name="Region",
                            description="Region object's name")
    bounds = EnumProperty(name="Bounds",
                          description="Region bounds",
                          items=bounds_types,
                          get=_get_bounds,
                          set=_set_bounds)
    block_cameras = BoolProperty(name="Block Cameras",
                                description="The region blocks cameras when it has been cleared")

    input_sockets = OrderedDict([
        ("safe_point", {
            "type": "PlasmaExcludeSafePointSocket",
            "text": "Safe Point",
            "spawn_empty": True,
            # This never links to anything...
            "valid_link_sockets": frozenset(),
        }),
        ("msg", {
            "type": "PlasmaExcludeMessageSocket",
            "text": "Message",
            "spawn_empty": True,
        }),
    ])

    output_sockets = OrderedDict([
        ("keyref", {
            "text": "References",
            "type": "PlasmaPythonReferenceNodeSocket",
            "valid_link_nodes": {"PlasmaPythonFileNode"},
        }),
    ])

    def draw_buttons(self, context, layout):
        layout.prop_search(self, "region", bpy.data, "objects", icon="MESH_DATA")
        layout.prop(self, "bounds")
        layout.prop(self, "block_cameras")

    def get_key(self, exporter, parent_so):
        region_bo = bpy.data.objects.get(self.region, None)
        if region_bo is None:
            self.raise_error("invalid region object '{}'".format(self.region))
        return exporter.mgr.find_create_key(plExcludeRegionModifier, bl=region_bo, name=self.key_name)

    def harvest_actors(self):
        return [i.safepoint_name for i in self.find_input_sockets("safe_points")]

    def export(self, exporter, bo, parent_so):
        region_bo = bpy.data.objects.get(self.region, None)
        if region_bo is None:
            self.raise_error("invalid region object '{}'".format(self.region))
        region_so = exporter.mgr.find_create_object(plSceneObject, bl=region_bo)
        excludergn = exporter.mgr.find_create_object(plExcludeRegionModifier, so=region_so, name=self.key_name)
        excludergn.setFlag(plExcludeRegionModifier.kBlockCameras, self.block_cameras)

        # Safe points
        for i in self.find_input_sockets("safe_point"):
            if not i.safepoint_name:
                continue
            safept = bpy.data.objects.get(i.safepoint_name, None)
            if safept is None:
                self.raise_error("invalid SafePoint '{}'".format(i.safepoint_name))
            excludergn.addSafePoint(exporter.mgr.find_create_key(plSceneObject, bl=safept))

        # Ensure the region is exported
        phys_name = "{}_XRgn".format(self.region)
        simIface, physical = exporter.physics.generate_physical(region_bo, region_so, self.bounds, phys_name)
        simIface.setProperty(plSimulationInterface.kPinned, True)
        physical.setProperty(plSimulationInterface.kPinned, True)
        physical.LOSDBs |= plSimDefs.kLOSDBUIBlockers


class PlasmaExcludeSafePointSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.0, 0.0, 0.0, 0.0)

    safepoint_name = StringProperty(name="Safe Point",
                                    description="A point outside of this exclude region to move the avatar to")

    def draw(self, context, layout, node, text):
        layout.prop_search(self, "safepoint_name", bpy.data, "objects", icon="EMPTY_DATA")

    @property
    def is_used(self):
        return bpy.data.objects.get(self.safepoint_name, None) is not None


class PlasmaExcludeMessageSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.467, 0.576, 0.424, 1.0)
