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
import math
from pathlib import Path
from PyHSPlasma import *
import weakref

from . import explosions
from .. import helpers
from ..korlib import *
from . import utils

_MAX_STENCILS = 6

class _Texture:
    _DETAIL_BLEND = {
        TEX_DETAIL_ALPHA: "AL",
        TEX_DETAIL_ADD: "AD",
        TEX_DETAIL_MULTIPLY: "ML",
    }

    def __init__(self, **kwargs):
        texture, image = kwargs.get("texture"), kwargs.get("image")
        assert texture or image

        if texture is not None:
            if image is None:
                image = texture.image
            self.calc_alpha = texture.use_calculate_alpha
            self.mipmap = texture.use_mipmap
        else:
            self.layer = kwargs.get("layer")
            self.calc_alpha = False
            self.mipmap = False

        if kwargs.get("is_detail_map", False):
            self.is_detail_map = True
            self.detail_blend = kwargs["detail_blend"]
            self.detail_fade_start = kwargs["detail_fade_start"]
            self.detail_fade_stop = kwargs["detail_fade_stop"]
            self.detail_opacity_start = kwargs["detail_opacity_start"]
            self.detail_opacity_stop = kwargs["detail_opacity_stop"]
            self.calc_alpha = False
            self.use_alpha = True
        else:
            self.is_detail_map = False
            use_alpha = kwargs.get("use_alpha")
            if kwargs.get("force_calc_alpha", False) or self.calc_alpha:
                self.calc_alpha = True
                self.use_alpha  = True
            elif use_alpha is None:
                self.use_alpha = (image.channels == 4 and image.use_alpha)
            else:
                self.use_alpha = use_alpha

        self.image = image

    def __eq__(self, other):
        if not isinstance(other, _Texture):
            return False

        # Yeah, the string name is a unique identifier. So shoot me.
        if str(self) == str(other):
            self._update(other)
            return True
        return False

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        if self.mipmap:
            name = str(Path(self.image.name).with_suffix(".dds"))
        else:
            name = str(Path(self.image.name).with_suffix(".bmp"))
        if self.calc_alpha:
            name = "ALPHAGEN_{}".format(name)

        if self.is_detail_map:
            name = "DETAILGEN_{}-{}-{}-{}-{}_{}".format(self._DETAIL_BLEND[self.detail_blend],
                                                        self.detail_fade_start, self.detail_fade_stop,
                                                        self.detail_opacity_start, self.detail_opacity_stop,
                                                        name)
        return name

    def _update(self, other):
        """Update myself with any props that might be overridable from another copy of myself"""
        # NOTE: detail map properties should NEVER be overridden. NEVER. EVER. kthx.
        if other.use_alpha:
            self.use_alpha = True
        if other.mipmap:
            self.mipmap = True


