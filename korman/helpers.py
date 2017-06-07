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
import math

class GoodNeighbor:
    """Leave Things the Way You Found Them! (TM)"""

    def __enter__(self):
        self._tracking = {}
        return self

    def track(self, cls, attr, value):
        if (cls, attr) not in self._tracking:
            self._tracking[(cls, attr)] = getattr(cls, attr)
        setattr(cls, attr, value)

    def __exit__(self, type, value, traceback):
        for (cls, attr), value in self._tracking.items():
            setattr(cls, attr, value)


class TemporaryObject:
    def __init__(self, obj, remove_func):
        self._obj = obj
        self._remove_func = remove_func

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self._remove_func(self._obj)

    def __getattr__(self, attr):
        return getattr(self._obj, attr)


def ensure_power_of_two(value):
    return pow(2, math.floor(math.log(value, 2)))


def find_modifier(bo, modid):
    """Given a Blender Object, finds a given modifier and returns it or None"""
    if bo is not None:
        # if they give us the wrong modid, it is a bug and an AttributeError
        return getattr(bo.plasma_modifiers, modid)
    return None
