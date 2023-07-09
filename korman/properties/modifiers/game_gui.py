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

from __future__ import annotations

import bpy
from bpy.props import *

import itertools
import math
from typing import *

from PyHSPlasma import *

from ...exporter import ExportError
from .base import PlasmaModifierProperties
from ... import idprops

if TYPE_CHECKING:
    from ...exporter import Exporter
    from ..prop_world import PlasmaAge, PlasmaPage

class _GameGuiMixin:
    @property
    def gui_sounds(self) -> Iterable[Tuple[str, int]]:
        """Overload to automatically export GUI sounds on the control. This should return an iterable
           of tuple attribute name and sound index.
        """
        return []

    def get_control(self, exporter: Exporter, bo: Optional[bpy.types.Object] = None, so: Optional[plSceneObject] = None) -> Optional[pfGUIControlMod]:
        return None

    @property
    def has_gui_proc(self) -> bool:
        return True

    def iterate_control_modifiers(self) -> Iterator[_GameGuiMixin]:
        pl_mods = self.id_data.plasma_modifiers
        yield from (
            getattr(pl_mods, i.pl_id)
            for i in self.iterate_control_subclasses()
            if getattr(pl_mods, i.pl_id).enabled
        )

    @classmethod
    def iterate_control_subclasses(cls) -> Iterator[_GameGuiMixin]:
        yield from filter(
            lambda x: x.is_game_gui_control(),
            _GameGuiMixin.__subclasses__()
        )

    @classmethod
    def is_game_gui_control(cls) -> bool:
        return True

    @property
    def requires_dyntext(self) -> bool:
        return False

    def sanity_check(self):
        age: PlasmaAge = bpy.context.scene.world.plasma_age

        # Game GUI modifiers must be attached to objects in a GUI page, ONLY
        page_name: str = self.id_data.plasma_object.page
        our_page: Optional[PlasmaPage] = next(
            (i for i in age.pages if i.name == page_name)
        )
        if our_page is None or our_page.page_type != "gui":
            raise ExportError(f"'{self.id_data.name}': {self.bl_label} Modifier must be in a GUI page!")

        # Only one Game GUI Control per object. Continuously check this because objects can be
        # generated/mutated during the pre-export phase.
        modifiers = self.id_data.plasma_modifiers
        controls = [i for i in self.iterate_control_subclasses() if getattr(modifiers, i.pl_id).enabled]
        num_controls = len(controls)
        if num_controls > 1:
            raise ExportError(f"'{self.id_data.name}': Only 1 GUI Control modifier is allowed per object. We found {num_controls}.")

        # Blow up on invalid sounds
        soundemit = self.id_data.plasma_modifiers.soundemit
        for attr_name, _ in self.gui_sounds:
            sound_name = getattr(self, attr_name)
            if not sound_name:
                continue
            sound = next((i for i in soundemit.sounds if i.name == sound_name), None)
            if sound is None:
                raise ExportError(f"'{self.id_data.name}': Invalid '{attr_name}' GUI Sound '{sound_name}'")


