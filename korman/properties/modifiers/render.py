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
from bpy.props import *
from PyHSPlasma import *

from .base import PlasmaModifierProperties
from ...exporter.etlight import _NUM_RENDER_LAYERS
from ...exporter import utils
from ...exporter.explosions import ExportError
from ... import idprops


class PlasmaFadeMod(PlasmaModifierProperties):
    pl_id = "fademod"

    bl_category = "Render"
    bl_label = "Opacity Fader"
    bl_description = "Fades an object based on distance or line-of-sight"

    fader_type = EnumProperty(name="Fader Type",
                              description="Type of opacity fade",
                              items=[("DistOpacity", "Distance", "Fade based on distance to object"),
                                     ("FadeOpacity", "Line-of-Sight", "Fade based on line-of-sight to object"),
                                     ("SimpleDist",  "Simple Distance", "Fade for use as Great Zero Markers")],
                              default="SimpleDist")

    fade_in_time = FloatProperty(name="Fade In Time",
                                 description="Number of seconds before the object is fully visible",
                                 min=0.0, max=5.0, default=0.5, subtype="TIME", unit="TIME")
    fade_out_time = FloatProperty(name="Fade Out Time",
                                  description="Number of seconds before the object is fully invisible",
                                  min=0.0, max=5.0, default=0.5, subtype="TIME", unit="TIME")
    bounds_center = BoolProperty(name="Use Mesh Midpoint",
                                 description="Use mesh's midpoint to calculate LOS instead of object origin",
                                 default=False)

    near_trans = FloatProperty(name="Near Transparent",
                               description="Nearest distance at which the object is fully transparent",
                               min=0.0, default=0.0, subtype="DISTANCE", unit="LENGTH")
    near_opaq = FloatProperty(name="Near Opaque",
                              description="Nearest distance at which the object is fully opaque",
                              min=0.0, default=0.0, subtype="DISTANCE", unit="LENGTH")
    far_opaq = FloatProperty(name="Far Opaque",
                             description="Farthest distance at which the object is fully opaque",
                             min=0.0, default=15.0, subtype="DISTANCE", unit="LENGTH")
    far_trans = FloatProperty(name="Far Transparent",
                              description="Farthest distance at which the object is fully transparent",
                              min=0.0, default=20.0, subtype="DISTANCE", unit="LENGTH")

    def export(self, exporter, bo, so):
        if self.fader_type == "DistOpacity":
            mod = exporter.mgr.find_create_object(plDistOpacityMod, so=so, name=self.key_name)
            mod.nearTrans = self.near_trans
            mod.nearOpaq = self.near_opaq
            mod.farOpaq = self.far_opaq
            mod.farTrans = self.far_trans
        elif self.fader_type == "FadeOpacity":
            mod = exporter.mgr.find_create_object(plFadeOpacityMod, so=so, name=self.key_name)
            mod.fadeUp = self.fade_in_time
            mod.fadeDown = self.fade_out_time
            mod.boundsCenter = self.bounds_center
        elif self.fader_type == "SimpleDist":
            mod = exporter.mgr.find_create_object(plDistOpacityMod, so=so, name=self.key_name)
            mod.nearTrans = 0.0
            mod.nearOpaq = 0.0
            mod.farOpaq = self.far_opaq
            mod.farTrans = self.far_trans


fog_types = {
    "none":     plFogEnvironment.kNoFog,
    "linear":   plFogEnvironment.kLinearFog,
    "exp2":     plFogEnvironment.kExp2Fog
}

class PlasmaFogEnvMod(PlasmaModifierProperties):
    pl_id = "fogenv"

    bl_category = "Render"
    bl_label = "Fog Environment"
    bl_description = "Adjust per-object fog settings"
    bl_icon = "MAT_SPHERE_SKY"

    environment = PointerProperty(name="Environment",
                                  description="Environment defining the fog settings for this object",
                                  type=bpy.types.World)

    def export(self, exporter, bo, so):
        if self.environment is None or self.environment == bpy.context.scene.world:
            # Don't generate a FogEnv for the default Age FNI fog
            return

        fe = exporter.mgr.find_create_object(plFogEnvironment, bl=bo, name=self.environment.name)
        env = self.environment.plasma_fni

        fe.type = fog_types[env.fog_method]
        fe.color = hsColorRGBA(env.fog_color.r, env.fog_color.g, env.fog_color.b, 1.0)
        fe.start = env.fog_start
        fe.end = env.fog_end
        fe.density = env.fog_density


