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

class AgeButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"

    @classmethod
    def poll(cls, context):
        return context.world and context.scene.render.engine == "PLASMA_GAME"


class PlasmaAgePanel(AgeButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Age"

    def draw(self, context):
        layout = self.layout
        age = context.world.plasma_age

        # Core age settings
        # ...

        # We want a list of pages and an editor below that
        row = layout.row()
        row.template_list(age, "pages", age, "active_page_index", rows=2)
        col = row.column(align=True)
        col.operator("world.plasma_page_add", icon="ZOOMIN", text="")
        col.operator("world.plasma_page_remove", icon="ZOOMOUT", text="")

        # name/id editor for current selection
        if age.active_page_index < len(age.pages):
            active_page = age.pages[age.active_page_index]
            split = layout.split(percentage=0.65)
            col = split.column()
            col.prop(active_page, "name")
            col = split.column()
            col.prop(active_page, "seq_suffix")


class PlasmaEnvironmentPanel(AgeButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Environment"

    def draw(self, context):
        layout = self.layout
        fni = context.world.plasma_fni

        # Column-ize the colors
        split = layout.split()
        col = split.column()
        col.prop(fni, "fog_color")
        col = split.column()
        col.prop(fni, "clear_color")

        layout.prop(fni, "yon")
