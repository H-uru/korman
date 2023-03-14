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

from .. import idprops
from .prop_anim import PlasmaAnimationCollection

class EnvMapVisRegion(idprops.IDPropObjectMixin, bpy.types.PropertyGroup):
    enabled = BoolProperty(default=True)
    control_region = PointerProperty(name="Control",
                                     description="Object defining a Plasma Visibility Control",
                                     type=bpy.types.Object,
                                     poll=idprops.poll_visregion_objects)

    @classmethod
    def _idprop_mapping(cls):
        return {"control_region": "region_name"}


class PlasmaLayer(bpy.types.PropertyGroup):
    bl_idname = "texture.plasma_layer"

    opacity = FloatProperty(name="Layer Opacity",
                                  description="Opacity of the texture",
                                  default=100.0, min=0.0, max=100.0,
                                  precision=0, subtype="PERCENTAGE")
    use_alpha_vcol = BoolProperty(name="Use Alpha VCol",
                                  description="Texture uses the Alpha vertex color values",
                                  default=False)
    alpha_halo = BoolProperty(name="High Alpha Test",
                              description="Fixes halos seen around semitransparent objects resulting from sorting errors",
                              default=False)

    envmap_color = FloatVectorProperty(name="Environment Map Color",
                                       description="The default background color rendered onto the Environment Map",
                                       min=0.0,
                                       max=1.0,
                                       default=(1.0, 1.0, 1.0),
                                       subtype="COLOR")

    envmap_addavatar = BoolProperty(name="Render Avatars",
                                    description="Toggle the rendering of avatars in the environment map",
                                    default=True)

    vis_regions = CollectionProperty(name="Visibility Regions",
                                     type=EnvMapVisRegion)
    active_region_index = IntProperty(options={"HIDDEN"})

    is_detail_map = BoolProperty(name="Detail Fade",
                                 description="Texture fades out as distance from the camera increases",
                                 default=False,
                                 options=set())
    detail_fade_start = IntProperty(name="Falloff Start",
                                    description="",
                                    min=0, max=100, default=0,
                                    options=set(), subtype="PERCENTAGE")
    detail_fade_stop = IntProperty(name="Falloff Stop",
                                   description="",
                                   min=0, max=100, default=100,
                                   options=set(), subtype="PERCENTAGE")
    detail_opacity_start = IntProperty(name="Opacity Start",
                                       description="",
                                       min=0, max=100, default=50,
                                       options=set(), subtype="PERCENTAGE")
    detail_opacity_stop = IntProperty(name="Opacity Stop",
                                      description="",
                                      min=0, max=100, default=0,
                                      options=set(), subtype="PERCENTAGE")

    z_bias = BoolProperty(name="Z Bias",
                          description="Request Z bias offset to defeat Z-fighting",
                          default=False,
                          options=set())
    skip_depth_test = BoolProperty(name="Skip Depth Test",
                                   description="Causes this layer to be rendered, even if behind others",
                                   default=False,
                                   options=set())
    skip_depth_write = BoolProperty(name="Skip Depth Write",
                                    description="Don't save the depth information, allowing rendering of layers behind this one",
                                    default=False,
                                    options=set())

    dynatext_resolution = EnumProperty(name="Dynamic Text Map Resolution",
                                       description="Size of the Dynamic Text Map's underlying image",
                                       items=[("128", "128x128", ""),
                                              ("256", "256x256", ""),
                                              ("512", "512x512", ""),
                                              ("1024", "1024x1024", "")],
                                       default="1024",
                                       options=set())

    subanimations = PointerProperty(type=PlasmaAnimationCollection)

    @classmethod
    def register(cls):
        PlasmaAnimationCollection.register_entire_animation(bpy.types.Texture, cls)
