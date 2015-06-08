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

import abc
import bpy
from bpy.props import *

class PlasmaModifierProperties(bpy.types.PropertyGroup):
    def created(self, obj):
        # This is here just to prevent us from having unnamed modifiers
        self.display_name = "{}Modifier{}".format(obj.name, self.display_order)

    def destroyed(self):
        pass

    @property
    def enabled(self):
        return self.display_order >= 0

    @property
    def requires_actor(self):
        """Indicates if this modifier requires the object to be a movable actor"""
        return False

    # Guess what?
    # You can't register properties on a base class--Blender isn't smart enough to do inheritance,
    # you see... So, we'll store our definitions in a dict and make those properties on each subclass
    # at runtime. What joy. Python FTW. See register() in __init__.py
    _subprops = {
        "display_name": (StringProperty, {"name": "Name",
                                          "description": "Modifier name"}),
        "display_order": (IntProperty, {"name": "INTERNAL: Display Ordering",
                                        "description": "Position in the list of buttons",
                                        "default": -1,
                                        "options": {"HIDDEN"}}),
        "show_expanded": (BoolProperty, {"name": "INTERNAL: Actually draw the modifier",
                                         "default": True,
                                         "options": {"HIDDEN"}})
    }


class PlasmaModifierLogicWiz:
    @property
    def node_tree(self):
        name = "LOGICWIZ_{}".format(self.display_name)
        try:
            return bpy.data.node_groups[name]
        except LookupError:
            return bpy.data.node_groups.new(name, "PlasmaNodeTree")

    @abc.abstractmethod
    def logicwiz(self, bo):
        pass
