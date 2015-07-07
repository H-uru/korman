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

class TextureButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "texture"

    @classmethod
    def poll(cls, context):
        return context.texture and context.scene.render.engine == "PLASMA_GAME"

class PlasmaLayerPanel(TextureButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Layer Options"

    def draw(self, context):
        layer_props = context.texture.plasma_layer
        layout = self.layout

        split = layout.split()
        col = split.column()
        col.label("Animation:")
        col.enabled = context.texture.animation_data is not None or \
                      context.material.animation_data is not None
        col.prop(layer_props, "anim_auto_start")
        col.prop(layer_props, "anim_loop")

        col = split.column()
        col.label("General:")
        col.prop(layer_props, "opacity", text="Opacity")
