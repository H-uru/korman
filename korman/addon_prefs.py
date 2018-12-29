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
from bpy.props import *

game_versions = [("pvPrime", "Ages Beyond Myst (63.11)", "Targets the original Uru (Live) game"),
                 ("pvPots", "Path of the Shell (63.12)", "Targets the most recent offline expansion pack"),
                 ("pvMoul", "Myst Online: Uru Live (70)", "Targets the most recent online game")]

class PlasmaGame(bpy.types.PropertyGroup):
    name = StringProperty(name="Name",
                          description="Name of the Plasma Game",
                          options=set())
    path = StringProperty(name="Path",
                          description="Path to this Plasma Game",
                          options=set())
    version = EnumProperty(name="Version",
                           description="Plasma version of this game",
                           items=game_versions,
                           options=set())


class KormanAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    games = CollectionProperty(type=PlasmaGame)
    active_game_index = IntProperty(options={"SKIP_SAVE"})

    def draw(self, context):
        layout = self.layout

        layout.label("Plasma Games:")
        row = layout.row()
        row.template_list("PlasmaGameListRW", "games", self, "games", self,
                          "active_game_index", rows=2)
        col = row.column(align=True)
        col.operator("world.plasma_game_add", icon="ZOOMIN", text="")
        col.operator("world.plasma_game_remove", icon="ZOOMOUT", text="")
        col.operator("world.plasma_game_convert", icon="IMPORT", text="")

        # Game Properties
        active_game_index = self.active_game_index
        if bool(self.games) and active_game_index < len(self.games):
            active_game = self.games[active_game_index]

            layout.separator()
            box = layout.box()

            box.prop(active_game, "path", emboss=False)
            box.prop(active_game, "version")
            box.separator()

            row = box.row(align=True)
            op = row.operator("world.plasma_game_add", icon="FILE_FOLDER", text="Change Path")
            op.filepath = active_game.path
            op.game_index = active_game_index

    @classmethod
    def register(cls):
        # Register the old-timey per-world Plasma Games for use in the conversion
        # operator. What fun. I guess....
        from .properties.prop_world import PlasmaGames
        PlasmaGames.games = CollectionProperty(type=PlasmaGame)