class PlasmaGameGuiControlModifier(PlasmaModifierProperties, _GameGuiMixin):
    pl_id = "gui_control"

    bl_category = "GUI"
    bl_label = "Ex: Game GUI Control"
    bl_description = "XXX"

    tag_id = IntProperty(
        name="Tag ID",
        description="",
        min=0,
        options=set()
    )
    visible = BoolProperty(
        name="Visible",
        description="",
        default=True,
        options=set()
        )
    proc = EnumProperty(
        name="Notification Procedure",
        description="",
        items=[
            ("default", "[Default]", "Send notifications to the owner's notification procedure."),
            ("close_dialog", "Close Dialog", "Close the current Game GUI Dialog."),
            ("console_command", "Run Console Command", "Run a Plasma Console command.")
        ],
        options=set()
    )
    console_command = StringProperty(
        name="Command",
        description="",
        options=set()
    )

    def convert_gui_control(self, exporter: Exporter, ctrl: pfGUIControlMod, bo: bpy.types.Object, so: plSceneObject):
        ctrl.tagID = self.tag_id
        ctrl.visible = self.visible
        if self.proc == "default":
            ctrl.setFlag(pfGUIControlMod.kInheritProcFromDlg, True)
        elif self.proc == "close_dialog":
            ctrl.handler = pfGUICloseDlgProc()
        elif self.proc == "console_command":
            handler = pfGUIConsoleCmdProc()
            handler.command = self.console_command
            ctrl.handler = handler

    def convert_gui_sounds(self, exporter: Exporter, ctrl: pfGUIControlMod, ctrl_mod: _GameGuiMixin):
        soundemit = ctrl_mod.id_data.plasma_modifiers.soundemit
        if not ctrl_mod.gui_sounds or not soundemit.enabled:
            return

        # This is a lot like the plPhysicalSndGroup where we have a vector behaving as a lookup table.
        # NOTE that zero is a special value here meaning no sound, so we need to offset the sounds
        # that we get from the emitter modifier by +1.
        sound_indices = {}
        for attr_name, gui_sound_idx in ctrl_mod.gui_sounds:
            sound_name = getattr(ctrl_mod, attr_name)
            if not sound_name:
                continue
            sound_keys = soundemit.get_sound_keys(exporter, sound_name)
            sound_key, soundemit_index = next(sound_keys, (None, -1))
            if sound_key is not None:
                sound_indices[gui_sound_idx] = soundemit_index + 1

        # Compress the list to include only the highest entry we need.
        if sound_indices:
            ctrl.soundIndices = [sound_indices.get(i, 0) for i in range(max(sound_indices) + 1)]

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        ctrl_mods = list(self.iterate_control_modifiers())
        if not ctrl_mods:
            exporter.report.msg(str(list(self.iterate_control_subclasses())))
            exporter.report.warn("This modifier has no effect because no GUI control modifiers are present!")
        for ctrl_mod in ctrl_mods:
            ctrl_obj = ctrl_mod.get_control(exporter, bo, so)
            self.convert_gui_control(exporter, ctrl_obj, bo, so)
            self.convert_gui_sounds(exporter, ctrl_obj, ctrl_mod)

    @property
    def has_gui_proc(self) -> bool:
        return any((i.has_gui_proc for i in self.iterate_control_modifiers()))

    @classmethod
    def is_game_gui_control(cls) -> bool:
        # How is a control not a control, you ask? Because, grasshopper, this modifier does not
        # actually export a GUI control itself. Instead, it holds common properties that may
        # or may not be used by other controls. This just helps fill out the other modifiers.
        return False


class GameGuiAnimation(bpy.types.PropertyGroup):
    def _poll_target_object(self, value):
        # Only allow targetting things that are in our GUI page.
        if value.plasma_object.page != self.id_data.plasma_object.page:
            return False
        if self.anim_type == "OBJECT":
            return idprops.poll_animated_objects(self, value)
        else:
            return idprops.poll_drawable_objects(self, value)

    def _poll_texture(self, value):
        # must be a legal option... but is it a member of this material... or, if no material,
        # any of the materials attached to the object?
        if self.target_material is not None:
            return value.name in self.target_material.texture_slots
        else:
            target_object = self.target_object if self.target_object is not None else self.id_data
            for i in (slot.material for slot in target_object.material_slots if slot and slot.material):
                if value in (slot.texture for slot in i.texture_slots if slot and slot.texture):
                    return True
            return False

    def _poll_material(self, value):
        # Don't filter materials by texture - this would (potentially) result in surprising UX
        # in that you would have to clear the texture selection before being able to select
        # certain materials.
        target_object = self.target_object if self.target_object is not None else self.id_data
        object_materials = (slot.material for slot in target_object.material_slots if slot and slot.material)
        return value in object_materials

    anim_type: str = EnumProperty(
        name="Type",
        description="Animation type to affect",
        items=[
            ("OBJECT", "Object", "Object Animation"),
            ("TEXTURE", "Texture", "Texture Animation"),
        ],
        default="OBJECT",
        options=set()
    )
    target_object: bpy.types.Object = PointerProperty(
        name="Object",
        description="Target object",
        poll=_poll_target_object,
        type=bpy.types.Object
    )
    target_material: bpy.types.Material = PointerProperty(
        name="Material",
        description="Target material",
        type=bpy.types.Material,
        poll=_poll_material
    )
    target_texture: bpy.types.Texture = PointerProperty(
        name="Texture",
        description="Target texture",
        type=bpy.types.Texture,
        poll=_poll_texture
    )


