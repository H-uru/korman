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
import mathutils
from PyHSPlasma import *
import weakref

from ..helpers import TemporaryObject
from . import utils

class PhysicsConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)

    def _convert_mesh_data(self, bo, physical, indices=True):
        mesh = bo.to_mesh(bpy.context.scene, True, "RENDER", calc_tessface=False)
        mat = bo.matrix_world

        with TemporaryObject(mesh, bpy.data.meshes.remove) as mesh:
            # We can only use the plPhysical xforms if there is a CI...
            if self._mgr.has_coordiface(bo):
                mesh.update(calc_tessface=indices)
                physical.pos = utils.vector3(mat.to_translation())
                quat = mat.to_quaternion()
                quat.normalize()
                physical.rot = utils.quaternion(quat)

                # Physicals can't have scale...
                scale = mat.to_scale()
                if scale[0] == 1.0 and scale[1] == 1.0 and scale[2] == 1.0:
                    # Whew, don't need to do any math!
                    vertices = [hsVector3(i.co.x, i.co.y, i.co.z) for i in mesh.vertices]
                else:
                    # Dagnabbit...
                    vertices = [hsVector3(i.co.x * scale.x, i.co.y * scale.y, i.co.z * scale.z) for i in mesh.vertices]
            else:
                # apply the transform to the physical itself
                mesh.transform(mat)
                mesh.update(calc_tessface=indices)
                vertices = [hsVector3(i.co.x, i.co.y, i.co.z) for i in mesh.vertices]

            if indices:
                indices = []
                for face in mesh.tessfaces:
                    v = face.vertices
                    if len(v) == 3:
                        indices += v
                    elif len(v) == 4:
                        indices += (v[0], v[1], v[2],)
                        indices += (v[0], v[2], v[3],)
                return (vertices, indices)
            else:
                return vertices

    def generate_physical(self, bo, so, bounds, name=None):
        """Generates a physical object for the given object pair"""
        if so.sim is None:
            if name is None:
                name = bo.name

            simIface = self._mgr.add_object(pl=plSimulationInterface, bl=bo)
            physical = self._mgr.add_object(pl=plGenericPhysical, bl=bo, name=name)

            simIface.physical = physical.key
            physical.object = so.key
            physical.sceneNode = self._mgr.get_scene_node(bl=bo)

            getattr(self, "_export_{}".format(bounds))(bo, physical)
        else:
            simIface = so.sim.object
            physical = simIface.physical.object
            if name is not None:
                physical.key.name = name

        return (simIface, physical)

    def _export_box(self, bo, physical):
        """Exports box bounds based on the object"""
        physical.boundsType = plSimDefs.kBoxBounds

        vertices = self._convert_mesh_data(bo, physical, indices=False)
        physical.calcBoxBounds(vertices)

    def _export_hull(self, bo, physical):
        """Exports convex hull bounds based on the object"""
        physical.boundsType = plSimDefs.kHullBounds

        vertices = self._convert_mesh_data(bo, physical, indices=False)
        # --- TODO ---
        # Until we have real convex hull processing, simply dump the verts into the physical
        # Note that PyPRP has always done this... PhysX will optimize this for us. So, it's not
        # the end of the world (but it is evil).
        physical.verts = vertices

    def _export_sphere(self, bo, physical):
        """Exports sphere bounds based on the object"""
        physical.boundsType = plSimDefs.kSphereBounds

        vertices = self._convert_mesh_data(bo, physical, indices=False)
        physical.calcSphereBounds(vertices)

    def _export_trimesh(self, bo, physical):
        """Exports an object's mesh as exact physical bounds"""
        physical.boundsType = plSimDefs.kExplicitBounds

        vertices, indices = self._convert_mesh_data(bo, physical)
        physical.verts = vertices
        physical.indices = indices

    @property
    def _mgr(self):
        return self._exporter().mgr
