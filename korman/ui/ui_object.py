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
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object and context.scene.render.engine == "PLASMA_GAME"


class PlasmaObjectPanel(ObjectButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Object"

    def draw_header(self, context):
        self.layout.prop(context.object.plasma_object, "enabled", text="")

    def draw(self, context):
        layout = self.layout
        pl_obj = context.object.plasma_object
        pl_age = context.scene.world.plasma_age
        layout.active = pl_obj.enabled

        # Which page does this object go in?
        # If left blank, the exporter puts it in page 0 -- "Default"
        layout.prop_search(pl_obj, "page", pl_age, "pages", icon="BOOKMARKS")


class PlasmaNetPanel(ObjectButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Synchronization"

    def draw_header(self, context):
        self.layout.prop(context.object.plasma_net, "manual_sdl", text="")

    def draw(self, context):
        layout = self.layout
        pl_net = context.object.plasma_net
        layout.active = pl_net.manual_sdl

        layout.prop(pl_net, "agmaster", text="Animation")
        layout.prop(pl_net, "layer", text="Material")
        layout.prop(pl_net, "physical")
        layout.prop(pl_net, "responder")
        layout.prop(pl_net, "sound")
        layout.prop(pl_net, "xregion")