class PlasmaFollowMod(idprops.IDPropObjectMixin, PlasmaModifierProperties):
    pl_id = "followmod"

    bl_category = "Render"
    bl_label = "Follow"
    bl_description = "Follow the movement of the camera, player, or another object"

    follow_mode = EnumProperty(name="Mode",
                               description="Leader's movement to follow",
                               items=[
                                      ("kPositionX", "X Axis", "Follow the leader's X movements"),
                                      ("kPositionY", "Y Axis", "Follow the leader's Y movements"),
                                      ("kPositionZ", "Z Axis", "Follow the leader's Z movements"),
                                      ("kRotate", "Rotation", "Follow the leader's rotation movements"),
                                ],
                               default={"kPositionX", "kPositionY", "kPositionZ"},
                               options={"ENUM_FLAG"})

    leader_type = EnumProperty(name="Leader Type",
                               description="Leader to follow",
                               items=[
                                      ("kFollowCamera", "Camera", "Follow the camera"),
                                      ("kFollowListener", "Listener", "Follow listeners"),
                                      ("kFollowPlayer", "Player", "Follow the local player"),
                                      ("kFollowObject", "Object", "Follow an object"),
                                ])

    leader = PointerProperty(name="Leader Object",
                             description="Object to follow",
                             type=bpy.types.Object)

    def export(self, exporter, bo, so):
        fm = exporter.mgr.find_create_object(plFollowMod, so=so, name=self.key_name)

        fm.mode = 0
        for flag in (getattr(plFollowMod, mode) for mode in self.follow_mode):
            fm.mode |= flag

        fm.leaderType = getattr(plFollowMod, self.leader_type)
        if self.leader_type == "kFollowObject":
            # If this object is following another object, make sure that the
            # leader has been selected and is a valid SO.
            if self.leader:
                fm.leader = exporter.mgr.find_create_key(plSceneObject, bl=self.leader)
            else:
                raise ExportError("'{}': Follow's leader object must be selected".format(self.key_name))

    @classmethod
    def _idprop_mapping(cls):
        return {"leader": "leader_object"}

    @property
    def requires_actor(self):
        return True


