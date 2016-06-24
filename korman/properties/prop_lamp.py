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

class PlasmaLamp(bpy.types.PropertyGroup):
    light_group = BoolProperty(name="Group Only",
                               description="This lamp will only affect materials that reference a group this lamp is a member of",
                               options=set(),
                               default=True)
    affect_characters = BoolProperty(name="Affect Avatars",
                                     description="This lamp affects avatars (can only be disabled if the lamp is \"Group Only\")",
                                     options=set(),
                                     default=True)
    cast_shadows = BoolProperty(name="Cast RT Shadows",
                                description="This lamp casts runtime shadows",
                                default=True)

    soft_region = StringProperty(name="Soft Volume",
                                 description="Soft region this light is active inside",
                                 options=set())

    # For LimitedDirLights
    size_height = FloatProperty(name="Height",
                               description="Size of the area for the Area Lamp in the Z direction",
                               min=0.0, default=200.0,
                               options=set())
