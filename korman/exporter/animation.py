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
import mathutils
from PyHSPlasma import *
import weakref

from . import utils

class AnimationConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self._bl_fps = bpy.context.scene.render.fps

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

    def make_pos_controller(self, fcurves, default_xform):
        pos_curves = [i for i in fcurves if i.data_path == "location" and i.keyframe_points]
        keyframes, bez_chans = self._process_keyframes(pos_curves)
        if not keyframes:
            return None

        # At one point, I had some... insanity here to try to crush bezier channels and hand off to
        # blah blah blah... As it turns out, point3 keyframe's tangents are vector3s :)
        ctrl = self._make_point3_controller(pos_curves, keyframes, bez_chans, default_xform.to_translation())
        return ctrl

    def make_rot_controller(self, fcurves, default_xform):
        # TODO: support rotation_quaternion
        rot_curves = [i for i in fcurves if i.data_path == "rotation_euler" and i.keyframe_points]
        keyframes, bez_chans = self._process_keyframes(rot_curves)
        if not keyframes:
            return None

        # Ugh. Unfortunately, it appears Blender's default interpolation is bezier. So who knows if
        # many users will actually see the benefit here? Makes me sad.
        if bez_chans:
            ctrl = self._make_scalar_controller(rot_curves, keyframes, bez_chans, default_xform.to_euler())
        else:
            ctrl = self._make_quat_controller(rot_curves, keyframes, default_xform.to_euler())
        return ctrl

    def make_scale_controller(self, fcurves, default_xform):
        scale_curves = [i for i in fcurves if i.data_path == "scale" and i.keyframe_points]
        keyframes, bez_chans = self._process_keyframes(scale_curves)
        if not keyframes:
            return None

        # There is no such thing as a compound scale controller... in Plasma, anyway.
        ctrl = self._make_scale_value_controller(scale_curves, keyframes, bez_chans, default_xform)
        return ctrl

    def _make_point3_controller(self, fcurves, keyframes, bezier, default_xform):
        ctrl = plLeafController()
        subctrls = ("X", "Y", "Z")
        keyframe_type = hsKeyFrame.kBezPoint3KeyFrame if bezier else hsKeyFrame.kPoint3KeyFrame
        exported_frames = []
        ctrl_fcurves = { i.array_index: i for i in fcurves }

        for keyframe in keyframes:
            exported = hsPoint3Key()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.type = keyframe_type

            in_tan = hsVector3()
            out_tan = hsVector3()
            value = hsVector3()
            for i, subctrl in enumerate(subctrls):
                fval = keyframe.values.get(i, None)
                if fval is not None:
                    setattr(value, subctrl, fval)
                    setattr(in_tan, subctrl, keyframe.in_tans[i])
                    setattr(out_tan, subctrl, keyframe.out_tans[i])
                else:
                    try:
                        setattr(value, subctrl, ctrl_fcurves[i].evaluate(keyframe.frame_num_blender))
                    except KeyError:
                        setattr(value, subctrl, default_xform[i])
                    setattr(in_tan, subctrl, 0.0)
                    setattr(out_tan, subctrl, 0.0)
            exported.inTan = in_tan
            exported.outTan = out_tan
            exported.value = value
            exported_frames.append(exported)
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _make_quat_controller(self, fcurves, keyframes, default_xform):
        ctrl = plLeafController()
        keyframe_type = hsKeyFrame.kQuatKeyFrame
        exported_frames = []
        ctrl_fcurves = { i.array_index: i for i in fcurves }

        for keyframe in keyframes:
            exported = hsQuatKey()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.type = keyframe_type
            # NOTE: quat keyframes don't do bezier nonsense

            value = mathutils.Euler()
            for i in range(3):
                fval = keyframe.values.get(i, None)
                if fval is not None:
                    value[i] = fval
                else:
                    try:
                        value[i] = ctrl_fcurves[i].evaluate(keyframe.frame_num_blender)
                    except KeyError:
                        value[i] = default_xform[i]
            quat = value.to_quaternion()
            exported.value = utils.quaternion(quat)
            exported_frames.append(exported)
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _make_scalar_controller(self, fcurves, keyframes, bez_chans, default_xform):
        ctrl = plCompoundController()
        subctrls = ("X", "Y", "Z")
        for i in subctrls:
            setattr(ctrl, i, plLeafController())
        exported_frames = ([], [], [])
        ctrl_fcurves = { i.array_index: i for i in fcurves }

        for keyframe in keyframes:
            for i, subctrl in enumerate(subctrls):
                fval = keyframe.values.get(i, None)
                if fval is not None:
                    keyframe_type = hsKeyFrame.kBezScalarKeyFrame if i in bez_chans else hsKeyFrame.kScalarKeyFrame
                    exported = hsScalarKey()
                    exported.frame = keyframe.frame_num
                    exported.frameTime = keyframe.frame_time
                    exported.inTan = keyframe.in_tans[i]
                    exported.outTan = keyframe.out_tans[i]
                    exported.type = keyframe_type
                    exported.value = fval
                    exported_frames[i].append(exported)
        for i, subctrl in enumerate(subctrls):
            my_keyframes = exported_frames[i]

            # ensure this controller has at least ONE keyframe
            if not my_keyframes:
                hack_frame = hsScalarKey()
                hack_frame.frame = 0
                hack_frame.frameTime = 0.0
                hack_frame.type = hsKeyFrame.kScalarKeyFrame
                hack_frame.value = default_xform[i]
                my_keyframes.append(hack_frame)
            getattr(ctrl, subctrl).keys = (my_keyframes, my_keyframes[0].type)
        return ctrl

    def _make_scale_value_controller(self, fcurves, keyframes, bez_chans, default_xform):
        subctrls = ("X", "Y", "Z")
        keyframe_type = hsKeyFrame.kBezScaleKeyFrame if bez_chans else hsKeyFrame.kScaleKeyFrame
        exported_frames = []
        ctrl_fcurves = { i.array_index: i for i in fcurves }

        default_scale = default_xform.to_scale()
        unit_quat = default_xform.to_quaternion()
        unit_quat.normalize()
        unit_quat = utils.quaternion(unit_quat)

        for keyframe in keyframes:
            exported = hsScaleKey()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.type = keyframe_type

            in_tan = hsVector3()
            out_tan = hsVector3()
            value = hsVector3()
            for i, subctrl in enumerate(subctrls):
                fval = keyframe.values.get(i, None)
                if fval is not None:
                    setattr(value, subctrl, fval)
                    setattr(in_tan, subctrl, keyframe.in_tans[i])
                    setattr(out_tan, subctrl, keyframe.out_tans[i])
                else:
                    try:
                        setattr(value, subctrl, ctrl_fcurves[i].evaluate(keyframe.frame_num_blender))
                    except KeyError:
                        setattr(value, subctrl, default_scale[i])
                    setattr(in_tan, subctrl, 0.0)
                    setattr(out_tan, subctrl, 0.0)
            exported.inTan = in_tan
            exported.outTan = out_tan
            exported.value = (value, unit_quat)
            exported_frames.append(exported)

        ctrl = plLeafController()
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _process_keyframes(self, fcurves):
        """Groups all FCurves for the same frame together"""
        keyframe_data = type("KeyFrameData", (), {})
        fps = self._bl_fps
        pi = math.pi

        keyframes = {}
        bez_chans = set()
        for fcurve in fcurves:
            fcurve.update()
            for fkey in fcurve.keyframe_points:
                frame_num, value = fkey.co
                keyframe = keyframes.get(frame_num, None)
                if keyframe is None:
                    keyframe = keyframe_data()
                    if fps == 30.0:
                        # hope you don't have a frame 29.9 and frame 30.0...
                        keyframe.frame_num = int(frame_num)
                    else:
                        keyframe.frame_num = int(frame_num * (30.0 / fps))
                    keyframe.frame_num_blender = frame_num
                    keyframe.frame_time = frame_num / fps
                    keyframe.in_tans = {}
                    keyframe.out_tans = {}
                    keyframe.values = {}
                    keyframes[frame_num] = keyframe
                idx = fcurve.array_index
                keyframe.values[idx] = value

                # Calculate the bezier interpolation nonsense
                if fkey.interpolation == "BEZIER":
                    keyframe.in_tans[idx] = -(value - fkey.handle_left[1])  / (frame_num - fkey.handle_left[0])  / fps / (2 * pi)
                    keyframe.out_tans[idx] = (value - fkey.handle_right[1]) / (frame_num - fkey.handle_right[0]) / fps / (2 * pi)
                    bez_chans.add(idx)
                else:
                    keyframe.in_tans[idx] = 0.0
                    keyframe.out_tans[idx] = 0.0

        # Return the keyframes in a sequence sorted by frame number
        final_keyframes = [keyframes[i] for i in sorted(keyframes)]
        return (final_keyframes, bez_chans)

    @property
    def _mgr(self):
        return self._exporter().mgr
