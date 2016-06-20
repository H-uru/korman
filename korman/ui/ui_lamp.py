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

    def draw (self, context):
        layout = self.layout
        rtlamp = context.object.data.plasma_lamp

        split = layout.split()
        col = split.column()
        col.prop(rtlamp, "light_group")
        row = col.row()
        row.active = rtlamp.light_group
        row.prop(rtlamp, "affect_characters")

        col = split.column()
        col.prop(rtlamp, "cast_shadows")

        if not context.object.plasma_modifiers.softvolume.enabled:
            layout.prop_search(rtlamp, "soft_region", bpy.data, "objects")
