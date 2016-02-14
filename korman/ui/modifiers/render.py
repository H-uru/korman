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

def fademod(modifier, layout, context):
    layout.prop(modifier, "fader_type")

    if modifier.fader_type == "DistOpacity":
        col = layout.column(align=True)
        col.prop(modifier, "near_trans")
        col.prop(modifier, "near_opaq")
        col.prop(modifier, "far_opaq")
        col.prop(modifier, "far_trans")
    elif modifier.fader_type == "FadeOpacity":
        col = layout.column(align=True)
        col.prop(modifier, "fade_in_time")
        col.prop(modifier, "fade_out_time")
        col.separator()
        col.prop(modifier, "bounds_center")
    elif modifier.fader_type == "SimpleDist":
        col = layout.column(align=True)
        col.prop(modifier, "far_opaq")
        col.prop(modifier, "far_trans")

    if not (modifier.near_trans <= modifier.near_opaq <= modifier.far_opaq <= modifier.far_trans):
        # Warn the user that the values are not recommended.
        layout.label("Distance values must be equal or increasing!", icon="ERROR")

def followmod(modifier, layout, context):
    layout.row().prop(modifier, "follow_mode", expand=True)
    layout.prop(modifier, "leader_type")
    if modifier.leader_type == "kFollowObject":
        layout.prop_search(modifier, "leader_object", bpy.data, "objects", icon="OUTLINER_OB_MESH")

def lightmap(modifier, layout, context):
    layout.row(align=True).prop(modifier, "quality", expand=True)
    layout.prop_search(modifier, "light_group", bpy.data, "groups", icon="GROUP")
    layout.prop_search(modifier, "uv_map", context.active_object.data, "uv_textures")

    operator = layout.operator("object.plasma_lightmap_preview", "Preview Lightmap", icon="RENDER_STILL")
    operator.light_group = modifier.light_group

    # Kind of clever stuff to show the user a preview...
    # We can't show images, so we make a hidden ImageTexture called LIGHTMAPGEN_PREVIEW. We check
    # the backing image name to see if it's for this lightmap. If so, you have a preview. If not,
    # well... It was nice knowing you!
    tex = bpy.data.textures.get("LIGHTMAPGEN_PREVIEW")
    if tex is not None:
        im_name = "{}_LIGHTMAPGEN.png".format(context.active_object.name)
        if tex.image.name == im_name:
            layout.template_preview(tex, show_buttons=False)

def viewfacemod(modifier, layout, context):
    layout.prop(modifier, "preset_options")

    if modifier.preset_options == "Custom":
        layout.row().prop(modifier, "follow_mode")
        if modifier.follow_mode == "kFaceObj":
            layout.prop_search(modifier, "target_object", bpy.data, "objects", icon="OUTLINER_OB_MESH")
            layout.separator()

        layout.prop(modifier, "pivot_on_y")
        layout.separator()

        split = layout.split()
        col = split.column()
        col.prop(modifier, "offset")
        row = col.row()
        row.enabled = modifier.offset
        row.prop(modifier, "offset_local")

        col = split.column()
        col.enabled = modifier.offset
        col.prop(modifier, "offset_coord")

class VisRegionListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        myIcon = "ERROR" if bpy.data.objects.get(item.region_name, None) is None else "OBJECT_DATA"
        label = item.region_name if item.region_name else "[No Object Specified]"
        layout.label(label, icon=myIcon)
        layout.prop(item, "enabled", text="")


def visibility(modifier, layout, context):
    row = layout.row()
    row.template_list("VisRegionListUI", "regions", modifier, "regions", modifier, "active_region_index",
                      rows=2, maxrows=3)
    col = row.column(align=True)
    op = col.operator("object.plasma_modifier_collection_add", icon="ZOOMIN", text="")
    op.modifier = modifier.pl_id
    op.collection = "regions"
    op = col.operator("object.plasma_modifier_collection_remove", icon="ZOOMOUT", text="")
    op.modifier = modifier.pl_id
    op.collection = "regions"
    op.index = modifier.active_region_index

    if modifier.regions:
        layout.prop_search(modifier.regions[modifier.active_region_index], "region_name", bpy.data, "objects")

def visregion(modifier, layout, context):
    layout.prop(modifier, "mode")

    # Only allow SoftVolume spec if this is not an FX and this object is not an SV itself
    sv = modifier.id_data.plasma_modifiers.softvolume
    if modifier.mode != "fx" and not sv.enabled:
        layout.prop_search(modifier, "softvolume", bpy.data, "objects")

    # Other settings
    layout.prop(modifier, "replace_normal")
