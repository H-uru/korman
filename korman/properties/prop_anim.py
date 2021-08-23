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

from PyHSPlasma import *

from copy import deepcopy
import functools
import itertools
from typing import Iterable, Iterator

class PlasmaAnimation(bpy.types.PropertyGroup):
    ENTIRE_ANIMATION = "(Entire Animation)"

    def _get_animation_name(self):
        if self.is_entire_animation:
            return self.ENTIRE_ANIMATION
        else:
            return self.animation_name_value

    def _set_animation_name(self, value):
        if not self.is_entire_animation:
            self.animation_name_value = value

    _PROPERTIES = {
        "animation_name": {
            "type": StringProperty,
            "property": {
                "name": "Animation Name",
                "description": "Name of this (sub-)animation",
                "get": _get_animation_name,
                "set": _set_animation_name,
            },
        },
        "start": {
            "type": IntProperty,
            "property": {
                "name": "Start",
                "description": "The first frame of this (sub-)animation",
                "soft_min": 0,
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.begin",
                bpy.types.Texture: "plasma_layer.anim_begin",
            },
        },
        "end": {
            "type": IntProperty,
            "property": {
                "name": "End",
                "description": "The last frame of this (sub-)animation",
                "soft_min": 0,
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.end",
                bpy.types.Texture: "plasma_layer.anim_end",
            },
        },
        "auto_start": {
            "type": BoolProperty,
            "property": {
                "name": "Auto Start",
                "description": "Automatically start this animation on link-in",
                "default": True,
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.auto_start",
                bpy.types.Texture: "plasma_layer.anim_auto_start",
            },
        },
        "loop": {
            "type": BoolProperty,
            "property": {
                "name": "Loop Anim",
                "description": "Loop the animation",
                "default": True,
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.loop",
                bpy.types.Texture: "plasma_layer.anim_loop",
            },
        },
        "initial_marker": {
            "type": StringProperty,
            "property": {
                "name": "Start Marker",
                "description": "Marker indicating the default start point",
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.initial_marker",
                bpy.types.Texture: "plasma_layer.anim_initial_marker",
            }
        },
        "loop_start": {
            "type": StringProperty,
            "property": {
                "name": "Loop Start",
                "description": "Marker indicating where the default loop begins",
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.loop_start",
                bpy.types.Texture: "plasma_layer.anim_loop_start",
            },
        },
        "loop_end": {
            "type": StringProperty,
            "property": {
                "name": "Loop End",
                "description": "Marker indicating where the default loop ends",
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.loop_end",
                bpy.types.Texture: "plasma_layer.anim_loop_end",
            },
        },
        "sdl_var": {
            "type": StringProperty,
            "property": {
                "name": "SDL Variable",
                "description": "Name of the SDL variable to use to control the playback of this animation",
            },
            "entire_animation": {
                bpy.types.Object: "plasma_modifiers.animation.obj_sdl_anim",
                bpy.types.Texture: "plasma_layer.anim_sdl_var",
            },
        },
    }

    @classmethod
    def iter_frame_numbers(cls, id_data) -> Iterator[int]:
        # It would be nice if this could use self.iter_fcurves, but the property that uses this
        # is not actually of type PlasmaAnimation. Meaning that self is some other object (great).
        fcurves = itertools.chain.from_iterable((id.animation_data.action.fcurves
                                                 for id in cls._iter_my_ids(id_data)
                                                 if id.animation_data and id.animation_data.action))
        frame_numbers = (keyframe.co[0] for fcurve in fcurves for keyframe in fcurve.keyframe_points)
        yield from frame_numbers

    @classmethod
    def _iter_my_ids(cls, id_data: bpy.types.ID) -> Iterator[bpy.types.ID]:
        yield id_data
        if isinstance(id_data, bpy.types.Object):
            if id_data.data is not None:
                yield id_data.data
        elif isinstance(id_data, bpy.types.Texture):
            material = getattr(bpy.context, "material", None)
            if material is not None and material in id_data.users_material:
                yield material

    def _get_entire_start(self) -> int:
        try:
            return min(PlasmaAnimation.iter_frame_numbers(self.id_data))
        except ValueError:
            return 0

    def _get_entire_end(self) -> int:
        try:
            return max(PlasmaAnimation.iter_frame_numbers(self.id_data))
        except ValueError:
            return 0

    def _set_dummy(self, value: int) -> None:
        pass

    _ENTIRE_ANIMATION_PROPERTIES = {
        "start": {
            "get": _get_entire_start,
            "set": _set_dummy,
        },
        "end": {
            "get": _get_entire_end,
            "set": _set_dummy,
        },
    }

    @classmethod
    def _get_from_class_lut(cls, id_data, lut):
        # This is needed so that things like bpy.types.ImageTexture can map to bpy.types.Texture.
        # Note that only one level of bases is attempted. Right now, that is sufficient for our
        # use case and what Blender does, but beware in the future.
        for i in itertools.chain((id_data.__class__,), id_data.__class__.__bases__):
            value = lut.get(i)
            if value is not None:
                return value

    @classmethod
    def _make_prop_getter(cls, prop_name: str, lut, default=None):
        def proc(self):
            if self.is_entire_animation:
                attr_path = cls._get_from_class_lut(self.id_data, lut)
                if attr_path is not None:
                    prop_delim = attr_path.rfind('.')
                    prop_group = self.id_data.path_resolve(attr_path[:prop_delim])
                    return getattr(prop_group, attr_path[prop_delim+1:])
                else:
                    return default
            else:
                return getattr(self, "{}_value".format(prop_name))
        return proc

    @classmethod
    def _make_prop_setter(cls, prop_name: str, lut):
        def proc(self, value):
            if self.is_entire_animation:
                attr_path = cls._get_from_class_lut(self.id_data, lut)
                if attr_path is not None:
                    prop_delim = attr_path.rfind('.')
                    prop_group = self.id_data.path_resolve(attr_path[:prop_delim])
                    setattr(prop_group, attr_path[prop_delim+1:], value)
            else:
                setattr(self, "{}_value".format(prop_name), value)
        return proc

    @classmethod
    def register(cls):
        # Register accessor and storage properties on this property group - we need these to be
        # separate because the old style single animation per-ID settings should map to the new
        # "(Entire Animation)" sub-animation. This will allow us to "trivially" allow downgrading
        # to previous Korman versions without losing data.
        for prop_name, definitions in cls._PROPERTIES.items():
            props, kwargs = definitions["property"], {}
            if "options" not in props:
                kwargs["options"] = set()

            value_kwargs = deepcopy(kwargs)
            value_kwargs["options"].add("HIDDEN")
            value_props = { key: value for key, value in props.items() if key not in {"get", "set", "update"} }
            setattr(cls, "{}_value".format(prop_name), definitions["type"](**value_props, **value_kwargs))

            needs_accessors = "get" not in props and "set" not in props
            if needs_accessors:
                # We have to use these weirdo wrappers because Blender only accepts function objects
                # for its property callbacks, not arbitrary callables eg lambdas, functools.partials.
                kwargs["get"] = cls._make_prop_getter(prop_name, definitions["entire_animation"], props.get("default"))
                kwargs["set"] = cls._make_prop_setter(prop_name, definitions["entire_animation"])
            setattr(cls, prop_name, definitions["type"](**props, **kwargs))

    @classmethod
    def register_entire_animation(cls, id_type, rna_type):
        """Registers all of the properties for the old style single animation per ID animations onto
           the property group given by `rna_type`. These were previously directly registered but are
           now abstracted away to serve as the backing store for the new "entire animation" method."""
        for prop_name, definitions in cls._PROPERTIES.items():
            lut = definitions.get("entire_animation", {})
            path_from_id = lut.get(id_type)
            if path_from_id:
                attr_name = path_from_id[path_from_id.rfind('.')+1:]
                kwargs = deepcopy(definitions["property"])
                kwargs.update(cls._ENTIRE_ANIMATION_PROPERTIES.get(prop_name, {}))
                setattr(rna_type, attr_name, definitions["type"](**kwargs))

    is_entire_animation = BoolProperty(default=False, options={"HIDDEN"})


