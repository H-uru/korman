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

    anim_auto_start = BoolProperty(name="Auto Start",
                                   description="Automatically start layer animation",
                                   default=True)
    anim_loop = BoolProperty(name="Loop",
                             description="Loop layer animation",
                             default=True)
    anim_sdl_var = StringProperty(name="SDL Variable",
                                  description="Name of the SDL Variable to use for this animation",
                                  options=set())

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

    funky_type = EnumProperty(name="Funky Blending Type",
                              description="Type of special funky layer blending",
                              items=[("FunkyNone", "None", "No funky layer blending"),
                                     ("FunkyDist", "Distance", "Distance-based funky layer blending"),
                                     ("FunkyNormal", "Normal", "Normal angle-based funky layer blending"),
                                     ("FunkyReflect", "Reflect", "Reflection angle-based funky layer blending"),
                                     ("FunkyUp", "Up", "Upwards angle-based funky layer blending")],
                              default="FunkyNone")
    funky_near_trans = FloatProperty(name="Near Transparent",
                                     description="Nearest distance at which the layer is fully transparent",
                                     min=0.0, default=0.0, subtype="DISTANCE", unit="LENGTH")
    funky_near_opaq = FloatProperty(name="Near Opaque",
                                    description="Nearest distance at which the layer is fully opaque",
                                    min=0.0, default=0.0, subtype="DISTANCE", unit="LENGTH")
    funky_far_opaq = FloatProperty(name="Far Opaque",
                                   description="Farthest distance at which the layer is fully opaque",
                                   min=0.0, default=15.0, subtype="DISTANCE", unit="LENGTH")
    funky_far_trans = FloatProperty(name="Far Transparent",
                                    description="Farthest distance at which the layer is fully transparent",
                                    min=0.0, default=20.0, subtype="DISTANCE", unit="LENGTH")