class GameGuiAnimationGroup(bpy.types.PropertyGroup):
    def _update_animation_name(self, context) -> None:
        if not self.animation_name:
            self.animation_name = "(Entire Animation)"

    animations = CollectionProperty(
        name="Animations",
        description="",
        type=GameGuiAnimation,
        options=set()
    )

    animation_name: str = StringProperty(
        name="Animation Name",
        description="Name of the animation to play",
        default="(Entire Animation)",
        update=_update_animation_name,
        options=set()
    )

    active_anim_index: int = IntProperty(options={"HIDDEN"})
    show_expanded: bool = BoolProperty(options={"HIDDEN"})

    def export(
            self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject,
            ctrl_obj: pfGUIControlMod, add_func: Callable[[plKey], None],
            anim_name_attr: str
    ):
        keys = set()
        for anim in self.animations:
            target_object = anim.target_object if anim.target_object is not None else bo
            if anim.anim_type == "OBJECT":
                keys.add(exporter.animation.get_animation_key(target_object))
            elif anim.anim_type == "TEXTURE":
                # Layer animations don't respect the name field, so we need to grab exactly the
                # layer animation key that is requested. Cyan's Max plugin does not allow specifying
                # layer animations here as best I can tell, but I don't see why we shouldn't.
                keys.update(
                    exporter.mesh.material.get_texture_animation_key(
                        target_object,
                        anim.target_material,
                        anim.target_texture,
                        self.animation_name
                    )
                )
            else:
                raise RuntimeError()

        # This is to make sure that we only waste space in the PRP file with the animation
        # name if we actually have some doggone animations.
        if keys:
            setattr(ctrl_obj, anim_name_attr, self.animation_name)
            for i in keys:
                add_func(i)


