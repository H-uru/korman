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

from .prop_lamp import *
from . import modifiers
from .prop_object import *
from .prop_texture import *
from .prop_world import *


def register():
    bpy.types.Lamp.plasma_lamp = bpy.props.PointerProperty(type=PlasmaLamp)
    bpy.types.Object.plasma_net = bpy.props.PointerProperty(type=PlasmaNet)
    bpy.types.Object.plasma_object = bpy.props.PointerProperty(type=PlasmaObject)
    bpy.types.Texture.plasma_layer = bpy.props.PointerProperty(type=PlasmaLayer)
    bpy.types.World.plasma_age = bpy.props.PointerProperty(type=PlasmaAge)
    bpy.types.World.plasma_fni = bpy.props.PointerProperty(type=PlasmaFni)
