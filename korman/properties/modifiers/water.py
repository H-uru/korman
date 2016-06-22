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
import math
from PyHSPlasma import *

from .base import PlasmaModifierProperties
from ...exporter import ExportError

class PlasmaWaterModifier(PlasmaModifierProperties, bpy.types.PropertyGroup):
    pl_id = "water_basic"

    bl_category = "Water"
    bl_label = "Basic Water"
    bl_description = "Basic water properties"

    wind_object_name = StringProperty(name="Wind Object",
                                      description="Object whose Y axis represents the wind direction")
    wind_speed = FloatProperty(name="Wind Speed",
                               description="Magnitude of the wind",
                               default=1.0)
    envmap_name = StringProperty(name="EnvMap",
                                 description="Texture defining an environment map for this water object")
    envmap_radius = FloatProperty(name="Environment Sphere Radius",
                                  description="How far away the first object you want to see is",
                                  min=5.0, max=10000.0,
                                  default=500.0)

    specular_tint = FloatVectorProperty(name="Specular Tint",
                                        subtype="COLOR",
                                        min=0.0, max=1.0,
                                        default=(1.0, 1.0, 1.0))
    specular_alpha = FloatProperty(name="Specular Alpha",
                                   min=0.0, max=1.0,
                                   default=0.3)
    noise = IntProperty(name="Noise",
                        subtype="PERCENTAGE",
                        min=0, max=300,
                        default=50)
    specular_start = FloatProperty(name="Specular Start",
                                   min=0.0, max=1000.0,
                                   default=50.0)
    specular_end = FloatProperty(name="Specular End",
                                 min=0.0, max=10000.0,
                                 default=1000.0)
    ripple_scale = FloatProperty(name="Ripple Scale",
                                 min=5.0, max=1000.0,
                                 default=25.0)

    depth_opacity = FloatProperty(name="Opacity End",
                                  min=0.5, max=20.0,
                                  default=3.0)
    depth_reflection = FloatProperty(name="Reflection End",
                                     min=0.5, max=20.0,
                                     default=3.0)
    depth_wave = FloatProperty(name="Wave End",
                               min=0.5, max=20.0,
                               default=4.0)
    zero_opacity = FloatProperty(name="Opacity Start",
                                 min=-10.0, max=10.0,
                                 default=-1.0)
    zero_reflection = FloatProperty(name="Reflection Start",
                                    min=-10.0, max=10.0,
                                    default=0.0)
    zero_wave = FloatProperty(name="Wave Start",
                              min=-10.0, max=10.0,
                              default=0.0)

    def export(self, exporter, bo, so):
        waveset = exporter.mgr.find_create_object(plWaveSet7, name=bo.name, so=so)
        if self.wind_object_name:
            wind_obj = bpy.data.objects.get(self.wind_object_name, None)
            if wind_obj is None:
                raise ExportError("{}: Wind Object '{}' not found".format(bo.name, self.wind_object_name))
            if wind_obj.plasma_object.enabled and wind_obj.plasma_modifiers.animation.enabled:
                waveset.refObj = exporter.mgr.find_create_key(plSceneObject, bl=wind_obj)
                waveset.setFlag(plWaveSet7.kHasRefObject, True)

            # This is much like what happened in PyPRP
            speed = self.wind_speed
            matrix = wind_obj.matrix_world
            wind_dir = hsVector3(matrix[1][0] * speed, matrix[1][1] * speed, matrix[1][2] * speed)
        else:
            # Stolen shamelessly from PyPRP
            wind_dir = hsVector3(0.0871562, 0.996195, 0.0)

        # Stuff we expose
        state = waveset.state
        state.rippleScale = self.ripple_scale
        state.waterHeight = bo.location[2]
        state.windDir = wind_dir
        state.specVector = hsVector3(self.noise / 100.0, self.specular_start, self.specular_end)
        state.specularTint = hsColorRGBA(*self.specular_tint, alpha=self.specular_alpha)
        state.waterOffset = hsVector3(self.zero_opacity * -1.0, self.zero_reflection * -1.0, self.zero_wave * -1.0)
        state.depthFalloff = hsVector3(self.depth_opacity, self.depth_reflection, self.depth_wave)

        # Environment Map
        if self.envmap_name:
            texture = bpy.data.textures.get(self.envmap_name, None)
            if texture is None:
                raise ExportError("{}: Texture '{}' not found".format(self.key_name, self.envmap_name))
            if texture.type != "ENVIRONMENT_MAP":
                raise ExportError("{}: Texture '{}' is not an ENVIRONMENT MAP".format(self.key_name, self.envmap_name))

            # maybe, just maybe, we're absuing our privledges?
            dem = exporter.mesh.material.export_dynamic_env(bo, None, texture, plDynamicEnvMap)
            waveset.envMap = dem.key
            state.envCenter = dem.position
            state.envRefresh = dem.refreshRate
        else:
            state.envCenter = hsVector3(*bo.location)
            state.envRefresh = 0.0
        state.envRadius = self.envmap_radius

        # These are either unused, set from somewhere else at runtime, or hardcoded
        state.waterTint = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
        state.maxColor = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
        state.shoreTint = hsColorRGBA(1.0, 1.0, 1.0, 1.0)
        state.maxAtten = hsVector3(1.0, 1.0, 1.0)
        state.minAtten = hsVector3(0.0, 0.0, 0.0)

        # Now, we have some related modifiers that may or may not be enabled... If not, we should
        # make them export their defaults.
        mods = bo.plasma_modifiers
        if not mods.water_geostate.enabled:
            mods.water_geostate.convert_default_wavestate(state.geoState)
        if not mods.water_texstate.enabled:
            mods.water_texstate.convert_default_wavestate(state.texState)
        if not mods.water_shore.enabled:
            mods.water_shore.convert_default(state)

    @property
    def key_name(self):
        return "{}_WaveSet7".format(self.id_data.name)


