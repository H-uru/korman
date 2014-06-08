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

        # We want a list of pages and an editor below that
        row = layout.row()
        row.template_list("UI_UL_list", "pages", age, "pages", age,
                          "active_page_index", rows=2)
        col = row.column(align=True)
        col.operator("world.plasma_page_add", icon="ZOOMIN", text="")
        col.operator("world.plasma_page_remove", icon="ZOOMOUT", text="")

        # Page Properties
        if age.active_page_index < len(age.pages):
            active_page = age.pages[age.active_page_index]
            split = layout.box().split()
            col = split.column()
            col.prop(active_page, "name", text="")
            col.prop(active_page, "auto_load")

            col = split.column()
            col.prop(active_page, "seq_suffix")
            col.prop(active_page, "local_only")

        # Core settings
        row = layout.row()
        row.prop(age, "day_length")
        row.prop(age, "seq_prefix", text="ID")
        layout.prop(age, "start_time")


class PlasmaEnvironmentPanel(AgeButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Environment"

    def draw(self, context):
        layout = self.layout
        fni = context.world.plasma_fni

        # basic colors
        split = layout.split()
        col = split.column()
        col.prop(fni, "fog_color")
        col = split.column()
        col.prop(fni, "clear_color")

        # fog box
        split = layout.box()
        row = split.row().split(percentage=0.50)
        row.column().prop_menu_enum(fni, "fog_method")
        if fni.fog_method == "linear":
            row.column().prop(fni, "fog_start")
        if fni.fog_method != "none":
            row = split.row()
            row.prop(fni, "fog_density")
            row.prop(fni, "fog_end")

        # tacked on: draw distance
        layout.prop(fni, "yon")
