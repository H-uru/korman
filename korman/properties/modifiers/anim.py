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

from typing import Iterable, Iterator, Optional

from PyHSPlasma import *

from .base import PlasmaModifierProperties
from ..prop_anim import PlasmaAnimationCollection
from ...exporter import ExportError, utils
from ... import idprops

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
        raise ExportError("'{}': Object has an animation modifier but is not animated".format(bo.name))

    def sanity_check(self) -> None:
        if not self.id_data.plasma_object.has_animation_data:
            raise ExportError("'{}': Has an animation modifier but no animation data.", self.id_data.name)

        if self.id_data.type == "CAMERA":
            if not self.id_data.data.plasma_camera.allow_animations:
                raise ExportError("'{}': Animation modifiers are not allowed on this camera type.", self.id_data.name)


class PlasmaAnimationModifier(ActionModifier, PlasmaModifierProperties):
    pl_id = "animation"

    bl_category = "Animation"
    bl_label = "Animation"
    bl_description = "Object animation"
    bl_icon = "ACTION"

    subanimations = PointerProperty(type=PlasmaAnimationCollection)

    def pre_export(self, exporter, bo):
        # We want to run the animation converting early in the process because of dependencies on
        # the animation data being available. Especially in the camera exporter.
        so = exporter.mgr.find_create_object(plSceneObject, bl=bo)
        self.convert_object_animations(exporter, bo, so, self.subanimations)

    def convert_object_animations(self, exporter, bo, so, anims: Optional[Iterable] = None):
        if not anims:
            anims = [self.subanimations.entire_animation]
        with exporter.report.indent():
            aganims = list(self._export_ag_anims(exporter, bo, so, anims))

        # Defer creation of the private animation until after the converter has been executed.
        # Just because we have some FCurves doesn't mean they will produce anything particularly
        # useful. Some versions of Uru will crash if we feed it an empty animation, so yeah.
        if aganims:
            agmod, agmaster = exporter.animation.get_anigraph_objects(bo, so)
            agmod.channelName = self.id_data.name
            for i in aganims:
                agmaster.addPrivateAnim(i.key)

    def _export_ag_anims(self, exporter, bo, so, anims: Iterable) -> Iterator[plAGAnim]:
        action = self.blender_action
        converter = exporter.animation

        for anim in anims:
            assert anim is not None, "Animation should not be None!"
            anim_name = anim.animation_name

            # If this is the entire animation, the range that anim.start and anim.end will return
            # is the range of all of the keyframes. Of course, we don't nesecarily convert every
            # keyframe, so we will defer figuring out the range until the conversion is complete.
            if not anim.is_entire_animation:
                start, end = anim.start, anim.end
                start, end = min((start, end)), max((start, end))
            else:
                start, end = None, None

            applicators = converter.convert_object_animations(bo, so, anim_name, start=start, end=end)
            if not applicators:
                exporter.report.warn(f"Animation '{anim_name}' generated no applicators. Nothing will be exported.")
                continue

            pClass = plAgeGlobalAnim if anim.sdl_var else plATCAnim
            aganim = exporter.mgr.find_create_object(pClass, bl=bo, so=so, name="{}_{}".format(bo.name, anim_name))
            aganim.name = anim_name
            aganim.start, aganim.end = converter.get_frame_time_range(*applicators, so=so)
            for i in applicators:
                aganim.addApplicator(i)

            if isinstance(aganim, plATCAnim):
                aganim.autoStart = anim.auto_start
                aganim.loop = anim.loop

                if action is not None:
                    markers = action.pose_markers
                    initial_marker = markers.get(anim.initial_marker)
                    if initial_marker is not None:
                        aganim.initial = converter.convert_frame_time(initial_marker.frame)
                    else:
                        aganim.initial = -1.0
                    if anim.loop:
                        loop_start = markers.get(anim.loop_start)
                        if loop_start is not None:
                            aganim.loopStart = converter.convert_frame_time(loop_start.frame)
                        else:
                            aganim.loopStart = aganim.start
                        loop_end = markers.get(anim.loop_end)
                        if loop_end is not None:
                            aganim.loopEnd = converter.convert_frame_time(loop_end.frame)
                        else:
                            aganim.loopEnd = aganim.end
                else:
                    if anim.loop:
                        aganim.loopStart = aganim.start
                        aganim.loopEnd = aganim.end

                # Fixme? Not sure if we really need to expose this...
                aganim.easeInMin = 1.0
                aganim.easeInMax = 1.0
                aganim.easeInLength = 1.0
                aganim.easeOutMin = 1.0
                aganim.easeOutMax = 1.0
                aganim.easeOutLength = 1.0

            if isinstance(aganim, plAgeGlobalAnim):
                aganim.globalVarName = anim.sdl_var

            yield aganim

    @classmethod
    def register(cls):
        PlasmaAnimationCollection.register_entire_animation(bpy.types.Object, cls)


