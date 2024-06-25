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

from __future__ import annotations

from bpy.props import *

from typing import *
import warnings

# These are the kinds of physical bounds Plasma can work with.
# This sequence is acceptable in any EnumProperty
_bounds_types = (
    ("box", "Bounding Box", "Use a perfect bounding box"),
    ("sphere", "Bounding Sphere", "Use a perfect bounding sphere"),
    ("hull", "Convex Hull", "Use a convex set encompasing all vertices"),
    ("trimesh", "Triangle Mesh", "Use the exact triangle mesh (SLOW!)")
)

def _bounds_type_index(key: str) -> int:
    return list(zip(*_bounds_types))[0].index(key)

def _bounds_type_str(idx: int) -> str:
    return _bounds_types[idx][0]

def _get_bounds(physics_attr: Optional[str]) -> Callable[[Any], int]:
    def getter(self) -> int:
        physics_object = getattr(self, physics_attr) if physics_attr is not None else self.id_data
        if physics_object is not None:
            return _bounds_type_index(physics_object.plasma_modifiers.collision.bounds)
        return _bounds_type_index("hull")
    return getter

def _set_bounds(physics_attr: Optional[str]) -> Callable[[Any, int], None]:
    def setter(self, value: int):
        physics_object = getattr(self, physics_attr) if physics_attr is not None else self.id_data
        if physics_object is not None:
            physics_object.plasma_modifiers.collision.bounds = _bounds_type_str(value)
    return setter

def bounds(physics_attr: Optional[str] = None, store_on_collider: bool = True, **kwargs) -> str:
    assert not {"items", "get", "set"} & kwargs.keys(), "You cannot use the `items`, `get`, or `set` keyword arguments"
    if store_on_collider:
        kwargs["get"] = _get_bounds(physics_attr)
        kwargs["set"] = _set_bounds(physics_attr)
    else:
        warnings.warn("Storing bounds properties outside of the collision modifier is deprecated.", category=DeprecationWarning)
    if "default" not in kwargs:
        kwargs["default"] = "hull"
    return EnumProperty(
        items=_bounds_types,
        **kwargs
    )

def upgrade_bounds(bl, bounds_attr: str) -> None:
    # Only perform this process if the property has a value. Otherwise, we'll
    # wind up blowing away the collision modifier's settings with nonsense.
    if not bl.is_property_set(bounds_attr):
        return

    # Before we unregister anything, grab a copy of what the collision modifier currently thinks.
    bounds_value_curr = getattr(bl, bounds_attr)

    # So, here's the deal. If someone has been playing with nodes and changed the bounds type,
    # Blender will think the property has been set, even if they wound up with the property
    # at the default value. I don't know that we can really trust the default in the property
    # definition to be the same as the old default (they shouldn't be different, but let's be safe).
    # So, let's apply rough justice. If the destination property thinks it's a triangle mesh, we
    # don't need to blow that away - it's a very specific non default setting.
    if bounds_value_curr == "trimesh":
        return

    # Unregister the new/correct proxy bounds property (with getter/setter) and re-register
    # the property without the proxy functions to get the old value. Reregister the new property
    # again and set it.
    cls = bl.__class__
    prop_func, prop_def = getattr(cls, bounds_attr)
    RemoveProperty(cls, attr=bounds_attr)
    del prop_def["attr"]

    # Remove the things we don't want in a copy to prevent hosing the new property.
    old_prop_def = dict(prop_def)
    del old_prop_def["get"]
    del old_prop_def["set"]
    setattr(cls, bounds_attr, prop_func(**old_prop_def))
    bounds_value_new = getattr(bl, bounds_attr)

    # Re-register new property.
    RemoveProperty(cls, attr=bounds_attr)
    setattr(cls, bounds_attr, prop_func(**prop_def))

    # Only set the property if the value different to avoid thrashing and log spam.
    if bounds_value_curr != bounds_value_new:
        print(f"Stashing bounds property: [{bl.name}] ({cls.__name__}) {bounds_value_curr} -> {bounds_value_new}") # TEMP
        setattr(bl, bounds_attr, bounds_value_new)