class PlasmaLightMapGen(idprops.IDPropMixin, PlasmaModifierProperties):
    pl_id = "lightmap"

    bl_category = "Render"
    bl_label = "Lightmap"
    bl_description = "Auto-Bake Lightmap"

    quality = EnumProperty(name="Quality",
                           description="Resolution of lightmap",
                           items=[
                                  ("128", "128px", "128x128 pixels"),
                                  ("256", "256px", "256x256 pixels"),
                                  ("512", "512px", "512x512 pixels"),
                                  ("1024", "1024px", "1024x1024 pixels"),
                            ])

    render_layers = BoolVectorProperty(name="Layers",
                                       description="Render layers to use for baking",
                                       options=set(),
                                       subtype="LAYER",
                                       size=_NUM_RENDER_LAYERS,
                                       default=((True,) * _NUM_RENDER_LAYERS))

    lights = PointerProperty(name="Light Group",
                             description="Group that defines the collection of lights to bake",
                             type=bpy.types.Group)

    uv_map = StringProperty(name="UV Texture",
                            description="UV Texture used as the basis for the lightmap")

    def export(self, exporter, bo, so):
        lightmap_im = bpy.data.images.get("{}_LIGHTMAPGEN.png".format(bo.name))

        # If no lightmap image is found, then either lightmap generation failed (error raised by oven)
        # or baking is turned off. Either way, bail out.
        if lightmap_im is None:
            return
        mat_mgr = exporter.mesh.material
        materials = mat_mgr.get_materials(bo)

        # Find the stupid UVTex
        uvw_src = 0
        for i, uvtex in enumerate(bo.data.tessface_uv_textures):
            if uvtex.name == "LIGHTMAPGEN":
                uvw_src = i
                break
        else:
            # TODO: raise exception
            pass

        for matKey in materials:
            layer = exporter.mgr.add_object(plLayer, name="{}_LIGHTMAPGEN".format(matKey.name), so=so)
            layer.UVWSrc = uvw_src

            # Colors science'd from PRPs
            layer.ambient = hsColorRGBA(1.0, 1.0, 1.0)
            layer.preshade = hsColorRGBA(0.5, 0.5, 0.5)
            layer.runtime = hsColorRGBA(0.5, 0.5, 0.5)

            # GMatState
            gstate = layer.state
            gstate.blendFlags |= hsGMatState.kBlendMult
            gstate.clampFlags |= (hsGMatState.kClampTextureU | hsGMatState.kClampTextureV)
            gstate.ZFlags |= hsGMatState.kZNoZWrite
            gstate.miscFlags |= hsGMatState.kMiscLightMap

            mat = matKey.object
            mat.compFlags |= hsGMaterial.kCompIsLightMapped
            mat.addPiggyBack(layer.key)

            # Mmm... cheating
            mat_mgr.export_prepared_layer(layer, lightmap_im)

    @classmethod
    def _idprop_mapping(cls):
        return {"lights": "light_group"}

    def _idprop_sources(self):
        return {"light_group": bpy.data.groups}

    @property
    def key_name(self):
        return "{}_LIGHTMAPGEN".format(self.id_data.name)

    @property
    def resolution(self):
        return int(self.quality)


class PlasmaLightingMod(PlasmaModifierProperties):
    pl_id = "lighting"

    bl_category = "Render"
    bl_label = "Lighting"
    bl_description = "Fine tune Plasma lighting settings"

    force_rt_lights = BoolProperty(name="Force RT Lighting",
                                   description="Unleashes satan by forcing the engine to dynamically light this object",
                                   default=False,
                                   options=set())
    force_preshade = BoolProperty(name="Force Vertex Shading",
                                  description="Ensures vertex lights are baked, even if illogical",
                                  default=False,
                                  options=set())

    @property
    def allow_preshade(self):
        bo = self.id_data
        if bo.plasma_modifiers.water_basic.enabled:
            return False
        if bo.plasma_modifiers.lightmap.enabled:
            return False
        return True

    def export(self, exporter, bo, so):
        # Exposes no new keyed objects, mostly a hint to the ET light code
        pass

    @property
    def preshade(self):
        bo = self.id_data
        if self.allow_preshade:
            if self.force_preshade:
                return True
            # RT lights means no preshading unless requested
            if self.rt_lights:
                return False
            if not bo.plasma_object.has_transform_animation:
                return True
        return False

    @property
    def rt_lights(self):
        """Are RT lights forcibly enabled or do we otherwise want them?"""
        return (self.enabled and self.force_rt_lights) or self.want_rt_lights

    @property
    def want_rt_lights(self):
        """Gets whether or not this object ought to be lit dynamically"""
        bo = self.id_data
        if bo.plasma_modifiers.lightmap.enabled:
            return False
        if bo.plasma_modifiers.water_basic.enabled:
            return True
        if bo.plasma_object.has_transform_animation:
            return True
        return False


