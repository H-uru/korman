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
from pathlib import Path

from . import ui_list

class ImageListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if item.image is None:
            layout.label("[No Image Specified]", icon="ERROR")
        else:
            layout.label(str(Path(item.image.name).with_suffix(".hsm")), icon_value=item.image.preview.icon_id)
            layout.prop(item, "enabled", text="")


def imagelibmod(modifier, layout, context):
    ui_list.draw_modifier_list(layout, "ImageListUI", modifier, "images", "active_image_index", rows=3, maxrows=6)

    if modifier.images:
        row = layout.row(align=True)
        row.template_ID(modifier.images[modifier.active_image_index], "image", open="image.open")

def journalbookmod(modifier, layout, context):
    layout.prop_menu_enum(modifier, "versions")

    if not {"pvPrime", "pvMoul"}.isdisjoint(modifier.versions):
        layout.prop(modifier, "start_state")

    if not {"pvPots", "pvMoul"}.isdisjoint(modifier.versions):
        layout.prop(modifier, "book_type")
        row = layout.row(align=True)
        row.label("Book Scaling:")
        row.prop(modifier, "book_scale_w", text="Width", slider=True)
        row.prop(modifier, "book_scale_h", text="Height", slider=True)

    if "pvPrime" in modifier.versions:
        layout.prop(modifier, "book_source_name", text="Name")
    if "pvPots" in modifier.versions:
        layout.prop(modifier, "book_source_filename", text="Filename")
    if "pvMoul" in modifier.versions:
        layout.prop(modifier, "book_source_locpath", text="LocPath")

    layout.prop(modifier, "clickable_region")
