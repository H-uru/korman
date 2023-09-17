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

import bmesh
import bpy
import mathutils

from contextlib import contextmanager
from typing import *

from PyHSPlasma import *

from ..import helpers

def affine_parts(xform):
    # Decompose the matrix into the 90s-era 3ds max affine parts sillyness
    # All that's missing now is something like "(c) 1998 HeadSpin" oh wait...
    affine = hsAffineParts()
    affine.T = hsVector3(*xform.to_translation())
    affine.K = hsVector3(*xform.to_scale())
    affine.F = -1.0 if xform.determinant() < 0.0 else 1.0
    rot = xform.to_quaternion()
    affine.Q = quaternion(rot)
    rot.normalize()
    affine.U = quaternion(rot)
    return affine

def color(blcolor, alpha=1.0):
    """Converts a Blender Color into an hsColorRGBA"""
    return hsColorRGBA(blcolor.r, blcolor.g, blcolor.b, alpha)

def matrix44(blmat):
    """Converts a mathutils.Matrix to an hsMatrix44"""
    hsmat = hsMatrix44()
    for i in range(4):
        hsmat[i, 0] = blmat[i][0]
        hsmat[i, 1] = blmat[i][1]
        hsmat[i, 2] = blmat[i][2]
        hsmat[i, 3] = blmat[i][3]
    return hsmat

def quaternion(blquat):
    """Converts a mathutils.Quaternion to an hsQuat"""
    return hsQuat(blquat.x, blquat.y, blquat.z, blquat.w)


class BMeshObject:
    def __init__(self, name: str, managed: bool = True):
        self._managed = managed
        self._bmesh = None
        self._mesh = bpy.data.meshes.new(name)
        self._obj = bpy.data.objects.new(name, self._mesh)
        self._obj.draw_type = "WIRE"
        bpy.context.scene.objects.link(self._obj)

    def __del__(self):
        if self._managed:
            bpy.context.scene.objects.unlink(self._obj)
            bpy.data.meshes.remove(self._mesh)

    def __enter__(self) -> bmesh.types.BMesh:
        if self._mesh is not None:
            self._bmesh = bmesh.new()
            self._bmesh.from_mesh(self._mesh)
            return self._bmesh

    def __exit__(self, type, value, traceback):
        if self._bmesh is not None:
            self._bmesh.to_mesh(self._mesh)
            self._bmesh.free()
            self._bmesh = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._obj, name)

    def __setattr__(self, name: str, value: Any) -> None:
        # NOTE: Calling `hasattr()` will trigger infinite recursion in __getattr__(), so
        # check the object dict itself for anything that we want on this instance.
        d = self.__dict__
        if name not in d:
            obj = d.get("_obj")
            if obj is not None:
                if hasattr(obj, name):
                    setattr(obj, name, value)
                    return
        super().__setattr__(name, value)

    @property
    def object(self) -> bpy.types.Object:
        return self._obj

    def release(self) -> bpy.types.Object:
        self._managed = False
        return self._obj


def create_empty_object(name: str, owner_object: Optional[bpy.types.Object] = None) -> bpy.types.Object:
    empty_object = bpy.data.objects.new(name, None)
    if owner_object is not None:
        empty_object.plasma_object.enabled = owner_object.plasma_object.enabled
        empty_object.plasma_object.page = owner_object.plasma_object.page
    bpy.context.scene.objects.link(empty_object)
    return empty_object

def create_camera_object(name: str) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new(name)
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.objects.link(cam_obj)
    return cam_obj

def create_cube_region(name: str, size: float, owner_object: bpy.types.Object) -> bpy.types.Object:
    """Create a cube shaped region object"""
    region_object = BMeshObject(name)
    region_object.plasma_object.enabled = True
    region_object.plasma_object.page = owner_object.plasma_object.page
    region_object.hide_render = True
    with region_object as bm:
        bmesh.ops.create_cube(bm, size=(size))
        bmesh.ops.transform(
            bm,
            matrix=mathutils.Matrix.Translation(
                owner_object.matrix_world.translation - region_object.matrix_world.translation
            ),
            space=region_object.matrix_world, verts=bm.verts
        )
    return region_object.release()

@contextmanager
def pre_export_optional_cube_region(source, attr: str, name: str, size: float, owner_object: bpy.types.Object) -> Optional[bpy.types.Object]:
    if getattr(source, attr) is None:
        region_object = create_cube_region(name, size, owner_object)
        setattr(source, attr, region_object)
        try:
            yield region_object
        finally:
            source.property_unset(attr)
    else:
        # contextlib.contextmanager requires for us to yield. Sad.
        yield

@contextmanager
def temporary_camera_object(scene: bpy.types.Scene, name: str) -> bpy.types.Object:
    try:
        cam_data = bpy.data.cameras.new(name)
        cam_obj = bpy.data.objects.new(name, cam_data)
        scene.objects.link(cam_obj)
        yield cam_obj
    finally:
        cam_obj = locals().get("cam_obj")
        if cam_obj is not None:
            bpy.data.objects.remove(cam_obj)
        cam_data = locals().get("cam_data")
        if cam_data is not None:
            bpy.data.cameras.remove(cam_data)

@contextmanager
def temporary_mesh_object(source : bpy.types.Object) -> bpy.types.Object:
    """Creates a temporary mesh object from a nonmesh object that will only exist for the duration
       of the context."""
    assert source.type != "MESH"

    obj = bpy.data.objects.new(source.name, source.to_mesh(bpy.context.scene, True, "RENDER"))
    obj.draw_type = "WIRE"
    obj.parent = source.parent
    obj.matrix_local, obj.matrix_world = source.matrix_local, source.matrix_world

    bpy.context.scene.objects.link(obj)
    try:
        yield obj
    finally:
        bpy.data.objects.remove(obj)

def transform_mesh(mesh: bpy.types.Mesh, matrix: mathutils.Matrix):
    # There is a disparity in terms of how negative scaling is displayed in Blender versus how it is
    # applied (Ctrl+A) in that the normals are different. Even though negative scaling is evil, we
    # prefer to match the visual behavior, not the non-intuitive apply behavior. So, we'll need to
    # flip the normals if the scaling is negative. The Blender documentation even "helpfully" warns
    # us about this.
    mesh.transform(matrix)
    if matrix.is_negative:
        mesh.flip_normals()
