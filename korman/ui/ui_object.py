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

class ObjectButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "physics"

    @classmethod
    def poll(cls, context):
        return context.object and context.scene.render.engine == "PLASMA_GAME"


class BlenderObjectSearchPanel(ObjectButtonsPanel, bpy.types.Panel):
    bl_label = ""
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        # Yes, this is stolen shamelessly from bl_ui
        layout = self.layout
        space = context.space_data

        if space.use_pin_id:
            layout.template_ID(space, "pin_id")
        else:
            row = layout.row()
            row.template_ID(context.scene.objects, "active")


class PlasmaObjectPanel(ObjectButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Object"

    def draw_header(self, context):
        self.layout.prop(context.object.plasma_object, "enabled", text="")

    def draw(self, context):
        layout = self.layout
        pl_obj = context.object.plasma_object
        pl_age = context.scene.world.plasma_age
        layout.active = pl_obj.enabled

        # It is an error to put objects in the wrong types of pages/
        active_page = next((i for i in pl_age.pages if i.name == pl_obj.page), None)
        is_external_page = active_page.page_type == "external" if active_page else False

        # Which page does this object go in?
        # If left blank, the exporter puts it in page 0 -- "Default"
        layout.alert = is_external_page
        layout.prop_search(pl_obj, "page", pl_age, "pages", icon="BOOKMARKS")
        layout.alert = False
        if is_external_page:
            layout.label("Objects cannot be exported to External pages.", icon="ERROR")


class PlasmaNetPanel(ObjectButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Synchronization"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.prop(context.object.plasma_net, "manual_sdl", text="")

    def draw(self, context):
        layout = self.layout
        pl_net = context.object.plasma_net
        layout.active = pl_net.manual_sdl

        for i in sorted(pl_net.sdl_names):
            layout.prop(pl_net, i)