class PlasmaShoreObject(bpy.types.PropertyGroup):
    display_name = StringProperty(name="Display Name")
    object_name = StringProperty(name="Shore Object",
                                 description="Object that waves crash upon")


class PlasmaWaterShoreModifier(PlasmaModifierProperties):
    pl_depends = {"water_basic"}
    pl_id = "water_shore"

    bl_category = "Water"
    bl_label = "Water Shore"
    bl_description = ""

    # The basic modifier may want to export a default copy of us
    _shore_tint_default = (0.2, 0.4, 0.4)
    _shore_opacity_default = 40
    _wispiness_default = 50
    _period_default = 100.0
    _finger_default = 100.0
    _edge_opacity_default = 100
    _edge_radius_default = 100.0

    shores = CollectionProperty(type=PlasmaShoreObject)
    active_shore_index = IntProperty(options={"HIDDEN"})

    shore_tint = FloatVectorProperty(name="Shore Tint",
                                     subtype="COLOR",
                                     min=0.0, max=1.0,
                                     default=_shore_tint_default)
    shore_opacity = IntProperty(name="Shore Opacity",
                                subtype="PERCENTAGE",
                                min=0, max=100,
                                default=_shore_opacity_default)
    wispiness = IntProperty(name="Wispiness",
                            subtype="PERCENTAGE",
                            min=0, max=200,
                            default=_wispiness_default)

    period = FloatProperty(name="Period",
                           min=0.0, max=200.0,
                           default=_period_default)
    finger = FloatProperty(name="Finger",
                           min=50.0, max=300.0,
                           default=_finger_default)
    edge_opacity = IntProperty(name="Edge Opacity",
                               subtype="PERCENTAGE",
                               min=0, max=100,
                               default=_edge_opacity_default)
    edge_radius = FloatProperty(name="Edge Radius",
                                subtype="PERCENTAGE",
                                min=50, max=300,
                                default=_edge_radius_default)

    def convert_default(self, wavestate):
        wavestate.wispiness = self._wispiness_default / 100.0
        wavestate.minColor = hsColorRGBA(*self._shore_tint_default, alpha=(self._shore_opacity_default / 100.0))
        wavestate.edgeOpacity = self._edge_opacity_default / 100.0
        wavestate.edgeRadius = self._edge_radius_default / 100.0
        wavestate.period = self._period_default / 100.0
        wavestate.fingerLength = self._finger_default / 100.0

    def export(self, exporter, bo, so):
        waveset = exporter.mgr.find_create_object(plWaveSet7, name=bo.name, so=so)
        wavestate = waveset.state

        for i in self.shores:
            shore = bpy.data.objects.get(i.object_name, None)
            if shore is None:
                raise ExportError("'{}': Shore Object '{}' does not exist".format(self.key_name, i.object_name))
            waveset.addShore(exporter.mgr.find_create_key(plSceneObject, bl=shore))

        wavestate.wispiness = self.wispiness / 100.0
        wavestate.minColor = hsColorRGBA(*self.shore_tint, alpha=(self.shore_opacity / 100.0))
        wavestate.edgeOpacity = self.edge_opacity / 100.0
        wavestate.edgeRadius = self.edge_radius / 100.0
        wavestate.period = self.period / 100.0
        wavestate.fingerLength = self.finger / 100.0


