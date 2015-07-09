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
from bpy.props import *
from PyHSPlasma import *

from .base import PlasmaModifierProperties
from ...exporter import ExportError, utils

def _convert_frame_time(frame_num):
    fps = bpy.context.scene.render.fps
    return frame_num / fps

def _get_blender_action(bo):
    if bo.animation_data is None or bo.animation_data.action is None:
        raise ExportError("Object '{}' has no Action to export".format(bo.name))
    return bo.animation_data.action

class PlasmaAnimationModifier(PlasmaModifierProperties):
    pl_id = "animation"

    bl_category = "Animation"
    bl_label = "Animation"
    bl_description = "Object animation"
    bl_icon = "ACTION"

    auto_start = BoolProperty(name="Auto Start",
                              description="Automatically start this animation on link-in",
                              default=True)
    loop = BoolProperty(name="Loop Anim",
                        description="Loop the animation",
                        default=True)

    initial_marker = StringProperty(name="Start Marker",
                                    description="Marker indicating the default start point")
    loop_start = StringProperty(name="Loop Start",
                                description="Marker indicating where the default loop begins")
    loop_end = StringProperty(name="Loop End",
                              description="Marker indicating where the default loop ends")

    def created(self, obj):
        self.display_name = "{}_(Entire Animation)".format(obj.name)

    @property
    def requires_actor(self):
        return True

    def export(self, exporter, bo, so):
        action = _get_blender_action(bo)
        markers = action.pose_markers

        atcanim = exporter.mgr.find_create_key(plATCAnim, so=so, name=self.display_name).object
        atcanim.autoStart = self.auto_start
        atcanim.loop = self.loop
        atcanim.name = "(Entire Animation)"
        atcanim.start = _convert_frame_time(action.frame_range[0])
        atcanim.end = _convert_frame_time(action.frame_range[1])

        # Simple start and loop info
        initial_marker = markers.get(self.initial_marker)
        if initial_marker is not None:
            atcanim.initial = _convert_fame_time(initial_marker.frame)
        else:
            atcanim.initial = -1.0
        if self.loop:
            loop_start = markers.get(self.loop_start)
            if loop_start is not None:
                atcanim.loopStart = _convert_frame_time(loop_start.frame)
            else:
                atcanim.loopStart = _convert_frame_time(action.frame_range[0])
            loop_end = markers.get(self.loop_end)
            if loop_end is not None:
                atcanim.loopEnd = _convert_frame_time(loop_end.frame)
            else:
                atcanim.loopEnd = _convert_frame_time(action.frame_range[1])

        # Marker points
        for marker in markers:
            atcanim.setMarker(marker.name, _convert_frame_time(marker.frame))

        # Fixme? Not sure if we really need to expose this...
        atcanim.easeInMin = 1.0
        atcanim.easeInMax = 1.0
        atcanim.easeInLength = 1.0
        atcanim.easeOutMin = 1.0
        atcanim.easeOutMax = 1.0
        atcanim.easeOutLength = 1.0

        # Now for the animation data. We're mostly just going to hand this off to the controller code
        matrix = bo.matrix_basis
        applicator = plMatrixChannelApplicator()
        applicator.enabled = True
        applicator.channelName = bo.name
        channel = plMatrixControllerChannel()
        channel.controller = exporter.animation.convert_action2tm(action, matrix)
        applicator.channel = channel
        atcanim.addApplicator(applicator)

        # Decompose the matrix into the 90s-era 3ds max affine parts sillyness
        # All that's missing now is something like "(c) 1998 HeadSpin" oh wait...
        affine = hsAffineParts()
        affine.T = utils.vector3(matrix.to_translation())
        affine.K = utils.vector3(matrix.to_scale())
        affine.F = -1.0 if matrix.determinant() < 0.0 else 1.0
        rot = matrix.to_quaternion()
        affine.Q = utils.quaternion(rot)
        rot.normalize()
        affine.U = utils.quaternion(rot)
        channel.affine = affine

        # We need both an AGModifier and an AGMasterMod
        # TODO: grouped animations (eg one door, two objects)
        agmod = exporter.mgr.add_object(plAGModifier, so=so, name=self.display_name)
        agmod.channelName = bo.name
        agmaster = exporter.mgr.add_object(plAGMasterMod, so=so, name=self.display_name)
        agmaster.addPrivateAnim(atcanim.key)

    def post_export(self, exporter, bo, so):
        # If this object has a physical, we need to tell the simulation iface that it can be animated
        sim = so.sim
        if sim is not None:
            sim = sim.object
            sim.setProperty(plSimulationInterface.kPhysAnim, True)
            phys = sim.physical.object
            phys.setProperty(plSimulationInterface.kPhysAnim, True)


class LoopMarker(bpy.types.PropertyGroup):
    loop_name = StringProperty(name="Loop Name",
                               description="Name of this loop")
    loop_start = StringProperty(name="Loop Start",
                                description="Marker name from whence the loop begins")
    loop_end = StringProperty(name="Loop End",
                                description="Marker name from whence the loop ends")


class PlasmaAnimationLoopModifier(PlasmaModifierProperties):
    pl_id = "animation_loop"
    pl_depends = {"animation"}

    bl_category = "Animation"
    bl_label = "Loop Markers"
    bl_description = "Animation loop settings"
    bl_icon = "PMARKER_SEL"

    loops = CollectionProperty(name="Loops",
                               description="Loop points within the animation",
                               type=LoopMarker)
    active_loop_index = IntProperty(options={"HIDDEN"})

    def created(self, obj):
        # who cares, this modifier creates no Keys...
        self.display_name = "AnimLoops"

    def export(self, exporter, bo, so):
        action = _get_blender_action(bo)
        markers = action.pose_markers

        key_name = bo.plasma_modifiers.animation.display_name
        atcanim = exporter.mgr.find_create_key(plATCAnim, so=so, name=key_name).object
        for loop in self.loops:
            start = markers.get(loop.loop_start)
            end = markers.get(loop.loop_end)
            if start is None:
                exporter.report.warn("Animation '{}' Loop '{}': Marker '{}' not found. This loop will not be exported".format(
                    action.name, loop.loop_name, loop.loop_start), indent=2)
            if end is None:
                exporter.report.warn("Animation '{}' Loop '{}': Marker '{}' not found. This loop will not be exported".format(
                    action.name, loop.loop_name, loop.loop_end), indent=2)
            if start is None or end is None:
                continue
            atcanim.setLoop(loop.loop_name, _convert_frame_time(start.frame), _convert_frame_time(end.frame))
