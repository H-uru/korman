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

class EnvMapVisRegion(bpy.types.PropertyGroup):
    enabled = BoolProperty(default=True)
    region_name = StringProperty(name="Control",
                                 description="Object defining a Plasma Visibility Control")


class PlasmaLayer(bpy.types.PropertyGroup):
    bl_idname = "texture.plasma_layer"

    opacity = FloatProperty(name="Layer Opacity",
                                  description="Opacity of the texture",
                                  default=100,
                                  min=0,
                                  max=100,
                                  subtype="PERCENTAGE")

    envmap_color = FloatVectorProperty(name="Environment Map Color",
                                       description="The default background color rendered onto the Environment Map",
                                       min=0.0,
                                       max=1.0,
                                       default=(1.0, 1.0, 1.0),
                                       subtype="COLOR")

    vis_regions = CollectionProperty(name="Visibility Regions",
                                     type=EnvMapVisRegion)
    active_region_index = IntProperty(options={"HIDDEN"})

    anim_auto_start = BoolProperty(name="Auto Start",
                                   description="Automatically start layer animation",
                                   default=True)
    anim_loop = BoolProperty(name="Loop",
                             description="Loop layer animation",
                             default=True)
