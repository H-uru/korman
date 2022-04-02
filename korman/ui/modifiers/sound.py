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

from .. import ui_list

def random_sound(modifier, layout, context):
    parent_bo = modifier.id_data.parent
    collision_bad = (modifier.mode == "collision" and (parent_bo is None or
                                                       not parent_bo.plasma_modifiers.collision.enabled))
    layout.alert = collision_bad
    layout.prop(modifier, "mode")
    if collision_bad:
        layout.label(icon="ERROR", text="Sound emitter must be parented to a collider.")
    layout.alert = False

    layout.separator()
    if modifier.mode == "random":
        split = layout.split()
        col = split.column()
        col.prop(modifier, "play_mode", text="")
        col.prop(modifier, "auto_start")
        col = col.column()
        col.active = not modifier.stop_after_play
        col.prop(modifier, "stop_after_set")

        col = split.column()
        col.prop(modifier, "stop_after_play")
        col = col.column(align=True)
        col.active = not modifier.stop_after_play
        col.alert = modifier.min_delay > modifier.max_delay
        col.prop(modifier, "min_delay")
        col.prop(modifier, "max_delay")
    elif modifier.mode == "collision":
        layout.prop(modifier, "play_on")
        # Ugh, Blender...
        layout.alert = len(modifier.surfaces) == 0
        layout.prop_menu_enum(modifier, "surfaces")

def _draw_fade_ui(modifier, layout, label):
    layout.label(label)
    layout.prop(modifier, "fade_type", text="")
    layout.prop(modifier, "length")

class SoundListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if item.sound:
            layout.prop(item, "name", emboss=False, icon="SOUND", text="")
            layout.prop(item, "enabled", text="")
        else:
            layout.label("[Empty]")


def soundemit(modifier, layout, context):
    ui_list.draw_modifier_list(layout, "SoundListUI", modifier, "sounds",
                               "active_sound_index", rows=2, maxrows=3)

    try:
        sound = modifier.sounds[modifier.active_sound_index]
    except:
        pass
    else:
        split = layout.split(percentage=0.75)
        col = split.column()

        # Sound datablock picker
        row = col.row(align=True)
        row.prop(sound, "sound", text="")
        open_op = row.operator("sound.plasma_open", icon="FILESEL", text="")
        open_op.data_path = repr(sound)
        open_op.sound_property = "sound"

        # Pack/Unpack
        data = sound.sound
        if data is not None:
            if data.packed_file is None:
                row.operator("sound.plasma_pack", icon="UGLYPACKAGE", text="")
            else:
                row.operator_menu_enum("sound.plasma_unpack", "method", icon="PACKAGE", text="")

        col = split.column()
        col.enabled = data is not None
        col.prop(sound, "package", text="Export")

        # If an invalid sound data block is spec'd, let them know about it.
        if data and not sound.is_valid:
            layout.label(text="Invalid sound specified", icon="ERROR")

        # Core Props
        row = layout.row()
        row.prop(sound, "sfx_type", text="")
        row.prop_menu_enum(sound, "channel")

        split = layout.split()
        col = split.column()
        col.label("Playback:")
        col.prop(sound, "auto_start")
        col.prop(sound, "incidental")
        col.prop(sound, "loop")
        col.prop(sound, "local_only")

        col.separator()
        _draw_fade_ui(sound.fade_in, col, "Fade In:")
        col.separator()
        _draw_fade_ui(sound.fade_out, col, "Fade Out:")

        col = split.column()
        col.label("Cone Effect:")
        col.prop(sound, "inner_cone")
        col.prop(sound, "outer_cone")
        col.prop(sound, "outside_volume", text="Volume")

        col.separator()
        col.label("Volume Falloff:")
        col.prop(sound, "min_falloff", text="Begin")
        col.prop(sound, "max_falloff", text="End")
        col.prop(sound, "volume", text="Max Volume")

        # Only allow SoftVolume spec if this is not an FX and this object is not an SV itself
        sv = modifier.id_data.plasma_modifiers.softvolume
        if not sv.enabled:
            col.separator()
            col.label("Soft Region:")
            col.prop(sound, "sfx_region", text="")
