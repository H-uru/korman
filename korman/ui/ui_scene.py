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
from . import ui_list

class SceneButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class DecalManagerListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.prop(item, "display_name", emboss=False, text="")


class WetManagerListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if item.name:
            layout.label(item.name)
            layout.prop(item, "enabled", text="")
        else:
            layout.label("[Empty]")


class PlasmaDecalManagersPanel(SceneButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Decal Managers"

    def draw(self, context):
        layout, scene = self.layout, context.scene.plasma_scene

        ui_list.draw_list(layout, "DecalManagerListUI", "scene", scene, "decal_managers",
                          "active_decal_index", name_prefix="Decal", name_prop="display_name",
                          rows=3)

        try:
            decal_mgr = scene.decal_managers[scene.active_decal_index]
        except:
            pass
        else:
            box = layout.box().column()

            box.prop(decal_mgr, "decal_type")
            box.alert = decal_mgr.image is None
            box.prop(decal_mgr, "image")
            box.alert = False
            box.prop(decal_mgr, "blend")
            box.separator()

            split = box.split()
            col = split.column(align=True)
            col.label("Scale:")
            col.alert = decal_mgr.decal_type in {"ripple", "puddle", "bullet", "torpedo"} \
                        and decal_mgr.length != decal_mgr.width
            col.prop(decal_mgr, "length")
            col.prop(decal_mgr, "width")

            col = split.column()
            col.label("Draw Settings:")
            col.prop(decal_mgr, "intensity")
            sub = col.row()
            sub.active = decal_mgr.decal_type in {"footprint_dry", "footprint_wet", "bullet", "torpedo"}
            sub.prop(decal_mgr, "life_span")
            sub = col.row()
            sub.active = decal_mgr.decal_type in {"puddle", "ripple"}
            sub.prop(decal_mgr, "wet_time")

            if decal_mgr.decal_type in {"puddle", "ripple"}:
                box.separator()
                box.label("Wet Footprints:")
                ui_list.draw_list(box, "WetManagerListUI", "scene", decal_mgr, "wet_managers",
                                  "active_wet_index", rows=2, maxrows=3)
                try:
                    wet_ref = decal_mgr.wet_managers[decal_mgr.active_wet_index]
                except:
                    pass
                else:
                    wet_mgr = next((i for i in scene.decal_managers if i.name == wet_ref.name), None)
                    box.alert = getattr(wet_mgr, "decal_type", None) == "footprint_wet"
                    box.prop_search(wet_ref, "name", scene, "decal_managers", icon="NONE")
                    if wet_ref.name == decal_mgr.name:
                        box.label(text="Circular reference", icon="ERROR")
