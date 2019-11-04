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

from ..operators.op_mesh import *

class PlasmaMenu:
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class PlasmaAddMenu(PlasmaMenu, bpy.types.Menu):
    bl_idname = "menu.plasma_add"
    bl_label = "Plasma"
    bl_description = "Add a Plasma premade"

    def draw(self, context):
        layout = self.layout

        layout.operator("mesh.plasma_flare_add", text="Lamp Flare", icon="PARTICLES")
        layout.operator("mesh.plasma_ladder_add", text="Ladder", icon="COLLAPSEMENU")
        layout.operator("mesh.plasma_linkingbook_add", text="Linking Book", icon="FILE_IMAGE")


def build_plasma_menu(self, context):
    if context.scene.render.engine != "PLASMA_GAME":
        return
    self.layout.separator()
    self.layout.menu("menu.plasma_add", icon="URL")


class PlasmaHelpMenu(PlasmaMenu, bpy.types.Menu):
    bl_idname = "menu.plasma_help"
    bl_label = "Korman..."

    def draw(self, context):
        layout = self.layout
        layout.operator("wm.url_open", text="About Korman", icon="URL").url = "https://guildofwriters.org/wiki/Korman"
        layout.operator("wm.url_open", text="Getting Started", icon="URL").url = "https://guildofwriters.org/wiki/Korman:Getting_Started"
        layout.operator("wm.url_open", text="Tutorials", icon="URL").url = "https://guildofwriters.org/wiki/Category:Korman_Tutorials"


def build_plasma_help_menu(self, context):
    self.layout.menu("menu.plasma_help", text="Korman", icon="URL")

def register():
    bpy.types.INFO_MT_add.append(build_plasma_menu)
    bpy.types.INFO_MT_help.prepend(build_plasma_help_menu)

def unregister():
    bpy.types.INFO_MT_add.remove(build_plasma_menu)
    bpy.types.INFO_MT_help.remove(build_plasma_help_menu)
