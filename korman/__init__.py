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
from . import exporter, render
from . import properties, ui
from . import operators

bl_info = {
    "name":        "Korman",
    "author":      "Guild of Writers",
    "blender":     (2, 71, 0),  # I can't be bothered to support old stuff
    "location":    "File > Import-Export",
    "description": "Exporter for Cyan Worlds' Plasma Engine",
    "warning":     "alpha",
    "category":    "System",  # Eventually, we will hide some of the default
                              # Blender panels (think materials)
}


def register():
    """Registers all Blender operators and GUI items in Korman"""

    # This will auto-magically register all blender classes for us
    bpy.utils.register_module(__name__)

    # Sigh... Blender isn't totally automated.
    operators.register()
    properties.register()


def unregister():
    """Unregisters all Blender operators and GUI items"""
    bpy.utils.unregister_module(__name__)
    operators.unregister()


if __name__ == "__main__":
    register()
