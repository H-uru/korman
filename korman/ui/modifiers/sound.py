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

class SoundListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if item.sound_data:
            sound = bpy.data.sounds.get(item.sound_data)
            icon = "SOUND" if sound is not None else "ERROR"
            layout.prop(item, "sound_data", emboss=False, icon=icon, text="")
            layout.prop(item, "enabled", text="")
        else:
            layout.label("[Empty]")


def soundemit(modifier, layout, context):
    row = layout.row()
    row.template_list("SoundListUI", "sounds", modifier, "sounds", modifier, "active_sound_index",
                      rows=2, maxrows=3)
    col = row.column(align=True)
    op = col.operator("object.plasma_modifier_collection_add", icon="ZOOMIN", text="")
    op.modifier = modifier.pl_id
    op.collection = "sounds"
    op = col.operator("object.plasma_modifier_collection_remove", icon="ZOOMOUT", text="")
    op.modifier = modifier.pl_id
    op.collection = "sounds"
    op.index = modifier.active_sound_index

    try:
        sound = modifier.sounds[modifier.active_sound_index]
    except:
        pass
    else:
        # Sound datablock picker
        row = layout.row(align=True)
        row.prop_search(sound, "sound_data", bpy.data, "sounds", text="")
        open_op = row.operator("sound.plasma_open", icon="FILESEL", text="")
        open_op.data_path = repr(sound)
        open_op.sound_property = "sound_data"

        # Pack/Unpack
        data = bpy.data.sounds.get(sound.sound_data)
        if data is not None:
            if data.packed_file is None:
                row.operator("sound.plasma_pack", icon="UGLYPACKAGE", text="")
            else:
                row.operator_menu_enum("sound.plasma_unpack", "method", icon="PACKAGE", text="")
