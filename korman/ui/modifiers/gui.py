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
    layout.separator()

    split = layout.split()
    main_col = split.column()

    main_col.label("Display Settings:")
    col = main_col.column()
    col.active = "pvMoul" in modifier.versions
    col.prop(modifier, "start_state", text="")
    main_col.prop(modifier, "book_type", text="")
    main_col.separator()
    main_col.label("Book Scaling:")
    col = main_col.column(align=True)
    col.prop(modifier, "book_scale_w", text="Width", slider=True)
    col.prop(modifier, "book_scale_h", text="Height", slider=True)

    main_col = split.column()
    main_col.label("Content Translations:")
    main_col.prop(modifier, "active_translation", text="")
    # This should never fail...
    try:
        translation = modifier.journal_translations[modifier.active_translation_index]
    except Exception as e:
        main_col.label(text="Error (see console)", icon="ERROR")
        print(e)
    else:
        main_col.prop(translation, "text_id", text="")
    main_col.separator()

    main_col.label("Clickable Region:")
    main_col.prop(modifier, "clickable_region", text="")

def linkingbookmod(modifier, layout, context):
    def row_alert(prop_name, **kwargs):
        row = layout.row()
        row.alert = not getattr(modifier, prop_name)
        row.prop(modifier, prop_name, **kwargs)

    layout.prop_menu_enum(modifier, "versions")
    layout.separator()

    row = layout.row()
    row.alert = modifier.clickable is None
    row.prop(modifier, "clickable")
    layout.prop(modifier, "clickable_region")

    if "pvMoul" in modifier.versions:
        row_alert("seek_point")
        layout.prop(modifier, "anim_type")
        layout.separator()
        layout.prop(modifier, "link_type")
        row_alert("age_instance")
        if modifier.link_type == "kChildAgeBook":
            row_alert("age_parent")
        if modifier.link_type == "kBasicLink":
            row_alert("age_uuid")

    row_alert("age_name")

    if "pvMoul" in modifier.versions and modifier.link_type == "kOriginalBook":
        layout.separator()
        layout.prop(modifier, "shareable")
        layout.prop(modifier, "share_region")

    if "pvMoul" in modifier.versions:
        layout.separator()
        layout.prop(modifier, "link_destination")
        layout.prop(modifier, "spawn_title")
    layout.prop(modifier, "spawn_point")

    if "pvPots" in modifier.versions:
        layout.separator()
        layout.prop(modifier, "link_panel_image")
        layout.prop(modifier, "book_cover_image")
        layout.prop(modifier, "stamp_image")
        if modifier.stamp_image:
            row = layout.row(align=True)
            row.label("Stamp Position:")
            row.prop(modifier, "stamp_x", text="X")
            row.prop(modifier, "stamp_y", text="Y")

def note_popup(modifier, layout, context):
    layout.prop(modifier, "gui_page")

    row = layout.row(align=True)
    row.prop(modifier, "gui_camera")
    op = row.operator("camera.plasma_create_game_gui_camera", text="", icon="CAMERA_DATA")
    op.mod_id = modifier.pl_id
    op.cam_prop_name = "gui_camera"
    op.gui_page = modifier.gui_page

    layout.prop(modifier, "clickable")
    layout.prop(modifier, "clickable_region")
