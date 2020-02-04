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
import itertools

from ..exporter.etlight import _NUM_RENDER_LAYERS

class PlasmaBakePass(bpy.types.PropertyGroup):
    def _get_display_name(self):
        return self.name
    def _set_display_name(self, value):
        for i in bpy.data.objects:
            lm = i.plasma_modifiers.lightmap
            if lm.bake_pass_name == self.name:
                lm.bake_pass_name = value
        self.name = value

    display_name = StringProperty(name="Pass Name",
                                  get=_get_display_name,
                                  set=_set_display_name,
                                  options=set())

    render_layers = BoolVectorProperty(name="Layers to Bake",
                                       description="Render layers to use for baking",
                                       options=set(),
                                       subtype="LAYER",
                                       size=_NUM_RENDER_LAYERS,
                                       default=((True,) * _NUM_RENDER_LAYERS))


class PlasmaWetDecalRef(bpy.types.PropertyGroup):
    enabled = BoolProperty(name="Enabled",
                           default=True,
                           options=set())

    name = StringProperty(name="Decal Name",
                          description="Wet decal manager",
                          options=set())


class PlasmaDecalManager(bpy.types.PropertyGroup):
    def _get_display_name(self):
        return self.name
    def _set_display_name(self, value):
        prev_value = self.name
        for i in bpy.data.objects:
            decal_receive = i.plasma_modifiers.decal_receive
            decal_print = i.plasma_modifiers.decal_print
            for j in itertools.chain(decal_receive.managers, decal_print.managers):
                if j.name == prev_value:
                    j.name = value
        for i in bpy.context.scene.plasma_scene.decal_managers:
            for j in i.wet_managers:
                if j.name == prev_value:
                    j.name = value
        self.name = value

    name = StringProperty(name="Decal Name",
                          options=set())
    display_name = StringProperty(name="Display Name",
                                  get=_get_display_name,
                                  set=_set_display_name,
                                  options=set())

    decal_type = EnumProperty(name="Decal Type",
                              description="",
                              items=[("footprint_dry", "Footprint (Dry)", ""),
                                     ("footprint_wet", "Footprint (Wet)", ""),
                                     ("puddle", "Water Ripple (Shallow)", ""),
                                     ("ripple", "Water Ripple (Deep)", "")],
                              default="footprint_dry",
                              options=set())
    image = PointerProperty(name="Image",
                            description="",
                            type=bpy.types.Image,
                            options=set())
    blend = EnumProperty(name="Blend Mode",
                         description="",
                         items=[("kBlendAdd", "Add", ""),
                                ("kBlendAlpha", "Alpha", ""),
                                ("kBlendMADD", "Brighten", ""),
                                ("kBlendMult", "Multiply", "")],
                         default="kBlendAlpha",
                         options=set())

    length = IntProperty(name="Length",
                         description="",
                         subtype="PERCENTAGE",
                         min=0, soft_min=25, soft_max=400, default=100,
                         options=set())
    width = IntProperty(name="Width",
                        description="",
                        subtype="PERCENTAGE",
                        min=0, soft_min=25, soft_max=400, default=100,
                        options=set())
    intensity = IntProperty(name="Intensity",
                            description="",
                            subtype="PERCENTAGE",
                            min=0, soft_max=100, default=100,
                            options=set())
    life_span = FloatProperty(name="Life Span",
                              description="",
                              subtype="TIME", unit="TIME",
                              min=0.0, soft_max=300.0, default=30.0,
                              options=set())
    wet_time = FloatProperty(name="Wet Time",
                             description="How long the decal print shapes stay wet after losing contact with this surface",
                             subtype="TIME", unit="TIME",
                             min=0.0, soft_max=300.0, default=10.0,
                             options=set())

    # Footprints to wet-ize
    wet_managers = CollectionProperty(type=PlasmaWetDecalRef)
    active_wet_index = IntProperty(options={"HIDDEN"})


class PlasmaScene(bpy.types.PropertyGroup):
    bake_passes = CollectionProperty(type=PlasmaBakePass)
    active_pass_index = IntProperty(options={"HIDDEN"})

    decal_managers = CollectionProperty(type=PlasmaDecalManager)
    active_decal_index = IntProperty(options={"HIDDEN"})

    modifier_copy_object = PointerProperty(name="INTERNAL: Object to copy modifiers from",
                                           options={"HIDDEN", "SKIP_SAVE"},
                                           type=bpy.types.Object)
    modifier_copy_id = StringProperty(name="INTERNAL: Modifier to copy from",
                                      options={"HIDDEN", "SKIP_SAVE"})
