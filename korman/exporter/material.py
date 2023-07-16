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
import mathutils

from collections import defaultdict
import functools
import itertools
import math
from pathlib import Path
from typing import Dict, Iterator, Optional, Union
import weakref

from PyHSPlasma import *

from .explosions import *
from .. import helpers
from ..korlib import *
from . import utils

_MAX_STENCILS = 6

# Blender cube map mega image to libHSPlasma plCubicEnvironmap faces mapping...
# See https://blender.stackexchange.com/questions/46891/how-to-render-an-environment-to-a-cube-map-in-cycles
BLENDER_CUBE_MAP = ("leftFace", "backFace", "rightFace",
                    "bottomFace", "topFace", "frontFace")

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
            self.calc_alpha = getattr(texture, "use_calculate_alpha", False)
            self.mipmap = texture.use_mipmap
        else:
            self.layer = kwargs.get("layer")
            self.calc_alpha = False
            self.mipmap = kwargs.get("mipmap", False)

        if kwargs.get("is_detail_map", False):
            self.is_detail_map = True
            self.mipmap = True
            self.detail_blend = kwargs["detail_blend"]
            self.detail_fade_start = kwargs["detail_fade_start"]
            self.detail_fade_stop = kwargs["detail_fade_stop"]
            self.detail_opacity_start = kwargs["detail_opacity_start"]
            self.detail_opacity_stop = kwargs["detail_opacity_stop"]
            self.calc_alpha = False
            self.alpha_type = TextureAlpha.full
            self.allowed_formats = {"DDS"}
            self.is_cube_map = False
        else:
            self.is_detail_map = False
            if kwargs.get("force_calc_alpha", False) or self.calc_alpha:
                self.calc_alpha = True
                self.alpha_type = TextureAlpha.full
            else:
                self.alpha_type = kwargs.get("alpha_type", TextureAlpha.opaque)
            self.allowed_formats = kwargs.get("allowed_formats",
                                              {"DDS"} if self.mipmap else {"PNG", "JPG"})
            self.is_cube_map = kwargs.get("is_cube_map", False)

        # Basic format sanity
        if self.mipmap:
            assert "DDS" in self.allowed_formats

        if len(self.allowed_formats) == 1:
            self.auto_ext = next(iter(self.allowed_formats)).lower()
        elif self.mipmap:
            self.auto_ext = "dds"
        else:
            self.auto_ext = "hsm"
        self.extension = kwargs.get("extension", self.auto_ext)
        self.ephemeral = kwargs.get("ephemeral", False)
        self.image = image
        self.tag = kwargs.get("tag", None)
        self.name = kwargs.get("name", image.name)

    def __eq__(self, other):
        if not isinstance(other, _Texture):
            return False

        # Yeah, the string name is a unique identifier. So shoot me.
        if str(self) == str(other) and self.tag == other.tag:
            self._update(other)
            return True
        return False

    def __hash__(self):
        return hash(str(self))

    def __str__(self):
        if self.extension is None:
            name = self.name
        else:
            name = str(Path(self.name).with_suffix(".{}".format(self.extension)))
        if self.calc_alpha:
            name = "ALPHAGEN_{}".format(self.name)

        if self.is_detail_map:
            name = "DETAILGEN_{}-{}-{}-{}-{}_{}".format(self._DETAIL_BLEND[self.detail_blend],
                                                        self.detail_fade_start, self.detail_fade_stop,
                                                        self.detail_opacity_start, self.detail_opacity_stop,
                                                        self.name)
        return name

    def _update(self, other):
        """Update myself with any props that might be overridable from another copy of myself"""
        # NOTE: detail map properties should NEVER be overridden. NEVER. EVER. kthx.
        if self.alpha_type < other.alpha_type:
            self.alpha_type = other.alpha_type
        if other.mipmap:
            self.mipmap = True


