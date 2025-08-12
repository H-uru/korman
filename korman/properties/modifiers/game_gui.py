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
from .gui import (
    _DEFAULT_LANGUAGE_NAME, languages,
    TranslationItem, TranslationMixin
)
from ... import idprops

if TYPE_CHECKING:
    from ...exporter import Exporter
    from ..prop_world import PlasmaAge, PlasmaPage


class GameGuiTranslationItem(TranslationItem, bpy.types.PropertyGroup):
    language = EnumProperty(
        name="Language",
        description="Language of this translation",
        items=languages,
        default=_DEFAULT_LANGUAGE_NAME,
        options=set()
    )
    value = StringProperty(
        name="Text",
        description="",
        options=set()
    )

    @property
    def text(self) -> str:
        return self.value


class _GameGuiMixin:
    @property
    def allow_better_hit_testing(self) -> bool:
        return False

    @property
    def copy_material(self) -> bool:
        # If this control uses a dynamic text map, then its contents are unique.
        # Therefore, we need to copy the material.
        return self.requires_dyntext

    @property
    def gui_sounds(self) -> Dict[str, int]:
        """Overload to automatically export GUI sounds on the control.
           This should return a dict of string attribute names to indices.
        """
        return {}

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

    def sanity_check(self, exporter):
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
        for attr_name in self.gui_sounds:
            sound_name = getattr(self, attr_name)
            if not sound_name:
                continue
            sound = next((i for i in soundemit.sounds if i.name == sound_name), None)
            if sound is None:
                raise ExportError(f"'{self.id_data.name}': Invalid '{attr_name}' GUI Sound '{sound_name}'")

    @property
    def wants_colorscheme(self) -> bool:
        return self.requires_dyntext


class PlasmaGameGuiColorSchemeModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_colorscheme"
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "Color Scheme (ex)"
    bl_description = "XXX"
    bl_icon = "COLOR"

    foreground_color = FloatVectorProperty(
        name="Foreground",
        description="",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        subtype="COLOR",
        size=4,
        options=set()
    )
    background_color = FloatVectorProperty(
        name="Background",
        description="",
        default=(0.0, 0.0, 0.0, 0.0),
        min=0.0, max=1.0,
        subtype="COLOR",
        size=4,
        options=set()
    )
    selection_foreground_color = FloatVectorProperty(
        name="Selection Foreground",
        description="",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        subtype="COLOR",
        size=4,
        options=set()
    )
    selection_background_color = FloatVectorProperty(
        name="Selection Background",
        description="",
        default=(0.0, 0.0, 0.0, 0.0),
        min=0.0, max=1.0,
        subtype="COLOR",
        size=4,
        options=set()
    )

    font_face: str = StringProperty(
        name="Font Face",
        description="",
        default="Arial",
        options=set()
    )
    font_size: int = IntProperty(
        name="Size",
        description="",
        default=12,
        subtype="UNSIGNED",
        soft_min=8,
        min=1,
        step=2,
        options=set()
    )
    font_style = EnumProperty(
        name="Style",
        description="",
        items=[
            ("kFontBold", "Bold", ""),
            ("kFontItalic", "Italic", ""),
            ("kFontShadowed", "Shadowed", ""),
        ],
        options={"ENUM_FLAG"}
    )

    def convert_colorscheme(self) -> pfGUIColorScheme:
        scheme = pfGUIColorScheme()
        scheme.foreColor = hsColorRGBA(*self.foreground_color)
        scheme.backColor = hsColorRGBA(*self.background_color)
        scheme.selForeColor = hsColorRGBA(*self.selection_foreground_color)
        scheme.selBackColor = hsColorRGBA(*self.selection_background_color)
        scheme.fontFace = self.font_face
        scheme.fontSize = self.font_size
        for flag in self.font_style:
            scheme.fontFlags |= getattr(pfGUIColorScheme, flag)
        return scheme

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        scheme_targets: Iterable[_GameGuiMixin] = (
            getattr(self.id_data.plasma_modifiers, i.pl_id)
            for i in _GameGuiMixin.__subclasses__()
        )
        scheme_targets: List[_GameGuiMixin] = [i for i in scheme_targets if i.wants_colorscheme]

        if not scheme_targets:
            exporter.report.warn("This modifier has no effect because no GUI modifiers want a color scheme!")
            return

        # Internally, libHSPlasma will steal the color scheme that we give to pfGUIControlMods,
        # so we need to give each control a unique color scheme object. Dialogs will copy, but
        # that's a less common case.
        for i in scheme_targets:
            ctrl = i.get_control(exporter, i.id_data)
            if ctrl is not None:
                ctrl.colorScheme = self.convert_colorscheme()

    @classmethod
    def is_game_gui_control(cls):
        # This is just an optional field on the GUI control itself.
        # It's also on dialogs themselves, so we separate it from
        # the main control.
        return False


class PlasmaGameGuiControlModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_control"
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Control (ex)"
    bl_description = "XXX"
    bl_object_types = {"FONT", "MESH"}

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
    texture = PointerProperty(
        name="Texture",
        description="The texture to draw GUI content on",
        type=bpy.types.Texture,
        poll=idprops.poll_object_dyntexts
    )
    hit_testing = EnumProperty(
        name="Hit Testing",
        description="",
        items=[
            ("bounding_box", "Bounding Box", ""),
            ("hull", "2D Convex Hull", ""),
        ],
        options=set()
    )

    def sanity_check(self, exporter: Exporter):
        if self.requires_dyntext and self.texture is None:
            raise ExportError(f"'{self.id_data.name}': GUI Control requires a Texture to draw onto.")

    def convert_gui_control(
        self, exporter: Exporter,
        ctrl: pfGUIControlMod, ctrl_mod: _GameGuiMixin,
        bo: bpy.types.Object, so: plSceneObject
    ) -> None:
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
        else:
            raise ValueError(self.proc)

        if ctrl_mod.allow_better_hit_testing:
            ctrl.setFlag(
                pfGUIControlMod.kBetterHitTesting,
                self.hit_testing == "hull"
            )

    def convert_gui_sounds(self, exporter: Exporter, ctrl: pfGUIControlMod, ctrl_mod: _GameGuiMixin):
        soundemit = ctrl_mod.id_data.plasma_modifiers.soundemit
        if not ctrl_mod.gui_sounds or not soundemit.enabled:
            return

        # This is a lot like the plPhysicalSndGroup where we have a vector behaving as a lookup table.
        # NOTE that zero is a special value here meaning no sound, so we need to offset the sounds
        # that we get from the emitter modifier by +1.
        sound_indices = {}
        for attr_name, gui_sound_idx in ctrl_mod.gui_sounds.items():
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

    def convert_gui_dyntext(self, exporter: Exporter, ctrl: pfGUIControlMod, ctrl_mod: _GameGuiMixin, bo: bpy.types.Object, so: plSceneObject):
        if not ctrl_mod.requires_dyntext:
            return

        layers = tuple(exporter.mesh.material.get_layers(bo=bo, tex=self.texture))
        num_layers = len(layers)
        if num_layers > 1:
            exporter.report.warn(f"GUI Texture '{self.texture.name}' mapped to {len(layers)} Plasma Layers. This can only be 1.")
        elif num_layers == 0:
            raise ExportError(f"'{bo.name}': Unable to lookup GUI Texture!")

        ctrl.dynTextLayer = layers[0]
        ctrl.dynTextMap = layers[0].object.texture

        # This is basically the blockRGB flag on the DynaTextMap
        ctrl.setFlag(pfGUIControlMod.kXparentBgnd, self.texture.use_alpha)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        ctrl_mods = list(self.iterate_control_modifiers())
        if not ctrl_mods:
            exporter.report.msg(str(list(self.iterate_control_subclasses())))
            exporter.report.warn("This modifier has no effect because no GUI control modifiers are present!")
        for ctrl_mod in ctrl_mods:
            ctrl_obj = ctrl_mod.get_control(exporter, bo, so)
            if ctrl_obj is not None:
                self.convert_gui_control(exporter, ctrl_obj, ctrl_mod, bo, so)
                self.convert_gui_sounds(exporter, ctrl_obj, ctrl_mod)

    def post_export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        for ctrl_mod in self.iterate_control_modifiers():
            ctrl_obj = ctrl_mod.get_control(exporter, bo, so)
            if ctrl_obj is not None:
                self.convert_gui_dyntext(exporter, ctrl_obj, ctrl_mod, bo, so)

    @property
    def allow_better_hit_testing(self) -> bool:
        return any((i.allow_better_hit_testing for i in self.iterate_control_modifiers()))

    @property
    def has_gui_proc(self) -> bool:
        return any((i.has_gui_proc for i in self.iterate_control_modifiers()))

    @classmethod
    def is_game_gui_control(cls) -> bool:
        # How is a control not a control, you ask? Because, grasshopper, this modifier does not
        # actually export a GUI control itself. Instead, it holds common properties that may
        # or may not be used by other controls. This just helps fill out the other modifiers.
        return False

    @property
    def requires_dyntext(self) -> bool:
        return any((i.requires_dyntext for i in self.iterate_control_modifiers()))


