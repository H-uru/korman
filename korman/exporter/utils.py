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
from typing import Callable
from contextlib import contextmanager

from PyHSPlasma import *

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


@contextmanager
def bmesh_temporary_object(name : str, factory : Callable, page_name : str=None):
    """Creates a temporary object and mesh that exists only for the duration of
       the context"""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.draw_type = "WIRE"
    if page_name is not None:
        obj.plasma_object.page = page_name
    bpy.context.scene.objects.link(obj)

    bm = bmesh.new()
    try:
        factory(bm)
        bm.to_mesh(mesh)
        yield obj
    finally:
        bm.free()
        bpy.context.scene.objects.unlink(obj)

@contextmanager
def bmesh_object(name : str):
    """Creates an object and mesh that will be removed if the context is exited
       due to an error"""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.draw_type = "WIRE"
    bpy.context.scene.objects.link(obj)

    bm = bmesh.new()
    try:
        yield obj, bm
    except:
        bpy.context.scene.objects.unlink(obj)
        bpy.data.meshes.remove(mesh)
        raise
    else:
        bm.to_mesh(mesh)
    finally:
        bm.free()