class PlasmaWaveState:
    pl_depends = {"water_basic"}

    def convert_wavestate(self, state):
        state.minLength = self.min_length
        state.maxLength = self.max_length
        state.ampOverLen = self.amplitude / 100.0
        state.chop = self.chop / 100.0
        state.angleDev = self.angle_dev

    def convert_default_wavestate(self, state):
        cls = self.__class__
        state.minLength = cls._min_length_default
        state.maxLength = cls._max_length_default
        state.ampOverLen = cls._amplitude_default / 100.0
        state.chop = cls._chop_default / 100.0
        state.angleDev = cls._angle_dev_default

    @classmethod
    def register(cls):
        cls.min_length = FloatProperty(name="Min Length",
                                       description="Smallest wave length",
                                       min=0.1, max=50.0,
                                       default=cls._min_length_default)
        cls.max_length = FloatProperty(name="Max Length",
                                       description="Largest wave length",
                                       min=0.1, max=50.0,
                                       default=cls._max_length_default)
        cls.amplitude = IntProperty(name="Amplitude",
                                    description="Multiplier for wave height",
                                    subtype="PERCENTAGE",
                                    min=0, max=100,
                                    default=cls._amplitude_default)
        cls.chop = IntProperty(name="Choppiness",
                               description="Sharpness of wave crests",
                               subtype="PERCENTAGE",
                               min=0, max=500,
                               default=cls._chop_default)
        cls.angle_dev = FloatProperty(name="Wave Spread",
                                      subtype="ANGLE",
                                      min=math.radians(0.0), max=math.radians(180.0),
                                      default=cls._angle_dev_default)


class PlasmaWaveGeoState(PlasmaWaveState, PlasmaModifierProperties):
    pl_id = "water_geostate"

    bl_category = "Water"
    bl_label = "Geometry Waves"
    bl_description = "Mesh wave settings"

    _min_length_default = 4.0
    _max_length_default = 8.0
    _amplitude_default = 10
    _chop_default = 50
    _angle_dev_default = math.radians(20.0)

    def export(self, exporter, bo, so):
        waveset = exporter.mgr.find_create_object(plWaveSet7, name=bo.name, so=so)
        self.convert_wavestate(waveset.state.geoState)


class PlasmaWaveTexState(PlasmaWaveState, PlasmaModifierProperties):
    pl_id = "water_texstate"

    bl_category = "Water"
    bl_label = "Texture Waves"
    bl_description = "Texture wave settings"

    _min_length_default = 0.1
    _max_length_default = 4.0
    _amplitude_default = 10
    _chop_default = 50
    _angle_dev_default = math.radians(20.0)

    def export(self, exporter, bo, so):
        waveset = exporter.mgr.find_create_object(plWaveSet7, name=bo.name, so=so)
        self.convert_wavestate(waveset.state.texState)
