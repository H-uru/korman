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
import functools
from PyHSPlasma import *

from .base import PlasmaModifierProperties, PlasmaModifierLogicWiz, PlasmaModifierUpgradable
from ...exporter.etlight import _NUM_RENDER_LAYERS
from ...exporter import utils
from ...exporter.explosions import ExportError
from .gui import languages, PlasmaJournalTranslation, TranslationMixin
from ... import idprops

class PlasmaBlendOntoObject(bpy.types.PropertyGroup):
    blend_onto = PointerProperty(name="Blend Onto",
                                 description="Object to render first",
                                 options=set(),
                                 type=bpy.types.Object,
                                 poll=idprops.poll_drawable_objects)
    enabled = BoolProperty(name="Enabled",
                           default=True,
                           options=set())


class PlasmaBlendMod(PlasmaModifierProperties):
    pl_id = "blend"
    pl_page_types = {"gui", "room"}

    bl_category = "Render"
    bl_label = "Blending"
    bl_description = "Advanced Blending Options"
    bl_object_types = {"MESH", "FONT"}

    render_level = EnumProperty(name="Render Pass",
                                description="Suggested render pass for this object.",
                                items=[("AUTO", "(Auto)", "Let Korman decide when to render this object."),
                                       ("OPAQUE", "Before Avatar", "Prefer for the object to draw before the avatar."),
                                       ("FRAMEBUF", "Frame Buffer", "Prefer for the object to draw after the avatar but before other blended objects."),
                                       ("BLEND", "Blended", "Prefer for the object to draw after most other geometry in the blended pass."),
                                       ("LATE", "Late", "Prefer for the object to draw after all other alpha-blended objects.")],
                                options=set())
    sort_faces = EnumProperty(name="Sort Faces",
                              description="",
                              items=[("AUTO", "(Auto)", "Let Korman decide if faces should be sorted."),
                                     ("ALWAYS", "Always", "Force the object's faces to be sorted."),
                                     ("NEVER", "Never", "Force the object's faces to never be sorted.")],
                              options=set())

    dependencies = CollectionProperty(type=PlasmaBlendOntoObject)
    active_dependency_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        # What'er you lookin at?
        pass

    @property
    def draw_opaque(self):
        return self.render_level == "OPAQUE"

    @property
    def draw_framebuf(self):
        return self.render_level == "FRAMEBUF"

    @property
    def draw_late(self):
        return self.render_level == "LATE"

    @property
    def draw_no_defer(self):
        return self.render_level != "BLEND"

    @property
    def face_sort(self):
        return self.sort_faces == "ALWAYS"

    @property
    def no_face_sort(self):
        return self.sort_faces == "NEVER"

    @property
    def has_dependencies(self):
        return bool(self.dependencies)

    @property
    def has_circular_dependency(self):
        return self._check_circular_dependency()

    def _check_circular_dependency(self, objects=None):
        if objects is None:
            objects = set()
        elif self.id_data.name in objects:
            return True
        objects.add(self.id_data.name)

        for i in self.iter_dependencies():
            # New deep copy of the set for each dependency, so an object can be reused as a
            # dependant's dependant.
            this_branch = set(objects)
            sub_mod = i.plasma_modifiers.blend
            if sub_mod.enabled and sub_mod._check_circular_dependency(this_branch):
                return True
        return False

    def iter_dependencies(self):
        for i in (j.blend_onto for j in self.dependencies if j.blend_onto is not None and j.enabled):
            yield i

    def sanity_check(self, exporter):
        if self.has_circular_dependency:
            raise ExportError("'{}': Circular Render Dependency detected!".format(self.id_data.name))


class PlasmaDecalManagerRef(bpy.types.PropertyGroup):
    enabled = BoolProperty(name="Enabled",
                           default=True,
                           options=set())

    name = StringProperty(name="Decal Name",
                          options=set())


class PlasmaDecalMod:
    def _iter_decals(self, func):
        for decal_ref in self.managers:
            if decal_ref.enabled:
                func(decal_ref.name)

    @classmethod
    def register(cls):
        cls.managers = CollectionProperty(type=PlasmaDecalManagerRef)
        cls.active_manager_index = IntProperty(options={"HIDDEN"})


