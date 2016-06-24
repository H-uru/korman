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


class PlasmaEnvMapPanel(TextureButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Environment Map"

    @classmethod
    def poll(cls, context):
        if super().poll(context):
            return context.texture.type == "ENVIRONMENT_MAP"
        return False

    def draw(self, context):
        layer_props = context.texture.plasma_layer
        layout = self.layout

        layout.label("Visibility Sets:")
        row = layout.row()
        row.template_list("VisRegionListUI", "vis_regions", layer_props, "vis_regions", layer_props, "active_region_index",
                          rows=2, maxrows=3)
        col = row.column(align=True)
        op = col.operator("texture.plasma_collection_add", icon="ZOOMIN", text="")
        op.group = "plasma_layer"
        op.collection = "vis_regions"
        op = col.operator("texture.plasma_collection_remove", icon="ZOOMOUT", text="")
        op.group = "plasma_layer"
        op.collection = "vis_regions"
        op.index = layer_props.active_region_index
        rgns = layer_props.vis_regions
        if layer_props.vis_regions:
            layout.prop_search(rgns[layer_props.active_region_index], "region_name", bpy.data, "objects")

        layout.separator()
        layout.prop(layer_props, "envmap_color")


class PlasmaLayerPanel(TextureButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Layer Options"

    def draw(self, context):
        texture = context.texture
        layer_props = texture.plasma_layer
        layout = self.layout

        split = layout.split()
        col = split.column()
        col.label("Animation:")
        col.enabled = self._has_animation_data(context)
        col.prop(layer_props, "anim_auto_start")
        col.prop(layer_props, "anim_loop")

        col = split.column()
        col.label("General:")
        col.prop(layer_props, "opacity", text="Opacity")
        col.prop(layer_props, "alpha_halo")

    def _has_animation_data(self, context):
        tex = getattr(context, "texture", None)
        if tex is not None:
            if tex.animation_data is not None:
                return True

        mat = getattr(context, "material", None)
        if mat is not None:
            if mat.animation_data is not None:
                return True

        return False