class PlasmaShadowCasterMod(PlasmaModifierProperties):
    pl_id = "rtshadow"

    bl_category = "Render"
    bl_label = "Cast RT Shadow"
    bl_description = "Cast runtime shadows"

    blur = IntProperty(name="Blur",
                       description="Blur factor for the shadow map",
                       min=0, max=100, default=0,
                       subtype="PERCENTAGE", options=set())
    boost = IntProperty(name="Boost",
                        description="Multiplies the shadow's power",
                        min=0, max=5000, default=100,
                        subtype="PERCENTAGE", options=set())
    falloff = IntProperty(name="Falloff",
                          description="Multiplier for each lamp's falloff value",
                          min=10, max=1000, default=100,
                          subtype="PERCENTAGE", options=set())

    limit_resolution = BoolProperty(name="Limit Resolution",
                                    description="Increase performance by halving the resolution of the shadow map",
                                    default=False,
                                    options=set())
    self_shadow = BoolProperty(name="Self Shadow",
                               description="Object can cast shadows on itself",
                               default=False,
                               options=set())

    def export(self, exporter, bo, so):
        caster = exporter.mgr.find_create_object(plShadowCaster, so=so, name=self.key_name)
        caster.attenScale = self.falloff / 100.0
        caster.blurScale = self.blur / 100.0
        caster.boost = self.boost / 100.0
        if self.limit_resolution:
            caster.castFlags |= plShadowCaster.kLimitRes
        if self.self_shadow:
            caster.castFlags |= plShadowCaster.kSelfShadow


class PlasmaViewFaceMod(idprops.IDPropObjectMixin, PlasmaModifierProperties):
    pl_id = "viewfacemod"

    bl_category = "Render"
    bl_label = "Swivel"
    bl_description = "Swivel object to face the camera, player, or another object"

    preset_options = EnumProperty(name="Type",
                                  description="Type of Facing",
                                  items=[
                                         ("Billboard", "Billboard", "Face the camera (Y Axis only)"),
                                         ("Sprite", "Sprite", "Face the camera (All Axis)"),
                                         ("Custom", "Custom", "Custom Swivel"),
                                   ])

    follow_mode = EnumProperty(name="Target Type",
                               description="Target of the swivel",
                               items=[
                                      ("kFaceCam", "Camera", "Face the camera"),
                                      ("kFaceList", "Listener", "Face listeners"),
                                      ("kFacePlay", "Player", "Face the local player"),
                                      ("kFaceObj", "Object", "Face an object"),
                                ])
    target = PointerProperty(name="Target Object",
                             description="Object to face",
                             type=bpy.types.Object)

    pivot_on_y = BoolProperty(name="Pivot on local Y",
                              description="Swivel only around the local Y axis",
                              default=False)

    offset = BoolProperty(name="Offset", description="Use offset vector", default=False)
    offset_local = BoolProperty(name="Local", description="Use local coordinates", default=False)
    offset_coord = FloatVectorProperty(name="", subtype="XYZ")

    def export(self, exporter, bo, so):
        vfm = exporter.mgr.find_create_object(plViewFaceModifier, so=so, name=self.key_name)

        # Set a default scaling (libHSPlasma will set this to 0 otherwise).
        vfm.scale = hsVector3(1,1,1)
        l2p = utils.matrix44(bo.matrix_local)
        vfm.localToParent = l2p
        vfm.parentToLocal = l2p.inverse()

        # Cyan has these as separate components, but they're really just preset
        # options for common swivels.  We've consolidated them both here, along
        # with the fully-customizable swivel as a third option.
        if self.preset_options == "Billboard":
            vfm.setFlag(plViewFaceModifier.kFaceCam, True)
            vfm.setFlag(plViewFaceModifier.kPivotY, True)
        elif self.preset_options == "Sprite":
            vfm.setFlag(plViewFaceModifier.kFaceCam, True)
            vfm.setFlag(plViewFaceModifier.kPivotFace, True)
        elif self.preset_options == "Custom":
            # For the discerning artist, full control over their swivel options!
            vfm.setFlag(getattr(plViewFaceModifier, self.follow_mode), True)

            if self.follow_mode == "kFaceObj":
                # If this swivel is following an object, make sure that the
                # target has been selected and is a valid SO.
                if self.target:
                    vfm.faceObj = exporter.mgr.find_create_key(plSceneObject, bl=self.target)
                else:
                    raise ExportError("'{}': Swivel's target object must be selected".format(self.key_name))

            if self.pivot_on_y:
                vfm.setFlag(plViewFaceModifier.kPivotY, True)
            else:
                vfm.setFlag(plViewFaceModifier.kPivotFace, True)

            if self.offset:
                vfm.offset = hsVector3(*self.offset_coord)
                if self.offset_local:
                    vfm.setFlag(plViewFaceModifier.kOffsetLocal, True)

    @classmethod
    def _idprop_mapping(cls):
        return {"target": "target_object"}

    @property
    def requires_actor(self):
        return True


