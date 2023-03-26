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

from collections import defaultdict
import functools
import itertools
import math
import mathutils
from typing import *
import weakref

from PyHSPlasma import *

from . import utils

class AnimationConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self._bl_fps = bpy.context.scene.render.fps

    def convert_frame_time(self, frame_num: int) -> float:
        return frame_num / self._bl_fps

    def convert_object_animations(self, bo: bpy.types.Object, so: plSceneObject, anim_name: str, *,
                                  start: Optional[int] = None, end: Optional[int] = None) -> Iterable[plAGApplicator]:
        if not bo.plasma_object.has_animation_data:
            return []

        def fetch_animation_data(id_data):
            if id_data is not None:
                if id_data.animation_data is not None:
                    action = id_data.animation_data.action
                    return action, getattr(action, "fcurves", [])
            return None, []

        obj_action, obj_fcurves = fetch_animation_data(bo)
        data_action, data_fcurves = fetch_animation_data(bo.data)

        # We're basically just going to throw all the FCurves at the controller converter (read: wall)
        # and see what sticks. PlasmaMAX has some nice animation channel stuff that allows for some
        # form of separation, but Blender's NLA editor is way confusing and appears to not work with
        # things that aren't the typical position, rotation, scale animations.
        applicators = []
        if isinstance(bo.data, bpy.types.Camera):
            applicators.append(self._convert_camera_animation(bo, so, obj_fcurves, data_fcurves, anim_name, start, end))
        else:
            applicators.append(self._convert_transform_animation(bo, obj_fcurves, bo.matrix_local, bo.matrix_parent_inverse, start=start, end=end))
        if bo.plasma_modifiers.soundemit.enabled:
            applicators.extend(self._convert_sound_volume_animation(bo.name, obj_fcurves, bo.plasma_modifiers.soundemit, start, end))
        if isinstance(bo.data, bpy.types.Lamp):
            lamp = bo.data
            applicators.extend(self._convert_lamp_color_animation(bo.name, data_fcurves, lamp, start, end))
            if isinstance(lamp, bpy.types.SpotLamp):
                applicators.extend(self._convert_spot_lamp_animation(bo.name, data_fcurves, lamp, start, end))
            if isinstance(lamp, bpy.types.PointLamp):
                applicators.extend(self._convert_omni_lamp_animation(bo.name, data_fcurves, lamp, start, end))

        return [i for i in applicators if i is not None]

    def _convert_camera_animation(self, bo, so, obj_fcurves, data_fcurves, anim_name: str,
                                  start: Optional[int], end: Optional[int]):
        has_fov_anim = False
        if data_fcurves:
            # The hard part about this crap is that FOV animations are not stored in ATC Animations
            # instead, FOV animation keyframes are held inside of the camera modifier. Cyan's solution
            # in PlasmaMAX appears to be for any xform keyframe, add two messages to the camera modifier
            # representing the FOV at that point. Makes more sense to me to use each FOV keyframe instead
            fov_fcurve = next((i for i in data_fcurves if i.data_path == "plasma_camera.settings.fov"), None)
            if fov_fcurve:
                # NOTE: this is another critically important key ordering in the SceneObject modifier
                #       list. CameraModifier calls into AGMasterMod code that assumes the AGModifier
                #       is already available. Should probably consider adding some code to libHSPlasma
                #       to order the SceneObject modifier key vector at some point.
                anim_key = self.get_animation_key(bo)
                camera = self._mgr.find_create_object(plCameraModifier, so=so)
                cam_key = camera.key
                aspect, fps = (3.0 / 4.0), self._bl_fps
                degrees = math.degrees
                fov_fcurve.update()


                # Well, now that we have multiple animations, we are using our fancier FCurve processing.
                # Unfortunately, the code still looks like sin. What can you do?
                keyframes, _ = self._process_fcurve(fov_fcurve, start=start, end=end)
                num_keyframes = len(keyframes)

                has_fov_anim = bool(num_keyframes)
                i = 0
                while i < num_keyframes:
                    # So remember, these are messages. When we hit a keyframe, we're dispatching a message
                    # representing the NEXT desired FOV.
                    this_keyframe = keyframes[i]
                    next_keyframe = keyframes[0] if i+1 == num_keyframes else keyframes[i+1]

                    # This message is held on the camera modifier and sent to the animation... It calls
                    # back when the animation reaches the keyframe time, causing the FOV message to be sent.
                    # This should be exported per-animation because it will be specific to each ATC.
                    cb_msg = plEventCallbackMsg()
                    cb_msg.event = kTime
                    cb_msg.eventTime = this_keyframe.frame_time
                    cb_msg.index = i
                    cb_msg.repeats = -1
                    cb_msg.addReceiver(cam_key)
                    anim_msg = plAnimCmdMsg()
                    anim_msg.animName = anim_name
                    anim_msg.time = this_keyframe.frame_time
                    anim_msg.sender = anim_key
                    anim_msg.addReceiver(anim_key)
                    anim_msg.addCallback(cb_msg)
                    anim_msg.setCmd(plAnimCmdMsg.kAddCallbacks, True)
                    camera.addMessage(anim_msg, anim_key)

                    # This is the message actually changes the FOV. Interestingly, it is sent at
                    # export-time and while playing the game, the camera modifier just steals its
                    # parameters and passes them to the brain. Can't make this stuff up.
                    # Be sure to only export each instruction once.
                    if not any((msg.config.accel == next_keyframe.frame_time for msg in camera.fovInstructions)):
                        cam_msg = plCameraMsg()
                        cam_msg.addReceiver(cam_key)
                        cam_msg.setCmd(plCameraMsg.kAddFOVKeyFrame, True)
                        cam_config = cam_msg.config
                        cam_config.accel = next_keyframe.frame_time # Yassss...
                        cam_config.fovW = degrees(next_keyframe.values[0])
                        cam_config.fovH = degrees(next_keyframe.values[0] * aspect)
                        camera.addFOVInstruction(cam_msg)

                    i += 1

        # If we exported any FOV animation at all, then we need to ensure there is an applicator
        # returned from here... At bare minimum, we'll need the applicator with an empty
        # CompoundController. This should be sufficient to keep CWE from crashing...
        applicator = self._convert_transform_animation(bo, obj_fcurves, bo.matrix_local, bo.matrix_parent_inverse,
                                                       allow_empty=has_fov_anim, start=start, end=end)
        camera = self._mgr.find_create_object(plCameraModifier, so=so)
        camera.animated = applicator is not None
        return applicator

    def _convert_lamp_color_animation(self, name, fcurves, lamp, start, end):
        if not fcurves:
            return None

        energy_curve = next((i for i in fcurves if i.data_path == "energy" and i.keyframe_points), None)
        color_curves = [i for i in fcurves if i.data_path == "color" and i.keyframe_points]
        if energy_curve is None and color_curves is None:
            return None
        elif lamp.use_only_shadow:
            self._exporter().report.warn("Cannot animate Lamp color because this lamp only casts shadows")
            return None
        elif not lamp.use_specular and not lamp.use_diffuse:
            self._exporter().report.warn("Cannot animate Lamp color because neither Diffuse nor Specular are enabled")
            return None

        # OK Specular is easy. We just toss out the color as a point3.
        def convert_specular_animation(color):
            if lamp.use_negative:
                return map(lambda x: x * -1.0, color)
            else:
                return color
        color_keyframes, color_bez = self._process_keyframes(color_curves, 3, lamp.color,
                                                             convert=convert_specular_animation,
                                                             start=start, end=end)
        if color_keyframes and lamp.use_specular:
            channel = plPointControllerChannel()
            channel.controller = self._make_point3_controller(color_keyframes, color_bez)
            applicator = plLightSpecularApplicator()
            applicator.channelName = name
            applicator.channel = channel
            yield applicator

        # Hey, look, it's a third way to process FCurves. YAY!
        def convert_diffuse_animation(color, energy):
            if lamp.use_negative:
                proc = lambda x: x * -1.0 * energy[0]
            else:
                proc = lambda x: x * energy[0]
            return map(proc, color)
        diffuse_channels = dict(color=3, energy=1)
        diffuse_defaults = dict(color=lamp.color, energy=lamp.energy)
        diffuse_fcurves = color_curves + [energy_curve,]
        diffuse_keyframes = self._process_fcurves(diffuse_fcurves, diffuse_channels, 3,
                                                  convert_diffuse_animation, diffuse_defaults,
                                                  start=start, end=end)
        if not diffuse_keyframes:
            return None

        # Whew.
        channel = plPointControllerChannel()
        channel.controller = self._make_point3_controller(diffuse_keyframes, False)
        applicator = plLightDiffuseApplicator()
        applicator.channelName = name
        applicator.channel = channel
        yield applicator

    def _convert_omni_lamp_animation(self, name, fcurves, lamp, start, end):
        if not fcurves:
            return None

        energy_fcurve = next((i for i in fcurves if i.data_path == "energy"), None)
        distance_fcurve = next((i for i in fcurves if i.data_path == "distance"), None)
        if energy_fcurve is None and distance_fcurve is None:
            return None

        light_converter, report = self._exporter().light, self._exporter().report
        omni_fcurves = [distance_fcurve, energy_fcurve]
        omni_channels = dict(distance=1, energy=1)
        omni_defaults = dict(distance=lamp.distance, energy=lamp.energy)

        def convert_omni_atten(distance, energy):
            intens = abs(energy[0])
            atten_end = distance[0] if lamp.use_sphere else distance[0] * 2
            return light_converter.convert_attenuation_linear(intens, atten_end)

        # All types allow animating cutoff
        if distance_fcurve is not None:
            channel = plScalarControllerChannel()
            channel.controller = self.make_scalar_leaf_controller(distance_fcurve,
                                                                  lambda x: x if lamp.use_sphere else x * 2,
                                                                  start=start, end=end)
            applicator = plOmniCutoffApplicator()
            applicator.channelName = name
            applicator.channel = channel
            yield applicator

        falloff = lamp.falloff_type
        if falloff == "CONSTANT":
            if energy_fcurve is not None:
                report.warn("Constant attenuation cannot be animated in Plasma", ident=3)
        elif falloff == "INVERSE_LINEAR":
            keyframes = self._process_fcurves(omni_fcurves, omni_channels, 1, convert_omni_atten,
                                              omni_defaults, start=start, end=end)
            if keyframes:
                channel = plScalarControllerChannel()
                channel.controller = self._make_scalar_leaf_controller(keyframes, False)
                applicator = plOmniApplicator()
                applicator.channelName = name
                applicator.channel = channel
                yield applicator
        elif falloff == "INVERSE_SQUARE":
            if self._mgr.getVer() >= pvMoul:
                report.port(f"Lamp {falloff} Falloff animations are only supported in Myst Online: Uru Live")
                keyframes = self._process_fcurves(omni_fcurves, omni_channels, 1, convert_omni_atten,
                                                  omni_defaults, start=start, end=end)
                if keyframes:
                    channel = plScalarControllerChannel()
                    channel.controller = self._make_scalar_leaf_controller(keyframes, False)
                    applicator = plOmniSqApplicator()
                    applicator.channelName = name
                    applicator.channel = channel
                    yield applicator
            else:
                report.warn(f"Lamp {falloff} Falloff animations are not supported for this version of Plasma")
        else:
            report.warn("Lamp Falloff '{}' animations are not supported", falloff, ident=3)

    def _convert_sound_volume_animation(self, name, fcurves, soundemit, start, end):
        if not fcurves:
            return None

        convert_volume = lambda x: math.log10(max(.01, x / 100.0)) * 20.0

        for sound in soundemit.sounds:
            path = "{}.volume".format(sound.path_from_id())
            fcurve = next((i for i in fcurves if i.data_path == path and i.keyframe_points), None)
            if fcurve is None:
                continue

            for i in soundemit.get_sound_indices(sound=sound):
                applicator = plSoundVolumeApplicator()
                applicator.channelName = name
                applicator.index = i

                # libHSPlasma assumes a channel is not shared among applicators...
                # so yes, we must convert the same animation data again and again.
                # To make matters worse, the way that these keyframes are stored can cause
                # the animation to evaluate to a no-op. Be ready for that.
                controller = self.make_scalar_leaf_controller(fcurve, convert=convert_volume, start=start, end=end)
                if controller is not None:
                    channel = plScalarControllerChannel()
                    channel.controller = controller
                    applicator.channel = channel
                    yield applicator
                else:
                    self._exporter().report.warn(f"[{sound.sound.name}]: Volume animation evaluated to zero keyframes!")
                    break

    def _convert_spot_lamp_animation(self, name, fcurves, lamp, start, end):
        if not fcurves:
            return None

        blend_fcurve = next((i for i in fcurves if i.data_path == "spot_blend"), None)
        size_fcurve = next((i for i in fcurves if i.data_path == "spot_size"), None)
        if blend_fcurve is None and size_fcurve is None:
            return None

        # Spot Outer is just the size keyframes...
        if size_fcurve is not None:
            channel = plScalarControllerChannel()
            channel.controller = self.make_scalar_leaf_controller(size_fcurve, lambda x: math.degrees(x),
                                                                  start=start, end=end)
            applicator = plSpotOuterApplicator()
            applicator.channelName = name
            applicator.channel = channel
            yield applicator

        # Spot inner must be calculated...
        def convert_spot_inner(spot_blend, spot_size):
            blend = min(0.001, spot_blend[0])
            size = spot_size[0]
            value = size - (blend * size)
            return math.degrees(value)

        inner_fcurves = [blend_fcurve, size_fcurve]
        inner_channels = dict(spot_blend=1, spot_size=1)
        inner_defaults = dict(spot_blend=lamp.spot_blend, spot_size=lamp.spot_size)
        keyframes = self._process_fcurves(inner_fcurves, inner_channels, 1, convert_spot_inner,
                                          inner_defaults, start=start, end=end)

        if keyframes:
            channel = plScalarControllerChannel()
            channel.controller = self._make_scalar_leaf_controller(keyframes, False)
            applicator = plSpotInnerApplicator()
            applicator.channelName = name
            applicator.channel = channel
            yield applicator

    def _convert_transform_animation(self, bo, fcurves, default_xform, adjust_xform, *, allow_empty: Optional[bool] = False,
                                     start: Optional[int] = None, end: Optional[int] = None) -> Optional[plMatrixChannelApplicator]:
        if adjust_xform != mathutils.Matrix.Identity(4):
            self._exporter().report.warn(
                f"'{bo.name}': Transform animation is not local and may export incorrectly. "
                "Please use Alt-P -> Clear Parent Inverse before animating objects to avoid issues."
            )
        else:
            # Adjustment matrix is identity, just pass None instead...
            adjust_xform = None

        tm = self.convert_transform_controller(fcurves, bo.rotation_mode, default_xform, adjust_xform, allow_empty=allow_empty,
                                               start=start, end=end)
        if tm is None and not allow_empty:
            return None

        applicator = plMatrixChannelApplicator()
        applicator.enabled = True
        applicator.channelName = bo.name
        channel = plMatrixControllerChannel()
        channel.controller = tm
        applicator.channel = channel
        channel.affine = utils.affine_parts(default_xform)

        return applicator

    def convert_transform_controller(self, fcurves, rotation_mode: str, default_xform, adjust_xform, *,
                                     allow_empty: Optional[bool] = False,
                                     start: Optional[int] = None,
                                     end: Optional[int] = None) -> Union[None, plCompoundController]:
        if not fcurves and not allow_empty:
            return None

        if adjust_xform is not None:
            # We have to edit the keyframes to make the anim local..
            # In many cases this should work fine, but sometimes scale and rotation might
            # still cause issues. Also, euler angles need to be converted to quaternion
            # and back to eulers, which could cause issues. Not much we can do about it.
            adjust_rotation = adjust_xform.to_quaternion()
            adjust_scale = adjust_xform.to_scale()

            # Helpers to adjust keyframes in case animation is not local (adjust_xform == identity)
            def convert_pos_keyframe(pos):
                # Position: can transform to local space without issues.
                return tuple(adjust_xform * mathutils.Vector(pos))

            def convert_rot_keyframe(rot):
                # Rotation: may cause issues if scale is present.
                if isinstance(rot, mathutils.Quaternion): # quaternion from an axis-angle
                    return adjust_rotation * rot
                elif isinstance(rot, mathutils.Euler):
                    return (adjust_rotation * rot.to_quaternion()).to_euler(rot.order)
                else: # tuple
                    if len(rot) == 4: # quat in a tuple
                        return (adjust_rotation * mathutils.Quaternion(rot))[:]
                    else: # XYZ euler in a tuple
                        rot = mathutils.Euler(rot, "XYZ").to_quaternion()
                        return (adjust_rotation * rot).to_euler("XYZ")[:]

            def convert_scale_keyframe(scale):
                # Scale: very likely to cause issues.
                return [a * b for a, b in zip(adjust_scale, scale)]

            convert_pos = convert_pos_keyframe
            convert_rot = convert_rot_keyframe
            convert_scale = convert_scale_keyframe
        else:
            # Don't change the keyframes at all, so we don't risk screwing them up.
            convert_pos = None
            convert_rot = None
            convert_scale = None

        pos = self.make_pos_controller(fcurves, "location", default_xform.to_translation(),
                                       convert=convert_pos, start=start, end=end)
        rot = self.make_rot_controller(fcurves, rotation_mode, default_xform,
                                       convert=convert_rot, start=start, end=end)
        scale = self.make_scale_controller(fcurves, "scale", default_xform.to_scale(),
                                           convert=convert_scale, start=start, end=end)
        if pos is None and rot is None and scale is None:
            if not allow_empty:
                return None

        tm = plCompoundController()
        tm.X = pos
        tm.Y = rot
        tm.Z = scale
        return tm

    def get_anigraph_keys(self, bo=None, so=None) -> Tuple[plKey, plKey]:
        mod = self._mgr.find_create_key(plAGModifier, so=so, bl=bo)
        master = self._mgr.find_create_key(plAGMasterMod, so=so, bl=bo)
        return mod, master

    def get_anigraph_objects(self, bo=None, so=None) -> Tuple[plAGModifier, plAGMasterMod]:
        mod = self._mgr.find_create_object(plAGModifier, so=so, bl=bo)
        master = self._mgr.find_create_object(plAGMasterMod, so=so, bl=bo)
        return mod, master

    def get_animation_key(self, bo, so=None) -> plKey:
        # we might be controlling more than one animation. isn't that cute?
        # https://www.youtube.com/watch?v=hspNaoxzNbs
        # (but obviously this is not wrong...)
        group_mod = bo.plasma_modifiers.animation_group
        if group_mod.enabled:
            return self._mgr.find_create_key(plMsgForwarder, bl=bo, so=so, name=group_mod.key_name)
        else:
            return self.get_anigraph_keys(bo, so)[1]

    def get_frame_time_range(self, *anims: Iterable[Union[plAGApplicator, plController]],
                             so: Optional[plSceneObject] = None, name: Optional[str] = None) -> Tuple[int, int]:
        """Determines the range of frame numbers in an exported animation."""
        def iter_frame_times():
            nonlocal name
            for anim in anims:
                if isinstance(anim, plAGApplicator):
                    anim = anim.channel.controller
                if anim is None:
                    # Maybe a camera FOV thing, or something.
                    continue

                def iter_leaves(ctrl: Optional[plController]) -> Iterator[plLeafController]:
                    if ctrl is None:
                        return
                    elif isinstance(ctrl, plCompoundController):
                        yield from iter_leaves(ctrl.X)
                        yield from iter_leaves(ctrl.Y)
                        yield from iter_leaves(ctrl.Z)
                    elif isinstance(ctrl, plLeafController):
                        yield ctrl
                    else:
                        raise ValueError(ctrl)

                yield from (key.frameTime for leaf in iter_leaves(anim) for key in leaf.keys[0])

                # Special case: camera animations are over on the plCameraModifier. Grr.
                if so is not None:
                    camera = self._mgr.find_object(plCameraModifier, so=so)
                    if camera is not None:
                        if not name:
                            name = "(Entire Animation)"
                        yield from (msg.time for msg, _ in camera.messageQueue if isinstance(msg, plAnimCmdMsg) and msg.animName == name)

        try:
            return min(iter_frame_times()), max(iter_frame_times())
        except ValueError:
            return 0.0, 0.0

    def make_matrix44_controller(self, fcurves, pos_path: str, scale_path: str, pos_default, scale_default,
                                 *, start: Optional[int] = None, end: Optional[int] = None) -> Optional[plLeafController]:
        def convert_matrix_keyframe(**kwargs) -> hsMatrix44:
            pos = kwargs[pos_path]
            scale = kwargs[scale_path]

            translation = hsVector3(pos[0] - (scale[0] - 1.0) / 2.0,
                                    -pos[1] - (scale[1] - 1.0) / 2.0,
                                    pos[2] - (scale[2] - 1.0) / 2.0)
            matrix = hsMatrix44()
            matrix.setTranslate(translation)
            matrix.setScale(hsVector3(*scale))
            return matrix

        fcurves = [i for i in fcurves if i.data_path == pos_path or i.data_path == scale_path]
        if not fcurves:
            return None

        channels = { pos_path: 3, scale_path: 3 }
        default_values = { pos_path: pos_default, scale_path: scale_default }
        keyframes = self._process_fcurves(fcurves, channels, 1, convert_matrix_keyframe,
                                          default_values, start=start, end=end)
        if not keyframes:
            return None

        # Now we make the controller
        return self._make_matrix44_controller(keyframes)

    def make_pos_controller(self, fcurves, data_path: str, default_xform,
                            convert: Optional[Callable] = None, *, start: Optional[int] = None,
                            end: Optional[int] = None) -> Optional[plLeafController]:
        pos_curves = [i for i in fcurves if i.data_path == data_path and i.keyframe_points]
        keyframes, bez_chans = self._process_keyframes(pos_curves, 3, default_xform, convert,
                                                       start=start, end=end)
        if not keyframes:
            return None

        # At one point, I had some... insanity here to try to crush bezier channels and hand off to
        # blah blah blah... As it turns out, point3 keyframe's tangents are vector3s :)
        ctrl = self._make_point3_controller(keyframes, bez_chans)
        return ctrl

    def make_rot_controller(self, fcurves, rotation_mode: str, default_xform,
                            convert: Optional[Callable] = None, *, start: Optional[int] = None,
                            end: Optional[int] = None) -> Union[None, plCompoundController, plLeafController]:
        if rotation_mode in {"AXIS_ANGLE", "QUATERNION"}:
            rot_curves = [i for i in fcurves if i.data_path == "rotation_{}".format(rotation_mode.lower()) and i.keyframe_points]
            if not rot_curves:
                return None

            default_xform = default_xform.to_quaternion()
            if rotation_mode == "AXIS_ANGLE":
                default_xform = default_xform.to_axis_angle()
                default_xform = (default_xform[1], default_xform[0].x, default_xform[0].y, default_xform[0].z)

                if convert is not None:
                    convert_original = convert
                    convert = lambda x: convert_original(mathutils.Quaternion(x[1:4], x[0]))[:]
                else:
                    convert = lambda x: mathutils.Quaternion(x[1:4], x[0])[:]

            # Just dropping bezier stuff on the floor because Plasma does not support it, and
            # I think that opting into quaternion keyframes is a good enough indication that
            # you're OK with that.
            keyframes, bez_chans = self._process_keyframes(rot_curves, 4, default_xform, convert,
                                                           start=start, end=end)
            if keyframes:
                return self._make_quat_controller(keyframes)
        else:
            rot_curves = [i for i in fcurves if i.data_path == "rotation_euler" and i.keyframe_points]
            if not rot_curves:
                return None

            # OK, so life is complicated with Euler keyframes because apparently they can store
            # different "orders" that really only become apparent when the engine converts them
            # into a quaternion to use in an animation. Converting orders isn't as simple as swapping
            # XYZ around, so we have to bus this through quaternion??? Ugh.
            def convert_euler_keyframe(euler_array: Tuple[float, float, float]):
                euler = mathutils.Euler(euler_array, rotation_mode)
                result = euler.to_quaternion().to_euler("XYZ")
                if convert is not None:
                    result = convert(result)
                return result[:]

            euler_convert = convert_euler_keyframe if rotation_mode != "XYZ" else convert
            keyframes, bez_chans = self._process_keyframes(rot_curves, 3, default_xform.to_euler(rotation_mode),
                                                           euler_convert, start=start, end=end)
            if keyframes:
                # Once again, quaternion keyframes do not support bezier interpolation. Ideally,
                # we would just drop support for rotation beziers entirely to simplify all this
                # Euler crap, but some artists may require bezier interpolation...
                if bez_chans:
                    return self._make_scalar_compound_controller(keyframes, bez_chans)
                else:
                    return self._make_quat_controller(keyframes)

    def make_scale_controller(self, fcurves, data_path: str, default_xform,
                              convert: Optional[Callable] = None, *, start: Optional[int] = None,
                              end: Optional[int] = None) -> Optional[plLeafController]:
        scale_curves = [i for i in fcurves if i.data_path == data_path and i.keyframe_points]
        keyframes, bez_chans = self._process_keyframes(scale_curves, 3, default_xform, convert,
                                                       start=start, end=end)
        if not keyframes:
            return None

        # There is no such thing as a compound scale controller... in Plasma, anyway.
        ctrl = self._make_scale_value_controller(keyframes, bez_chans)
        return ctrl

    def make_scalar_leaf_controller(self, fcurve: bpy.types.FCurve,
                                    convert: Optional[Callable] = None, *,
                                    start: Optional[int] = None,
                                    end: Optional[int] = None) -> Optional[plLeafController]:
        keyframes, bezier = self._process_fcurve(fcurve, convert, start=start, end=end)
        if not keyframes:
            return None

        ctrl = self._make_scalar_leaf_controller(keyframes, bezier)
        return ctrl

    def _make_matrix44_controller(self, keyframes) -> plLeafController:
        ctrl = plLeafController()
        keyframe_type = hsKeyFrame.kMatrix44KeyFrame
        exported_frames = []

        for keyframe in keyframes:
            exported = hsMatrix44Key()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.type = keyframe_type
            exported.value = keyframe.values[0]
            exported_frames.append(exported)
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _make_point3_controller(self, keyframes, bezier) -> plLeafController:
        ctrl = plLeafController()
        keyframe_type = hsKeyFrame.kBezPoint3KeyFrame if bezier else hsKeyFrame.kPoint3KeyFrame
        exported_frames = []

        for keyframe in keyframes:
            exported = hsPoint3Key()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.type = keyframe_type
            exported.inTan = hsVector3(*keyframe.in_tans)
            exported.outTan = hsVector3(*keyframe.out_tans)
            exported.value = hsVector3(*keyframe.values)
            exported_frames.append(exported)
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _make_quat_controller(self, keyframes) -> plLeafController:
        ctrl = plLeafController()
        keyframe_type = hsKeyFrame.kQuatKeyFrame
        exported_frames = []

        for keyframe in keyframes:
            exported = hsQuatKey()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.type = keyframe_type
            # NOTE: quat keyframes don't do bezier nonsense

            values = keyframe.values
            num_channels = len(values)
            if num_channels == 3:
                value = mathutils.Euler(values)
                exported.value = utils.quaternion(value.to_quaternion())
            elif num_channels == 4:
                # Blender orders its quats WXYZ (nonstandard) but Plasma uses XYZW (standard)
                # Also note that manual incoming quat data might be goofy, so renormalize
                value = mathutils.Quaternion(values)
                value.normalize()
                exported.value = utils.quaternion(value)
            else:
                raise ValueError("Unexpected number of channels in quaternion keyframe {}".format(num_channels))
            exported_frames.append(exported)
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _make_scalar_compound_controller(self, keyframes, bez_chans) -> plCompoundController:
        ctrl = plCompoundController()
        subctrls = ("X", "Y", "Z")
        for i in subctrls:
            setattr(ctrl, i, plLeafController())
        exported_frames = ([], [], [])

        for keyframe in keyframes:
            for i, subctrl in enumerate(subctrls):
                keyframe_type = hsKeyFrame.kBezScalarKeyFrame if i in bez_chans else hsKeyFrame.kScalarKeyFrame
                exported = hsScalarKey()
                exported.frame = keyframe.frame_num
                exported.frameTime = keyframe.frame_time
                exported.inTan = keyframe.in_tans[i]
                exported.outTan = keyframe.out_tans[i]
                exported.type = keyframe_type
                exported.value = keyframe.values[i]
                exported_frames[i].append(exported)
        for i, subctrl in enumerate(subctrls):
            my_keyframes = exported_frames[i]
            getattr(ctrl, subctrl).keys = (my_keyframes, my_keyframes[0].type)
        return ctrl

    def _make_scalar_leaf_controller(self, keyframes, bezier) -> plLeafController:
        ctrl = plLeafController()
        keyframe_type = hsKeyFrame.kBezScalarKeyFrame if bezier else hsKeyFrame.kScalarKeyFrame
        exported_frames = []

        for keyframe in keyframes:
            exported = hsScalarKey()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.inTan = keyframe.in_tans[0]
            exported.outTan = keyframe.out_tans[0]
            exported.type = keyframe_type
            exported.value = keyframe.values[0]
            exported_frames.append(exported)
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _make_scale_value_controller(self, keyframes, bez_chans) -> plLeafController:
        keyframe_type = hsKeyFrame.kBezScaleKeyFrame if bez_chans else hsKeyFrame.kScaleKeyFrame
        exported_frames = []

        # Hmm... This smells... But it was basically doing this before the rewrite.
        unit_quat = hsQuat(0.0, 0.0, 0.0, 1.0)

        for keyframe in keyframes:
            exported = hsScaleKey()
            exported.frame = keyframe.frame_num
            exported.frameTime = keyframe.frame_time
            exported.type = keyframe_type
            exported.inTan = hsVector3(*keyframe.in_tans)
            exported.outTan = hsVector3(*keyframe.out_tans)
            exported.value = (hsVector3(*keyframe.values), unit_quat)
            exported_frames.append(exported)

        ctrl = plLeafController()
        ctrl.keys = (exported_frames, keyframe_type)
        return ctrl

    def _sort_and_dedupe_keyframes(self, keyframes: Dict) -> Sequence:
        """Takes in the final, unsorted keyframe sequence and sorts it. If all keyframes are
           equivalent, eg due to a convert function, then they are discarded."""

        num_keyframes = len(keyframes)
        keyframes_sorted = [keyframes[i] for i in sorted(keyframes)]

        # If any keyframe's value is equivalent to its boundary keyframes, discard it.
        def filter_boundaries(i):
            if i == 0 or i == num_keyframes - 1:
                return False
            left, me, right = keyframes_sorted[i - 1], keyframes_sorted[i], keyframes_sorted[i + 1]
            return left.values == me.values == right.values

        filtered_indices = list(itertools.filterfalse(filter_boundaries, range(num_keyframes)))
        if len(filtered_indices) == 2:
            if keyframes_sorted[filtered_indices[0]].values == keyframes_sorted[filtered_indices[1]].values:
                return []
        return [keyframes_sorted[i] for i in filtered_indices]

    def _process_fcurve(self, fcurve: bpy.types.FCurve, convert: Optional[Callable] = None, *,
                        start: Optional[int] = None, end: Optional[int] = None) -> Tuple[Sequence, AbstractSet]:
        """Like _process_keyframes, but for one fcurve"""

        # Adapt from incoming single item sequence to a single argument.
        if convert is not None:
            single_convert = lambda x: convert(x[0])
        else:
            single_convert = None
        # Can't proxy to _process_fcurves because it only supports linear interoplation.
        return self._process_keyframes([fcurve], 1, [0.0], single_convert, start=start, end=end)

    def _santize_converted_values(self, num_channels: int, raw_values: Union[Dict, Sequence], convert: Callable):
        assert convert is not None
        if isinstance(raw_values, Dict):
            values = convert(**raw_values)
        elif isinstance(raw_values, Sequence):
            values = convert(raw_values)
        else:
            raise AssertionError("Unexpected type for raw_values: {}".format(raw_values.__class__))

        if not isinstance(values, Sequence) and isinstance(values, Iterable):
            values = tuple(values)
        if not isinstance(values, Sequence):
            assert num_channels == 1, "Converter returned 1 value but expected {}".format(num_channels)
            values = (values,)
        else:
            assert len(values) == num_channels, "Converter returned {} values but expected {}".format(len(values), num_channels)
        return values

    def _process_fcurves(self, fcurves: Sequence, channels: Dict[str, int], result_channels: int,
                         convert: Callable, defaults: Dict[str, Union[float, Sequence]], *,
                         start: Optional[int] = None, end: Optional[int] = None) -> Sequence:
        """This consumes a sequence of Blender FCurves that map to a single Plasma controller.
           Like `_process_keyframes()`, except the converter function is mandatory, and each
           Blender `data_path` must have a fixed number of channels.
        """

        # TODO: This fxn should probably issue a warning if any keyframes use bezier interpolation.
        # But there's no indication given by any other fxn when an invalid interpolation mode is
        # given, so what can you do?
        keyframe_data = type("KeyFrameData", (), {})
        fps, pi = self._bl_fps, math.pi

        grouped_fcurves = defaultdict(dict)
        for fcurve in (i for i in fcurves if i is not None):
            fcurve.update()
            grouped_fcurves[fcurve.data_path][fcurve.array_index] = fcurve

        if start is not None and end is not None:
            framenum_filter = lambda x: x.co[0] >= start and x.co[0] <= end
        elif start is not None and end is None:
            framenum_filter = lambda x: x.co[0] >= start
        elif start is None and end is not None:
            framenum_filter = lambda x: x.co[0] <= end
        else:
            framenum_filter = lambda x: True

        fcurve_keyframes = defaultdict(lambda: defaultdict(dict))
        for fcurve in (i for i in fcurves if i is not None):
            for fkey in filter(framenum_filter, fcurve.keyframe_points):
                fcurve_keyframes[fkey.co[0]][fcurve.data_path][fcurve.array_index] = fkey

        def iter_channel_values(frame_num : int, fcurves : Dict, fkeys : Dict, num_channels : int, defaults : Union[float, Sequence]):
            for i in range(num_channels):
                fkey = fkeys.get(i, None)
                if fkey is None:
                    fcurve = fcurves.get(i, None)
                    if fcurve is None:
                        # We would like to test this to see if it makes sense, but Blender's mathutils
                        # types don't actually implement the sequence protocol. So, we'll have to
                        # just try to subscript it and see what happens.
                        try:
                            yield defaults[i]
                        except:
                            assert num_channels == 1, "Got a non-subscriptable default for a multi-channel keyframe."
                            yield defaults
                    else:
                        yield fcurve.evaluate(frame_num)
                else:
                    yield fkey.co[1]

        keyframes = {}
        for frame_num, fkeys in fcurve_keyframes.items():
            keyframe = keyframe_data()
            # hope you don't have a frame 29.9 and frame 30.0...
            keyframe.frame_num = int(frame_num * (30.0 / fps))
            keyframe.frame_num_blender = frame_num
            keyframe.frame_time = frame_num / fps
            keyframe.values_raw = { data_path: tuple(iter_channel_values(frame_num, grouped_fcurves[data_path], fkeys, num_channels, defaults[data_path]))
                                    for data_path, num_channels in channels.items() }
            keyframe.values = self._santize_converted_values(result_channels, keyframe.values_raw, convert)

            # Very gnawty
            keyframe.in_tans = [0.0] * result_channels
            keyframe.out_tans = [0.0] * result_channels
            keyframes[frame_num] = keyframe

        return self._sort_and_dedupe_keyframes(keyframes)

    def _process_keyframes(self, fcurves, num_channels: int, default_values: Sequence,
                           convert: Optional[Callable] = None, *, start: Optional[int] = None,
                           end: Optional[int] = None) -> Tuple[Sequence, AbstractSet]:
        """Groups all FCurves for the same frame together"""
        keyframe_data = type("KeyFrameData", (), {})
        fps, pi = self._bl_fps, math.pi

        keyframes, fcurve_keyframes = {}, defaultdict(dict)

        if start is not None and end is not None:
            framenum_filter = lambda x: x.co[0] >= start and x.co[0] <= end
        elif start is not None and end is None:
            framenum_filter = lambda x: x.co[0] >= start
        elif start is None and end is not None:
            framenum_filter = lambda x: x.co[0] <= end
        else:
            framenum_filter = lambda x: True

        indexed_fcurves = { fcurve.array_index: fcurve for fcurve in fcurves if fcurve is not None }
        for i, fcurve in indexed_fcurves.items():
            fcurve.update()
            for fkey in filter(framenum_filter, fcurve.keyframe_points):
                fcurve_keyframes[fkey.co[0]][i] = fkey

        def iter_values(frame_num, fkeys) -> Generator[float, None, None]:
            for i in range(num_channels):
                fkey = fkeys.get(i, None)
                if fkey is not None:
                    yield fkey.co[1]
                else:
                    fcurve = indexed_fcurves.get(i, None)
                    if fcurve is not None:
                        yield fcurve.evaluate(frame_num)
                    else:
                        yield default_values[i]

        # Does this really need to be a set?
        bez_chans = set()

        for frame_num, fkeys in fcurve_keyframes.items():
            keyframe = keyframe_data()
            # hope you don't have a frame 29.9 and frame 30.0...
            keyframe.frame_num = int(frame_num * (30.0 / fps))
            keyframe.frame_num_blender = frame_num
            keyframe.frame_time = frame_num / fps
            keyframe.in_tans = [0.0] * num_channels
            keyframe.out_tans = [0.0] * num_channels
            keyframe.values_raw = tuple(iter_values(frame_num, fkeys))
            if convert is None:
                keyframe.values = keyframe.values_raw
            else:
                keyframe.values = self._santize_converted_values(num_channels, keyframe.values_raw, convert)

            for i, fkey in ((i, fkey) for i, fkey in fkeys.items() if fkey.interpolation == "BEZIER"):
                value = keyframe.values_raw[i]
                keyframe.in_tans[i] = -(value - fkey.handle_left[1])  / (frame_num - fkey.handle_left[0])  / fps / (2 * pi)
                keyframe.out_tans[i] = (value - fkey.handle_right[1]) / (frame_num - fkey.handle_right[0]) / fps / (2 * pi)
                bez_chans.add(i)
            keyframes[frame_num] = keyframe

        # Return the keyframes in a sequence sorted by frame number
        return (self._sort_and_dedupe_keyframes(keyframes), bez_chans)

    @property
    def _mgr(self):
        return self._exporter().mgr
