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
from mathutils import Matrix
import weakref
from PyHSPlasma import *

from . import utils

class ArmatureConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)

    def convert_armature_to_empties(self, bo):
        # Creates Blender equivalents to each bone of the armature, adjusting a whole bunch of stuff along the way.
        # Yes, this is ugly, but required to get anims to export properly. I tried other ways to export armatures,
        # but AFAICT sooner or later you have to implement similar hacks. Might as well create something that the
        # animation exporter can already deal with, with no modification...
        # Don't worry, we'll return a list of temporary objects to clean up after ourselves.
        armature = bo.data
        pose = bo.pose if armature.pose_position == "POSE" else None
        generated_bones = {} # name: Blender empty.
        temporary_objects = []
        for bone in armature.bones:
            if bone.parent:
                continue
            self._export_bone(bo, bone, bo, Matrix.Identity(4), pose, generated_bones, temporary_objects)

        if bo.plasma_modifiers.animation.enabled and bo.animation_data is not None and bo.animation_data.action is not None:
            # Let the anim exporter handle the anim crap.
            temporary_objects.extend(self._exporter().animation.copy_armature_animation_to_temporary_bones(bo, generated_bones))

        return temporary_objects

    def _export_bone(self, bo, bone, parent, matrix, pose, generated_bones, temporary_objects):
        bone_empty = bpy.data.objects.new(ArmatureConverter.get_bone_name(bo, bone), None)
        bpy.context.scene.objects.link(bone_empty)
        bone_empty.plasma_object.enabled = True

        # Grmbl, animation is relative to rest pose in Blender, and relative to parent in Plasma...
        # Using matrix_parent_inverse or manually adjust keyframes will just mess up rotation keyframes,
        # so let's just insert an extra empty object to correct all that. This is why the CoordinateInterface caches computed matrices, after all...
        bone_parent = bpy.data.objects.new(bone_empty.name + "_REST", None)
        bpy.context.scene.objects.link(bone_parent)
        bone_parent.plasma_object.enabled = True
        bone_parent.parent = parent
        bone_empty.parent = bone_parent
        bone_empty.matrix_local = Matrix.Identity(4)

        if pose is not None:
            pose_bone = pose.bones[bone.name]
            bone_empty.rotation_mode = pose_bone.rotation_mode
            pose_matrix = pose_bone.matrix_basis
        else:
            pose_bone = None
            pose_matrix = Matrix.Identity(4)

        temporary_objects.append(bone_empty)
        temporary_objects.append(bone_parent)
        generated_bones[bone.name] = bone_empty
        bone_parent.matrix_local = matrix * bone.matrix_local.to_4x4() * pose_matrix

        for child in bone.children:
            child_empty = self._export_bone(bo, child, bone_empty, bone.matrix_local.inverted(), pose, generated_bones, temporary_objects)
        return bone_empty

    @staticmethod
    def get_bone_name(bo, bone):
        if isinstance(bone, str):
            return "{}_{}".format(bo.name, bone)
        return "{}_{}".format(bo.name, bone.name)

    @property
    def _mgr(self):
        return self._exporter().mgr

    @property
    def _report(self):
        return self._exporter().report
