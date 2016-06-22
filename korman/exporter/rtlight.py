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
from PyHSPlasma import *
import weakref

from .explosions import *
from . import utils

_BL2PL = {
    "POINT": plOmniLightInfo,
    "SPOT": plSpotLightInfo,
    "SUN": plDirectionalLightInfo,
}

_FAR_POWER = 15.0

class LightConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self._converter_funcs = {
            "POINT": self._convert_point_lamp,
            "SPOT": self._convert_spot_lamp,
            "SUN": self._convert_sun_lamp,
        }

    def _convert_attenuation(self, bl, pl):
        intens = bl.energy
        if intens < 0:
            intens = -intens
        attenEnd = bl.distance * 2 if bl.use_sphere else bl.distance

        if bl.falloff_type == "CONSTANT":
            print("        Attenuation: No Falloff")
            pl.attenConst = intens
            pl.attenLinear = 0.0
            pl.attenQuadratic = 0.0
            pl.attenCutoff = attenEnd
        elif bl.falloff_type == "INVERSE_LINEAR":
            print("        Attenuation: Inverse Linear")
            pl.attenConst = 1.0
            pl.attenLinear = max(0.0, (intens * _FAR_POWER - 1.0) / attenEnd)
            pl.attenQuadratic = 0.0
            pl.attenCutoff = attenEnd
        elif bl.falloff_type == "INVERSE_SQUARE":
            print("        Attenuation: Inverse Square")
            pl.attenConst = 1.0
            pl.attenLinear = 0.0
            pl.attenQuadratic = max(0.0, (intens * _FAR_POWER - 1.0) / (attenEnd * attenEnd))
            pl.attenCutoff = attenEnd
        else:
            raise BlenderOptionNotSupportedError(bl.falloff_type)


    def _convert_point_lamp(self, bl, pl):
        print("    [OmniLightInfo '{}']".format(bl.name))
        self._convert_attenuation(bl, pl)

    def _convert_spot_lamp(self, bl, pl):
        print("    [SpotLightInfo '{}']".format(bl.name))
        self._convert_attenuation(bl, pl)

        # Spot lights have a few more things...
        spot_size = bl.spot_size
        pl.spotOuter = spot_size

        blend = max(0.001, bl.spot_blend)
        pl.spotInner = spot_size - (blend*spot_size)

        if bl.use_halo:
            pl.falloff = bl.halo_intensity
        else:
            pl.falloff = 1.0

    def _convert_sun_lamp(self, bl, pl):
        print("    [DirectionalLightInfo '{}']".format(bl.name))

    def export_rtlight(self, so, bo):
        bl_light = bo.data

        # The specifics be here...
        pl_light = self.get_light_key(bo, bl_light, so).object
        self._converter_funcs[bl_light.type](bl_light, pl_light)

        # Light color nonsense
        energy = bl_light.energy
        if bl_light.use_negative:
            diff_color = [(0.0 - i) * energy for i in bl_light.color]
            spec_color = [(0.0 - i) for i in bl_light.color]
        else:
            diff_color = [i * energy for i in bl_light.color]
            spec_color = [i for i in bl_light.color]

        diff_str = "({:.4f}, {:.4f}, {:.4f})".format(*diff_color)
        diff_color.append(energy)

        spec_str = "({:.4f}, {:.4f}, {:.4f})".format(*spec_color)
        spec_color.append(energy)

        # Do we *only* want a shadow?
        shadow_only = bl_light.shadow_method != "NOSHADOW" and bl_light.use_only_shadow

        # Apply the colors
        if bl_light.use_diffuse and not shadow_only:
            print("        Diffuse: {}".format(diff_str))
            pl_light.diffuse = hsColorRGBA(*diff_color)
        else:
            print("        Diffuse: OFF")
            pl_light.diffuse = hsColorRGBA(0.0, 0.0, 0.0, energy)

        if bl_light.use_specular and not shadow_only:
            print("        Specular: {}".format(spec_str))
            pl_light.setProperty(plLightInfo.kLPHasSpecular, True)
            pl_light.specular = hsColorRGBA(*spec_color)
        else:
            print("        Specular: OFF")
            pl_light.specular = hsColorRGBA(0.0, 0.0, 0.0, energy)

        # Crazy flags
        rtlamp = bl_light.plasma_lamp
        if rtlamp.light_group:
            pl_light.setProperty(plLightInfo.kLPHasIncludes, True)
            pl_light.setProperty(plLightInfo.kLPIncludesChars, rtlamp.affect_characters)
        if rtlamp.cast_shadows:
            pl_light.setProperty(plLightInfo.kLPShadowLightGroup, True)
            pl_light.setProperty(plLightInfo.kLPShadowOnly, shadow_only)

        # AFAICT ambient lighting is never set in PlasmaMax...
        # If you can think of a compelling reason to support it, be my guest.
        pl_light.ambient = hsColorRGBA(0.0, 0.0, 0.0, 1.0)

        # Now, let's apply the matrices...
        # Science indicates that Plasma RT Lights should *always* have mats, even if there is a CI
        l2w = utils.matrix44(bo.matrix_local)
        pl_light.lightToWorld = l2w
        pl_light.worldToLight = l2w.inverse()

        # Soft Volume science
        sv_mod, sv_key = bo.plasma_modifiers.softvolume, None
        if sv_mod.enabled:
            sv_key = sv_mod.get_key(self._exporter())
        elif rtlamp.soft_region:
            sv_bo = bpy.data.objects.get(rtlamp.soft_region, None)
            if sv_bo is None:
                raise ExportError("'{}': Invalid object for Lamp soft volume '{}'".format(bo.name, rtlamp.soft_region))
            sv_mod = sv_bo.plasma_modifiers.softvolume
            if not sv_mod.enabled:
                raise ExportError("'{}': '{}' is not a SoftVolume".format(bo.name, rtlamp.soft_region))
            sv_key = sv_mod.get_key(self._exporter())
        pl_light.softVolume = sv_key

        # Is this a projector?
        projectors = tuple(self.get_projectors(bl_light))
        if projectors:
            self._export_rt_projector(bo, pl_light, projectors)

        # *Sigh*
        pl_light.sceneNode = self.mgr.get_scene_node(location=so.key.location)

    def _export_rt_projector(self, bo, pl_light, tex_slots):
        mat = self._exporter().mesh.material
        slot = tex_slots[0]

        # There is a Material available in the caller, but that is for the parent Mesh. We are a
        # projection Lamp with our own faux Material. Unfortunately, Plasma only supports projecting
        # one layer. We could exploit the fUnderLay and fOverLay system to export everything, but meh.
        if len(tex_slots) > 1:
            self._exporter().warn("Only one texture slot can be exported per Lamp. Picking the first one: '{}'".format(slot.name), indent=3)
        layer = mat.export_texture_slot(bo, None, None, tex_slots, 0, blend_flags=False)
        state = layer.state

        # Colors science'd from PRPs
        layer.preshade = hsColorRGBA(0.5, 0.5, 0.5)
        layer.runtime = hsColorRGBA(0.5, 0.5, 0.5)

        # Props for projectors...
        # Note that we tell the material exporter to (try not to) do any blend flags for us
        layer.UVWSrc |= plLayer.kUVWPosition
        if bo.data.type == "SPOT":
            state.miscFlags |= hsGMatState.kMiscPerspProjection
        else:
            state.miscFlags |= hsGMatState.kMiscOrthoProjection
        state.ZFlags |= hsGMatState.kZNoZWrite
        pl_light.setProperty(plLightInfo.kLPMovable, True)
        pl_light.setProperty(plLightInfo.kLPCastShadows, False)

        if slot.blend_type == "ADD":
            state.blendFlags |= hsGMatState.kBlendAdd
            pl_light.setProperty(plLightInfo.kLPOverAll, True)
        elif slot.blend_type == "MULTIPLY":
            # From PlasmaMAX
            state.blendFlags |= hsGMatState.kBlendMult | hsGMatState.kBlendInvertColor | hsGMatState.kBlendInvertFinalColor
            pl_light.setProperty(plLightInfo.kLPOverAll, True)

        pl_light.projection = layer.key

    def find_material_light_keys(self, bo, bm):
        """Given a blender material, we find the keys of all matching Plasma RT Lights.
           NOTE: We return a tuple of lists: ([permaLights], [permaProjs])"""
        print("    Searching for runtime lights...")
        permaLights = []
        permaProjs = []

        # We're going to inspect the material's light group.
        # If there is no light group, we'll say that there is no runtime lighting...
        # If there is, we will harvest all Blender lamps in that light group that are Plasma Objects
        lg = bm.light_group
        if lg is not None:
            for obj in lg.objects:
                if obj.type != "LAMP":
                    # moronic...
                    continue
                elif not obj.plasma_object.enabled:
                    # who cares?
                    continue
                lamp = obj.data

                # Check to see if they only want this light to work on its layer...
                if lamp.use_own_layer:
                    # Pairs up elements from both layers sequences such that we can compare
                    # to see if the lamp and object are in the same layer.
                    # If you can think of a better way, be my guest.
                    test = zip(bo.layers, obj.layers)
                    for i in test:
                        if i == (True, True):
                            break
                    else:
                        # didn't find a layer where both lamp and object were, skip it.
                        print("        [{}] '{}': not in same layer, skipping...".format(lamp.type, obj.name))
                        continue

                # This is probably where PermaLight vs PermaProj should be sorted out...
                pl_light = self.get_light_key(obj, lamp, None)
                if self._is_projection_lamp(lamp):
                    print("        [{}] PermaProj '{}'".format(lamp.type, obj.name))
                    permaProjs.append(pl_light)
                else:
                    print("        [{}] PermaLight '{}'".format(lamp.type, obj.name))
                    permaLights.append(pl_light)

        return (permaLights, permaProjs)

    def get_light_key(self, bo, bl_light, so):
        try:
            xlate = _BL2PL[bl_light.type]
            return self.mgr.find_create_key(xlate, bl=bo, so=so)
        except LookupError:
            raise BlenderOptionNotSupportedError("Object ('{}') lamp type '{}'".format(bo.name, bl_light.type))

    def get_projectors(self, bl_light):
        for tex in bl_light.texture_slots:
            if tex is not None and tex.texture is not None:
                yield tex

    def _is_projection_lamp(self, bl_light):
        for tex in bl_light.texture_slots:
            if tex is None or tex.texture is None:
                continue
            return True
        return False

    @property
    def mgr(self):
        return self._exporter().mgr