class PlasmaDecalPrintMod(PlasmaDecalMod, PlasmaModifierProperties):
    pl_id = "decal_print"

    bl_category = "Render"
    bl_label = "Print Decal"
    bl_description = "Prints a decal onto an object"
    bl_object_types = {"MESH", "FONT"}

    decal_type = EnumProperty(name="Decal Type",
                              description="Type of decal to print onto another object",
                              items=[("DYNAMIC", "Dynamic", "This object prints a decal onto dynamic decal surfaces"),
                                     ("STATIC", "Static", "This object is a decal itself")],
                              options=set())

    # Dynamic Decals
    length = FloatProperty(name="Length",
                           min=0.1, soft_max=30.0, precision=2,
                           default=0.45,
                           options=set())
    width = FloatProperty(name="Width",
                          min=0.1, soft_max=30.0, precision=2,
                          default=0.9,
                          options=set())
    height = FloatProperty(name="Height",
                           min=0.1, soft_max=30.0, precision=2,
                           default=1.0,
                           options=set())

    @property
    def copy_material(self):
        return self.decal_type == "STATIC"

    def get_key(self, exporter, so):
        if self.decal_type == "DYNAMIC":
            pClass = plActivePrintShape if any((i.enabled for i in self.managers)) else plPrintShape
            return exporter.mgr.find_create_key(pClass, so=so)

    def export(self, exporter, bo, so):
        if self.decal_type == "STATIC":
            exporter.decal.export_static_decal(bo)
        elif self.decal_type == "DYNAMIC":
            print_shape = self.get_key(exporter, so).object
            print_shape.length = self.length
            print_shape.width = self.width
            print_shape.height = self.height

    def post_export(self, exporter, bo, so):
        if self.decal_type == "DYNAMIC":
            print_shape = self.get_key(exporter, so).object
            f = functools.partial(exporter.decal.export_active_print_shape, print_shape)
            self._iter_decals(f)

class PlasmaDecalReceiveMod(PlasmaDecalMod, PlasmaModifierProperties):
    pl_id = "decal_receive"

    bl_category = "Render"
    bl_label = "Receive Decal"
    bl_description = "Allows this object to receive dynamic decals"
    bl_object_types = {"MESH", "FONT"}

    managers = CollectionProperty(type=PlasmaDecalManagerRef)
    active_manager_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        f = functools.partial(exporter.decal.generate_dynamic_decal, bo)
        self._iter_decals(f)

    def post_export(self, exporter, bo, so):
        f = functools.partial(exporter.decal.add_dynamic_decal_receiver, so)
        self._iter_decals(f)


class PlasmaFadeMod(PlasmaModifierProperties):
    pl_id = "fademod"

    bl_category = "Render"
    bl_label = "Opacity Fader"
    bl_description = "Fades an object based on distance or line-of-sight"
    bl_object_types = {"MESH", "FONT"}

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
            
    @property
    def requires_actor(self):
        return self.fader_type == "FadeOpacity"


class PlasmaFollowMod(idprops.IDPropObjectMixin, PlasmaModifierProperties):
    pl_id = "followmod"

    bl_category = "Render"
    bl_label = "Follow"
    bl_description = "Follow the movement of the camera, player, or another object"
    bl_object_types = {"MESH", "FONT"}

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


class PlasmaGrassWave(bpy.types.PropertyGroup):
    distance = FloatVectorProperty(name="Distance",
                                   size=3,
                                   default=(0.2, 0.2, 0.1),
                                   subtype="XYZ",
                                   unit="LENGTH",
                                   options=set())
    direction = FloatVectorProperty(name="Direction",
                                    size=2,
                                    default=(0.2, 0.05),
                                    soft_min=0.0, soft_max=1.0,
                                    unit="LENGTH",
                                    subtype="XYZ",
                                    options=set())
    speed = FloatProperty(name="Speed",
                          default=0.1,
                          unit="VELOCITY",
                          options=set())