class MaterialConverter:
    def __init__(self, exporter):
        self._obj2mat = {}
        self._bumpMats = {}
        self._exporter = weakref.ref(exporter)
        self._pending = {}
        self._alphatest = {}
        self._tex_exporters = {
            "ENVIRONMENT_MAP": self._export_texture_type_environment_map,
            "IMAGE": self._export_texture_type_image,
            "NONE": self._export_texture_type_none,
        }
        self._animation_exporters = {
            "opacityCtl": self._export_layer_opacity_animation,
            "transformCtl": self._export_layer_transform_animation,
        }

    def export_material(self, bo, bm):
        """Exports a Blender Material as an hsGMaterial"""
        print("    Exporting Material '{}'".format(bm.name))

        hsgmat = self._mgr.add_object(hsGMaterial, name=bm.name, bl=bo)
        slots = [(idx, slot) for idx, slot in enumerate(bm.texture_slots) if slot is not None and slot.use \
                 and slot.texture is not None and slot.texture.type in self._tex_exporters]

        # There is a major difference in how Blender and Plasma handle stencils.
        # In Blender, the stencil is on top and applies to every layer below is. In Plasma, the stencil
        # is below the SINGLE layer it affects. The main texture is marked BindNext and RestartPassHere.
        # The pipeline indicates that we can render 8 layers simultaneously, so we will collect all
        # stencils and apply this arrangement. We're going to limit to 6 stencils however. 1 layer for
        # main texture and 1 piggyback.
        num_stencils = sum((1 for i in slots if i[1].use_stencil))
        if num_stencils > _MAX_STENCILS:
            raise ExportError("Material '{}' uses too many stencils. The maximum is {}".format(bm.name, _MAX_STENCILS))
        stencils = []

        # Loop over layers
        for idx, slot in slots:
            # Prepend any BumpMapping magic layers
            if slot.use_map_normal:
                if bo in self._bumpMats:
                    raise ExportError("Material '{}' has more than one bumpmap layer".format(bm.name))
                du, dw, dv = self.export_bumpmap_slot(bo, bm, hsgmat, slot, idx)
                hsgmat.addLayer(du.key) # Du
                hsgmat.addLayer(dw.key) # Dw
                hsgmat.addLayer(dv.key) # Dv

            if slot.use_stencil:
                stencils.append((idx, slot))
            else:
                tex_layer = self.export_texture_slot(bo, bm, hsgmat, slot, idx)
                hsgmat.addLayer(tex_layer.key)
                if slot.use_map_normal:
                    self._bumpMats[bo] = (tex_layer.UVWSrc, tex_layer.transform)
                if stencils:
                    tex_state = tex_layer.state
                    if not tex_state.blendFlags & hsGMatState.kBlendMask:
                        tex_state.blendFlags |= hsGMatState.kBlendAlpha
                    tex_state.miscFlags |= hsGMatState.kMiscRestartPassHere | hsGMatState.kMiscBindNext
                    curr_stencils = len(stencils)
                    for i in range(curr_stencils):
                        stencil_idx, stencil = stencils[i]
                        stencil_name = "STENCILGEN_{}@{}_{}".format(stencil.name, bm.name, slot.name)
                        stencil_layer = self.export_texture_slot(bo, bm, hsgmat, stencil, stencil_idx, name=stencil_name)
                        if i+1 < curr_stencils:
                            stencil_layer.state.miscFlags |= hsGMatState.kMiscBindNext
                        hsgmat.addLayer(stencil_layer.key)

        # Plasma makes several assumptions that every hsGMaterial has at least one layer. If this
        # material had no Textures, we will need to initialize a default layer
        if not hsgmat.layers:
            layer = self._mgr.add_object(plLayer, name="{}_AutoLayer".format(bm.name), bl=bo)
            self._propagate_material_settings(bm, layer)
            hsgmat.addLayer(layer.key)

        # Cache this material for later
        if bo in self._obj2mat:
            self._obj2mat[bo].append(hsgmat.key)
        else:
            self._obj2mat[bo] = [hsgmat.key]

        # Looks like we're done...
        return hsgmat.key

    def export_waveset_material(self, bo, bm):
        print("    Exporting WaveSet Material '{}'".format(bm.name))

        # WaveSets MUST have their own material
        unique_name = "{}_WaveSet7".format(bm.name)
        hsgmat = self._mgr.add_object(hsGMaterial, name=unique_name, bl=bo)

        # Materials MUST have one layer. Wavesets need alpha blending...
        layer = self._mgr.add_object(plLayer, name=unique_name, bl=bo)
        self._propagate_material_settings(bm, layer)
        layer.state.blendFlags |= hsGMatState.kBlendAlpha
        hsgmat.addLayer(layer.key)

        # Wasn't that easy?
        return hsgmat.key

    def export_bumpmap_slot(self, bo, bm, hsgmat, slot, idx):
        name = "{}_{}".format(bm.name if bm is not None else bo.name, slot.name)
        print("        Exporting Plasma Bumpmap Layers for '{}'".format(name))

        # Okay, now we need to make 3 layers for the Du, Dw, and Dv
        du_layer = self._mgr.add_object(plLayer, name="{}_DU_BumpLut".format(name), bl=bo)
        dw_layer = self._mgr.add_object(plLayer, name="{}_DW_BumpLut".format(name), bl=bo)
        dv_layer = self._mgr.add_object(plLayer, name="{}_DV_BumpLut".format(name), bl=bo)

        for layer in (du_layer, dw_layer, dv_layer):
            layer.ambient = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
            layer.preshade = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
            layer.runtime = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
            layer.specular = hsColorRGBA(0.0, 0.0, 0.0, 1.0)

            state = layer.state
            state.ZFlags = hsGMatState.kZNoZWrite
            state.clampFlags = hsGMatState.kClampTexture
            state.miscFlags = hsGMatState.kMiscBindNext
            state.blendFlags = hsGMatState.kBlendAdd

        if not slot.use_map_specular:
            du_layer.state.blendFlags = hsGMatState.kBlendMADD

        du_layer.state.miscFlags |= hsGMatState.kMiscBumpDu | hsGMatState.kMiscRestartPassHere
        dw_layer.state.miscFlags |= hsGMatState.kMiscBumpDw
        dv_layer.state.miscFlags |= hsGMatState.kMiscBumpDv

        du_uv = len(bo.data.uv_layers)
        du_layer.UVWSrc = du_uv
        dw_layer.UVWSrc = du_uv | plLayerInterface.kUVWNormal
        dv_layer.UVWSrc = du_uv + 1

        page = self._mgr.get_textures_page(du_layer.key)
        LUT_key = self._mgr.find_key(plMipmap, loc=page, name="BumpLutTexture")

        if LUT_key is None:
            bumpLUT = plMipmap("BumpLutTexture", 16, 16, 1, plBitmap.kUncompressed, plBitmap.kRGB8888)
            GLTexture.create_bump_LUT(bumpLUT)
            self._mgr.AddObject(page, bumpLUT)
            LUT_key = bumpLUT.key

        du_layer.texture = LUT_key
        dw_layer.texture = LUT_key
        dv_layer.texture = LUT_key

        return (du_layer, dw_layer, dv_layer)

    def export_texture_slot(self, bo, bm, hsgmat, slot, idx, name=None, blend_flags=True):
        if name is None:
            name = "{}_{}".format(bm.name if bm is not None else bo.name, slot.name)
        print("        Exporting Plasma Layer '{}'".format(name))
        layer = self._mgr.add_object(plLayer, name=name, bl=bo)
        if bm is not None and not slot.use_map_normal:
            self._propagate_material_settings(bm, layer)

        # UVW Channel
        if slot.texture_coords == "UV":
            for i, uvchan in enumerate(bo.data.uv_layers):
                if uvchan.name == slot.uv_layer:
                    layer.UVWSrc = i
                    print("            Using UV Map #{} '{}'".format(i, name))
                    break
            else:
                print("            No UVMap specified... Blindly using the first one, maybe it exists :|")

        # Transform
        xform = hsMatrix44()
        xform.setTranslate(hsVector3(*slot.offset))
        xform.setScale(hsVector3(*slot.scale))
        layer.transform = xform

        wantStencil, canStencil = slot.use_stencil, slot.use_stencil and bm is not None and not slot.use_map_normal
        if wantStencil and not canStencil:
            self._exporter().report.warn("{} wants to stencil, but this is not a real Material".format(slot.name))

        state = layer.state
        if canStencil:
            hsgmat.compFlags |= hsGMaterial.kCompNeedsBlendChannel
            state.blendFlags |= hsGMatState.kBlendAlpha | hsGMatState.kBlendAlphaMult | hsGMatState.kBlendNoTexColor
            if slot.texture.type == "BLEND":
                state.clampFlags |= hsGMatState.kClampTexture
            state.ZFlags |= hsGMatState.kZNoZWrite
            layer.ambient = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
        elif blend_flags:
            # Standard layer flags ahoy
            if slot.blend_type == "ADD":
                state.blendFlags |= hsGMatState.kBlendAddColorTimesAlpha
            elif slot.blend_type == "MULTIPLY":
                state.blendFlags |= hsGMatState.kBlendMult

        texture = slot.texture

        # Apply custom layer properties
        if slot.use_map_normal:
            state.blendFlags = hsGMatState.kBlendDot3
            state.miscFlags = hsGMatState.kMiscBumpLayer
            strength = max(min(1.0, slot.normal_factor), 0.0)
            layer.ambient = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
            layer.preshade = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
            layer.runtime = hsColorRGBA(strength, 0.0, 0.0, 1.0)
            layer.specular = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
        else:
            layer_props = texture.plasma_layer
            layer.opacity = layer_props.opacity / 100
            if layer_props.opacity < 100:
                state.blendFlags |= hsGMatState.kBlendAlpha
            if layer_props.alpha_halo:
                state.blendFlags |= hsGMatState.kBlendAlphaTestHigh
            if layer_props.z_bias:
                state.ZFlags |= hsGMatState.kZIncLayer
            if layer_props.skip_depth_test:
                state.ZFlags |= hsGMatState.kZNoZRead
            if layer_props.skip_depth_write:
                state.ZFlags |= hsGMatState.kZNoZWrite

        # Export the specific texture type
        self._tex_exporters[texture.type](bo, layer, slot)

        # Export any layer animations
        # NOTE: animated stencils and bumpmaps are nonsense.
        if not slot.use_stencil and not slot.use_map_normal:
            layer = self._export_layer_animations(bo, bm, slot, idx, layer)
        return layer

    def _export_layer_animations(self, bo, bm, tex_slot, idx, base_layer):
        """Exports animations on this texture and chains the Plasma layers as needed"""

        def harvest_fcurves(bl_id, collection, data_path=None):
            if bl_id is None:
                return None

            anim = bl_id.animation_data
            if anim is not None:
                action = anim.action
                if action is not None:
                    if data_path is None:
                        collection.extend(action.fcurves)
                    else:
                        collection.extend((i for i in action.fcurves if i.data_path.startswith(data_path)))
                    return action
            return None

        fcurves = []
        mat_action = harvest_fcurves(bm, fcurves, "texture_slots[{}]".format(idx))
        tex_action = harvest_fcurves(tex_slot.texture, fcurves)
        if not fcurves:
            return base_layer

        # Okay, so we have some FCurves. We'll loop through our known layer animation converters
        # and chain this biotch up as best we can.
        layer_animation = None
        for attr, converter in self._animation_exporters.items():
            ctrl = converter(tex_slot, base_layer, fcurves)
            if ctrl is not None:
                if layer_animation is None:
                    name = "{}_LayerAnim".format(base_layer.key.name)
                    layer_animation = self.get_texture_animation_key(bo, bm, tex_slot=tex_slot).object
                setattr(layer_animation, attr, ctrl)

        # Alrighty, if we exported any controllers, layer_animation is a plLayerAnimation. We need to do
        # the common schtuff now.
        if layer_animation is not None:
            layer_animation.underLay = base_layer.key

            fps = bpy.context.scene.render.fps
            atc = layer_animation.timeConvert
            if tex_action is not None:
                start, end = tex_action.frame_range
            else:
                start, end = mat_action.frame_range
            atc.begin = start / fps
            atc.end = end / fps

            layer_props = tex_slot.texture.plasma_layer
            if not layer_props.anim_auto_start:
                atc.flags |= plAnimTimeConvert.kStopped
            if layer_props.anim_loop:
                atc.flags |= plAnimTimeConvert.kLoop
                atc.loopBegin = atc.begin
                atc.loopEnd = atc.end
            if layer_props.anim_sdl_var:
                layer_animation.varName = layer_props.anim_sdl_var
            return layer_animation

        # Well, we had some FCurves but they were garbage... Too bad.
        return base_layer

    def _export_layer_opacity_animation(self, tex_slot, base_layer, fcurves):
        for i in fcurves:
            if i.data_path == "plasma_layer.opacity":
                base_layer.state.blendFlags |= hsGMatState.kBlendAlpha
                ctrl = self._exporter().animation.make_scalar_leaf_controller(i)
                return ctrl
        return None

    def _export_layer_transform_animation(self, tex_slot, base_layer, fcurves):
        path = tex_slot.path_from_id()
        pos_path = "{}.offset".format(path)
        scale_path = "{}.scale".format(path)

        # Plasma uses the controller to generate a matrix44... so we have to produce a leaf controller
        ctrl = self._exporter().animation.make_matrix44_controller(fcurves, pos_path, scale_path, tex_slot.offset, tex_slot.scale)
        return ctrl

    def _export_texture_type_environment_map(self, bo, layer, slot):
        """Exports a Blender EnvironmentMapTexture to a plLayer"""

        texture = slot.texture
        bl_env = texture.environment_map
        if bl_env.source in {"STATIC", "ANIMATED"}:
            if bl_env.mapping == "PLANE" and self._mgr.getVer() >= pvMoul:
                pl_env = plDynamicCamMap
            else:
                pl_env = plDynamicEnvMap
            pl_env = self.export_dynamic_env(bo, layer, texture, pl_env)
        else:
            # We should really export a CubicEnvMap here, but we have a good setup for DynamicEnvMaps
            # that create themselves when the explorer links in, so really... who cares about CEMs?
            self._exporter().report.warn("IMAGE EnvironmentMaps are not supported. '{}' will not be exported!".format(layer.key.name))
            pl_env = None
        layer.state.shadeFlags |= hsGMatState.kShadeEnvironMap
        layer.texture = pl_env.key

    def export_dynamic_env(self, bo, layer, texture, pl_class):
        # To protect the user from themselves, let's check to make sure that a DEM/DCM matching this
        # viewpoint object has not already been exported...
        bl_env = texture.environment_map
        viewpt = bl_env.viewpoint_object
        if viewpt is None:
            viewpt = bo
        name = "{}_DynEnvMap".format(viewpt.name)
        pl_env = self._mgr.find_object(pl_class, bl=bo, name=name)
        if pl_env is not None:
            print("            EnvMap for viewpoint {} already exported... NOTE: Your settings here will be overridden by the previous object!".format(viewpt.name))
            if isinstance(pl_env, plDynamicCamMap):
                pl_env.addTargetNode(self._mgr.find_key(plSceneObject, bl=bo))
                pl_env.addMatLayer(layer.key)
            return pl_env

        # Ensure POT
        oRes = bl_env.resolution
        eRes = helpers.ensure_power_of_two(oRes)
        if oRes != eRes:
            print("            Overriding EnvMap size to ({}x{}) -- POT".format(eRes, eRes))

        # And now for the general ho'hum-ness
        pl_env = self._mgr.add_object(pl_class, bl=bo, name=name)
        pl_env.hither = bl_env.clip_start
        pl_env.yon = bl_env.clip_end
        pl_env.refreshRate = 0.01 if bl_env.source == "ANIMATED" else 0.0
        pl_env.incCharacters = True

        # Perhaps the DEM/DCM fog should be separately configurable at some point?
        pl_fog = bpy.context.scene.world.plasma_fni
        pl_env.color = utils.color(texture.plasma_layer.envmap_color)
        pl_env.fogStart = pl_fog.fog_start

        # EffVisSets
        # Whoever wrote this PyHSPlasma binding didn't follow the convention. Sigh.
        visregions = []
        for region in texture.plasma_layer.vis_regions:
            rgn = bpy.data.objects.get(region.region_name, None)
            if rgn is None:
                raise ExportError("'{}': VisControl '{}' not found".format(texture.name, region.region_name))
            if not rgn.plasma_modifiers.visregion.enabled:
                raise ExportError("'{}': '{}' is not a VisControl".format(texture.name, region.region_name))
            visregions.append(self._mgr.find_create_key(plVisRegion, bl=rgn))
        pl_env.visRegions = visregions

        if isinstance(pl_env, plDynamicCamMap):
            faces = (pl_env,)

            # It matters not whether or not the viewpoint object is a Plasma Object, it is exported as at
            # least a SceneObject and CoordInterface so that we can touch it...
            # NOTE: that harvest_actor makes sure everyone alread knows we're going to have a CI
            root = self._mgr.find_create_key(plSceneObject, bl=viewpt)
            pl_env.rootNode = root # FIXME: DCM camera
            # FIXME: DynamicCamMap Camera

            pl_env.addTargetNode(self._mgr.find_key(plSceneObject, bl=bo))
            pl_env.addMatLayer(layer.key)

            # This is really just so we don't raise any eyebrows if anyone is looking at the files.
            # If you're disabling DCMs, then you're obviuously trolling!
            # Cyan generates a single color image, but we'll just set the layer colors and go away.
            fake_layer = self._mgr.add_object(plLayer, bl=bo, name="{}_DisabledDynEnvMap".format(viewpt.name))
            fake_layer.ambient = layer.ambient
            fake_layer.preshade = layer.preshade
            fake_layer.runtime = layer.runtime
            fake_layer.specular = layer.specular
            pl_env.disableTexture = fake_layer.key

            if pl_env.camera is None:
                layer.UVWSrc = plLayerInterface.kUVWPosition
                layer.state.miscFlags |= (hsGMatState.kMiscCam2Screen | hsGMatState.kMiscPerspProjection)
        else:
            faces = pl_env.faces + (pl_env,)

            # DEMs can do just a position vector. We actually prefer this because the WaveSet exporter
            # will probably want to steal it for diabolical purposes...
            pl_env.position = hsVector3(*viewpt.location)

            if layer is not None:
                layer.UVWSrc = plLayerInterface.kUVWReflect
                layer.state.miscFlags |= hsGMatState.kMiscUseRefractionXform

        # Because we might be working with a multi-faced env map. It's even worse than have two faces...
        for i in faces:
            i.setConfig(plBitmap.kRGB8888)
            i.flags |= plBitmap.kIsTexture
            i.flags &= ~plBitmap.kAlphaChannelFlag
            i.width = eRes
            i.height = eRes
            i.proportionalViewport = False
            i.viewportLeft = 0
            i.viewportTop = 0
            i.viewportRight = eRes
            i.viewportBottom = eRes
            i.ZDepth = 24

        return pl_env

    def _export_texture_type_image(self, bo, layer, slot):
        """Exports a Blender ImageTexture to a plLayer"""
        texture = slot.texture
        layer_props = texture.plasma_layer

        # Does the image have any alpha at all?
        if texture.image is not None:
            has_alpha = texture.use_calculate_alpha or slot.use_stencil or self._test_image_alpha(texture.image)
            if (texture.image.use_alpha and texture.use_alpha) and not has_alpha:
                warning = "'{}' wants to use alpha, but '{}' is opaque".format(texture.name, texture.image.name)
                self._exporter().report.warn(warning, indent=3)
        else:
            has_alpha = True

        # First, let's apply any relevant flags
        state = layer.state
        if not slot.use_stencil and not slot.use_map_normal:
            # mutually exclusive blend flags
            if texture.use_alpha and has_alpha:
                if slot.blend_type == "ADD":
                    state.blendFlags |= hsGMatState.kBlendAlphaAdd
                elif slot.blend_type == "MULTIPLY":
                    state.blendFlags |= hsGMatState.kBlendAlphaMult
                else:
                    state.blendFlags |= hsGMatState.kBlendAlpha

            if texture.invert_alpha and has_alpha:
                state.blendFlags |= hsGMatState.kBlendInvertAlpha

        if texture.extension in {"CLIP", "EXTEND"}:
            state.clampFlags |= hsGMatState.kClampTexture

        # Now, let's export the plBitmap
        # If the image is None (no image applied in Blender), we assume this is a plDynamicTextMap
        # Otherwise, we toss this layer and some info into our pending texture dict and process it
        #     when the exporter tells us to finalize all our shit
        if texture.image is None:
            dtm = self._mgr.find_create_object(plDynamicTextMap, name="{}_DynText".format(layer.key.name), bl=bo)
            dtm.hasAlpha = texture.use_alpha
            # if you have a better idea, let's hear it...
            dtm.visWidth, dtm.visHeight = 1024, 1024
            layer.texture = dtm.key
        else:
            detail_blend = TEX_DETAIL_ALPHA
            if layer_props.is_detail_map and texture.use_mipmap:
                if slot.blend_type == "ADD":
                    detail_blend = TEX_DETAIL_ADD
                elif slot.blend_type == "MULTIPLY":
                    detail_blend = TEX_DETAIL_MULTIPLY

            # Herp, derp... Detail blends are all based on alpha
            if layer_props.is_detail_map and not state.blendFlags & hsGMatState.kBlendMask:
                state.blendFlags |= hsGMatState.kBlendAlpha

            key = _Texture(texture=texture, use_alpha=has_alpha, force_calc_alpha=slot.use_stencil,
                           is_detail_map=layer_props.is_detail_map, detail_blend=detail_blend,
                           detail_fade_start=layer_props.detail_fade_start, detail_fade_stop=layer_props.detail_fade_stop,
                           detail_opacity_start=layer_props.detail_opacity_start, detail_opacity_stop=layer_props.detail_opacity_stop)
            if key not in self._pending:
                print("            Stashing '{}' for conversion as '{}'".format(texture.image.name, str(key)))
                self._pending[key] = [layer.key,]
            else:
                print("            Found another user of '{}'".format(texture.image.name))
                self._pending[key].append(layer.key)

    def _export_texture_type_none(self, bo, layer, texture):
        # We'll allow this, just for sanity's sake...
        pass

    def export_prepared_layer(self, layer, image):
        """This exports an externally prepared layer and image"""
        key = _Texture(image=image)
        if key not in self._pending:
            print("        Stashing '{}' for conversion as '{}'".format(image.name, str(key)))
            self._pending[key] = [layer.key,]
        else:
            print("        Found another user of '{}'".format(key))
            self._pending[key].append(layer.key)

    def finalize(self):
        for key, layers in self._pending.items():
            name = str(key)
            print("\n[Mipmap '{}']".format(name))

            image = key.image
            oWidth, oHeight = image.size
            eWidth = helpers.ensure_power_of_two(oWidth)
            eHeight = helpers.ensure_power_of_two(oHeight)
            if (eWidth != oWidth) or (eHeight != oHeight):
                print("    Image is not a POT ({}x{}) resizing to {}x{}".format(oWidth, oHeight, eWidth, eHeight))
                self._resize_image(image, eWidth, eHeight)

            # Some basic mipmap settings.
            compression = plBitmap.kDirectXCompression if key.mipmap else plBitmap.kUncompressed
            dxt = plBitmap.kDXT5 if key.use_alpha or key.calc_alpha else plBitmap.kDXT1

            # Grab the image data from OpenGL and stuff it into the plBitmap
            helper = GLTexture(key)
            with helper as glimage:
                if key.mipmap:
                    numLevels = glimage.num_levels
                    print("    Generating mip levels")
                    glimage.generate_mipmap()
                else:
                    numLevels = 1
                    print("    Stuffing image data")

                # Uncompressed bitmaps are BGRA
                fmt = compression == plBitmap.kUncompressed

                # Hold the uncompressed level data for now. We may have to make multiple copies of
                # this mipmap for per-page textures :(
                data = []
                for i in range(numLevels):
                    data.append(glimage.get_level_data(i, key.calc_alpha, fmt))

            # Be a good citizen and reset the Blender Image to pre-futzing state
            image.reload()

            # Now we poke our new bitmap into the pending layers. Note that we have to do some funny
            # business to account for per-page textures
            mgr = self._mgr
            pages = {}

            print("    Adding to Layer(s)")
            for layer in layers:
                print("        {}".format(layer.name))
                page = mgr.get_textures_page(layer) # Layer's page or Textures.prp

                # If we haven't created this plMipmap in the page (either layer's page or Textures.prp),
                # then we need to do that and stuff the level data. This is a little tedious, but we
                # need to be careful to manage our resources correctly
                if page not in pages:
                    mipmap = plMipmap(name=name, width=eWidth, height=eHeight, numLevels=numLevels,
                                      compType=compression, format=plBitmap.kRGB8888, dxtLevel=dxt)
                    helper.store_in_mipmap(mipmap, data, compression)
                    mgr.AddObject(page, mipmap)
                    pages[page] = mipmap
                else:
                    mipmap = pages[page]
                layer.object.texture = mipmap.key

    def get_materials(self, bo):
        return self._obj2mat.get(bo, [])

    def get_bump_layer(self, bo):
        return self._bumpMats.get(bo, None)

    def get_texture_animation_key(self, bo, bm, tex_name=None, tex_slot=None):
        """Finds or creates the appropriate key for sending messages to an animated Texture"""
        assert tex_name or tex_slot

        if tex_slot is None:
            tex_slot = bm.texture_slots.get(tex_name, None)
            if tex_slot is None:
                raise ExportError("Material '{}' does not contain Texture '{}'".format(bm.name, tex_name))
        if tex_name is None:
            tex_name = tex_slot.name

        name = "{}_{}_LayerAnim".format(bm.name, tex_name)
        layer = tex_slot.texture.plasma_layer
        pClass = plLayerSDLAnimation if layer.anim_sdl_var else plLayerAnimation
        return self._mgr.find_create_key(pClass, bl=bo, name=name)

    @property
    def _mgr(self):
        return self._exporter().mgr

    def _propagate_material_settings(self, bm, layer):
        """Converts settings from the Blender Material to corresponding plLayer settings"""
        state = layer.state

        # Shade Flags
        if not bm.use_mist:
            state.shadeFlags |= hsGMatState.kShadeNoFog # Dead in CWE
            state.shadeFlags |= hsGMatState.kShadeReallyNoFog

        # Colors
        layer.ambient = utils.color(bpy.context.scene.world.ambient_color)
        layer.preshade = utils.color(bm.diffuse_color)
        layer.runtime = utils.color(bm.diffuse_color)
        layer.specular = utils.color(bm.specular_color)

    def _resize_image(self, image, width, height):
        image.scale(width, height)
        image.update()

        # If the image is already loaded into OpenGL, we need to refresh it to get the scaling.
        if image.bindcode[0] != 0:
            image.gl_free()
            image.gl_load()

    def _test_image_alpha(self, image):
        """Tests to see if this image has any alpha data"""

        # In the interest of speed, let's see if we've already done this one...
        result = self._alphatest.get(image, None)
        if result is not None:
            return result

        if image.channels != 4:
            result = False
        elif not image.use_alpha:
            result = False
        else:
            # Using bpy.types.Image.pixels is VERY VERY VERY slow...
            key = _Texture(image=image)
            with GLTexture(key) as glimage:
                result = glimage.has_alpha

        self._alphatest[image] = result
        return result