class AnimGroupObject(idprops.IDPropObjectMixin, bpy.types.PropertyGroup):
    child_anim = PointerProperty(name="Child Animation",
                                 description="Object whose action is a child animation",
                                 type=bpy.types.Object,
                                 poll=idprops.poll_animated_objects)

    @classmethod
    def _idprop_mapping(cls):
        return {"child_anim": "object_name"}


class PlasmaAnimationFilterModifier(PlasmaModifierProperties):
    pl_id = "animation_filter"

    bl_category = "Animation"
    bl_label = "Filter Transform"
    bl_description = "Filter animation components"
    bl_icon = "UNLINKED"

    no_rotation = BoolProperty(name="Filter Rotation",
                               description="Filter rotations",
                               options=set())

    no_transX = BoolProperty(name="Filter X Translation",
                             description="Filter the X component of translations",
                             options=set())
    no_transY = BoolProperty(name="Filter Y Translation",
                             description="Filter the Y component of translations",
                             options=set())
    no_transZ = BoolProperty(name="Filter Z Translation",
                             description="Filter the Z component of translations",
                             options=set())

    def export(self, exporter, bo, so):
        # By this point, the object should already have a plFilterCoordInterface
        # created by the converter. Let's test that assumption.
        coord = so.coord.object
        assert isinstance(coord, plFilterCoordInterface)

        # Apply filtercoordinterface properties
        if self.no_rotation:
            coord.filterMask |= plFilterCoordInterface.kNoRotation
        if self.no_transX:
            coord.filterMask |= plFilterCoordInterface.kNoTransX
        if self.no_transY:
            coord.filterMask |= plFilterCoordInterface.kNoTransY
        if self.no_transZ:
            coord.filterMask |= plFilterCoordInterface.kNoTransZ

    @property
    def requires_actor(self):
        return True


class PlasmaAnimationGroupModifier(ActionModifier, PlasmaModifierProperties):
    pl_id = "animation_group"
    pl_depends = {"animation"}

    bl_category = "Animation"
    bl_label = "Group Master"
    bl_description = "Defines related animations"
    bl_icon = "GROUP"

    children = CollectionProperty(name="Child Animations",
                                  description="Animations that will execute the same commands as this one",
                                  type=AnimGroupObject)
    active_child_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        if not bo.plasma_object.has_animation_data:
            raise ExportError("'{}': Object is not animated".format(bo.name))

        # The message forwarder is the guy that makes sure that everybody knows WTF is going on
        msgfwd = exporter.mgr.find_create_object(plMsgForwarder, so=so, name=self.key_name)

        # Now, this is da swhiz...
        agmod, agmaster = exporter.animation.get_anigraph_objects(bo, so)
        agmaster.msgForwarder = msgfwd.key
        agmaster.isGrouped, agmaster.isGroupMaster = True, True
        for i in self.children:
            child_bo = i.child_anim
            if child_bo is None:
                msg = "Animation Group '{}' specifies an invalid object. Ignoring..."
                exporter.report.warn(msg, self.key_name, ident=2)
                continue
            if not child_bo.plasma_object.has_animation_data:
                msg = "Animation Group '{}' specifies an object '{}' with no valid animation data. Ignoring..."
                exporter.report.warn(msg, self.key_name, child_bo.name)
                continue
            child_animation = child_bo.plasma_modifiers.animation
            if not child_animation.enabled:
                msg = "Animation Group '{}' specifies an object '{}' with no Plasma Animation modifier. Ignoring..."
                exporter.report.warn(msg, self.key_name, child_bo.name)
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
                    action.name, loop.loop_name, loop.loop_start))
            if end is None:
                exporter.report.warn("Animation '{}' Loop '{}': Marker '{}' not found. This loop will not be exported".format(
                    action.name, loop.loop_name, loop.loop_end))
            if start is None or end is None:
                continue
            atcanim.setLoop(loop.loop_name, _convert_frame_time(start.frame), _convert_frame_time(end.frame))
