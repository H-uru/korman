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
import functools

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

        layout.operator("mesh.plasma_ladder_add", text="Ladder", icon="COLLAPSEMENU")


class PlasmaImageMenu(PlasmaMenu, bpy.types.Menu):
    bl_idname = "menu.plasma_image"
    bl_label = "Plasma"
    bl_description = "Plasma Image Operators"

    def draw(self, context):
        layout = self.layout

        layout.operator("image.plasma_bake_image_alpha", icon="IMAGE_RGB_ALPHA")
        layout.operator("image.plasma_build_cube_map", icon="MATCUBE")


def _build_plasma_menu(menu_operator, self, context):
    if context.scene.render.engine != "PLASMA_GAME":
        return
    self.layout.separator()
    self.layout.menu(menu_operator, icon="URL")

build_plasma_add_menu = functools.partial(_build_plasma_menu, "menu.plasma_add")
build_plasma_image_menu = functools.partial(_build_plasma_menu, "menu.plasma_image")

def register():
    bpy.types.INFO_MT_add.append(build_plasma_add_menu)
    bpy.types.IMAGE_MT_image.append(build_plasma_image_menu)

def unregister():
    bpy.types.INFO_MT_add.remove(build_plasma_add_menu)
    bpy.types.IMAGE_MT_image.remove(build_plasma_image_menu)
