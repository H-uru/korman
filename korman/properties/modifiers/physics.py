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
from ...enum_props import _bounds_types
from ...exporter import ExportError
from ... import idprops

# These are the collision sound surface types
surface_types = (
    # Danger: do not reorder this one.
    ("kNone", "[None]", ""),
    # Reorder away down here...
    ("kBone", "Bone", ""),
    ("kDirt", "Dirt", ""),
    ("kGrass", "Grass", ""),
    ("kMetal", "Metal", ""),
    ("kCone", "Plastic", ""),
    ("kRug", "Rug", ""),
    ("kStone", "Stone", ""),
    ("kWater", "Water", ""),
    ("kWood", "Wood", ""),
    ("kUser1", "User 1", ""),
    ("kUser2", "User 2", ""),
    ("kUser3", "User 3", ""),
)

subworld_types = (
    ("auto", "Auto", "Korman will decide which physics strategy to use"),
    ("dynamicav", "Dynamic Avatar", "Allows the avatar to affected by dynamic physicals"),
    ("subworld", "Separate World", "Causes all objects to be placed in a separate physics simulation"),
)

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
    bl_object_types = {"MESH", "FONT"}

    bounds = EnumProperty(name="Bounds Type",
                          description="",
                          items=_bounds_types,
                          default="hull")

    avatar_blocker = BoolProperty(name="Blocks Avatars",
                                  description="Object blocks avatars",
                                  default=True)
    camera_blocker = BoolProperty(name="Blocks Camera LOS",
                                  description="Object blocks camera line-of-sight",
                                  default=True)
    dynamic_blocker = BoolProperty(name="Blocks Dynamics",
                                   description="Object blocks dynamic objects (kickables)",
                                   default=True)

    friction = FloatProperty(name="Friction",
                             min=0.0,
                             default=0.5)
    restitution = FloatProperty(name="Restitution",
                                description="Coefficient of collision elasticity",
                                min=0.0,
                                max=1.0)
    terrain = BoolProperty(name="Terrain",
                           description="Object represents the ground",
                           default=False)

    dynamic = BoolProperty(name="Dynamic",
                           description="Object can be influenced by other objects (ie is kickable)",
                           default=False)
    mass = FloatProperty(name="Mass",
                         description="Mass of object in pounds",
                         min=0.0,
                         default=1.0)
    start_asleep = BoolProperty(name="Start Asleep",
                                description="Object is not active until influenced by another object",
                                default=False)

    proxy_object = PointerProperty(name="Proxy",
                                   description="Object used as the collision geometry",
                                   type=bpy.types.Object,
                                   poll=idprops.poll_mesh_objects)

    surface = EnumProperty(name="Surface Type",
                           description="Type of surface sound effect to play on collision",
                           items=surface_types,
                           default="kNone",
                           options=set())

    def export(self, exporter, bo, so):
        # All modifier properties are examined by this little stinker...
        exporter.physics.generate_physical(bo, so)

    @property
    def requires_actor(self):
        return self.dynamic


class PlasmaSubworld(PlasmaModifierProperties):
    pl_id = "subworld_def"

    bl_category = "Physics"
    bl_label = "Subworld"
    bl_description = "Subworld definition"
    bl_icon = "WORLD"

    sub_type = EnumProperty(name="Subworld Type",
                            description="Specifies the physics strategy to use for this subworld",
                            items=subworld_types,
                            default="auto",
                            options=set())
    gravity = FloatVectorProperty(name="Gravity",
                                  description="Subworld's gravity defined in feet per second squared",
                                  size=3,
                                  default=(0.0, 0.0, -32.174),
                                  precision=3,
                                  subtype="ACCELERATION",
                                  unit="ACCELERATION")

    def export(self, exporter, bo, so):
        if self.is_dedicated_subworld(exporter):
            # NOTE to posterity... Cyan's PotS/Havok subworlds appear to have a
            # plHKPhysical object that is set as LOSOnly convex hull. They appear to
            # be a bounding box. PyPRP generated PRPs do not do this and work just fine,
            # however, so this is probably just a quirk of the Havok-era PlasmaMAX
            subworld = exporter.mgr.find_create_object(plHKSubWorld, so=so)
            subworld.gravity = hsVector3(*self.gravity)

    def is_dedicated_subworld(self, exporter):
        if exporter.mgr.getVer() != pvMoul:
            return True
        if self.sub_type == "subworld":
            return True
        elif self.sub_type == "dynamicav":
            return False
        else:
            return not self.property_unset("gravity")

    def post_export(self, exporter, bo, so):
        # It appears PotS does something really fancy with subworlds under the hood such that
        # if you make a subworld that has collision, it will get into an infinite loop in
        # plCoordinateInterface::IGetRoot. Not really sure why this happens (nor do I care),
        # but we definitely don't want it to happen.
        if bo.type != "EMPTY":
            exporter.report.warn(f"Subworld '{bo.name}' is attached to a '{bo.type}'--this should be an empty.")
        if so.sim:
            if exporter.mgr.getVer() > pvPots:
                exporter.report.port(f"Subworld '{bo.name}' has physics data--this will cause PotS to crash.")
            else:
                raise ExportError(f"Subworld '{bo.name}' cannot have physics data (should be an empty).")
