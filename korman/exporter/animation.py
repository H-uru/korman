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
import math
from PyHSPlasma import *
import weakref

class AnimationConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self._bl_fps = bpy.context.scene.render.fps

    def _check_scalar_subcontrollers(self, ctrl, default_xform):
        """Ensures that all scalar subcontrollers have at least one keyframe in the default state"""
        for i in ("X", "Y", "Z"):
            sub = getattr(ctrl, i)
            if not sub.hasKeys():
                keyframe = hsScalarKey()
                keyframe.frame = 0
                keyframe.frameTime = 0.0
                keyframe.type = hsKeyFrame.kScalarKeyFrame
                keyframe.value = getattr(default_xform, i.lower())
                sub.keys = ([keyframe,], hsKeyFrame.kScalarKeyFrame)

    def convert_action2tm(self, action, default_xform):
        """Converts a Blender Action to a plCompoundController."""
        fcurves = action.fcurves
        if not fcurves:
            return None

        # NOTE: plCompoundController is from Myst 5 and was backported to MOUL.
        # Worry not however... libHSPlasma will do the conversion for us.
        tm = plCompoundController()
        tm.X = self.make_pos_controller(fcurves, default_xform)
        tm.Y = self.make_rot_controller(fcurves, default_xform)
        tm.Z = self.make_scale_controller(fcurves, default_xform)
        return tm

    def _is_bezier_curve(self, keyframes):
        for i in keyframes:
            if i.interpolation == "BEZIER":
                return True
        return False

    def make_pos_controller(self, fcurves, default_xform):
        pos_curves = (i for i in fcurves if i.data_path == "location" and i.keyframe_points)
        ctrl = self.make_scalar_controller(pos_curves)
        if ctrl is not None and default_xform is not None:
            self._check_scalar_subcontrollers(ctrl, default_xform.to_transpose())

    def make_rot_controller(self, fcurves, default_xform):
        rot_curves = (i for i in fcurves if i.data_path == "rotation_euler" and i.keyframe_points)
        ctrl = self.make_scalar_controller(rot_curves)
        if ctrl is not None and default_xform is not None:
            self._check_scalar_subcontrollers(ctrl, default_xform.to_euler("XYZ"))
        return ctrl

    def make_scale_controller(self, fcurves, default_xform):
        # ... TODO ...
        # who needs this anyway?
        return None

    def make_scalar_controller(self, fcurves):
        ctrl = plCompoundController()
        subctls = ("X", "Y", "Z")

        # this ensures that all subcontrollers are populated -- otherwise KABLOOEY!
        for i in subctls:
            setattr(ctrl, i, plLeafController())

        for fcurve in fcurves:
            fcurve.update()
            if self._is_bezier_curve(fcurve.keyframe_points):
                key_type = hsKeyFrame.kScalarKeyFrame
            else:
                key_type = hsKeyFrame.kBezScalarKeyFrame
            frames = []
            pi = math.pi
            fps = self._bl_fps

            for i in fcurve.keyframe_points:
                bl_frame_num, value = i.co
                frame = hsScalarKey()
                if i.interpolation == "BEZIER":
                    frame.inTan = -(value - i.handle_left[1])  / (bl_frame_num - i.handle_left[0])  / fps / (2 * pi)
                    frame.outTan = (value - i.handle_right[1]) / (bl_frame_num - i.handle_right[0]) / fps / (2 * pi)
                else:
                    frame.inTan = 0.0
                    frame.outTan = 0.0
                frame.type = key_type
                frame.frame = int(bl_frame_num * (30.0 / fps))
                frame.frameTime = bl_frame_num / fps
                frame.value = value
                frames.append(frame)
            controller = plLeafController()
            getattr(ctrl, subctls[fcurve.array_index]).keys = (frames, key_type)

        # Compact this bamf
        if not ctrl.X.hasKeys() and not ctrl.Y.hasKeys() and not ctrl.Z.hasKeys():
            return None
        else:
            return ctrl

    @property
    def _mgr(self):
        return self._exporter().mgr
