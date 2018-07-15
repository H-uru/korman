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

from .explosions import *

class CameraConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)

    def _convert_brain(self, so, bo, camera_props, brain):
        trans_props = camera_props.transition

        brain.poaOffset = hsVector3(*camera_props.poa_offset)
        if camera_props.poa_type == "object":
            brain.subject = self._mgr.find_create_key(plSceneObject, bl=camera_props.poa_object)

        brain.xPanLimit = camera_props.x_pan_angle / 2.0
        brain.zPanLimit = camera_props.y_pan_angle / 2.0
        brain.panSpeed = camera_props.pan_rate
        if camera_props.limit_zoom:
            brain.setFlags(plCameraBrain1.kZoomEnabled, True)
            brain.zoomMax = camera_props.zoom_max * (4.0 / 3.0)
            brain.zoomMin = camera_props.zoom_min * (4.0 / 3.0)
            brain.zoomRate = camera_props.zoom_rate

        brain.acceleration = trans_props.pos_acceleration
        brain.deceleration = trans_props.pos_deceleration
        brain.velocity = trans_props.pos_velocity
        brain.poaAcceleration = trans_props.poa_acceleration
        brain.poaDeceleration = trans_props.poa_deceleration
        brain.poaVelocity = trans_props.poa_velocity

        if trans_props.pos_cut:
            brain.setFlags(plCameraBrain1.kCutPos, True)
        if trans_props.poa_cut:
            brain.setFlags(plCameraBrain1.kCutPOA, True)
        if camera_props.poa_type == "avatar":
            brain.setFlags(plCameraBrain1.kFollowLocalAvatar, True)
        if camera_props.maintain_los:
            brain.setFlags(plCameraBrain1.kMaintainLOS, True)
        if camera_props.poa_worldspace:
            brain.setFlags(plCameraBrain1.kWorldspacePOA, True)
        if camera_props.pos_worldspace:
            brain.setFlags(plCameraBrain1.kWorldspacePos, True)
        if camera_props.ignore_subworld:
            brain.setFlags(plCameraBrain1.kIgnoreSubworldMovement, True)
        if camera_props.fall_vertical:
            brain.setFlags(plCameraBrain1.kVerticalWhenFalling, True)
        if camera_props.fast_run:
            brain.setFlags(plCameraBrain1.kSpeedUpWhenRunning, True)

    def export_camera(self, so, bo, camera_type, camera_props):
        mod = self._export_camera_modifier(so, bo, camera_props)
        brain = getattr(self, "_export_{}_camera".format(camera_type))(so, bo, camera_props)
        mod.brain = brain.key

    def _export_camera_modifier(self, so, bo, props):
        # PlasmaMAX allows the user to specify the horizontal OR vertical FOV, but not both.
        # We only allow setting horizontal FOV (how often do you look up?), however.
        # Plasma assumes 4:3 aspect ratio...
        mod = self._mgr.find_create_object(plCameraModifier, so=so)
        fov = props.fov
        mod.fovW, mod.fovH = math.degrees(fov), math.degrees(fov * (3.0 / 4.0))

        # TODO: do we need to do something about animations here?
        return mod

    def _export_circle_camera(self, so, bo, props):
        brain = self._mgr.find_create_object(plCameraBrain1_Circle, so=so)
        self._convert_brain(so, bo, props, brain)

        # Circle Camera specific stuff ahoy!
        if props.poa_type == "avatar":
            brain.circleFlags |= plCameraBrain1_Circle.kCircleLocalAvatar
        elif props.poa_type == "object":
            brain.poaObject = self._mgr.find_create_key(plSceneObject, bl=props.poa_object)
        else:
            self._report.warn("Circle Camera '{}' has no Point of Attention. Is this intended?", bo.name, indent=3)
        if props.circle_pos == "farthest":
            brain.circleFlags |= plCameraBrain1_Circle.kFarthest

        # If no center object is specified, we will use the camera object's location.
        # We will use a simple vector for this object to make life simpler, however,
        # specifying an actual center allows you to do interesting things like animate the center...
        # Fascinating! Therefore, we will expose the Plasma Object...
        if props.circle_center is None:
            brain.center = hsVector3(*bo.location)
        else:
            brain.centerObject = self._mgr.find_create_key(plSceneObject, bl=props.circle_center)
            # This flag has no effect in CWE, but I'm using it for correctness' sake
            brain.circleFlags |= plCameraBrain1_Circle.kHasCenterObject

        # PlasmaMAX forces these values so the circle camera is rather slow, which is somewhat
        # sensible to me. Fast circular motion seems like a poor idea to me... If we want these
        # values to be customizable, we probably want add some kind of range limitation or at least
        # a flashing red light in the UI...
        brain.acceleration = 10.0
        brain.deceleration = 10.0
        brain.velocity = 15.0

        # Related to above, circle cameras use a slightly different velocity method.
        # This is stored in Plasma as a fraction of the circle's circumference. It makes
        # more sense to me to present it in terms of degrees per second, however.
        # NOTE that Blender returns radians!!!
        brain.cirPerSec = props.circle_velocity / (2 * math.pi)

        # I consider this clever... If we have a center object, we use the magnitude of the displacement
        # of the camera's object to the center object (at frame 0) to determine the radius. If no center
        # object is specified, we allow the user to specify the radius.
        # Well, it's clever until you realize it's the same thing Cyan did in PlasmaMAX... But it's harder
        # here because Blendsucks.
        brain.radius = props.get_circle_radius(bo)

        # Done already?
        return brain

    def _export_fixed_camera(self, so, bo, props):
        brain = self._mgr.find_create_object(plCameraBrain1_Fixed, so=so)
        self._convert_brain(so, bo, props, brain)
        # TODO: animations???
        return brain

    def _export_follow_camera(self, so, bo, props):
        brain = self._mgr.find_create_object(plCameraBrain1_Avatar, so=so)
        self._convert_brain(so, bo, props, brain)

        # Follow camera specific stuff ahoy!
        brain.offset = hsVector3(*camera_props.pos_offset)
        return brain

    @property
    def _mgr(self):
        return self._exporter().mgr

    @property
    def _report(self):
        return self._exporter().report