class MaterialConverter:
    def __init__(self, exporter):
        self._obj2mat = defaultdict(dict)
        self._obj2layer = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self._bump_mats = {}
        self._exporter = weakref.ref(exporter)
        self._pending = {}
        self._alphatest = {}
        self._tex_exporters = {
            "BLEND": self._export_texture_type_blend,
            "ENVIRONMENT_MAP": self._export_texture_type_environment_map,
            "IMAGE": self._export_texture_type_image,
            "NONE": self._export_texture_type_none,
        }
        self._animation_exporters = {
            "ambientCtl": functools.partial(self._export_layer_diffuse_animation, converter=self.get_material_ambient),
            "opacityCtl": self._export_layer_opacity_animation,
            "preshadeCtl": functools.partial(self._export_layer_diffuse_animation, converter=self.get_material_preshade),
            "runtimeCtl": functools.partial(self._export_layer_diffuse_animation, converter=self.get_material_runtime),
            "transformCtl": self._export_layer_transform_animation,
        }

    def _can_export_texslot(self, slot):
        if slot is None or not slot.use:
            return False
        texture = slot.texture
        if texture is None or texture.type not in self._tex_exporters:
            return False

        # Per-texture type rules
        if texture.type == "ENVIRONMENT_MAP":
            envmap = texture.environment_map
            # If this is a static, image based cube map, then we will allow it
            # to be exported anyway. Note that as of the writing of this code,
            # that is kind of pointless because CEMs are not yet implemented...
            if envmap.source == "IMAGE_FILE":
                return True

            # Now for the ruelz
            method, ver = self._exporter().envmap_method, self._mgr.getVer()
            if method == "skip":
                return False
            elif method == "dcm2dem":
                return True
            elif method == "perengine":
                return (ver >= pvMoul and envmap.mapping == "PLANE") or envmap.mapping == "CUBE"
            else:
                raise NotImplementedError(method)
        else:
            return True

    def export_material(self, bo, bm):
        """Exports a Blender Material as an hsGMaterial"""

        # Sometimes, a material might need to be single-use due to settings like baked lighting,
        # being a waveset, doublesided, etc.
        single_user = self._requires_single_user(bo, bm)
        if single_user:
            mat_name = f"{bm.name}_AutoSingle" if bo.name == bm.name else f"{bo.name}_{bm.name}"
            self._report.msg(f"Exporting Material '{bm.name}' as single user '{mat_name}'")
        else:
            # Ensure that RT-lit objects don't infect the static-lit objects.
            lighting_mod = bo.plasma_modifiers.lighting
            if lighting_mod.unleashed:
                mat_prefix = "Unleashed_"
            elif lighting_mod.rt_lights:
                mat_prefix = "RTLit_"
            else:
                mat_prefix = ""
            mat_prefix2 = "NonVtxP_" if self._exporter().mesh.is_nonpreshaded(bo, bm) else ""
            mat_name = "".join((mat_prefix, mat_prefix2, bm.name))
            self._report.msg(f"Exporting Material '{mat_name}'")
            hsgmat = self._mgr.find_key(hsGMaterial, name=mat_name, bl=bo)
            if hsgmat is not None:
                return hsgmat

        hsgmat = self._mgr.add_object(hsGMaterial, name=mat_name, bl=bo)
        slots = [(idx, slot) for idx, slot in enumerate(bm.texture_slots) if self._can_export_texslot(slot)]

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
        restart_pass_next = False

        # Loop over layers
        with self._report.indent():
            for idx, slot in slots:
                # Prepend any BumpMapping magic layers
                if slot.use_map_normal:
                    if bo in self._bump_mats:
                        raise ExportError("Material '{}' has more than one bumpmap layer".format(bm.name))
                    du, dw, dv = self.export_bumpmap_slot(bo, bm, hsgmat, slot, idx)
                    hsgmat.addLayer(du.key) # Du
                    hsgmat.addLayer(dw.key) # Dw
                    hsgmat.addLayer(dv.key) # Dv

                if slot.use_stencil:
                    stencils.append((idx, slot))
                else:
                    tex_name = "{}_{}".format(mat_name, slot.name)
                    tex_layer = self.export_texture_slot(bo, bm, hsgmat, slot, idx, name=tex_name)
                    if restart_pass_next:
                        tex_layer.state.miscFlags |= hsGMatState.kMiscRestartPassHere
                        restart_pass_next = False
                    hsgmat.addLayer(tex_layer.key)
                    if slot.use_map_normal:
                        self._bump_mats[bo] = (tex_layer.UVWSrc, tex_layer.transform)
                        # After a bumpmap layer(s), the next layer *must* be in a
                        # new pass, otherwise it gets added in non-intuitive ways
                        restart_pass_next = True
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
            layer = self._mgr.find_create_object(plLayer, name="{}_AutoLayer".format(mat_name), bl=bo)
            self._obj2layer[bo][bm][None].append(layer.key)
            self._propagate_material_settings(bo, bm, None, layer)
            layer = self._export_layer_animations(bo, bm, None, 0, layer)
            hsgmat.addLayer(layer.key)

        # Cache this material for later
        self._obj2mat[bo][bm] = hsgmat.key

        # Looks like we're done...
        return hsgmat.key

    def export_print_materials(self, bo, image, name, blend):
        """Exports dynamic decal print material(s)"""

        def make_print_material(name):
            layer = self._mgr.add_object(plLayer, bl=bo, name=name)
            layer.state.blendFlags = blend
            layer.state.clampFlags = hsGMatState.kClampTexture
            layer.state.ZFlags = hsGMatState.kZNoZWrite | hsGMatState.kZIncLayer
            layer.ambient = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
            layer.preshade = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
            layer.runtime = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
            self.export_prepared_image(name=image_name, image=image, alpha_type=image_alpha,
                                       owner=layer, allowed_formats={"DDS"})
            material = self._mgr.add_object(hsGMaterial, bl=bo, name=name)
            material.addLayer(layer.key)
            return material, layer

        want_preshade = blend == hsGMatState.kBlendAlpha

        image_alpha = self._test_image_alpha(image)
        if image_alpha == TextureAlpha.opaque and want_preshade:
            self._report.warn("Using an opaque texture with alpha blending -- this may look bad")

        # Non-alpha blendmodes absolutely cannot have an alpha channel. Period. Nada.
        # You can't even filter it out with blend flags. We'll try to mitigate the damage by
        # exporting a DXT1 version. As of right now, opaque vs on_off does nothing, so we still
        # get some turd-alpha data.
        if image_alpha == TextureAlpha.full and not want_preshade:
            self._report.warn("Using an alpha texture with a non-alpha blend mode -- this may look bad")
            image_alpha = TextureAlpha.opaque
            image_name = "DECALPRINT_{}".format(image.name)
        else:
            image_name = image.name

        # Check to see if we have already processed this print material...
        rtname = "DECALPRINT_{}".format(name)
        rt_key = self._mgr.find_key(hsGMaterial, bl=bo, name=rtname)
        if want_preshade:
            prename = "DECALPRINT_{}_AH".format(name)
            pre_key = self._mgr.find_key(hsGMaterial, bl=bo, name=prename)
        else:
            pre_key = None
        if rt_key or pre_key:
            return pre_key, rt_key

        self._report.msg(f"Exporting Print Material '{rtname}'")
        with self._report.indent():
            rt_material, rt_layer = make_print_material(rtname)
        if blend == hsGMatState.kBlendMult:
            rt_layer.state.blendFlags |= hsGMatState.kBlendInvertFinalColor
        rt_key = rt_material.key

        if want_preshade:
            self._report.msg(f"Exporting Print Material '{prename}'")
            with self._report.indent():
                pre_material, pre_layer = make_print_material(prename)
            pre_material.compFlags |= hsGMaterial.kCompNeedsBlendChannel
            pre_layer.state.miscFlags |= hsGMatState.kMiscBindNext | hsGMatState.kMiscRestartPassHere
            pre_layer.preshade = hsColorRGBA(1.0, 1.0, 1.0, 1.0)

            blend_layer = self._mgr.add_object(plLayer, bl=bo, name="{}_AlphaBlend".format(rtname))
            blend_layer.state.blendFlags = hsGMatState.kBlendAlpha | hsGMatState.kBlendNoTexColor | \
                                           hsGMatState.kBlendAlphaMult
            blend_layer.state.clampFlags = hsGMatState.kClampTexture
            blend_layer.state.ZFlags = hsGMatState.kZNoZWrite
            blend_layer.ambient = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
            pre_material.addLayer(blend_layer.key)
            with self._report.indent():
                self.export_alpha_blend("LINEAR", "HORIZONTAL", owner=blend_layer)

            pre_key = pre_material.key
        else:
            pre_key = None
        return pre_key, rt_key

    def export_waveset_material(self, bo, bm):
        self._report.msg(f"Exporting WaveSet Material '{bm.name}'")

        # WaveSets MUST have their own material
        unique_name = f"{bm.name}_WaveSet7"
        hsgmat = self._mgr.add_object(hsGMaterial, name=unique_name, bl=bo)

        # Materials MUST have one layer. Wavesets need alpha blending...
        layer = self._mgr.add_object(plLayer, name=unique_name, bl=bo)
        self._propagate_material_settings(bo, bm, None, layer)
        layer.state.blendFlags |= hsGMatState.kBlendAlpha
        hsgmat.addLayer(layer.key)

        # Wasn't that easy?
        return hsgmat.key

    def export_bumpmap_slot(self, bo, bm, hsgmat, slot, idx):
        name = f"{hsgmat.key.name}_{slot.name}"
        self._report.msg(f"Exporting Plasma Bumpmap Layers for '{name}'")

        # Okay, now we need to make 3 layers for the Du, Dw, and Dv
        du_layer = self._mgr.find_create_object(plLayer, name=f"{name}_DU_BumpLut", bl=bo)
        dw_layer = self._mgr.find_create_object(plLayer, name=f"{name}_DW_BumpLut", bl=bo)
        dv_layer = self._mgr.find_create_object(plLayer, name=f"{name}_DV_BumpLut", bl=bo)

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
            create_bump_LUT(bumpLUT)
            self._mgr.AddObject(page, bumpLUT)
            LUT_key = bumpLUT.key

        du_layer.texture = LUT_key
        dw_layer.texture = LUT_key
        dv_layer.texture = LUT_key

        return (du_layer, dw_layer, dv_layer)

    def export_texture_slot(self, bo, bm, hsgmat, slot, idx, name=None, blend_flags=True):
        if name is None:
            name = f"{bm.name if bm is not None else bo.name}_{slot.name}"
        self._report.msg(f"Exporting Plasma Layer '{name}'")
        layer = self._mgr.find_create_object(plLayer, name=name, bl=bo)
        if bm is not None and not slot.use_map_normal:
            self._propagate_material_settings(bo, bm, slot, layer)

        with self._report.indent():
            # UVW Channel
            if slot.texture_coords == "UV":
                for i, uvchan in enumerate(bo.data.uv_layers):
                    if uvchan.name == slot.uv_layer:
                        layer.UVWSrc = i
                        self._report.msg(f"Using UV Map #{i} '{name}'")
                        break
                else:
                    self._report.msg("No UVMap specified... Blindly using the first one, maybe it exists :|")

            # Transform
            xform = hsMatrix44()
            translation = hsVector3(slot.offset.x - (slot.scale.x - 1.0) / 2.0,
                                    -slot.offset.y - (slot.scale.y - 1.0) / 2.0,
                                    slot.offset.z - (slot.scale.z - 1.0) / 2.0)
            xform.setTranslate(translation)
            xform.setScale(hsVector3(*slot.scale))
            layer.transform = xform

            wantStencil, canStencil = slot.use_stencil, slot.use_stencil and bm is not None and not slot.use_map_normal
            if wantStencil and not canStencil:
                self._exporter().report.warn(f"{slot.name} wants to stencil, but this is not a real Material")

            state = layer.state
            if canStencil:
                hsgmat.compFlags |= hsGMaterial.kCompNeedsBlendChannel
                state.blendFlags |= hsGMatState.kBlendAlpha | hsGMatState.kBlendAlphaMult | hsGMatState.kBlendNoTexColor
                state.ZFlags |= hsGMatState.kZNoZWrite
                layer.ambient = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
            elif blend_flags:
                # Standard layer flags ahoy
                if slot.blend_type == "ADD":
                    state.blendFlags |= hsGMatState.kBlendAddColorTimesAlpha
                elif slot.blend_type == "MULTIPLY":
                    state.blendFlags |= hsGMatState.kBlendMult

            # Check if this layer uses diffuse/runtime lighting
            if bm is not None and not slot.use_map_color_diffuse:
                layer.preshade = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
                layer.runtime = hsColorRGBA(0.0, 0.0, 0.0, 1.0)

            # Check if this layer uses specular lighting
            if bm is not None and slot.use_map_color_spec:
                state.shadeFlags |= hsGMatState.kShadeSpecular
            else:
                layer.specular = hsColorRGBA(0.0, 0.0, 0.0, 1.0)
                layer.specularPower = 1.0

            texture = slot.texture
            if texture.type == "BLEND":
                hsgmat.compFlags |= hsGMaterial.kCompNeedsBlendChannel

            # Handle material and per-texture emissive
            if self._is_emissive(bm):
                # If the previous slot's use_map_emit is different, then we need to flag this as a new
                # pass so that the new emit color will be used. But only if it's not a doggone stencil.
                if not wantStencil and bm is not None and slot is not None:
                    filtered_slots = tuple(filter(lambda x: x and x.use, bm.texture_slots[:idx]))
                    if filtered_slots:
                        prev_slot = filtered_slots[-1]
                        if prev_slot != slot and prev_slot.use_map_emit != slot.use_map_emit:
                            state.miscFlags |= hsGMatState.kMiscRestartPassHere

                if self._is_emissive(bm, slot):
                    # Lightmapped emissive layers seem to cause cascading render issues. Skip flagging it
                    # and just hope that the ambient color bump is good enough.
                    if bo.plasma_modifiers.lightmap.bake_lightmap:
                        self._report.warn("A lightmapped and emissive material??? You like living dangerously...")
                    else:
                        state.shadeFlags |= hsGMatState.kShadeEmissive

            # Apply custom layer properties
            wantBumpmap = bm is not None and slot.use_map_normal
            if wantBumpmap:
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
                self._handle_layer_opacity(layer, layer_props.opacity)
                if layer_props.alpha_halo:
                    state.blendFlags |= hsGMatState.kBlendAlphaTestHigh
                if layer_props.z_bias:
                    state.ZFlags |= hsGMatState.kZIncLayer
                if layer_props.skip_depth_test:
                    state.ZFlags |= hsGMatState.kZNoZRead
                if layer_props.skip_depth_write:
                    state.ZFlags |= hsGMatState.kZNoZWrite

            # Export the specific texture type
            self._tex_exporters[texture.type](bo, layer, slot, idx)

            # Export any layer animations
            # NOTE: animated stencils and bumpmaps are nonsense.
            if not slot.use_stencil and not wantBumpmap:
                layer = self._export_layer_animations(bo, bm, slot, idx, layer)

            # Stash the top of the stack for later in the export
            if bm is not None:
                self._obj2layer[bo][bm][texture].append(layer.key)
            return layer

    def _export_layer_animations(self, bo, bm, tex_slot, idx, base_layer) -> plLayer:
        top_layer = base_layer
        converter = self._exporter().animation
        texture = tex_slot.texture if tex_slot is not None else None

        def attach_layer(pClass: type, anim_name: str, controllers: Dict[str, plController]):
            nonlocal top_layer
            name = "{}_{}".format(base_layer.key.name, anim_name)
            layer_animation = self._mgr.find_create_object(pClass, bl=bo, name=name)

            # A word: in my testing, saving the Layer SDL to a server can result in issues where
            # the animation get stuck in a state that no longer matches the animation you've
            # created, and the result is an irrecoverable mess. Meaning, the animation plays
            # whenever and however it wants, regardless of your fancy logic nodes. At some point,
            # we may (TODO) want to pass these animations through the PlasmaNet thingo and apply
            # the synch flags it thinks we need. For now, just exclude everything.
            layer_animation.synchFlags |= plSynchedObject.kExcludeAllPersistentState

            for attr, ctrl in controllers.items():
                setattr(layer_animation, attr, ctrl)
            layer_animation.underLay = top_layer.key
            top_layer = layer_animation

        if texture is not None:
            layer_props = texture.plasma_layer
            for anim in layer_props.subanimations:
                if not anim.is_entire_animation:
                    start, end = anim.start, anim.end
                else:
                    start, end = None, None
                controllers = self._export_layer_controllers(bo, bm, tex_slot, idx, base_layer,
                                                             start=start, end=end)
                if not controllers:
                    continue

                pClass = plLayerSDLAnimation if anim.sdl_var else plLayerAnimation
                attach_layer(pClass, anim.animation_name, controllers)
                atc = top_layer.timeConvert
                atc.begin, atc.end = converter.get_frame_time_range(*controllers.values())
                atc.loopBegin, atc.loopEnd = atc.begin, atc.end
                if not anim.auto_start:
                    atc.flags |= plAnimTimeConvert.kStopped
                if anim.loop:
                    atc.flags |= plAnimTimeConvert.kLoop
                if isinstance(top_layer, plLayerSDLAnimation):
                    top_layer.varName = anim.sdl_var
        else:
            # Crappy automatic entire layer animation. Loop it by default.
            controllers = self._export_layer_controllers(bo, bm, tex_slot, idx, base_layer)
            if controllers:
                attach_layer(plLayerAnimation, "(Entire Animation)", controllers)
                atc = top_layer.timeConvert
                atc.flags |= plAnimTimeConvert.kLoop
                atc.begin, atc.end = converter.get_frame_time_range(*controllers.values())
                atc.loopBegin = atc.begin
                atc.loopEnd = atc.end

        return top_layer


    def _export_layer_controllers(self, bo: bpy.types.Object, bm: bpy.types.Material, tex_slot,
                                  idx: int, base_layer, *, start: Optional[int] = None,
                                  end: Optional[int] = None) -> Dict[str, plController]:
        """Convert animations on this material/texture combo in the requested range to Plasma controllers"""

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

        # Base layers get all of the fcurves for animating things like the diffuse color. Danger,
        # however, the user can insert fake base layers on top, so be careful.
        texture = tex_slot.texture if tex_slot is not None else None
        if idx == 0 or base_layer.state.miscFlags & hsGMatState.kMiscRestartPassHere:
            harvest_fcurves(bm, fcurves)
            harvest_fcurves(texture, fcurves)
        elif tex_slot is not None:
            harvest_fcurves(bm, fcurves, tex_slot.path_from_id())
            harvest_fcurves(texture, fcurves)

        # Take the FCurves and ram them through our converters, hopefully returning some valid
        # animation controllers.
        controllers = {}
        for attr, converter in self._animation_exporters.items():
            ctrl = converter(bo, bm, tex_slot, base_layer, fcurves, start=start, end=end)
            if ctrl is not None:
                controllers[attr] = ctrl
        return controllers

    def _export_layer_diffuse_animation(self, bo, bm, tex_slot, base_layer, fcurves, *, start, end, converter):
        assert converter is not None

        # If there's no material, then this is simply impossible.
        if bm is None:
            return None

        def translate_color(color_sequence):
            # See things like get_material_preshade
            result = converter(bo, bm, tex_slot, mathutils.Color(color_sequence))
            return result.red, result.green, result.blue

        ctrl = self._exporter().animation.make_pos_controller(fcurves, "diffuse_color",
                                                              bm.diffuse_color, translate_color,
                                                              start=start, end=end)
        return ctrl

    def _export_layer_opacity_animation(self, bo, bm, tex_slot, base_layer, fcurves, *, start, end):
        # Dumb function to intercept the opacity values and properly flag the base layer
        def process_opacity(value):
            self._handle_layer_opacity(base_layer, value)
            return value

        for i in fcurves:
            if i.data_path == "plasma_layer.opacity":
                ctrl = self._exporter().animation.make_scalar_leaf_controller(i, process_opacity, start=start, end=end)
                return ctrl
        return None

    def _export_layer_transform_animation(self, bo, bm, tex_slot, base_layer, fcurves, *, start, end):
        if tex_slot is not None:
            path = tex_slot.path_from_id()
            pos_path = "{}.offset".format(path)
            scale_path = "{}.scale".format(path)

            # Plasma uses the controller to generate a matrix44... so we have to produce a leaf controller
            ctrl = self._exporter().animation.make_matrix44_controller(fcurves, pos_path, scale_path,
                                                                       tex_slot.offset, tex_slot.scale,
                                                                       start=start, end=end)
            return ctrl
        return None

    def _export_texture_type_environment_map(self, bo, layer, slot, idx):
        """Exports a Blender EnvironmentMapTexture to a plLayer"""

        texture = slot.texture
        bl_env = texture.environment_map
        if bl_env.source in {"STATIC", "ANIMATED"}:
            # NOTE: It is assumed that if we arrive here, we are at lease dcm2dem on the
            #       environment map export method. You're welcome!
            if bl_env.mapping == "PLANE" and self._mgr.getVer() >= pvMoul:
                pl_env = plDynamicCamMap
            else:
                pl_env = plDynamicEnvMap
            pl_env = self.export_dynamic_env(bo, layer, texture, pl_env)
        elif bl_env.source == "IMAGE_FILE":
            pl_env = self.export_cubic_env(bo, layer, texture)
        else:
            raise NotImplementedError(bl_env.source)
        layer.state.shadeFlags |= hsGMatState.kShadeEnvironMap
        if pl_env is not None:
            layer.texture = pl_env.key

    def export_cubic_env(self, bo, layer, texture):
        if texture.image is None:
            raise ExportError(f"CubeMap '{texture.name}' has no cube image!")
        width, height = texture.image.size

        # Sanity check: the image here should be 3x2 faces, so we should not have any
        #               dam remainder...
        if width % 3 != 0:
            raise ExportError("CubeMap '{}' width must be a multiple of 3".format(texture.image.name))
        if height % 2 != 0:
            raise ExportError("CubeMap '{}' height must be a multiple of 2".format(texture.image.name))

        # According to PlasmaMAX, we don't give a rip about UVs...
        layer.UVWSrc = plLayerInterface.kUVWReflect
        layer.state.miscFlags |= hsGMatState.kMiscUseReflectionXform

        # Well, this is kind of sad...
        # Back before the texture cache existed, all the image work was offloaded
        # to a big "finalize" save step to prevent races. The texture cache would
        # prevent that as well, so we could theoretically slice-and-dice the single
        # image here... but... meh. Offloading taim.
        self.export_prepared_image(texture=texture, owner=layer, indent=3,
                                   alpha_type=TextureAlpha.opaque, mipmap=True,
                                   allowed_formats={"DDS"}, is_cube_map=True, tag="cubemap")


    def export_dynamic_env(self, bo, layer, texture, pl_class):
        bl_env = texture.environment_map
        viewpt = bl_env.viewpoint_object
        if viewpt is None:
            viewpt = bo
        name = "{}_DynEnvMap".format(texture.name)
        pl_env = self._mgr.find_object(pl_class, bl=bo, name=name)

        # Ensure POT
        oRes = bl_env.resolution
        eRes = helpers.ensure_power_of_two(oRes)
        if oRes != eRes:
            self._report.msg(f"Overriding EnvMap size to ({eRes}x{eRes}) -- POT")

        # And now for the general ho'hum-ness
        pl_env = self._mgr.find_create_object(pl_class, bl=bo, name=name)
        pl_env.hither = bl_env.clip_start
        pl_env.yon = bl_env.clip_end
        pl_env.refreshRate = 0.01 if bl_env.source == "ANIMATED" else 0.0
        pl_env.incCharacters = texture.plasma_layer.envmap_addavatar

        # Perhaps the DEM/DCM fog should be separately configurable at some point?
        pl_env.color = utils.color(texture.plasma_layer.envmap_color)
        pl_env.fogStart = -1.0

        # EffVisSets
        # Whoever wrote this PyHSPlasma binding didn't follow the convention. Sigh.
        visregions = []
        for region in texture.plasma_layer.vis_regions:
            rgn = region.control_region
            if rgn is None:
                raise ExportError("'{}': Has an invalid Visibility Control".format(texture.name))
            if not rgn.plasma_modifiers.visregion.enabled:
                raise ExportError("'{}': '{}' is not a VisControl".format(texture.name, rgn.name))
            visregions.append(self._mgr.find_create_key(plVisRegion, bl=rgn))
        pl_env.visRegions = visregions

        if isinstance(pl_env, plDynamicCamMap):
            faces = (pl_env,)

            # It matters not whether or not the viewpoint object is a Plasma Object, it is exported as at
            # least a SceneObject and CoordInterface so that we can touch it...
            # NOTE: that harvest_actor makes sure everyone alread knows we're going to have a CI
            if isinstance(viewpt.data, bpy.types.Camera):
                pl_env.camera = self._mgr.find_create_key(plCameraModifier, bl=viewpt)
            else:
                pl_env.rootNode = self._mgr.find_create_key(plSceneObject, bl=viewpt)

            pl_env.addTargetNode(self._mgr.find_key(plSceneObject, bl=bo))
            pl_env.addMatLayer(layer.key)

            # This is really just so we don't raise any eyebrows if anyone is looking at the files.
            # If you're disabling DCMs, then you're obviuously trolling!
            # Cyan generates a single color image, but we'll just set the layer colors and go away.
            fake_layer = self._mgr.find_create_object(plLayer, bl=bo, name="{}_DisabledDynEnvMap".format(texture.name))
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

            # If the user specifies a camera object, this might be worthy of a notice.
            if viewpt.type == "CAMERA":
                warn = self._report.port if bl_env.mapping == "PLANE" else self._report.warn
                warn("Environment Map '{}' is exporting as a cube map. The viewpoint '{}' is a camera, but only its position will be used.",
                     bl_env.id_data.name, viewpt.name)

            # DEMs can do just a position vector. We actually prefer this because the WaveSet exporter
            # will probably want to steal it for diabolical purposes... In MOUL, root objects are
            # allowed, but that introduces a gotcha with regard to animated roots and PotS. Also,
            # sharing root objects with a DCM seems to result in bad problems in game O.o
            pl_env.position = hsVector3(*viewpt.matrix_world.translation)

            if layer is not None:
                layer.UVWSrc = plLayerInterface.kUVWReflect
                layer.state.miscFlags |= hsGMatState.kMiscUseReflectionXform

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

    def _export_texture_type_image(self, bo, layer, slot, idx):
        """Exports a Blender ImageTexture to a plLayer"""
        texture = slot.texture
        layer_props = texture.plasma_layer
        mipmap = texture.use_mipmap

        # Does the image have any alpha at all?
        if texture.image is not None:
            alpha_type = self._test_image_alpha(texture.image)
            has_alpha = texture.use_calculate_alpha or slot.use_stencil or alpha_type != TextureAlpha.opaque
            if (texture.image.use_alpha and texture.use_alpha) and not has_alpha:
                self._report.warn(f"'{texture.name}' wants to use alpha, but '{texture.image.name}' is opaque")
        else:
            alpha_type, has_alpha = TextureAlpha.opaque, False

        # First, let's apply any relevant flags
        state = layer.state
        if not slot.use_stencil and not getattr(slot, "use_map_normal", False):
            # mutually exclusive blend flags
            if texture.use_alpha and has_alpha:
                if slot.blend_type == "ADD":
                    state.blendFlags |= hsGMatState.kBlendAlphaAdd
                elif slot.blend_type == "MULTIPLY":
                    state.blendFlags |= hsGMatState.kBlendAlphaMult
                elif not (state.blendFlags & hsGMatState.kBlendMask):
                    state.blendFlags |= hsGMatState.kBlendAlpha

            if texture.invert_alpha and has_alpha:
                state.blendFlags |= hsGMatState.kBlendInvertAlpha

            # Not really mutually exclusive, but if this isn't the first slot and there's no alpha,
            # then this is probably a new base layer, meaning that we need to restart the render pass.
            if not has_alpha and idx > 0:
                state.miscFlags |= hsGMatState.kMiscRestartPassHere

        if texture.extension in {"CLIP", "EXTEND"}:
            state.clampFlags |= hsGMatState.kClampTexture

        # Now, let's export the plBitmap
        # If the image is None (no image applied in Blender), we assume this is a plDynamicTextMap
        # Otherwise, we toss this layer and some info into our pending texture dict and process it
        #     when the exporter tells us to finalize all our shit
        if texture.image is None:
            dtm = self._mgr.find_create_object(plDynamicTextMap, name="{}_DynText".format(layer.key.name), bl=bo)
            if texture.use_alpha:
                dtm.hasAlpha = True
                if not state.blendFlags & hsGMatState.kBlendMask:
                    state.blendFlags |= hsGMatState.kBlendAlpha
            else:
                dtm.hasAlpha = False
            dtm.visWidth = int(layer_props.dynatext_resolution)
            dtm.visHeight = int(layer_props.dynatext_resolution)
            layer.texture = dtm.key
        else:
            detail_blend = TEX_DETAIL_ALPHA
            if layer_props.is_detail_map and mipmap:
                if slot.blend_type == "ADD":
                    detail_blend = TEX_DETAIL_ADD
                elif slot.blend_type == "MULTIPLY":
                    detail_blend = TEX_DETAIL_MULTIPLY

            # Herp, derp... Detail blends are all based on alpha
            if layer_props.is_detail_map and not state.blendFlags & hsGMatState.kBlendMask:
                state.blendFlags |= hsGMatState.kBlendDetail

            allowed_formats = {"DDS"} if mipmap else {"PNG", "BMP"}
            self.export_prepared_image(texture=texture, owner=layer,
                                       alpha_type=alpha_type, force_calc_alpha=slot.use_stencil,
                                       is_detail_map=layer_props.is_detail_map,
                                       detail_blend=detail_blend,
                                       detail_fade_start=layer_props.detail_fade_start,
                                       detail_fade_stop=layer_props.detail_fade_stop,
                                       detail_opacity_start=layer_props.detail_opacity_start,
                                       detail_opacity_stop=layer_props.detail_opacity_stop,
                                       mipmap=mipmap, allowed_formats=allowed_formats)

    def _export_texture_type_none(self, bo, layer, slot, idx):
        # We'll allow this, just for sanity's sake...
        pass

    def _export_texture_type_blend(self, bo, layer, slot, idx):
        state = layer.state
        state.blendFlags |= hsGMatState.kBlendAlpha | hsGMatState.kBlendAlphaMult | hsGMatState.kBlendNoTexColor
        state.clampFlags |= hsGMatState.kClampTexture
        state.ZFlags |= hsGMatState.kZNoZWrite

        # This has been separated out because other things may need alpha blend textures.
        texture = slot.texture
        self.export_alpha_blend(texture.progression, texture.use_flip_axis, layer)

    def export_alpha_blend(self, progression, axis, owner):
        """This exports an alpha blend texture as exposed by bpy.types.BlendTexture.
           The following arguments are expected:
           - progression: (required)
           - axis: (required)
           - owner: (required) the Plasma object using this image
        """

        # Certain blend types don't use an axis...
        progression_axes = {"EASING", "LINEAR", "RADIAL", "QUADRATIC"}
        if progression in progression_axes:
            filename = "ALPHA_BLEND_{}_{}".format(progression, axis)
        else:
            filename = "ALPHA_BLEND_{}".format(progression)
            axis = ""

        image = bpy.data.images.get(filename)
        if image is None:
            def _calc_diagonal(x, y, width, height):
                distance = math.sqrt(pow(x, 2) + pow(y, 2))
                total = math.sqrt(pow(width, 2) + pow(height, 2))
                return distance / total

            def _calc_radial(x, y, width, height, horizontal=None):
                if horizontal is True:
                    relative = (y - height / 2, x - width / 2)
                elif horizontal is False:
                    relative = (x - width / 2, y - height / 2)
                else:
                    raise RuntimeError()
                angle = math.atan2(*relative) + math.pi
                # PyPRP had some weird code that looked like an infinite loop for clamping from
                # zero through 2pi. atan2 is documented to return in the range of -pi through pi.
                two_pi = math.pi * 2
                if angle < 0.0:
                    angle += two_pi
                return max(0.0, angle / two_pi)

            def _calc_lin_sphere(x, y, width, height):
                half_width, half_height = width / 2, height / 2
                distance = math.sqrt(pow(x - half_width, 2) + pow(y - half_height, 2))
                value = math.cos(distance / half_width * 0.5 * math.pi)
                if value < 0.0 or distance > half_width:
                    return 0.0
                else:
                    return min(1.0, value)

            def _calc_quad_sphere(x, y, width, height):
                half_width, half_height = width / 2, height / 2
                distance = math.sqrt(pow(x - half_width, 2) + pow(y - half_height, 2))
                value = 0.5 + (0.5 * math.cos(distance / half_width * math.pi))
                if value < 0.0 or distance > half_width:
                    return 0.0
                else:
                    return min(1.0, value)

            dimensions = {
                ("EASING", "HORIZONTAL"): (64, 4),
                ("EASING", "VERTICAL"): (4, 64),
                ("LINEAR", "HORIZONTAL"): (64, 4),
                ("LINEAR", "VERTICAL"): (4, 64),
                ("QUADRATIC", "HORIZONTAL"): (64, 4),
                ("QUADRATIC", "VERTICAL"): (4, 64),
            }
            funcs = {
                ("DIAGONAL", ""):  _calc_diagonal,
                ("EASING", "HORIZONTAL"): lambda x, y, width, height: 0.5 - math.cos(x / width * math.pi) * 0.5,
                ("EASING", "VERTICAL"): lambda x, y, width, height: 0.5 - math.cos(y / height * math.pi) * 0.5,
                ("LINEAR", "HORIZONTAL"): lambda x, y, width, height: x / width,
                ("LINEAR", "VERTICAL"): lambda x, y, width, height: y / height,
                ("QUADRATIC", "HORIZONTAL"): lambda x, y, width, height: pow(x / width, 2),
                ("QUADRATIC", "VERTICAL"): lambda x, y, width, height: pow(y / height, 2),
                ("QUADRATIC_SPHERE", ""): _calc_quad_sphere,
                ("RADIAL", "HORIZONTAL"): functools.partial(_calc_radial, horizontal=True),
                ("RADIAL", "VERTICAL"): functools.partial(_calc_radial, horizontal=False),
                ("SPHERICAL", ""): _calc_lin_sphere,
            }

            blend_type = (progression, axis)
            width, height = dimensions.get(blend_type, (64, 64))
            pixels = [None] * (width * height * 4)
            func = funcs.get(blend_type)
            if func is None:
                raise BlendNotSupported(progression, axis)

            # This is slower than a custom writer for each blend texture, but that would be uglier
            # and less maintainable. Running this function in the Blender console is nearly instant,
            # so I think this is the best option, really.
            for x in range(width):
                for y in range(height):
                    offset = (y * width * 4) + (x * 4)
                    value = func(x, y, width, height)
                    pixels[offset:offset+4] = (value,) * 4
            image = bpy.data.images.new(filename, width=width, height=height, alpha=True)
            image.source = "GENERATED"
            image.pixels = pixels
            image.update()
            image.pack(True)

        self.export_prepared_image(image=image, owner=owner, allowed_formats={"BMP"},
                                   alpha_type=TextureAlpha.full, ephemeral=True)

    def export_prepared_image(self, **kwargs):
        """This exports an externally prepared image and an optional owning layer.
           The following arguments are typical:
           - texture: (co-required) the image texture datablock to export
           - image: (co-required) the image datablock to export
           - owner: (required) the Plasma object using this image
           - mipmap: (optional) should the image be mipmapped?
           - allowed_formats: (optional) set of string *hints* for desired image export type
                              valid options: BMP, DDS, JPG, PNG
           - extension: (optional) file extension to use for the image object
                        to use the image datablock extension, set this to None
           - ephemeral: (optional) never cache this image
           - tag: (optional) an optional identifier hint that allows multiple images with the
                             same name to coexist in the cache
           - is_cube_map: (optional) indicates the provided image contains six cube faces
                                     that must be split into six separate images for Plasma
        """
        owner = kwargs.pop("owner", None)
        key = _Texture(**kwargs)
        image = key.image

        if key not in self._pending:
            self._report.msg("Stashing '{}' for conversion as '{}'", image.name, key)
            self._pending[key] = [owner.key,]
        else:
            self._report.msg("Found another user of '{}'", key)
            self._pending[key].append(owner.key)

    def finalize(self):
        self._report.progress_advance()
        self._report.progress_range = len(self._pending)
        inc_progress = self._report.progress_increment
        mgr = self._mgr

        # This with statement causes the texture cache to hold open a
        # read stream for the cache file, preventing spurious open-close
        # spin washing during this tight loop. Note that the cache still
        # has to actually be loaded ^_^
        with self._texcache as texcache:
            texcache.load()

            for key, owners in self._pending.items():
                name = str(key)
                pClassName = "CubicEnvironmap" if key.is_cube_map else "Mipmap"
                self._report.msg("\n[{} '{}']", pClassName, name)

                with self._report.indent():
                    image = key.image

                    # Now we try to use the pile of hints we were given to figure out what format to use
                    allowed_formats = key.allowed_formats
                    if key.mipmap:
                        compression = plBitmap.kDirectXCompression
                    elif "PNG" in allowed_formats and self._mgr.getVer() == pvMoul:
                        compression = plBitmap.kPNGCompression
                    elif "DDS" in allowed_formats:
                        compression = plBitmap.kDirectXCompression
                    elif "JPG" in allowed_formats:
                        compression = plBitmap.kJPEGCompression
                    elif "BMP" in allowed_formats:
                        compression = plBitmap.kUncompressed
                    else:
                        raise RuntimeError(allowed_formats)
                    dxt = plBitmap.kDXT5 if key.alpha_type == TextureAlpha.full else plBitmap.kDXT1

                    # Mayhaps we have a cached version of this that has already been exported
                    cached_image = texcache.get_from_texture(key, compression)

                    if cached_image is None:
                        numLevels, width, height, data = self._finalize_cache(texcache, key, image, name, compression, dxt)
                        self._finalize_bitmap(key, owners, name, numLevels, width, height, compression, dxt, data)
                    else:
                        width, height = cached_image.export_size
                        data = cached_image.image_data
                        numLevels = cached_image.mip_levels

                        # If the cached image data is junk, PyHSPlasma will raise a RuntimeError,
                        # so we'll attempt a recache...
                        try:
                            self._finalize_bitmap(key, owners, name, numLevels, width, height, compression, dxt, data)
                        except RuntimeError:
                            self._report.warn("Cached image is corrupted! Recaching image...")
                            numLevels, width, height, data = self._finalize_cache(texcache, key, image, name, compression, dxt)
                            self._finalize_bitmap(key, owners, name, numLevels, width, height, compression, dxt, data)

                inc_progress()

    def _finalize_bitmap(self, key, owners, name, numLevels, width, height, compression, dxt, data):
        mgr = self._mgr

        # Now we poke our new bitmap into the pending layers. Note that we have to do some funny
        # business to account for per-page textures
        pages = {}

        self._report.msg("Adding to...")
        with self._report.indent():
            for owner_key in owners:
                owner = owner_key.object
                self._report.msg(f"[{owner.ClassName()[2:]} '{owner_key.name}']")
                page = mgr.get_textures_page(owner_key) # Layer's page or Textures.prp

                # If we haven't created this texture in the page (either layer's page or Textures.prp),
                # then we need to do that and stuff the level data. This is a little tedious, but we
                # need to be careful to manage our resources correctly
                if page not in pages:
                    mipmap = plMipmap(name=name, width=width, height=height, numLevels=numLevels,
                                    compType=compression, format=plBitmap.kRGB8888, dxtLevel=dxt)
                    if key.is_cube_map:
                        assert len(data) == 6
                        texture = plCubicEnvironmap(name)
                        for face_name, face_data in zip(BLENDER_CUBE_MAP, data):
                            for i in range(numLevels):
                                mipmap.setLevel(i, face_data[i])
                            setattr(texture, face_name, mipmap)
                    else:
                        assert len(data) == 1
                        for i in range(numLevels):
                            mipmap.setLevel(i, data[0][i])
                        texture = mipmap

                    mgr.AddObject(page, texture)
                    pages[page] = texture
                else:
                    texture = pages[page]

                # The object that references this image can be either a layer (will appear
                # in the 3d world) or an image library (will appear in a journal or in another
                # dynamic manner in game)
                if isinstance(owner, plLayerInterface):
                    owner.texture = texture.key
                elif isinstance(owner, plImageLibMod):
                    owner.addImage(texture.key)
                else:
                    raise NotImplementedError(owner.ClassName())

    def _finalize_cache(self, texcache, key, image, name, compression, dxt):
        if key.is_cube_map:
            numLevels, width, height, data = self._finalize_cube_map(key, image, name, compression, dxt)
        else:
            numLevels, width, height, data = self._finalize_single_image(key, image, name, compression, dxt)
        texcache.add_texture(key, numLevels, (width, height), compression, data)
        return numLevels, width, height, data

    def _finalize_cube_map(self, key, image, name, compression, dxt):
        oWidth, oHeight = image.size
        if oWidth == 0 and oHeight == 0:
            raise ExportError(f"Image '{image.name}' could not be loaded.")

        # Non-DXT images are BGRA in Plasma
        bgra = compression != plBitmap.kDirectXCompression

        # Grab the cube map data from OpenGL and prepare to begin...
        with GLTexture(key, bgra=bgra) as glimage:
            cWidth, cHeight, data = glimage.image_data

        # On some platforms, Blender will be "helpful" and scale the image to a POT.
        # That's great, but we have 3 faces as a width, which will certainly be NPOT
        # in the case of POT faces. So, we will scale the image AGAIN, if Blender did
        # something funky.
        if oWidth != cWidth or oHeight != cHeight:
            self._report.warn("Image was resized by Blender to ({}x{})--resizing the resize to ({}x{})",
                              cWidth, cHeight, oWidth, oHeight)
            data = scale_image(data, cWidth, cHeight, oWidth, oHeight)

        # Face dimensions
        fWidth, fHeight = oWidth // 3, oHeight // 2

        # Copy each of the six faces into a separate image buffer.
        # NOTE: At present, I am well pleased with the speed of this functionality.
        #       According to my profiling, it takes roughly 0.7 seconds to process a
        #       cube map whose faces are 1024x1024 (3072x2048 total). Maybe a later
        #       commit will move this into korlib. We'll see.
        face_num = len(BLENDER_CUBE_MAP)
        face_images = [None] * face_num
        for i in range(face_num):
            col_id = i if i < 3 else i - 3
            row_start = 0 if i < 3 else fHeight
            row_end = fHeight if i < 3 else oHeight

            face_data = bytearray(fWidth * fHeight * 4)
            for row_current in range(row_start, row_end, 1):
                src_start_idx = (row_current * oWidth * 4) + (col_id * fWidth * 4)
                src_end_idx = src_start_idx + (fWidth * 4)
                dst_start_idx = (row_current - row_start) * fWidth * 4
                dst_end_idx = dst_start_idx + (fWidth * 4)
                face_data[dst_start_idx:dst_end_idx] = data[src_start_idx:src_end_idx]
            face_images[i] = bytes(face_data)

        # Now that we have our six faces, we'll toss them into the GLTexture helper
        # to generate mipmaps, if needed...
        for i, face_name in enumerate(BLENDER_CUBE_MAP):
            glimage = GLTexture(key)
            glimage.image_data = fWidth, fHeight, face_images[i]
            eWidth, eHeight = glimage.size_pot
            name = face_name[:-4].upper()
            if compression == plBitmap.kDirectXCompression:
                numLevels = glimage.num_levels
                self._report.msg("Generating mip levels for cube face '{}'", name)

                # If we're compressing this mofo, we'll need a temporary mipmap to do that here...
                mipmap = plMipmap(name=name, width=eWidth, height=eHeight, numLevels=numLevels,
                                  compType=compression, format=plBitmap.kRGB8888, dxtLevel=dxt)
            else:
                numLevels = 1
                self._report.msg("Compressing single level for cube face '{}'", name)

            face_images[i] = [None] * numLevels
            for j in range(numLevels):
                level_data = glimage.get_level_data(j, key.calc_alpha, report=self._report)
                if compression == plBitmap.kDirectXCompression:
                    mipmap.CompressImage(j, level_data)
                    level_data = mipmap.getLevel(j)
                face_images[i][j] = level_data
        return numLevels, eWidth, eHeight, face_images

    def _finalize_single_image(self, key, image, name, compression, dxt):
        oWidth, oHeight = image.size
        if oWidth == 0 and oHeight == 0:
            raise ExportError("Image '{}' could not be loaded.".format(image.name))

        # Non-DXT images are BGRA in Plasma
        bgra = compression != plBitmap.kDirectXCompression

        # Grab the image data from OpenGL and stuff it into the plBitmap
        with GLTexture(key, bgra=bgra) as glimage:
            eWidth, eHeight = glimage.size_pot
            if compression == plBitmap.kDirectXCompression:
                numLevels = glimage.num_levels
                self._report.msg("Generating mip levels")

                # If this is a DXT-compressed mipmap, we need to use a temporary mipmap
                # to do the compression. We'll then steal the data from it.
                mipmap = plMipmap(name=name, width=eWidth, height=eHeight, numLevels=numLevels,
                                  compType=compression, format=plBitmap.kRGB8888, dxtLevel=dxt)
            else:
                numLevels = 1
                self._report.msg("Compressing single level")

            # Hold the uncompressed level data for now. We may have to make multiple copies of
            # this mipmap for per-page textures :(
            data = [None] * numLevels
            for i in range(numLevels):
                level_data = glimage.get_level_data(i, key.calc_alpha, report=self._report)
                if compression == plBitmap.kDirectXCompression:
                    mipmap.CompressImage(i, level_data)
                    level_data = mipmap.getLevel(i)
                data[i] = level_data
        return numLevels, eWidth, eHeight, [data,]

    def get_materials(self, bo: bpy.types.Object, bm: Optional[bpy.types.Material] = None) -> Iterator[plKey]:
        material_dict = self._obj2mat.get(bo, {})
        if bm is None:
            return material_dict.values()
        else:
            return material_dict.get(bm, [])

    def get_layers(self, bo: Optional[bpy.types.Object] = None,
                   bm: Optional[bpy.types.Material] = None,
                   tex: Optional[bpy.types.Texture] = None) -> Iterator[plKey]:

        # All three? Simple.
        if bo is not None and bm is not None and tex is not None:
            yield from filter(None, self._obj2layer[bo][bm][tex])
            return
        if bo is None and bm is None and tex is None:
            self._exporter().report.warn("Asking for all the layers we've ever exported, eh? You like living dangerously.")

        # What we want to do is filter _obj2layers:
        # bo if set, or all objects
        # bm if set, or tex.users_materials if set, or all materials... ON THE OBJECT(s)
        # tex if set, or all layers... ON THE OBJECT(s) MATERIAL(s)
        object_iter = lambda: (bo,) if bo is not None else self._obj2layer.keys()
        if bm is not None:
            material_seq = (bm,)
        elif tex is not None:
            material_seq = tex.users_material
        else:
            _iter = filter(lambda x: x and x.material, itertools.chain.from_iterable((i.material_slots for i in object_iter())))
            # Performance turd: this could, in the worst case, block on creating a list of every material
            # attached to every single Plasma Object in the current scene. This whole algorithm sucks,
            # though, so whatever.
            material_seq = [slot.material for slot in _iter]

        for filtered_obj in object_iter():
            for filtered_mat in material_seq:
                all_texes = self._obj2layer[filtered_obj][filtered_mat]
                filtered_texes = all_texes[tex] if tex is not None else itertools.chain.from_iterable(all_texes.values())
                yield from filter(None, filtered_texes)

    def get_base_layer(self, hsgmat):
        try:
            layer = hsgmat.layers[0].object
        except IndexError:
            return None
        else:
            return layer.bottomOfStack.object

    def get_bump_layer(self, bo):
        return self._bump_mats.get(bo, None)

    def get_material_ambient(self, bo, bm, tex_slot, color: Union[None, mathutils.Color] = None) -> hsColorRGBA:
        if self._is_emissive(bm, tex_slot):
            # Although Plasma calls this the ambient color, it is actually always used as the emissive color.
            emit_scale = bm.emit * 0.5
            if color is None:
                color = bm.diffuse_color
            return hsColorRGBA(color.r * emit_scale,
                               color.g * emit_scale,
                               color.b * emit_scale,
                               1.0)
        else:
            return utils.color(bpy.context.scene.world.ambient_color)

    def get_material_preshade(self, bo, bm, tex_slot, color: Union[None, mathutils.Color] = None) -> hsColorRGBA:
        # This color is always used for shading. In all lighting equations, it represents the world
        # ambient color. Anyway, if we have a manual (read: animated color), just dump that out.
        if color is not None:
            return utils.color(color)

        # Runtime lit objects want light from runtime lights, so they have an ambient world color
        # of black - and yes, this is an ambient world color. But it gets more fascinating...
        # The color has been folded into the vertex colors for nonpreshaded, so for nonpreshaded,
        # we'll want black if it's ONLY runtime lighting (and white for lightmaps). Otherwise,
        # just use the material color for now.
        if self._exporter().mesh.is_nonpreshaded(bo, bm):
            if bo.plasma_modifiers.lightmap.bake_lightmap and not bo.plasma_modifiers.lighting.rt_lights:
                return hsColorRGBA.kWhite
            elif not bo.plasma_modifiers.lighting.preshade:
                return hsColorRGBA.kBlack

        # Gulp
        return utils.color(bm.diffuse_color)

    def get_material_runtime(self, bo, bm, tex_slot, color: Union[None, mathutils.Color] = None) -> hsColorRGBA:
        # The layer runstime color has no effect if the lighting equation is kLiteVtxNonPreshaded,
        # so return black to prevent animations from being exported.
        if self._exporter().mesh.is_nonpreshaded(bo, bm):
            return hsColorRGBA.kBlack

        # Hmm...
        if color is None:
            color = bm.diffuse_color
        return utils.color(color)

    def get_texture_animation_key(self, bo, bm, texture, anim_name: str) -> Iterator[plKey]:
        """Finds the appropriate key for sending messages to an animated Texture"""
        if not anim_name:
            anim_name = "(Entire Animation)"

        for top_layer in filter(lambda x: isinstance(x.object, plLayerAnimationBase), self.get_layers(bo, bm, texture)):
            base_layer = top_layer.object.bottomOfStack
            needle = top_layer
            while needle is not None:
                if needle.name == "{}_{}".format(base_layer.name, anim_name):
                    yield needle
                    break
                needle = needle.object.underLay

    def _handle_layer_opacity(self, layer: plLayerInterface, value: float):
        if value < 100:
            base_layer = layer.bottomOfStack.object
            state = base_layer.state
            if not state.blendFlags & hsGMatState.kBlendMask:
                state.blendFlags |= hsGMatState.kBlendAlpha

    def _is_emissive(self, bm, tex_slot=None):
        # Backwards compatibility... Check all the textures to see if any of them have set use_map_emit.
        # If not and bm.emit > 0, then all textures are emissive. Otherwise, only the textures
        # that set use_map_emit are emissive.
        if bm is None:
            return False
        if tex_slot is None:
            return bm.emit > 0.0
        else:
            return bm.emit > 0.0 and (tex_slot.use_map_emit or not any((i.use_map_emit for i in bm.texture_slots if i)))

    @property
    def _mgr(self):
        return self._exporter().mgr

    def _propagate_material_settings(self, bo, bm, tex_slot, layer):
        """Converts settings from the Blender Material to corresponding plLayer settings"""
        state = layer.state

        is_waveset = bo.plasma_modifiers.water_basic.enabled
        if bo.data.show_double_sided:
            if is_waveset:
                self._report.warn("FORCING single sided--this is a waveset (are you insane?)")
            else:
                state.miscFlags |= hsGMatState.kMiscTwoSided

        # Shade Flags
        if not bm.use_mist:
            state.shadeFlags |= hsGMatState.kShadeNoFog # Dead in CWE
            state.shadeFlags |= hsGMatState.kShadeReallyNoFog

        if bm.use_shadeless:
            state.shadeFlags |= hsGMatState.kShadeWhite

        # Colors
        layer.ambient = self.get_material_ambient(bo, bm, tex_slot)
        layer.preshade = self.get_material_preshade(bo, bm, tex_slot)
        layer.runtime = self.get_material_runtime(bo, bm, tex_slot)
        layer.specular = utils.color(bm.specular_color)

        layer.specularPower = min(100.0, float(bm.specular_hardness))
        layer.LODBias = -1.0

    def requires_material_shading(self, bm: bpy.types.Material) -> bool:
        """Determines if this material requires the lighting equation we all know and love
           (kLiteMaterial) in order to display opacity and color animations."""
        if bm.animation_data is not None and bm.animation_data.action is not None:
            if any((i.data_path == "diffuse_color" for i in bm.animation_data.action.fcurves)):
                return True

        for slot in filter(lambda x: x and x.use and x.texture, bm.texture_slots):
            tex = slot.texture

            # TODO (someday): I think PlasmaMax will actually bake some opacities into the vertices
            # so that kLiteVtxNonPreshaded can be used. Might be a good idea at some point.
            if tex.plasma_layer.opacity < 100:
                return True

            if tex.animation_data is not None and tex.animation_data.action is not None:
                if any((i.data_path == "plasma_layer.opacity" for i in tex.animation_data.action.fcurves)):
                    return True
        return False

    def _requires_single_user(self, bo, bm):
        if bo.data.show_double_sided:
            return True
        return any((i.copy_material for i in bo.plasma_modifiers.modifiers))

    @property
    def _report(self):
        return self._exporter().report

    def _test_image_alpha(self, image):
        """Tests to see if this image has any alpha data"""

        # In the interest of speed, let's see if we've already done this one...
        result = self._alphatest.get(image, None)
        if result is not None:
            return result

        if image.channels != 4 or not image.use_alpha:
            result = TextureAlpha.opaque
        else:
            # Using bpy.types.Image.pixels is VERY VERY VERY slow...
            key = _Texture(image=image)
            with GLTexture(key, fast=True) as glimage:
                result = glimage.has_alpha

        self._alphatest[image] = result
        return result

    @property
    def _texcache(self):
        return self._exporter().image
