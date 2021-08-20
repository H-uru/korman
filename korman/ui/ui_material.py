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

from . import ui_list

class MaterialButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material and context.scene.render.engine == "PLASMA_GAME"


class PlasmaMaterialPanel(MaterialButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Material Options"
	
    def draw(self, context):
        mat = context.material
        mat_props = mat.plasma_material
        layout = self.layout

        split = layout.split()
        col = split.column()
        sub = col.column()
        col.prop(mat_props, "double_sided")

