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

from ..korlib import ConsoleToggler


class AgeButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"

    @classmethod
    def poll(cls, context):
        return context.world and context.scene.render.engine == "PLASMA_GAME"


class PlasmaGamePanel(AgeButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Games"

    def draw(self, context):
        layout = self.layout
        prefs = context.user_preferences.addons["korman"].preferences
        games = context.world.plasma_games
        age = context.world.plasma_age

        row = layout.row()
        # Remember: game storage moved to addon preferences!
        row.template_list("PlasmaGameListRO", "games", prefs, "games", games,
                          "active_game_index", rows=2)
        row.operator("ui.korman_open_prefs", icon="PREFERENCES", text="")

        # Game Tools
        active_game_index = games.active_game_index
        if active_game_index < len(prefs.games):
            active_game = prefs.games[active_game_index]
        else:
            active_game = None

        layout.separator()
        row = layout.row(align=True)

        row.operator_context = "EXEC_DEFAULT"
        row.enabled = bool(age.age_name.strip()) and active_game is not None
        op = row.operator("export.plasma_age", icon="EXPORT")
        if active_game is not None:
            op.dat_only = False
            op.filepath = str((Path(active_game.path) / "dat" / age.age_name).with_suffix(".age"))
            op.version = active_game.version
        row = row.row(align=True)
        row.operator_context = "INVOKE_DEFAULT"
        op = row.operator("export.plasma_age", icon="PACKAGE", text="Package Age")
        if active_game is not None:
            op.dat_only = False
            op.filepath = "{}.zip".format(age.age_name)
            op.version = active_game.version


class PlasmaGameListRO(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.label(item.name, icon="BOOKMARKS")

class PlasmaGameListRW(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.prop(item, "name", text="", emboss=False, icon="BOOKMARKS")


class PlasmaPageList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.prop(item, "name", text="", emboss=False, icon="BOOKMARKS")
        layout.prop(item, "enabled", text="")


class PlasmaAgePanel(AgeButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Age"

    def draw(self, context):
        layout = self.layout
        age = context.world.plasma_age

        # We want a list of pages and an editor below that
        row = layout.row()
        row.template_list("PlasmaPageList", "pages", age, "pages", age,
                          "active_page_index", rows=2)
        col = row.column(align=True)
        col.operator("world.plasma_page_add", icon="ZOOMIN", text="")
        col.operator("world.plasma_page_remove", icon="ZOOMOUT", text="")

        # Page Properties
        if age.active_page_index < len(age.pages):
            active_page = age.pages[age.active_page_index]

            layout.separator()
            box = layout.box()
            split = box.split()

            col = split.column()
            col.label("Page Flags:")
            col.prop(active_page, "auto_load")
            col.prop(active_page, "local_only")

            col = split.column()
            col.label("Page Info:")
            col.prop(active_page, "name", text="")
            col.prop(active_page, "seq_suffix")
            col.prop_menu_enum(active_page, "version")

        # Core settings
        layout.separator()
        split = layout.split()

        col = split.column()
        col.label("Age Time:")
        col.prop(age, "start_time", text="Epoch")
        col.prop(age, "day_length")

        col = split.column()
        col.label("Age Settings:")
        col.prop(age, "seq_prefix", text="ID")
        col.alert = not age.age_name.strip()
        col.prop(age, "age_name", text="")

        layout.separator()
        split = layout.split()

        col = split.column()
        col.label("Export Settings:")
        col.enabled = ConsoleToggler.is_platform_supported()
        col.prop(age, "verbose")
        col.prop(age, "show_console")

        col = split.column()
        col.label("Plasma Settings:")
        col.prop(age, "age_sdl")
        col.prop(age, "use_texture_page")

        layout.separator()
        layout.prop(age, "envmap_method")
        layout.prop(age, "lighting_method")
        layout.prop(age, "texcache_method")


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

        split = layout.split()
        col = split.column()
        col.label("Fog Settings:")
        col.prop_menu_enum(fni, "fog_method")
        col.separator()
        if fni.fog_method == "linear":
            col.prop(fni, "fog_start")
        if fni.fog_method != "none":
            col.prop(fni, "fog_end")
            col.prop(fni, "fog_density")

        col = split.column()
        col.label("Draw Settings:")
        col.prop(fni, "yon", text="Clipping")