class PlasmaVisControl(idprops.IDPropObjectMixin, PlasmaModifierProperties):
    pl_id = "visregion"

    bl_category = "Render"
    bl_label = "Visibility Control"
    bl_description = "Controls object visibility using VisRegions"

    mode = EnumProperty(name="Mode",
                        description="Purpose of the VisRegion",
                        items=[("normal", "Normal", "Objects are only visible when the camera is inside this region"),
                               ("exclude", "Exclude", "Objects are only visible when the camera is outside this region"),
                               ("fx", "Special FX", "This is a list of objects used for special effects only")])
    soft_region = PointerProperty(name="Region",
                                  description="Object defining the SoftVolume for this VisRegion",
                                  type=bpy.types.Object,
                                  poll=idprops.poll_softvolume_objects)
    replace_normal = BoolProperty(name="Hide Drawables",
                                  description="Hides drawables attached to this region",
                                  default=True)

    def export(self, exporter, bo, so):
        rgn = exporter.mgr.find_create_object(plVisRegion, bl=bo, so=so)
        rgn.setProperty(plVisRegion.kReplaceNormal, self.replace_normal)

        if self.mode == "fx":
            rgn.setProperty(plVisRegion.kDisable, True)
        else:
            this_sv = bo.plasma_modifiers.softvolume
            if this_sv.enabled:
                exporter.report.msg("[VisRegion] I'm a SoftVolume myself :)", indent=1)
                rgn.region = this_sv.get_key(exporter, so)
            else:
                if not self.soft_region:
                    raise ExportError("'{}': Visibility Control must have a Soft Volume selected".format(self.key_name))
                sv_bo = self.soft_region
                sv = sv_bo.plasma_modifiers.softvolume
                exporter.report.msg("[VisRegion] SoftVolume '{}'", sv_bo.name, indent=1)
                if not sv.enabled:
                    raise ExportError("'{}': '{}' is not a SoftVolume".format(self.key_name, sv_bo.name))
                rgn.region = sv.get_key(exporter)
            rgn.setProperty(plVisRegion.kIsNot, self.mode == "exclude")

    @classmethod
    def _idprop_mapping(cls):
        return {"soft_region": "softvolume"}


class VisRegion(idprops.IDPropObjectMixin, bpy.types.PropertyGroup):
    enabled = BoolProperty(default=True)
    control_region = PointerProperty(name="Control",
                                     description="Object defining a Plasma Visibility Control",
                                     type=bpy.types.Object,
                                     poll=idprops.poll_visregion_objects)

    @classmethod
    def _idprop_mapping(cls):
        return {"control_region": "region_name"}


class PlasmaVisibilitySet(PlasmaModifierProperties):
    pl_id = "visibility"

    bl_category = "Render"
    bl_label = "Visibility Set"
    bl_description = "Defines areas where this object is visible"

    regions = CollectionProperty(name="Visibility Regions",
                                 type=VisRegion)
    active_region_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        if not self.regions:
            # TODO: Log message about how this modifier is totally worthless
            return

        # Currently, this modifier is valid for meshes and lamps
        if bo.type == "MESH":
            diface = exporter.mgr.find_create_object(plDrawInterface, bl=bo, so=so)
            addRegion = diface.addRegion
        elif bo.type == "LAMP":
            light = exporter.light.get_light_key(bo, bo.data, so)
            addRegion = light.object.addVisRegion

        for region in self.regions:
            if not region.enabled:
                continue
            if not region.control_region:
                raise ExportError("{}: Not all Visibility Controls are set up properly in Visibility Set".format(bo.name))
            addRegion(exporter.mgr.find_create_key(plVisRegion, bl=region.control_region))
