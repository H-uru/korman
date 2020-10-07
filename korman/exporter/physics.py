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
import itertools
import mathutils
from PyHSPlasma import *
import weakref

from .explosions import ExportError, ExportAssertionError
from ..helpers import bmesh_from_object, TemporaryObject
from . import utils

def _set_phys_prop(prop, sim, phys, value=True):
    """Sets properties on plGenericPhysical and plSimulationInterface (seeing as how they are duped)"""
    sim.setProperty(prop, value)
    phys.setProperty(prop, value)

class PhysicsConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self._bounds_converters = {
            "box": self._export_box,
            "sphere": self._export_sphere,
            "hull": self._export_hull,
            "trimesh": self._export_trimesh,
        }

    def _apply_props(self, simIface, physical, props):
        for i in props.get("properties", []):
            _set_phys_prop(getattr(plSimulationInterface, i), simIface, physical)
        for i in props.get("losdbs", []):
            physical.LOSDBs |= getattr(plSimDefs, i)
        for i in props.get("report_groups", []):
            physical.reportGroup |= 1 << getattr(plSimDefs, i)
        for i in props.get("collide_groups", []):
            physical.collideGroup |= 1 << getattr(plSimDefs, i)

    def _convert_indices(self, mesh):
        indices = []
        for face in mesh.tessfaces:
            v = face.vertices
            if len(v) == 3:
                indices += v
            elif len(v) == 4:
                indices += (v[0], v[1], v[2],)
                indices += (v[0], v[2], v[3],)
        return indices

    def _convert_mesh_data(self, bo, physical, local_space, indices=True):
        mat = bo.matrix_world

        mesh = bo.to_mesh(bpy.context.scene, True, "RENDER", calc_tessface=False)
        with TemporaryObject(mesh, bpy.data.meshes.remove):
            if local_space:
                mesh.update(calc_tessface=indices)
                physical.pos = hsVector3(*mat.to_translation())
                physical.rot = utils.quaternion(mat.to_quaternion())

                # Physicals can't have scale...
                scale = mat.to_scale()
                if scale[0] == 1.0 and scale[1] == 1.0 and scale[2] == 1.0:
                    # Whew, don't need to do any math!
                    vertices = [hsVector3(*i.co) for i in mesh.vertices]
                else:
                    # Dagnabbit...
                    vertices = [hsVector3(i.co.x * scale.x, i.co.y * scale.y, i.co.z * scale.z) for i in mesh.vertices]
            else:
                # apply the transform to the physical itself
                mesh.transform(mat)
                mesh.update(calc_tessface=indices)
                vertices = [hsVector3(*i.co) for i in mesh.vertices]

            if indices:
                return (vertices, self._convert_indices(mesh))
            else:
                return vertices

    def generate_flat_proxy(self, bo, so, **kwargs):
        """Generates a flat physical object"""
        z_coord = kwargs.pop("z_coord", None)

        if so.sim is None:
            simIface = self._mgr.add_object(pl=plSimulationInterface, bl=bo)
            physical = self._mgr.add_object(pl=plGenericPhysical, bl=bo, name=name)

            simIface.physical = physical.key
            physical.object = so.key
            physical.sceneNode = self._mgr.get_scene_node(bl=bo)

            mesh = bo.to_mesh(bpy.context.scene, True, "RENDER", calc_tessface=False)
            with TemporaryObject(mesh, bpy.data.meshes.remove):
                # No mass and no emedded xform, so we force worldspace collision.
                mesh.transform(bo.matrix_world)
                mesh.update(calc_tessface=True)

                if z_coord is None:
                    # Ensure all vertices are coplanar
                    z_coords = [i.co.z for i in mesh.vertices]
                    delta = max(z_coords) - min(z_coords)
                    if delta > 0.0002:
                        raise ExportAssertionError()
                    vertices = [hsVector3(*i.co) for i in mesh.vertices]
                else:
                    # Flatten out all points to the given Z-coordinate
                    vertices = [hsVector3(i.co.x, i.co.y, z_coord) for i in mesh.vertices]
                physical.verts = vertices
                physical.indices = self._convert_indices(mesh)
                physical.boundsType = plSimDefs.kProxyBounds

                group_name = kwargs.get("member_group")
                if group_name:
                    physical.memberGroup = getattr(plSimDefs, group_name)
        else:
            simIface = so.sim.object
            physical = simIface.physical.object

            member_group = getattr(plSimDefs, kwargs.get("member_group", "kGroupLOSOnly"))
            if physical.memberGroup != member_group and member_group != plSimDefs.kGroupLOSOnly:
                self._report.warn("{}: Physical memberGroup overwritten!", bo.name)
                physical.memberGroup = member_group
        self._apply_props(simIface, physical, kwargs)

    def generate_physical(self, bo, so, **kwargs):
        """Generates a physical object for the given object pair.
           The following optional arguments are allowed:
           - bounds: (defaults to collision modifier setting)
           - member_group: str attribute of plSimDefs, defaults to kGroupStatic
                           NOTE that kGroupLOSOnly generation will only succeed if no one else
                           has generated this physical in another group
           - properties: sequence of str bit names from plSimulationInterface
           - losdbs: sequence of str bit names from plSimDefs
           - report_groups: sequence of str bit names from plSimDefs
           - collide_groups: sequence of str bit names from plSimDefs
        """
        if so.sim is None:
            simIface = self._mgr.add_object(pl=plSimulationInterface, bl=bo)
            physical = self._mgr.add_object(pl=plGenericPhysical, bl=bo)
            ver = self._mgr.getVer()

            simIface.physical = physical.key
            physical.object = so.key
            physical.sceneNode = self._mgr.get_scene_node(bl=bo)

            # Got subworlds?
            subworld = bo.plasma_object.subworld
            if subworld is not None and self.is_dedicated_subworld(subworld, sanity_check=False):
                physical.subWorld = self._mgr.find_create_key(plHKSubWorld, bl=subworld)

            # Export the collision modifier here since we like stealing from it anyway.
            mod = bo.plasma_modifiers.collision
            bounds = kwargs.get("bounds", mod.bounds)
            if mod.enabled:
                physical.friction = mod.friction
                physical.restitution = mod.restitution

                if mod.dynamic:
                    if ver <= pvPots:
                        physical.collideGroup = (1 << plSimDefs.kGroupDynamic) | \
                                                (1 << plSimDefs.kGroupStatic)
                    physical.memberGroup = plSimDefs.kGroupDynamic
                    physical.mass = mod.mass
                    _set_phys_prop(plSimulationInterface.kStartInactive, simIface, physical,
                                   value=mod.start_asleep)
                elif not mod.avatar_blocker:
                    physical.memberGroup = plSimDefs.kGroupLOSOnly
                else:
                    physical.memberGroup = plSimDefs.kGroupStatic

                # Line of Sight DB
                if mod.camera_blocker:
                    physical.LOSDBs |= plSimDefs.kLOSDBCameraBlockers
                    _set_phys_prop(plSimulationInterface.kCameraAvoidObject, simIface, physical)
                if mod.terrain:
                    physical.LOSDBs |= plSimDefs.kLOSDBAvatarWalkable
            else:
                group_name = kwargs.get("member_group")
                if group_name:
                    physical.memberGroup = getattr(plSimDefs, group_name)

            # Ensure this thing is set up properly for animations.
            # This was previously the collision modifier's postexport method, but that
            # would miss cases where we have animated detectors (subworlds!!!)
            def _iter_object_tree(bo, stop_at_subworld):
                while bo is not None:
                    if stop_at_subworld and self.is_dedicated_subworld(bo, sanity_check=False):
                        return
                    yield bo
                    bo = bo.parent

            for i in _iter_object_tree(bo, ver == pvMoul):
                if i.plasma_object.has_transform_animation:
                    tree_xformed = True
                    break
            else:
                tree_xformed = False

            if tree_xformed:
                bo_xformed = bo.plasma_object.has_transform_animation

                # MOUL: only objects that have animation data are kPhysAnim
                if mod.enabled and (ver != pvMoul or bo_xformed):
                    _set_phys_prop(plSimulationInterface.kPhysAnim, simIface, physical)
                # PotS: objects inheriting parent animation only are not pinned
                # MOUL: animated objects in subworlds are not pinned
                if (bo_xformed and (ver != pvMoul or subworld is None)) or ((ver != pvMoul) and subworld is not None and (not bo_xformed)):
                     _set_phys_prop(plSimulationInterface.kPinned, simIface, physical)
                # MOUL: child objects are kPassive
                if ver == pvMoul and bo.parent is not None:
                    _set_phys_prop(plSimulationInterface.kPassive, simIface, physical)
                # FilterCoordinateInterfaces are kPassive
                if bo.plasma_object.ci_type == plFilterCoordInterface:
                    _set_phys_prop(plSimulationInterface.kPassive, simIface, physical)

                # If the mass is zero, then we will fail to animate. Fix that.
                if physical.mass == 0.0:
                    physical.mass = 1.0

            if ver <= pvPots:
                local_space = physical.mass > 0.0
            else:
                local_space = self._exporter().has_coordiface(bo)
            self._bounds_converters[bounds](bo, physical, local_space)
        else:
            simIface = so.sim.object
            physical = simIface.physical.object

            member_group = getattr(plSimDefs, kwargs.get("member_group", "kGroupLOSOnly"))
            if physical.memberGroup != member_group and member_group != plSimDefs.kGroupLOSOnly:
                self._report.warn("{}: Physical memberGroup overwritten!", bo.name, indent=2)
                physical.memberGroup = member_group

        self._apply_props(simIface, physical, kwargs)

    def _export_box(self, bo, physical, local_space):
        """Exports box bounds based on the object"""
        physical.boundsType = plSimDefs.kBoxBounds

        vertices = self._convert_mesh_data(bo, physical, local_space, indices=False)
        physical.calcBoxBounds(vertices)

    def _export_hull(self, bo, physical, local_space):
        """Exports convex hull bounds based on the object"""
        physical.boundsType = plSimDefs.kHullBounds

        # Only certain builds of libHSPlasma are able to take artist generated triangle soups and
        # bake them to convex hulls. Specifically, Windows 32-bit w/PhysX 2.6. Everything else just
        # needs to have us provide some friendlier data...
        with bmesh_from_object(bo) as mesh:
            mat = bo.matrix_world
            if local_space:
                physical.pos = hsVector3(*mat.to_translation())
                physical.rot = utils.quaternion(mat.to_quaternion())
                bmesh.ops.scale(mesh, vec=mat.to_scale(), verts=mesh.verts)
            else:
                mesh.transform(mat)

            result = bmesh.ops.convex_hull(mesh, input=mesh.verts, use_existing_faces=False)
            BMVert = bmesh.types.BMVert
            verts = itertools.takewhile(lambda x: isinstance(x, BMVert), result["geom"])
            physical.verts = [hsVector3(*i.co) for i in verts]

    def _export_sphere(self, bo, physical, local_space):
        """Exports sphere bounds based on the object"""
        physical.boundsType = plSimDefs.kSphereBounds

        vertices = self._convert_mesh_data(bo, physical, local_space, indices=False)
        physical.calcSphereBounds(vertices)

    def _export_trimesh(self, bo, physical, local_space):
        """Exports an object's mesh as exact physical bounds"""

        # Triangle meshes MAY optionally specify a proxy object to fetch the triangles from...
        mod = bo.plasma_modifiers.collision
        if mod.enabled and mod.proxy_object is not None:
            physical.boundsType = plSimDefs.kProxyBounds
            vertices, indices = self._convert_mesh_data(mod.proxy_object, physical, local_space)
        else:
            physical.boundsType = plSimDefs.kExplicitBounds
            vertices, indices = self._convert_mesh_data(bo, physical, local_space)

        physical.verts = vertices
        physical.indices = indices

    def is_dedicated_subworld(self, bo, sanity_check=True):
        """Determines if a subworld object defines an alternate physics world"""
        if bo is None:
            return False
        subworld_mod = bo.plasma_modifiers.subworld_def
        if not subworld_mod.enabled:
            if sanity_check:
                raise ExportError("'{}' is not a subworld".format(bo.name))
            else:
                return False
        return subworld_mod.is_dedicated_subworld(self._exporter())

    @property
    def _mgr(self):
        return self._exporter().mgr

    @property
    def _report(self):
        return self._exporter().report
