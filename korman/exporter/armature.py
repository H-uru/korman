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
        self._skinned_objects_modifiers = {}
        self._bones_local_to_world = {}

    def convert_armature_to_empties(self, bo, handle_temporary):
        # Creates Blender equivalents to each bone of the armature, adjusting a whole bunch of stuff along the way.
        # Yes, this is ugly, but required to get anims to export properly. I tried other ways to export armatures,
        # but AFAICT sooner or later you have to implement similar hacks. Might as well generate something that the
        # animation exporter can already deal with, with no modification...
        # Obviously the created objects will be cleaned up afterwards.
        armature = bo.data
        generated_bones = {} # name: Blender empty.
        temporary_bones = []
        # Note: ideally we would give the temporary bone objects to handle_temporary as soon as they are created.
        # However we need to delay until we actually create their animation modifiers, so that these get exported.
        try:
            for bone in armature.bones:
                if bone.parent:
                    continue
                self._export_bone(bo, bone, bo, Matrix.Identity(4), bo.pose, armature.pose_position == "POSE", generated_bones, temporary_bones)

            if bo.plasma_modifiers.animation.enabled and bo.animation_data is not None and bo.animation_data.action is not None:
                # Let the anim exporter handle the anim crap.
                self._exporter().animation.copy_armature_animation_to_temporary_bones(bo, generated_bones, handle_temporary)
        finally:
            for bone in temporary_bones:
                handle_temporary(bone)

    def get_bone_local_to_world(self, bo):
        return self._bones_local_to_world[bo]

    def get_skin_modifiers(self, bo):
        if self.is_skinned(bo):
            return self._skinned_objects_modifiers[bo]
        return []

    def is_skinned(self, bo):
        if bo.type != "MESH":
            return False
        if bo in self._skinned_objects_modifiers:
            return True

        # We need to cache the armature modifiers, because mesh.py will likely fiddle with them later.
        armatures = []
        for mod in bo.modifiers:
            # Armature modifiers only result in exporting skinning if they are linked to an exported armature.
            # If the armature is not exported, the deformation will simply get baked into the exported mesh.
            if mod.type == "ARMATURE" and mod.object is not None and mod.object.plasma_object.enabled and mod.use_vertex_groups and mod.show_render:
                armatures.append(mod)
        if len(armatures):
            self._skinned_objects_modifiers[bo] = armatures
            return True
        return False

    def _export_bone(self, bo, bone, parent, matrix, pose, pose_mode, generated_bones, temporary_bones):
        bone_empty = bpy.data.objects.new(ArmatureConverter.get_bone_name(bo, bone), None)
        bpy.context.scene.objects.link(bone_empty)
        bone_empty.plasma_object.enabled = True
        pose_bone = pose.bones[bone.name]
        bone_empty.rotation_mode = pose_bone.rotation_mode

        if pose_mode:
            pose_matrix = pose_bone.matrix_basis
        else:
            pose_matrix = Matrix.Identity(4)

        # Grmbl, animation is relative to rest pose in Blender, and relative to parent in Plasma...
        # Using matrix_parent_inverse or manually adjust keyframes will just mess up rotation keyframes,
        # so let's just insert an extra empty object to correct all that. This is why the CoordinateInterface caches computed matrices, after all...
        bone_parent = bpy.data.objects.new(bone_empty.name + "_REST", None)
        bpy.context.scene.objects.link(bone_parent)
        bone_parent.plasma_object.enabled = True
        bone_parent.parent = parent
        bone_empty.parent = bone_parent
        bone_empty.matrix_local = Matrix.Identity(4)
        temporary_bones.append(bone_parent)
        bone_parent.matrix_local = matrix * bone.matrix_local * pose_matrix
        # The bone's local to world matrix may change when we copy animations over, which we don't want.
        # Cache the matrix so we can use it when exporting meshes.
        self._bones_local_to_world[bone_empty] = bo.matrix_world * bone.matrix_local
        temporary_bones.append(bone_empty)
        generated_bones[bone.name] = bone_empty

        for child in bone.children:
            self._export_bone(bo, child, bone_empty, bone.matrix_local.inverted(), pose, pose_mode, generated_bones, temporary_bones)

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