class PlasmaGrassShaderMod(PlasmaModifierProperties):
    pl_id = "grass_shader"

    bl_category = "Render"
    bl_label = "Grass Shader"
    bl_description = "Applies waving grass effect at run-time"
    bl_object_types = {"MESH", "FONT"}

    wave1 = PointerProperty(type=PlasmaGrassWave)
    wave2 = PointerProperty(type=PlasmaGrassWave)
    wave3 = PointerProperty(type=PlasmaGrassWave)
    wave4 = PointerProperty(type=PlasmaGrassWave)

    # UI Accessor
    wave_selector = EnumProperty(items=[("wave1", "Wave 1", ""),
                                        ("wave2", "Wave 2", ""),
                                        ("wave3", "Wave 3", ""),
                                        ("wave4", "Wave 4", "")],
                                 name="Waves",
                                 options=set())

    @property
    def copy_material(self):
        return True

    def export(self, exporter, bo, so):
        if exporter.mgr.getVer() <= pvPots:
            exporter.report.warn("Not supported on this version of Plasma")
            return
        else:
            exporter.report.port("This will only function on MOUL and EOA")

        materials = exporter.mesh.material.get_materials(bo)
        if not materials:
            exporter.report.warn("No materials are associated with this object, no grass shader exported!")
            return
        elif len(materials) > 1:
            exporter.report.warn("Ah, a multiple material grass shader, eh. You like living dangerously...")

        for material in materials:
            mod = exporter.mgr.find_create_object(plGrassShaderMod, so=so, name=material.name)
            mod.material = material
            for mod_wave, settings in zip(mod.waves, (self.wave1, self.wave2, self.wave3, self.wave4)):
                mod_wave.dist = hsVector3(*settings.distance)
                mod_wave.dirX, mod_wave.dirY = settings.direction
                mod_wave.speed = settings.speed


class PlasmaLightMapGen(idprops.IDPropMixin, PlasmaModifierProperties, PlasmaModifierUpgradable):
    pl_id = "lightmap"

    bl_category = "Render"
    bl_label = "Bake Lighting"
    bl_description = "Auto-Bake Static Lighting"
    bl_object_types = {"MESH", "FONT"}

    deprecated_properties = {"render_layers"}

    quality = EnumProperty(name="Quality",
                           description="Resolution of lightmap",
                           items=[
                                  ("128", "128px", "128x128 pixels"),
                                  ("256", "256px", "256x256 pixels"),
                                  ("512", "512px", "512x512 pixels"),
                                  ("1024", "1024px", "1024x1024 pixels"),
                                  ("2048", "2048px", "2048x2048 pixels"),
                            ])

    bake_type = EnumProperty(name="Bake To",
                             description="Destination for baked lighting data",
                             items=[
                                ("lightmap", "Lightmap Texture", "Bakes lighting to a lightmap texture"),
                                ("vcol", "Vertex Colors", "Bakes lighting to vertex colors"),
                             ],
                             options=set())

    render_layers = BoolVectorProperty(name="Layers",
                                       description="DEPRECATED: Render layers to use for baking",
                                       options={"HIDDEN"},
                                       subtype="LAYER",
                                       size=_NUM_RENDER_LAYERS,
                                       default=((True,) * _NUM_RENDER_LAYERS))

    bake_pass_name = StringProperty(name="Bake Pass",
                                    description="Pass in which to bake lighting",
                                    options=set())

    lights = PointerProperty(name="Light Group",
                             description="Group that defines the collection of lights to bake",
                             type=bpy.types.Group)

    uv_map = StringProperty(name="UV Texture",
                            description="UV Texture used as the basis for the lightmap")

    image = PointerProperty(name="Baked Image",
                            description="Use this image instead of re-baking the lighting each export",
                            type=bpy.types.Image)

    @property
    def bake_lightmap(self):
        if not self.enabled:
            return False
        age = bpy.context.scene.world.plasma_age
        if age.export_active:
            if age.lighting_method == "force_lightmap":
                return True
            elif self.bake_type == "lightmap" and age.lighting_method == "bake":
                return True
            else:
                return False
        else:
            return self.bake_type == "lightmap"

    @property
    def copy_material(self):
        return self.bake_lightmap

    def export(self, exporter, bo, so):
        # If we're exporting vertex colors, who gives a rat's behind?
        if not self.bake_lightmap:
            return

        # If no lightmap image is found, then either lightmap generation failed (error raised by oven)
        # or baking is turned off. Either way, bail out.
        lightmap_im = self.image if self.image is not None else exporter.oven.get_lightmap(bo)
        if lightmap_im is None:
            return
        mat_mgr = exporter.mesh.material
        materials = mat_mgr.get_materials(bo)

        # Find the stupid UVTex
        uvtex_name = exporter.oven.lightmap_uvtex_name
        uvw_src = next((i for i, uvtex in enumerate(bo.data.uv_textures) if uvtex.name == uvtex_name), None)
        if uvw_src is None:
            raise ExportError("'{}': Lightmap UV Texture '{}' seems to be missing. Did you delete it?", bo.name, uvtex_name)

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
            mat_mgr.export_prepared_image(owner=layer, image=lightmap_im,
                                          allowed_formats={"PNG", "JPG"},
                                          extension="hsm",
                                          ephemeral=True)

    @classmethod
    def _idprop_mapping(cls):
        return {"lights": "light_group"}

    def _idprop_sources(self):
        return {"light_group": bpy.data.groups}

    @property
    def key_name(self):
        return "{}_LIGHTMAPGEN".format(self.id_data.name)

    @property
    def latest_version(self):
        return 2

    @property
    def resolution(self):
        return int(self.quality)

    def upgrade(self):
        # In version 1, bake passes were assigned on a per modifier basis by setting
        # the view layers on the modifier. Version 2 moves them into a global list
        # that can be selected by name in the modifier
        if self.current_version < 2:
            bake_passes = bpy.context.scene.plasma_scene.bake_passes
            render_layers = tuple(self.render_layers)

            # Try to find a render pass matching, if possible...
            bake_pass = next((i for i in bake_passes if tuple(i.render_layers) == render_layers), None)
            if bake_pass is None:
                bake_pass = bake_passes.add()
                bake_pass.display_name = "Pass {}".format(len(bake_passes))
                bake_pass.render_layers = render_layers
            self.bake_pass_name = bake_pass.display_name
            self.property_unset("render_layers")
            self.current_version = 2


