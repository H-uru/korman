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

class ActionModifier:
    @property
    def blender_action(self):
        bo = self.id_data
        if bo.animation_data is not None and bo.animation_data.action is not None:
            return bo.animation_data.action
        if bo.data is not None:
            if bo.data.animation_data is not None and bo.data.animation_data.action is not None:
                # we will not use this action for any animation logic. that must be stored on the Object
                # datablock for simplicity's sake.
                return None
        raise ExportError("Object '{}' is not animated".format(bo.name))


class PlasmaAnimationModifier(ActionModifier, PlasmaModifierProperties):
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

    @property
    def requires_actor(self):
        return True

    def export(self, exporter, bo, so):
        action = self.blender_action

        atcanim = exporter.mgr.find_create_object(plATCAnim, so=so)
        atcanim.autoStart = self.auto_start
        atcanim.loop = self.loop

        # Simple start and loop info
        if action is not None:
            markers = action.pose_markers
            initial_marker = markers.get(self.initial_marker)
            if initial_marker is not None:
                atcanim.initial = _convert_frame_time(initial_marker.frame)
            else:
                atcanim.initial = -1.0
            if self.loop:
                loop_start = markers.get(self.loop_start)
                if loop_start is not None:
                    atcanim.loopStart = _convert_frame_time(loop_start.frame)
                else:
                    atcanim.loopStart = atcanim.start
                loop_end = markers.get(self.loop_end)
                if loop_end is not None:
                    atcanim.loopEnd = _convert_frame_time(loop_end.frame)
                else:
                    atcanim.loopEnd = atcanim.end
        else:
            if self.loop:
                atcanim.loopStart = atcanim.start
                atcanim.loopEnd = atcanim.end

    def _make_physical_movable(self, so):
        sim = so.sim
        if sim is not None:
            sim = sim.object
            sim.setProperty(plSimulationInterface.kPhysAnim, True)
            phys = sim.physical.object
            phys.setProperty(plSimulationInterface.kPhysAnim, True)

            # If the mass is zero, then we will fail to animate. Fix that.
            if phys.mass == 0.0:
                phys.mass = 1.0
                
                # set kPinned so it doesn't fall through
                sim.setProperty(plSimulationInterface.kPinned, True)
                phys.setProperty(plSimulationInterface.kPinned, True)
        
        # Do the same for children objects
        for child in so.coord.object.children:
            self.make_physical_movable(child.object)

    def post_export(self, exporter, bo, so):
        # If this object has a physical, we need to tell the simulation iface that it can be animated
        self._make_physical_movable(so)


class AnimGroupObject(bpy.types.PropertyGroup):
    object_name = StringProperty(name="Child",
                                 description="Object whose action is a child animation")


class PlasmaAnimationGroupModifier(PlasmaModifierProperties):
    pl_id = "animation_group"
    pl_depends = {"animation"}

    bl_category = "Animation"
    bl_label = "Group"
    bl_description = "Defines related animations"
    bl_icon = "GROUP"

    children = CollectionProperty(name="Child Animations",
                                  description="Animations that will execute the same commands as this one",
                                  type=AnimGroupObject)
    active_child_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        if not exporter.animation.is_animated(bo):
            raise ExportError("'{}': Object is not animated".format(bo.name))

        # The message forwarder is the guy that makes sure that everybody knows WTF is going on
        msgfwd = exporter.mgr.find_create_object(plMsgForwarder, so=so, name=self.key_name)

        # Now, this is da swhiz...
        agmod, agmaster = exporter.animation.get_anigraph_objects(bo, so)
        agmaster.msgForwarder = msgfwd.key
        agmaster.isGrouped, agmaster.isGroupMaster = True, True
        for i in self.children:
            child_bo = bpy.data.objects.get(i.object_name, None)
            if child_bo is None:
                msg = "Animation Group '{}' specifies an invalid object '{}'. Ignoring..."
                exporter.report.warn(msg.format(self.key_name, i.object_name), ident=2)
                continue
            if child_bo.animation_data is None or child_bo.animation_data.action is None:
                msg = "Animation Group '{}' specifies an object '{}' with no valid animation data. Ignoring..."
                exporter.report.warn(msg.format(self.key_name, i.object_name), indent=2)
                continue
            child_animation = child_bo.plasma_modifiers.animation
            if not child_animation.enabled:
                msg = "Animation Group '{}' specifies an object '{}' with no Plasma Animation modifier. Ignoring..."
                exporter.report.warn(msg.format(self.key_name, i.object_name), indent=2)
                continue
            child_agmod, child_agmaster = exporter.animation.get_anigraph_objects(bo=child_bo)
            msgfwd.addForwardKey(child_agmaster.key)
        msgfwd.addForwardKey(agmaster.key)

    @property
    def key_name(self):
        return "{}_AnimGroup".format(self.id_data.name)


class LoopMarker(bpy.types.PropertyGroup):
    loop_name = StringProperty(name="Loop Name",
                               description="Name of this loop")
    loop_start = StringProperty(name="Loop Start",
                                description="Marker name from whence the loop begins")
    loop_end = StringProperty(name="Loop End",
                                description="Marker name from whence the loop ends")


class PlasmaAnimationLoopModifier(ActionModifier, PlasmaModifierProperties):
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

    def export(self, exporter, bo, so):
        action = self.blender_action
        if action is None:
            raise ExportError("'{}': No object animation data".format(bo.name))
        markers = action.pose_markers

        atcanim = exporter.mgr.find_create_object(plATCAnim, so=so)
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
