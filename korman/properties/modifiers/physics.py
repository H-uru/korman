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

from .base import PlasmaModifierProperties

# These are the kinds of physical bounds Plasma can work with.
# This sequence is acceptable in any EnumProperty
bounds_types = (
    ("box", "Bounding Box", "Use a perfect bounding box"),
    ("sphere", "Bounding Sphere", "Use a perfect bounding sphere"),
    ("hull", "Convex Hull", "Use a convex set encompasing all vertices"),
    ("trimesh", "Triangle Mesh", "Use the exact triangle mesh (SLOW!)")
)

def bounds_type_index(key):
    return list(zip(*bounds_types))[0].index(key)

def _set_phys_prop(prop, sim, phys, value=True):
    """Sets properties on plGenericPhysical and plSimulationInterface (seeing as how they are duped)"""
    sim.setProperty(prop, value)
    phys.setProperty(prop, value)


class PlasmaCollider(PlasmaModifierProperties):
    pl_id = "collision"

    bl_category = "Physics"
    bl_label = "Collision"
    bl_icon = "MOD_PHYSICS"
    bl_description = "Simple physical collider"

    bounds = EnumProperty(name="Bounds Type", description="", items=bounds_types, default="hull")

    avatar_blocker = BoolProperty(name="Blocks Avatars", description="Object blocks avatars", default=True)
    camera_blocker = BoolProperty(name="Blocks Camera", description="Object blocks the camera", default=True)

    friction = FloatProperty(name="Friction", min=0.0, default=0.5)
    restitution = FloatProperty(name="Restitution", description="Coefficient of collision elasticity", min=0.0, max=1.0)
    terrain = BoolProperty(name="Terrain", description="Object represents the ground", default=False)

    dynamic = BoolProperty(name="Dynamic", description="Object can be influenced by other objects (ie is kickable)", default=False)
    mass = FloatProperty(name="Mass", description="Mass of object in pounds", min=0.0, default=1.0)
    start_asleep = BoolProperty(name="Start Asleep", description="Object is not active until influenced by another object", default=False)

    def export(self, exporter, bo, so):
        simIface, physical = exporter.physics.generate_physical(bo, so, self.bounds, self.key_name)

        # Common props
        physical.friction = self.friction
        physical.restitution = self.restitution

        # Collision groups and such
        if self.dynamic:
            physical.memberGroup = plSimDefs.kGroupDynamic
            physical.mass = self.mass
            _set_phys_prop(plSimulationInterface.kStartInactive, simIface, physical, value=self.start_asleep)
        elif not self.avatar_blocker:
            # the UI is kind of misleading on this count. oh well.
            physical.memberGroup = plSimDefs.kGroupLOSOnly
        else:
            physical.memberGroup = plSimDefs.kGroupStatic

        # Line of Sight DB
        if self.camera_blocker:
            physical.LOSDBs |= plSimDefs.kLOSDBCameraBlockers
            # This appears to be dead in CWE, but we'll set it anyway
            _set_phys_prop(plSimulationInterface.kCameraAvoidObject, simIface, physical)
        if self.terrain:
            physical.LOSDBs |= plSimDefs.kLOSDBAvatarWalkable

    def _make_physical_movable(self, so):
        sim = so.sim
        if sim is not None:
            sim = sim.object
            phys = sim.physical.object
            _set_phys_prop(plSimulationInterface.kPhysAnim, sim, phys)

            # If the mass is zero, then we will fail to animate. Fix that.
            if phys.mass == 0.0:
                phys.mass = 1.0

                # set kPinned so it doesn't fall through
                _set_phys_prop(plSimulationInterface.kPinned, sim, phys)

        # Do the same for child objects
        for child in so.coord.object.children:
            self._make_physical_movable(child.object)

    def post_export(self, exporter, bo, so):
        test_bo = bo
        while test_bo is not None:
            if exporter.animation.has_transform_animation(test_bo):
                self._make_physical_movable(so)
                break
            test_bo = test_bo.parent

    @property
    def key_name(self):
        return "{}_Collision".format(self.id_data.name)

    @property
    def requires_actor(self):
        return self.dynamic
