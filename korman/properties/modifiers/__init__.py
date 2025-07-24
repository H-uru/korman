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

from .base import PlasmaModifierProperties
from .anim import *
from .avatar import *
from .game_gui import *
from .gui import *
from .logic import *
from .physics import *
from .region import *
from .render import *
from .sound import *
from .water import *

# Check our mixins to ensure that the subclasses have them first in their MRO.
_mod_mixins = [game_gui._GameGuiMixin]
for mixin in _mod_mixins:
    for sub in mixin.__subclasses__():
        mro = sub.__mro__
        if mro.index(mixin) > mro.index(PlasmaModifierProperties):
            raise ImportError(
                f"{sub.__name__} base class {mixin.__name__} isn't properly "
                "overriding PlasmaModifierProperties!"
                )

class PlasmaModifiers(bpy.types.PropertyGroup):
    def determine_next_id(self):
        """Gets the ID for the next modifier in the UI"""
        # This is NOT a property, otherwise the modifiers property would access this...
        # Which acesses the modifiers property... INFINITE RECURSION! :D
        ids = [mod.display_order for mod in self.modifiers]
        if ids:
            return max(ids) + 1
        else:
            return 0

    @property
    def modifiers(self):
        """Generates all of the enabled modifiers.
           NOTE: We do not promise to return modifiers in their display_order!
        """
        for i in dir(self):
            attr = getattr(self, i, None)
            # Assumes each modifier is a single pointer to PlasmaModifierProperties
            if isinstance(attr, PlasmaModifierProperties):
                if attr.enabled:
                    yield attr

    @classmethod
    def register(cls):
        # Okay, so we have N plasma modifer property groups...
        # Rather than have (dis)organized chaos on the Blender Object, we will collect all of the
        #     property groups of type PlasmaModifierProperties and generate on-the-fly a PlasmaModifier
        #     property group to rule them all. The class attribute 'pl_id' will determine the name of
        #     the property group in PlasmaModifiers.
        # Also, just to spite us, Blender doesn't seem to handle PropertyGroup inheritance... at all.
        #     So, we're going to have to create our base properties on all of the PropertyGroups.
        #     It's times like these that make me wonder about life...
        # Enjoy!
        for i in PlasmaModifierProperties.__subclasses__():
            for name, (prop, kwargs) in PlasmaModifierProperties._subprops.items():
                setattr(i, name, prop(**kwargs))
            setattr(cls, i.pl_id, bpy.props.PointerProperty(type=i))
        bpy.types.Object.plasma_modifiers = bpy.props.PointerProperty(type=cls)

    def test_property(self, property : str) -> bool:
        """Tests a property on all enabled Plasma modifiers"""
        return any((getattr(i, property) for i in self.modifiers))


class PlasmaModifierSpec(bpy.types.PropertyGroup):
    pass

