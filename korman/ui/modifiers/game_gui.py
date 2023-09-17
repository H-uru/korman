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
from typing import *

import bpy.types

from .. import ui_list

if TYPE_CHECKING:
    from ...properties.modifiers.game_gui import GameGuiAnimation, GameGuiAnimationGroup

class GuiAnimListUI(bpy.types.UIList):
    def _iter_target_names(self, item: GameGuiAnimation):
        if item.target_object is not None:
            yield item.target_object.name
        else:
            yield item.id_data.name
        if item.target_material is not None:
            yield item.target_material.name
        if item.target_texture is not None:
            yield item.target_texture.name

    def draw_item(
            self, context, layout, data, item: GameGuiAnimation, icon, active_data,
            active_property, index=0, flt_flag=0
    ):
        if item.anim_type == "OBJECT":
            name = item.target_object.name if item.target_object is not None else item.id_data.name
            layout.label(name, icon="OBJECT_DATA")
        elif item.anim_type == "TEXTURE":
            name_seq = list(self._iter_target_names(item))
            layout.label(" / ".join(name_seq), icon="TEXTURE")
        else:
            raise RuntimeError()


def _gui_anim(name: str, group: GameGuiAnimationGroup, layout, context):
    box = layout.box()
    row = box.row(align=True)

    exicon = "TRIA_DOWN" if group.show_expanded else "TRIA_RIGHT"
    row.prop(group, "show_expanded", text="", icon=exicon, emboss=False)
    row.prop(group, "animation_name", text=name, icon="ANIM")
    if not group.show_expanded:
        return

    ui_list.draw_modifier_list(box, "GuiAnimListUI", group, "animations", "active_anim_index", rows=2)
    try:
        anim: GameGuiAnimation = group.animations[group.active_anim_index]
    except:
        pass
    else:
        col = box.column()
        col.prop(anim, "anim_type")
        col.prop(anim, "target_object")
        if anim.anim_type == "TEXTURE":
            col.prop(anim, "target_material")
            col.prop(anim, "target_texture")


def gui_button(modifier, layout, context):
    row = layout.row()
    row.label("Notify On:")
    row.prop(modifier, "notify_type")

    _gui_anim("Mouse Click", modifier.mouse_click_anims, layout, context)
    _gui_anim("Mouse Over", modifier.mouse_over_anims, layout, context)

    box = layout.box()
    row = box.row(align=True)
    exicon = "TRIA_DOWN" if modifier.show_expanded_sounds else "TRIA_RIGHT"
    row.prop(modifier, "show_expanded_sounds", text="", icon=exicon, emboss=False)
    row.label("Sound Effects")
    if modifier.show_expanded_sounds:
        col = box.column()
        soundemit = modifier.id_data.plasma_modifiers.soundemit
        col.active = soundemit.enabled
        col.prop_search(modifier, "mouse_down_sound", soundemit, "sounds", text="Mouse Down", icon="SPEAKER")
        col.prop_search(modifier, "mouse_up_sound", soundemit, "sounds", text="Mouse Up", icon="SPEAKER")
        col.prop_search(modifier, "mouse_over_sound", soundemit, "sounds", text="Mouse Over", icon="SPEAKER")
        col.prop_search(modifier, "mouse_off_sound", soundemit, "sounds", text="Mouse Off", icon="SPEAKER")

def gui_control(modifier, layout, context):
    split = layout.split()
    col = split.column()
    col.prop(modifier, "visible")

    col = split.column()
    col.prop(modifier, "tag_id")

    col = layout.column()
    col.active = modifier.has_gui_proc
    col.prop(modifier, "proc")
    row = col.row()
    row.active = col.active and modifier.proc == "console_command"
    row.prop(modifier, "console_command")

def gui_dialog(modifier, layout, context):
    row = layout.row(align=True)
    row.prop(modifier, "camera_object")
    op = row.operator("camera.plasma_create_game_gui_camera", text="", icon="CAMERA_DATA")
    op.mod_id = modifier.pl_id
    op.cam_prop_name = "camera_object"
    op.gui_page = modifier.id_data.plasma_object.page

    layout.prop(modifier, "is_modal")
