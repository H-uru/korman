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
    if "default" not in kwargs:
        kwargs["default"] = "hull"
    return EnumProperty(
        items=_bounds_types,
        **kwargs
    )
