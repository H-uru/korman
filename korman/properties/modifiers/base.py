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

import abc
from typing import Any, Dict, Generator

class PlasmaModifierProperties(bpy.types.PropertyGroup):
    @property
    def copy_material(self):
        """Materials MUST be single-user"""
        return False

    def created(self):
        pass

    def destroyed(self):
        pass

    @property
    def draw_opaque(self):
        """Render geometry before the avatar"""
        return False

    @property
    def draw_framebuf(self):
        """Render geometry after the avatar but before other blended geometry"""
        return False

    @property
    def draw_no_defer(self):
        """Disallow geometry being sorted into a blending span"""
        return False

    @property
    def enabled(self):
        return self.display_order >= 0

    def export(self, exporter, bo, so):
        """This is the main phase of the modifier export where most, if not all, PRP objects should
           be generated. No new Blender objects should be created unless their lifespan is constrained
           to the duration of this method.
        """
        pass

    @property
    def face_sort(self):
        """Indicates that the geometry's faces should be sorted by the engine"""
        return False

    def harvest_actors(self):
        return ()

    @property
    def key_name(self):
        return self.id_data.name

    @property
    def no_face_sort(self):
        """Indicates that the geometry's faces should never be sorted by the engine"""
        return False

    @property
    def no_span_sort(self):
        """Indicates that the geometry's Spans should never be sorted with those from other
           Drawables that will render in the same pass"""
        return False

    def pre_export(self, exporter, bo: bpy.types.Object) -> Generator:
        """This is the first phase of the modifier export; allowing modifiers to create additonal
           objects or logic nodes to be used by the exporter. To do so, overload this method
           and yield any Blender ID from your method. That ID will then be exported and deleted
           when the export completes. PRP objects should generally not be exported in this phase.
        """
        yield

    @property
    def requires_actor(self):
        """Indicates if this modifier requires the object to be a movable actor"""
        return False

    # Guess what?
    # You can't register properties on a base class--Blender isn't smart enough to do inheritance,
    # you see... So, we'll store our definitions in a dict and make those properties on each subclass
    # at runtime. What joy. Python FTW. See register() in __init__.py
    _subprops = {
        "display_order": (IntProperty, {"name": "INTERNAL: Display Ordering",
                                        "description": "Position in the list of buttons",
                                        "default": -1,
                                        "options": {"HIDDEN"}}),
        "show_expanded": (BoolProperty, {"name": "INTERNAL: Actually draw the modifier",
                                         "default": True,
                                         "options": {"HIDDEN"}}),
        "current_version": (IntProperty, {"name": "INTERNAL: Modifier version",
                                          "default": 1,
                                          "options": {"HIDDEN"}}),
    }


class PlasmaModifierLogicWiz:
    def convert_logic(self, bo, **kwargs):
        """Creates, converts, and returns an unmanaged NodeTree for this logic wizard. If the wizard
           fails during conversion, the temporary tree is deleted for you. However, on success, you
           are responsible for removing the tree from Blender, if applicable."""
        name = kwargs.pop("name", self.key_name)
        assert not "tree" in kwargs
        tree = bpy.data.node_groups.new(name, "PlasmaNodeTree")
        kwargs["tree"] = tree
        try:
            self.logicwiz(bo, **kwargs)
        except:
            bpy.data.node_groups.remove(tree)
            raise
        else:
            return tree

    def _create_python_file_node(self, tree, filename: str, attributes: Dict[str, Any]) -> bpy.types.Node:
        pfm_node = tree.nodes.new("PlasmaPythonFileNode")
        with pfm_node.NoUpdate():
            pfm_node.filename = filename
            for attr in attributes:
                new_attr = pfm_node.attributes.add()
                new_attr.attribute_id = attr["id"]
                new_attr.attribute_type = attr["type"]
                new_attr.attribute_name = attr["name"]
        pfm_node.update()
        return pfm_node

    @abc.abstractmethod
    def logicwiz(self, bo, tree):
        pass

    def pre_export(self, exporter, bo):
        """Default implementation of the pre_export phase for logic wizards that simply triggers
           the logic nodes to be created and for their export to be scheduled."""
        yield self.convert_logic(bo)


class PlasmaModifierUpgradable:
    @property
    @abc.abstractmethod
    def latest_version(self):
        raise NotImplementedError()

    @property
    def requires_upgrade(self):
        current_version, latest_version = self.current_version, self.latest_version
        assert current_version <= latest_version
        return current_version < latest_version

    @abc.abstractmethod
    def upgrade(self):
        raise NotImplementedError()


@bpy.app.handlers.persistent
def _restore_properties(dummy):
    # When Blender opens, it loads the default blend. The post load handler
    # below is executed and deprecated properties are unregistered. When the
    # user goes to load a new blend file, the handler below tries to execute
    # again and BOOM--there are no deprecated properties available. Therefore,
    # we reregister them here.
    for mod_cls in PlasmaModifierUpgradable.__subclasses__():
        for prop_name in mod_cls.deprecated_properties:
            # Unregistered propertes are a sequence of (property function,
            # property keyword arguments). Interesting design decision :)
            prop_cb, prop_kwargs = getattr(mod_cls, prop_name)
            del prop_kwargs["attr"] # Prevents proper registration
            setattr(mod_cls, prop_name, prop_cb(**prop_kwargs))
bpy.app.handlers.load_pre.append(_restore_properties)

@bpy.app.handlers.persistent
def _upgrade_modifiers(dummy):
    # First, run all the upgrades
    for i in bpy.data.objects:
        for mod_cls in PlasmaModifierUpgradable.__subclasses__():
            mod = getattr(i.plasma_modifiers, mod_cls.pl_id)
            if mod.requires_upgrade:
                mod.upgrade()

    # Now that everything is upgraded, forcibly remove all properties
    # from the modifiers to prevent sneaky zombie-data type export bugs
    for mod_cls in PlasmaModifierUpgradable.__subclasses__():
        for prop in mod_cls.deprecated_properties:
            RemoveProperty(mod_cls, attr=prop)
bpy.app.handlers.load_post.append(_upgrade_modifiers)