class PlasmaLightingMod(PlasmaModifierProperties):
    pl_id = "lighting"
    pl_page_types = {"gui", "room"}

    bl_category = "Render"
    bl_label = "Lighting Info"
    bl_description = "Fine tune Plasma lighting settings"
    bl_object_types = {"MESH", "FONT"}

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
        mods = self.id_data.plasma_modifiers
        if mods.water_basic.enabled:
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
    def unleashed(self):
        """Has Satan been unleashed? Meaning, RT lights and preshading."""
        return self.enabled and self.rt_lights and self.preshade

    @property
    def want_rt_lights(self):
        """Gets whether or not this object ought to be lit dynamically"""
        mods = self.id_data.plasma_modifiers
        if mods.lightmap.enabled and mods.lightmap.bake_type == "lightmap":
            return False
        if mods.water_basic.enabled:
            return True
        if self.id_data.plasma_object.has_transform_animation:
            return True
        if mods.collision.enabled and mods.collision.dynamic:
            return True
        return False


class PlasmaLocalizedTextModifier(PlasmaModifierProperties, PlasmaModifierLogicWiz, TranslationMixin):
    pl_id = "dynatext"
    pl_page_types = {"gui", "room"}

    bl_category = "Render"
    bl_label = "Localized Text"
    bl_description = ""
    bl_icon = "TEXT"
    bl_object_types = {"MESH", "FONT"}

    translations = CollectionProperty(name="Translations",
                                      type=PlasmaJournalTranslation,
                                      options=set())
    active_translation_index = IntProperty(options={"HIDDEN"})
    active_translation = EnumProperty(name="Language",
                                      description="Language of this translation",
                                      items=languages,
                                      get=TranslationMixin._get_translation,
                                      set=TranslationMixin._set_translation,
                                      options=set())

    texture = PointerProperty(name="Texture",
                              description="The texture to write the localized text on",
                              type=bpy.types.Texture,
                              poll=idprops.poll_object_dyntexts)

    font_face = StringProperty(name="Font Face",
                               default="Arial",
                               options=set())
    font_size = IntProperty(name="Font Size",
                            default=12,
                            min=0, soft_max=72,
                            options=set())
    font_color = FloatVectorProperty(name="Font Color",
                                     default=(0.0, 0.0, 0.0, 1.0),
                                     min=0.0, max=1.0,
                                     subtype="COLOR", size=4,
                                     options=set())

    # Using individual properties for better UI documentation
    margin_top = IntProperty(name="Margin Top",
                             min=-4096, soft_min=0, max=4096,
                             options=set())
    margin_left = IntProperty(name="Margin Left",
                              min=-4096, soft_min=0, max=4096,
                              options=set())
    margin_bottom = IntProperty(name="Margin Bottom",
                                min=-4096, soft_min=0, max=4096,
                                options=set())
    margin_right = IntProperty(name="Margin Right",
                               min=-4096, soft_min=0, max=4096,
                               options=set())

    justify = EnumProperty(name="Justification",
                           items=[("left", "Left", ""),
                                  ("center", "Center", ""),
                                  ("right", "Right", "")],
                           default="left",
                           options=set())
    line_spacing = IntProperty(name="Line Spacing",
                               default=0,
                               soft_min=0, soft_max=10,
                               options=set())

    def pre_export(self, exporter, bo):
        yield self.convert_logic(bo, age_name=exporter.age_name, version=exporter.mgr.getVer())

    def logicwiz(self, bo, tree, *, age_name, version):
        # Rough justice. If the dynamic text map texture doesn't request alpha, then we'll want
        # to explicitly clear it to the material's diffuse color. This will allow artists to trivially
        # add text surfaces directly to objects, opposed to where Cyan tends to use a separate
        # transparent object over the background object.
        if not self.texture.use_alpha:
            material_filter = lambda slot: slot and slot.material and self.texture in (i.texture for i in slot.material.texture_slots if i)
            for slot in filter(material_filter, bo.material_slots):
                self._create_nodes(bo, tree, age_name=age_name, version=version,
                                   material=slot.material, clear_color=slot.material.diffuse_color)
        else:
            self._create_nodes(bo, tree, age_name=age_name, version=version)

    def _create_nodes(self, bo, tree, *, age_name, version, material=None, clear_color=None):
        pfm_node = self._create_standard_python_file_node(tree, "xDynTextLoc.py")
        loc_path = self.key_name if version <= pvPots else "{}.{}.{}".format(age_name, self.localization_set, self.key_name)

        self._create_python_attribute(pfm_node, "dynTextMap",
                                      target_object=bo, material=material, texture=self.texture)
        self._create_python_attribute(pfm_node, "locPath", value=loc_path)
        self._create_python_attribute(pfm_node, "fontFace", value=self.font_face)
        self._create_python_attribute(pfm_node, "fontSize", value=self.font_size)
        self._create_python_attribute(pfm_node, "fontColorR", value=self.font_color[0])
        self._create_python_attribute(pfm_node, "fontColorG", value=self.font_color[1])
        self._create_python_attribute(pfm_node, "fontColorB", value=self.font_color[2])
        self._create_python_attribute(pfm_node, "fontColorA", value=self.font_color[3])
        self._create_python_attribute(pfm_node, "marginTop", value=self.margin_top)
        self._create_python_attribute(pfm_node, "marginLeft", value=self.margin_left)
        self._create_python_attribute(pfm_node, "marginBottom", value=self.margin_bottom)
        self._create_python_attribute(pfm_node, "marginRight", value=self.margin_right)
        self._create_python_attribute(pfm_node, "justify", value=self.justify)

        if clear_color is not None:
            self._create_python_attribute(pfm_node, "clearColorR", value=clear_color[0])
            self._create_python_attribute(pfm_node, "clearColorG", value=clear_color[1])
            self._create_python_attribute(pfm_node, "clearColorB", value=clear_color[2])
            self._create_python_attribute(pfm_node, "clearColorA", value=1.0)

        # BlockRGB is some weird flag the engine uses to properly render when the DynaTextMap has
        # alpha. Why the engine can't figure this out on its own is beyond me.
        self._create_python_attribute(pfm_node, "blockRGB", value=self.texture.use_alpha)

    @property
    def localization_set(self):
        return "DynaTexts"

    def sanity_check(self, exporter):
        if self.texture is None:
            raise ExportError("'{}': Localized Text modifier requires a texture", self.id_data.name)


class PlasmaShadowCasterMod(PlasmaModifierProperties):
    pl_id = "rtshadow"

    bl_category = "Render"
    bl_label = "Cast RT Shadow"
    bl_description = "Cast runtime shadows"
    bl_object_types = {"MESH", "FONT"}

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
    bl_object_types = {"MESH", "FONT", "EMPTY"}

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
                exporter.report.msg("[VisRegion] I'm a SoftVolume myself :)")
                rgn.region = this_sv.get_key(exporter, so)
            else:
                if not self.soft_region:
                    raise ExportError("'{}': Visibility Control must have a Soft Volume selected".format(self.key_name))
                sv_bo = self.soft_region
                sv = sv_bo.plasma_modifiers.softvolume
                exporter.report.msg("[VisRegion] SoftVolume '{}'", sv_bo.name)
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
    bl_object_types = {"MESH", "LAMP"}

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
