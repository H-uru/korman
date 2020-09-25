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

class PlasmaMaterial(bpy.types.PropertyGroup):
    bl_idname = "material.plasma_mat"
    
    runtime_color = FloatVectorProperty(name="Runtime Color:",
                                        description="Sets the Runtime Color for Animated and Kickable Objects",
                                        min=0.0,
                                        max=1.0,
                                        default=(0.0, 0.0, 0.0),
                                        subtype="COLOR")
