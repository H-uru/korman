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

from .. import ui_list
from ...exporter.mesh import _VERTEX_COLOR_LAYERS

class BlendOntoListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if item.blend_onto is None:
            layout.label("[No Object Specified]", icon="ERROR")
        else:
            layout.label(item.blend_onto.name, icon="OBJECT_DATA")
        layout.prop(item, "enabled", text="")


def blend(modifier, layout, context):
    # Warn if there are render dependencies and a manual render level specification -- this
    # could lead to unpredictable results.
    layout.alert = modifier.render_level != "AUTO" and bool(modifier.dependencies)
    layout.prop(modifier, "render_level")
    layout.alert = False
    layout.prop(modifier, "sort_faces")

    layout.separator()
    layout.label("Render Dependencies:")
    ui_list.draw_modifier_list(layout, "BlendOntoListUI", modifier, "dependencies",
                              "active_dependency_index", rows=2, maxrows=4)
    try:
        dependency_ref = modifier.dependencies[modifier.active_dependency_index]
    except:
        pass
    else:
        layout.alert = dependency_ref.blend_onto is None
        layout.prop(dependency_ref, "blend_onto")


class DecalMgrListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        if item.name:
            layout.label(item.name, icon="BRUSH_DATA")
            layout.prop(item, "enabled", text="")
        else:
            layout.label("[Empty]")


def decal_print(modifier, layout, context):
    layout.prop(modifier, "decal_type")

    layout = layout.column()
    layout.enabled = modifier.decal_type == "DYNAMIC"
    layout.label("Dimensions:")
    row = layout.row(align=True)
    row.prop(modifier, "length")
    row.prop(modifier, "width")
    row.prop(modifier, "height")
    layout.separator()

    ui_list.draw_modifier_list(layout, "DecalMgrListUI", modifier, "managers",
                               "active_manager_index", rows=2, maxrows=3)
    try:
        mgr_ref = modifier.managers[modifier.active_manager_index]
    except:
        pass
    else:
        scene = context.scene.plasma_scene
        decal_mgr = next((i for i in scene.decal_managers if i.display_name == mgr_ref), None)

        layout.alert = decal_mgr is None
        layout.prop_search(mgr_ref, "name", scene, "decal_managers", icon="BRUSH_DATA")
        layout.alert = False

def decal_receive(modifier, layout, context):
    ui_list.draw_modifier_list(layout, "DecalMgrListUI", modifier, "managers",
                               "active_manager_index", rows=2, maxrows=3)
    try:
        mgr_ref = modifier.managers[modifier.active_manager_index]
    except:
        pass
    else:
        scene = context.scene.plasma_scene
        decal_mgr = next((i for i in scene.decal_managers if i.display_name == mgr_ref), None)

        layout.alert = decal_mgr is None
        layout.prop_search(mgr_ref, "name", scene, "decal_managers", icon="BRUSH_DATA")

def dynatext(modifier, layout, context):
    col = layout.column()
    col.alert = modifier.texture is None
    col.prop(modifier, "texture")
    if modifier.texture is None:
        col.label("You must specify a blank image texture to draw on.", icon="ERROR")

    split = layout.split()
    col = split.column()
    col.label("Content Translations:")
    col.prop(modifier, "active_translation", text="")
    # This should never fail...
    try:
        translation = modifier.translations[modifier.active_translation_index]
    except Exception as e:
        col.label(text="Error (see console)", icon="ERROR")
        print(e)
    else:
        col.prop(translation, "text_id", text="")

    col = split.column()
    col.label("Font:")
    sub = col.row()
    sub.alert = not modifier.font_face.strip()
    sub.prop(modifier, "font_face", text="", icon="OUTLINER_DATA_FONT")
    col.prop(modifier, "font_size", text="Size")

    layout.separator()
    split = layout.split()
    col = split.column(align=True)
    if modifier.texture is not None:
        col.alert = modifier.margin_top + modifier.margin_bottom >= int(modifier.texture.plasma_layer.dynatext_resolution)
    col.prop(modifier, "margin_top")
    col.prop(modifier, "margin_bottom")
    col = split.column(align=True)
    if modifier.texture is not None:
        col.alert = modifier.margin_left + modifier.margin_right >= int(modifier.texture.plasma_layer.dynatext_resolution)
    col.prop(modifier, "margin_left")
    col.prop(modifier, "margin_right")

    layout.separator()
    flow = layout.column_flow(columns=2)
    flow.prop_menu_enum(modifier, "justify")
    flow.prop(modifier, "line_spacing")

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

    if (modifier.fader_type in ("SimpleDist", "DistOpacity") and
        not (modifier.near_trans <= modifier.near_opaq <= modifier.far_opaq <= modifier.far_trans)):
        # Warn the user that the values are not recommended.
        layout.label("Distance values must be equal or increasing!", icon="ERROR")

def followmod(modifier, layout, context):
    layout.row().prop(modifier, "follow_mode", expand=True)
    layout.prop(modifier, "leader_type")
    if modifier.leader_type == "kFollowObject":
        layout.prop(modifier, "leader", icon="OUTLINER_OB_MESH")

def grass_shader(modifier, layout, context):
    layout.prop(modifier, "wave_selector", icon="SMOOTHCURVE")
    layout.separator()

    wave = getattr(modifier, modifier.wave_selector)
    box = layout.box()
    split = box.split()
    col = split.column()
    col.label("Distortion:")
    col.prop(wave, "distance", text="")
    col = split.column()
    col.label("Direction:")
    col.prop(wave, "direction", text="")
    box.prop(wave, "speed")