class PlasmaGameGuiButtonModifier(PlasmaModifierProperties, _GameGuiMixin):
    pl_id = "gui_button"
    pl_depends = {"gui_control"}

    bl_category = "GUI"
    bl_label = "Ex: Game GUI Button"
    bl_description = "XXX"

    def _update_notify_type(self, context):
        # It doesn't make sense to have no notify type at all selected, so
        # default to at least one option.
        if not self.notify_type:
            self.notify_type = {"DOWN"}

    notify_type = EnumProperty(
        name="Notify On",
        description="When the button should perform its action",
        items=[
            ("UP", "Up", "When the mouse button is down over the GUI button."),
            ("DOWN", "Down", "When the mouse button is released over the GUI button."),
        ],
        default={"UP"},
        options={"ENUM_FLAG"},
        update=_update_notify_type
    )

    mouse_over_anims: GameGuiAnimationGroup = PointerProperty(type=GameGuiAnimationGroup)
    mouse_click_anims: GameGuiAnimationGroup = PointerProperty(type=GameGuiAnimationGroup)
    show_expanded_sounds: bool = BoolProperty(options={"HIDDEN"})

    mouse_down_sound: str = StringProperty(
        name="Mouse Down SFX",
        description="Sound played when the mouse button is down",
        options=set()
    )

    mouse_up_sound: str = StringProperty(
        name="Mouse Up SFX",
        description="Sound played when the mouse button is released",
        options=set()
    )

    mouse_over_sound: str = StringProperty(
        name="Mouse Over SFX",
        description="Sound played when the mouse moves over the GUI button",
        options=set()
    )

    mouse_off_sound: str = StringProperty(
        name="Mouse Off SFX",
        description="Sound played when the mouse moves off of the GUI button",
        options=set()
    )

    @property
    def gui_sounds(self):
        return (
            ("mouse_down_sound", pfGUIButtonMod.kMouseDown),
            ("mouse_up_sound", pfGUIButtonMod.kMouseUp),
            ("mouse_over_sound", pfGUIButtonMod.kMouseOver),
            ("mouse_off_sound", pfGUIButtonMod.kMouseOff),
        )

    def get_control(self, exporter: Exporter, bo: Optional[bpy.types.Object] = None, so: Optional[plSceneObject] = None) -> pfGUIButtonMod:
        return exporter.mgr.find_create_object(pfGUIButtonMod, bl=bo, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        ctrl = self.get_control(exporter, bo, so)
        ctrl.setFlag(pfGUIControlMod.kWantsInterest, True)

        if self.notify_type == {"UP"}:
            ctrl.notifyType = pfGUIButtonMod.kNotifyOnUp
        elif self.notify_type == {"DOWN"}:
            ctrl.notifyType = pfGUIButtonMod.kNotifyOnDown
        elif self.notify_type == {"UP", "DOWN"}:
            ctrl.notifyType = pfGUIButtonMod.kNotifyOnUpAndDown
        else:
            raise ValueError(self.notify_type)

        self.mouse_over_anims.export(exporter, bo, so, ctrl, ctrl.addMouseOverKey, "mouseOverAnimName")
        self.mouse_click_anims.export(exporter, bo, so, ctrl, ctrl.addAnimationKey, "animName")


class PlasmaGameGuiDialogModifier(PlasmaModifierProperties, _GameGuiMixin):
    pl_id = "gui_dialog"

    bl_category = "GUI"
    bl_label = "Ex: Game GUI Dialog"
    bl_description = "XXX"

    camera_object: bpy.types.Object = PointerProperty(
        name="GUI Camera",
        description="Camera used to project the GUI to screenspace.",
        type=bpy.types.Object,
        poll=idprops.poll_camera_objects,
        options=set()
    )
    is_modal = BoolProperty(
        name="Modal",
        description="",
        default=True,
        options=set()
    )

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        # Find all of the visible objects in the GUI page for use in hither/yon raycast and
        # camera matrix calculations.
        visible_objects = [
            i for i in exporter.get_objects(bo.plasma_object.page)
            if i.type == "MESH" and i.data.materials
        ]

        camera_object = self.id_data if self.id_data.type == "CAMERA" else self.camera_object
        if camera_object:
            exporter.report.msg(f"Using camera matrix from camera '{camera_object.name}'")
            if camera_object != self.id_data and camera_object.plasma_object.enabled:
                with exporter.report.indent():
                    exporter.report.warn("The camera object should NOT be a Plasma Object!")
            camera_matrix = camera_object.matrix_world

            # Save the clipping info from the camera for later use.
            cam_data = camera_object.data
            fov, hither, yonder = cam_data.angle, cam_data.clip_start, cam_data.clip_end
        else:
            exporter.report.msg(f"Building a camera matrix to view: {', '.join((i.name for i in visible_objects))}")
            fov = math.radians(45.0)
            camera_matrix = exporter.gui.calc_camera_matrix(
                bpy.context.scene,
                visible_objects,
                fov
            )

            # There isn't a real camera, so just pretend like the user didn't set the clipping info.
            hither, yonder = 0.0, 0.0
        with exporter.report.indent():
            exporter.report.msg(str(camera_matrix))

        # If no hither or yonder was specified on the camera, then we need to determine that ourselves.
        if not hither or not yonder:
            exporter.report.msg(f"Incomplete clipping: H:{hither:.02f} Y:{yonder:.02f}; calculating new...")
            with exporter.report.indent():
                clipping = exporter.gui.calc_clipping(
                    camera_matrix,
                    bpy.context.scene,
                    visible_objects,
                    fov
                )
                exporter.report.msg(f"Calculated: H:{clipping.hither:.02f} Y:{clipping.yonder:.02f}")
                if not hither:
                    hither = clipping.hither
                if not yonder:
                    yonder = clipping.yonder
                exporter.report.msg(f"Corrected clipping: H:{hither:.02f} Y:{yonder:.02f}")

        # Both of the objects we export go into the pool.
        scene_node_key = exporter.mgr.get_scene_node(bl=bo)

        post_effect = exporter.mgr.find_create_object(plPostEffectMod, bl=bo)
        post_effect.defaultC2W, post_effect.defaultW2C = exporter.gui.convert_post_effect_matrices(camera_matrix)
        post_effect.fovX = math.degrees(fov)
        post_effect.fovY = math.degrees(fov * (3.0 / 4.0))
        post_effect.hither = min((hither, yonder))
        post_effect.yon = max((hither, yonder))
        post_effect.nodeKey = scene_node_key

        dialog_mod = exporter.mgr.find_create_object(pfGUIDialogMod, bl=bo)
        dialog_mod.name = bo.plasma_object.page
        dialog_mod.setFlag(pfGUIDialogMod.kModal, self.is_modal)
        dialog_mod.renderMod = post_effect.key
        dialog_mod.sceneNode = scene_node_key

    @property
    def has_gui_proc(self) -> bool:
        return False

    @classmethod
    def is_game_gui_control(cls) -> bool:
        return False

    def post_export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        # All objects have been exported. Now, we can establish linkage to all controls that
        # have been exported.
        dialog = exporter.mgr.find_object(pfGUIDialogMod, bl=bo, so=so)
        control_modifiers: Iterable[_GameGuiMixin] = itertools.chain.from_iterable(
            obj.plasma_modifiers.gui_control.iterate_control_modifiers()
            for obj in exporter.get_objects(bo.plasma_object.page)
            if obj.plasma_modifiers.gui_control.enabled
        )
        for control_modifier in control_modifiers:
            control = control_modifier.get_control(exporter, control_modifier.id_data)
            ctrl_key = control.key
            exporter.report.msg(f"GUIDialog '{bo.name}': [{control.ClassName()}] '{ctrl_key.name}'")
            dialog.addControl(ctrl_key)
