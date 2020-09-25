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

class LampButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return (context.object and context.scene.render.engine == "PLASMA_GAME" and
                isinstance(context.object.data, bpy.types.Lamp))


class PlasmaLampPanel(LampButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma RT Lamp"

    def draw(self, context):
        layout = self.layout
        rtlamp = context.lamp.plasma_lamp

        split = layout.split()
        col = split.column()
        col.label("General:")
        row = col.row()
        row.active = rtlamp.has_light_group(context.object)
        row.prop(rtlamp, "affect_characters")

        col = split.column()
        col.label("Soft Volume:")
        col.active = not context.object.plasma_modifiers.softvolume.enabled
        col.prop(rtlamp, "lamp_region", text="")


class PlasmaShadowPanel(LampButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma RT Shadow"

    def draw_header(self, context):
        self.layout.prop(context.lamp.plasma_lamp, "cast_shadows", text="")

    def draw(self, context):
        layout = self.layout
        rtlamp = context.lamp.plasma_lamp
        layout.active = rtlamp.cast_shadows

        split = layout.split()
        col = split.column()
        col.prop(rtlamp, "shadow_quality", text="")
        col.separator()
        col.prop(rtlamp, "shadow_self")

        col = split.column()
        col.prop(rtlamp, "shadow_power")
        col.prop(rtlamp, "shadow_falloff")
        col.prop(rtlamp, "shadow_distance")
        
class PlasmaRuntimeLampPanel(LampButtonsPanel, bpy.types.Panel):
    bl_label = "Runtime Lamp"
    
    def draw(self, context):
        layout = self.layout
        rtlamp = context.lamp.plasma_lamp
        
        split = layout.split()
        col = split.column()
        col.prop(rtlamp, "runtime_lamp")

def _draw_area_lamp(self, context):
    """Draw dispatch function for DATA_PT_area"""
    if context.scene.render.engine == "PLASMA_GAME":
        _plasma_draw_area_lamp(self, context)
    else:
        self._draw_blender(context)


def _plasma_draw_area_lamp(self, context):
    """Draw function for DATA_PT_area when Korman is active"""
    layout = self.layout
    lamp = context.lamp
    plasma_lamp = lamp.plasma_lamp

    col = layout.column()
    col.row().prop(lamp, "shape", expand=True)
    sub = col.row(align=True)

    if lamp.shape == "SQUARE":
        sub.prop(lamp, "size")
        sub.prop(plasma_lamp, "size_height")
    elif lamp.shape == "RECTANGLE":
        sub.prop(lamp, "size", text="W")
        sub.prop(lamp, "size_y", text="D")
        sub.prop(plasma_lamp, "size_height", text="H")

# Swap out the draw functions for the standard Area Shape panel
# TODO: Maybe we should consider standardizing an interface for overriding
#       standard Blender panels? This seems like a really useful approach.
from bl_ui import properties_data_lamp
properties_data_lamp.DATA_PT_area._draw_blender = properties_data_lamp.DATA_PT_area.draw
properties_data_lamp.DATA_PT_area.draw = _draw_area_lamp
del properties_data_lamp
