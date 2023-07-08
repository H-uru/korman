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

def gui_button(modifier, layout, context):
    row = layout.row()
    row.label("Notify On:")
    row.prop(modifier, "notify_type")

    soundemit = modifier.id_data.plasma_modifiers.soundemit
    col = layout.column()
    col.label("Sound Effects:")
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