def lighting(modifier, layout, context):
    split = layout.split()
    col = split.column()
    col.prop(modifier, "force_rt_lights")
    col = split.column()
    col.active = modifier.allow_preshade
    col.prop(modifier, "force_preshade")
    layout.separator()

    lightmap = modifier.id_data.plasma_modifiers.lightmap
    have_static_lights = lightmap.enabled or modifier.preshade

    col = layout.column(align=True)
    col.label("Plasma Lighting Summary:")
    if modifier.unleashed:
        col.label("You have unleashed Satan!", icon="GHOST_ENABLED")
    else:
        col.label("Satan remains ensconced deep in the abyss...", icon="GHOST_ENABLED")
    col.label("Animated lights will be cast at runtime.", icon="LAYER_USED")
    col.label("Projection lights will be cast at runtime.", icon="LAYER_USED")
    col.label("Specular lights will be cast to specular materials at runtime.", icon="LAYER_USED")
    col.label("Other Plasma lights {} be cast at runtime.".format("will" if modifier.rt_lights else "will NOT"),
              icon="LAYER_USED")

    map_type = "a lightmap" if lightmap.bake_lightmap else "vertex colors"
    if lightmap.enabled and lightmap.lights:
            col.label("All '{}' lights will be baked to {}".format(lightmap.lights.name, map_type),
                      icon="LAYER_USED")
    elif have_static_lights:
        light_type = "Blender-only" if modifier.rt_lights else "unanimated"
        col.label("Other {} lights will be baked to {} (if applicable).".format(light_type, map_type), icon="LAYER_USED")
    else:
        col.label("No static lights will be baked.", icon="LAYER_USED")

def lightmap(modifier, layout, context):
    pl_scene = context.scene.plasma_scene
    is_texture = modifier.bake_type == "lightmap" or modifier.bake_type == "lmandvcol"

    layout.prop(modifier, "bake_type")
    if modifier.bake_type == "vcol" or modifier.bake_type == "lmandvcol":
        col_layer = next((i for i in modifier.id_data.data.vertex_colors if i.name.lower() in _VERTEX_COLOR_LAYERS), None)
        if col_layer is not None:
            layout.label("Mesh color layer '{}' will override this lighting.".format(col_layer.name), icon="ERROR")

    col = layout.column()
    col.active = is_texture
    col.prop(modifier, "quality")
    layout.prop_search(modifier, "bake_pass_name", pl_scene, "bake_passes", icon="RENDERLAYERS")
    layout.prop(modifier, "lights")
    col = layout.column()
    col.active = is_texture
    col.prop_search(modifier, "uv_map", context.active_object.data, "uv_textures")
    if bool(modifier.id_data.modifiers) and modifier.uv_map:
        col.label("UV Map islands will be packed on export.", icon="ERROR")
    col = layout.column()
    col.active = is_texture
    col.prop(modifier, "image", icon="IMAGE_RGB")

    # Lightmaps can only be applied to objects with opaque materials.
    if is_texture and any((i.use_transparency for i in modifier.id_data.data.materials if i is not None)):
        layout.label("Transparent objects cannot be lightmapped.", icon="ERROR")
    else:
        row = layout.row(align=True)
        if modifier.bake_lightmap:
            row.operator("object.plasma_lightmap_preview", "Preview", icon="RENDER_STILL").final = False
            row.operator("object.plasma_lightmap_preview", "Bake for Export", icon="RENDER_STILL").final = True
        else:
            row.operator("object.plasma_lightmap_preview", "Bake", icon="RENDER_STILL").final = True

        # Kind of clever stuff to show the user a preview...
        # We can't show images, so we make a hidden ImageTexture called LIGHTMAPGEN_PREVIEW. We check
        # the backing image name to see if it's for this lightmap. If so, you have a preview. If not,
        # well... It was nice knowing you!
        if is_texture:
            tex = bpy.data.textures.get("LIGHTMAPGEN_PREVIEW")
            if tex is not None and tex.image is not None:
                im_name = "{}_LIGHTMAPGEN_PREVIEW.png".format(context.active_object.name)
                if tex.image.name == im_name:
                    layout.template_preview(tex, show_buttons=False)

def rtshadow(modifier, layout, context):
    split = layout.split()
    col = split.column()
    col.prop(modifier, "blur")
    col.prop(modifier, "boost")
    col.prop(modifier, "falloff")

    col = split.column()
    col.prop(modifier, "limit_resolution")
    col.prop(modifier, "self_shadow")

def viewfacemod(modifier, layout, context):
    layout.prop(modifier, "preset_options")

    if modifier.preset_options == "Custom":
        layout.row().prop(modifier, "follow_mode")
        if modifier.follow_mode == "kFaceObj":
            layout.prop(modifier, "target", icon="OUTLINER_OB_MESH")
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
        if item.control_region is None:
            layout.label("[No Object Specified]", icon="ERROR")
        else:
            layout.label(item.control_region.name, icon="OBJECT_DATA")
        layout.prop(item, "enabled", text="")


def visibility(modifier, layout, context):
    ui_list.draw_modifier_list(layout, "VisRegionListUI", modifier, "regions",
                               "active_region_index", rows=2, maxrows=3)

    if modifier.regions:
        layout.prop(modifier.regions[modifier.active_region_index], "control_region")

def visregion(modifier, layout, context):
    layout.prop(modifier, "mode")

    # Only allow SoftVolume spec if this is not an FX and this object is not an SV itself
    sv = modifier.id_data.plasma_modifiers.softvolume
    if modifier.mode != "fx" and not sv.enabled:
        layout.prop(modifier, "soft_region")

    # Other settings
    layout.prop(modifier, "replace_normal")