class GameGuiAnimation(bpy.types.PropertyGroup):
    def _poll_target_object(self, value):
        # Only allow targetting things that are in our GUI page.
        if value.plasma_object.page != self.id_data.plasma_object.page:
            return False
        if self.anim_type == "OBJECT":
            return idprops.poll_animated_objects(self, value)
        else:
            return idprops.poll_drawable_objects(self, value)

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
    target_object: bpy.types.Object = idprops.triprop_object(
        "target_object", "target_material", "target_texure",
        name="Object",
        description="Target object",
        poll=_poll_target_object,
    )
    target_material: bpy.types.Material = idprops.triprop_material(
        "target_object", "target_material", "target_texure",
        name="Material",
        description="Target material",
    )
    target_texture: bpy.types.Texture = idprops.triprop_texture(
        "target_object", "target_material", "target_texure",
        name="Texture",
        description="Target texture",
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


class PlasmaGameGuiButtonModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_button"
    pl_depends = {"gui_control"}
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Button (ex)"
    bl_description = "XXX"
    bl_icon = "BUTS"
    bl_object_types = {"FONT", "MESH"}

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
    def allow_better_hit_testing(self):
        return True

    @property
    def gui_sounds(self) -> Dict[str, int]:
        return {
            "mouse_down_sound": pfGUIButtonMod.kMouseDown,
            "mouse_up_sound": pfGUIButtonMod.kMouseUp,
            "mouse_over_sound": pfGUIButtonMod.kMouseOver,
            "mouse_off_sound": pfGUIButtonMod.kMouseOff,
        }

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



class PlasmaGameGuiCheckBoxModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_checkbox"
    pl_depends = {"gui_control"}
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Checkbox (ex)"
    bl_description = "XXX"
    bl_icon = "CHECKBOX_HLT"
    bl_object_types = {"MESH"}

    def _update_notify_type(self, context):
        # It doesn't make sense to have no notify type at all selected, so
        # default to at least one option.
        if not self.notify_type:
            self.notify_type = {"DOWN"}

    anims: GameGuiAnimationGroup = PointerProperty(type=GameGuiAnimationGroup)
    show_expanded_sounds: bool = BoolProperty(options={"HIDDEN"})

    checked_value: bool = BoolProperty(options={"HIDDEN"})

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

    def _poll_radio_group(self, object: bpy.types.Object):
        if object.plasma_object.page == self.id_data.plasma_object.page:
            if object.plasma_modifiers.gui_radio_group.enabled:
                return True
        return False

    def _iter_other_checkboxes(self, context: bpy.types.Context) -> Iterator[Self]:
        if self.radio_group is None:
            return
        rg_mod = self.radio_group.plasma_modifiers.gui_radio_group
        for i in rg_mod.iter_checkbox_mods(context):
            if i.id_data.name != self.id_data.name:
                yield i

    def _get_checked(self) -> bool:
        # Short circuit if we don't think we're checked
        if not self.checked_value:
            return False

        if self.radio_group is not None:
            others = self._iter_other_checkboxes(bpy.context)
            if any(i.checked_value for i in others):
                return False

        return self.checked_value

    def _set_checked(self, value: bool) -> None:
        if not value:
            self.checked_value = False
            return

        for i in self._iter_other_checkboxes(bpy.context):
            i.checked_value = False
        self.checked_value = True

    checked: bool = BoolProperty(
        name="Checked",
        description="Whether or not the checkbox is checked by default",
        get=_get_checked,
        set=_set_checked,
        options=set()
    )

    radio_group = PointerProperty(
        name="Radio Group",
        description="",
        type=bpy.types.Object,
        poll=_poll_radio_group
    )

    @property
    def allow_better_hit_testing(self):
        return True

    @property
    def gui_sounds(self) -> Dict[str, int]:
        return {
            "mouse_down_sound": pfGUICheckBoxCtrl.kMouseDown,
            "mouse_up_sound": pfGUICheckBoxCtrl.kMouseUp,
            "mouse_over_sound": pfGUICheckBoxCtrl.kMouseOver,
            "mouse_off_sound": pfGUICheckBoxCtrl.kMouseOff,
        }

    def get_control(self, exporter: Exporter, bo: Optional[bpy.types.Object] = None, so: Optional[plSceneObject] = None) -> pfGUICheckBoxCtrl:
        return exporter.mgr.find_create_object(pfGUICheckBoxCtrl, bl=bo, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        ctrl = self.get_control(exporter, bo, so)
        ctrl.setFlag(pfGUIControlMod.kWantsInterest, True)
        ctrl.checked = self.checked

        self.anims.export(exporter, bo, so, ctrl, ctrl.addAnimKey, "animName")


class PlasamGameGuiClickMapModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_clickmap"
    pl_depends = {"gui_control"}
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI ClickMap (ex)"
    bl_description = "XXX"
    bl_icon = "HAND"

    report_while: Set[str] = EnumProperty(
        name="Report While",
        description="",
        items=[
            ("kMouseDragged", "Dragging", ""),
            ("kMouseHovered", "Hovering", ""),
        ],
        options={"ENUM_FLAG"}
    )

    def get_control(self, exporter: Exporter, bo: Optional[bpy.types.Object] = None, so: Optional[plSceneObject] = None) -> pfGUIClickMapCtrl:
        return exporter.mgr.find_create_object(pfGUIClickMapCtrl, bl=bo, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        ctrl = self.get_control(exporter, bo, so)
        for report in self.report_while:
            ctrl.setFlag(getattr(pfGUIClickMapCtrl, report), True)


class PlasmaGameGuiDragBarModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_dragbar"
    pl_depends = {"gui_control"}
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Drag Bar (ex)"
    bl_description = "XXX"
    bl_icon = "ARROW_LEFTRIGHT"

    @property
    def allow_better_hit_testing(self):
        return True

    def get_control(self, exporter: Exporter, bo: Optional[bpy.types.Object] = None, so: Optional[plSceneObject] = None) -> pfGUIDragBarCtrl:
        return exporter.mgr.find_create_object(pfGUIDragBarCtrl, bl=bo, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        ctrl = self.get_control(exporter, bo, so)

    @property
    def requires_actor(self) -> bool:
        return True


class PlasmaGameGuiDynamicDisplayModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_dynamic_display"
    pl_depends = {"gui_control"}
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Dynamic Display (ex)"
    bl_description = "XXX"
    bl_icon = "TPAINT_HLT"

    texture = PointerProperty(
        name="Texture",
        description="Texture this GUI control can modify",
        type=bpy.types.Texture,
        poll=idprops.poll_object_image_textures
    )

    def sanity_check(self, exporter):
        if self.texture is None:
            raise ExportError(f"'{self.id_data.name}': GUI Dynamic Display Modifier requires a Texture!")

    def get_control(self, exporter: Exporter, bo: Optional[bpy.types.Object] = None, so: Optional[plSceneObject] = None) -> pfGUIDynDisplayCtrl:
        return exporter.mgr.find_create_object(pfGUIDynDisplayCtrl, bl=bo, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject) -> None:
        ctrl = self.get_control(exporter, bo, so)

        layers = exporter.mesh.material.get_layers(bo, tex=self.texture)
        materials = exporter.mesh.material.get_materials(bo)
        for layer in layers:
            ctrl.addLayer(layer)
            tex_key = layer.object.texture

            # It is completely possible and legal to have a plMipmap. That
            # happens on journal covers. We're provided a default cover
            # texture that could be swapped out.
            if tex_key is not None and tex_key.type == plFactory.kDynamicTextMap:
                ctrl.addTextMap(tex_key)

            # This is a little lazy, but GUIs are so uncommon that we
            # don't need to sweat efficiency.
            for material in materials:
                bottom_iter = (i.object.bottomOfStack for i in material.object.layers)
                if layer.object.bottomOfStack in bottom_iter:
                    # PlasmaMax unconditionally adds materials, but that seems
                    # a little wasteful.
                    if material not in ctrl.materials:
                        ctrl.addMaterial(material)


class PlasmaGameGuiRadioGroupModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_radio_group"
    pl_depends = {"gui_control"}
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Radio Group (ex)"
    bl_description = "XXX"
    bl_icon = "RADIOBUT_ON"

    allow_no_selection = BoolProperty(
        name="Allow No Selection",
        description="Allows no check boxes to be checked",
        options=set()
    )

    def get_control(self, exporter: Exporter, bo = None, so = None) -> pfGUIRadioGroupCtrl:
        return exporter.mgr.find_create_object(pfGUIRadioGroupCtrl, bl=bo, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject) -> None:
        ctrl = self.get_control(exporter, bo, so)
        ctrl.setFlag(pfGUIRadioGroupCtrl.kAllowNoSelection, self.allow_no_selection)
        active_cbs = (
            i for i in self.iter_checkbox_mods(bpy.context)
            if i.id_data.plasma_object.enabled
        )
        for i, cb_mod in enumerate(active_cbs):
            exporter.report.msg(f"Found checkbox '{cb_mod.id_data.name}'")
            ctrl.addControl(cb_mod.get_control(exporter, i.id_data).key)
            if cb_mod.checked:
                ctrl.defaultValue = i

    def iter_checkbox_mods(self, context: bpy.types.Context) -> Iterator[PlasmaGameGuiCheckBoxModifier]:
        # This is really not the fastest way to do this. The fastest way would be for us
        # to maintain a list of the checkbox children here. But that means the user could
        # try to add a single checkbox to multiple radio groups. That seems silly, but it
        # feels like a problem waiting to happen. So, instead, we'll set the radio group
        # on the checkboxes themselves to prevent that tomfoolery. It does mean the export
        # will be slightly slower because we have to iterate all of the objects in the scene
        # to find checkboxes, but it should be negligible.
        for i in context.scene.objects:
            checkbox_mod: PlasmaGameGuiCheckBoxModifier = i.plasma_modifiers.gui_checkbox
            if not checkbox_mod.enabled:
                continue

            rg = checkbox_mod.radio_group
            if rg is not None and rg.name == self.id_data.name:
                yield checkbox_mod


class PlasmaGameGuiTextBoxModifier(_GameGuiMixin, TranslationMixin, PlasmaModifierProperties):
    pl_id = "gui_textbox"
    pl_depends = {"gui_control"}
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Text Box (ex)"
    bl_description = "XXX"
    bl_icon = "SYNTAX_OFF"
    bl_object_types = {"MESH"}

    _JUSTIFICATION_LUT = {
        "center": pfGUITextBoxMod.kCenterJustify,
        "right": pfGUITextBoxMod.kRightJustify,
    }

    justification: str = EnumProperty(
        name="Justification",
        description="",
        items=[
            ("left", "Left", ""),
            ("center", "Center", ""),
            ("right", "Right", ""),
        ],
        options=set()
    )

    text_translations = CollectionProperty(
        name="Translations",
        type=GameGuiTranslationItem,
        options=set()
    )
    active_translation_index = IntProperty(options={"HIDDEN"})
    active_translation = EnumProperty(
        name="Language",
        description="Language of this translation",
        items=languages,
        get=TranslationMixin._get_translation,
        set=TranslationMixin._set_translation,
        options=set()
    )

    def convert_string(self, exporter: Exporter) -> str:
        with exporter.report.indent():
            exporter.report.msg("Converting legacy GUI localization...")
            value = exporter.locman.get_localized_string(
                { i.language: i.text for i in self.translations if i.text }
            )
            exporter.report.msg(value)
            return value

    def export_localization(self, exporter: Exporter):
        # Only MOUL, EoA, and Hex Isle have pfLocalization support in GUIs.
        # Otherwise, this translation mixin does something we don't actually want.
        ctrl = self.get_control(exporter, self.id_data)
        if exporter.mgr.getVer() >= pvMoul:
            super().export_localization(exporter)
            ctrl.localizationPath = f"{exporter.age_name}.{self.localization_set}.{self.key_name}"
        else:
            ctrl.text = self.convert_string(exporter)

    def get_control(self, exporter: Exporter, bo: Optional[bpy.types.Object] = None, so: Optional[plSceneObject] = None) -> pfGUITextBoxMod:
        return exporter.mgr.find_create_object(pfGUITextBoxMod, bl=bo, so=so)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        ctrl = self.get_control(exporter, bo, so)
        ctrl.setFlag(pfGUIControlMod.kIntangible, True)

        just_flag = self._JUSTIFICATION_LUT.get(self.justification)
        if just_flag is not None:
            ctrl.setFlag(just_flag, True)

    @property
    def localization_set(self) -> str:
        return "GUI"

    @property
    def translations(self) -> Iterable[GameGuiTranslationItem]:
        return self.text_translations

    @property
    def requires_dyntext(self):
        return True


class PlasmaGameGuiDialogModifier(_GameGuiMixin, PlasmaModifierProperties):
    pl_id = "gui_dialog"
    pl_page_types = {"gui"}

    bl_category = "GUI"
    bl_label = "GUI Dialog (ex)"
    bl_description = "XXX"
    bl_icon = "SPLITSCREEN"

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

    def get_control(self, exporter: Exporter, bo = None, so = None) -> pfGUIDialogMod:
        # This isn't really a control, but we may need this.
        return exporter.mgr.find_create_object(pfGUIDialogMod, bl=bo, so=so)

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

    @property
    def wants_colorscheme(self) -> bool:
        return True
