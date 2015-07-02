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

class ToolboxPanel:
    bl_category = "Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    @classmethod
    def poll(cls, context):
        return context.object and context.scene.render.engine == "PLASMA_GAME"


class PlasmaToolboxPanel(ToolboxPanel, bpy.types.Panel):
    bl_context = "objectmode"
    bl_label = "Plasma"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.label("Enable All:")
        col.operator("object.plasma_enable_all_objects", icon="OBJECT_DATA")
        col.operator("texture.plasma_enable_all_textures", icon="TEXTURE")

        col.label("Convert All:")
        col.operator("texture.plasma_convert_layer_opacities", icon="IMAGE_RGB_ALPHA")