class PlasmaAnimationCollection(bpy.types.PropertyGroup):
    """The magical turdfest!"""

    def _get_active_index(self) -> int:
        # Remember: this is bound to an impostor object by Blender's rna system
        PlasmaAnimationCollection._ensure_default_animation(self)
        return self.active_animation_index_value

    def _set_active_index(self, value: int) -> None:
        self.active_animation_index_value = value

    active_animation_index = IntProperty(get=_get_active_index, set=_set_active_index,
                                         options={"HIDDEN"})
    active_animation_index_value = IntProperty(options={"HIDDEN"})

    # Animations backing store--don't use this except to display the list in Blender's UI.
    animation_collection = CollectionProperty(type=PlasmaAnimation)

    def _get_hack(self):
        if not any((i.is_entire_animation for i in self.animation_collection)):
            entire_animation = self.animation_collection.add()
            entire_animation.is_entire_animation = True
        return True

    def _set_hack(self, value):
        raise RuntimeError("Don't set this.")

    # Blender locks properties to a read-only state during the UI draw phase. This is a problem
    # because we may need to initialize a default animation (or the entire animation) when we
    # want to observe it in the UI. That restriction is dropped, however, when RNA poperties are
    # being observed or set. So, this will allow us to initialize the entire animation in the
    # UI phase at the penalty of potentially having to loop through the animation collection twice.
    request_entire_animation = BoolProperty(get=_get_hack, set=_set_hack, options={"HIDDEN"})

    @property
    def animations(self) -> Iterable[PlasmaAnimation]:
        self._ensure_default_animation()
        return self.animation_collection

    def __iter__(self) -> Iterator[PlasmaAnimation]:
        return iter(self.animations)

    def _ensure_default_animation(self) -> None:
        if not bool(self.animation_collection):
            assert self.request_entire_animation

    @property
    def entire_animation(self) -> PlasmaAnimation:
        assert self.request_entire_animation
        return next((i for i in self.animation_collection if i.is_entire_animation))

    @classmethod
    def register_entire_animation(cls, id_type, rna_type):
        # Forward helper so we can get away with only importing this klass
        PlasmaAnimation.register_entire_animation(id_type, rna_type)
