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
