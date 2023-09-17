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

import bmesh
import bpy
from contextlib import contextmanager
import math
from typing import *

@contextmanager
def bmesh_from_object(bl):
    """Converts a Blender Object to a BMesh with modifiers applied."""
    mesh = bmesh.new()
    try:
        # Empirical evidence indicates that this applies Blender Modifiers
        mesh.from_object(bl, bpy.context.scene)
        yield mesh
    finally:
        mesh.free()

def copy_action(source):
    if source is not None and source.animation_data is not None and source.animation_data.action is not None:
        source.animation_data.action = source.animation_data.action.copy()
        return source.animation_data.action

def copy_object(bl, name: Optional[str] = None):
    dupe_object = bl.copy()
    if name is not None:
        dupe_object.name = name
    bpy.context.scene.objects.link(dupe_object)
    return dupe_object

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


@contextmanager
def TemporaryCollectionItem(collection):
    item = collection.add()
    try:
        yield item
    finally:
        index = next((i for i, j in enumerate(collection) if j == item), None)
        if index is not None:
            collection.remove(index)

class TemporaryObject:
    def __init__(self, obj, remove_func):
        self._obj = obj
        self._remove_func = remove_func

    def __enter__(self):
        return self._obj

    def __exit__(self, type, value, traceback):
        self._remove_func(self._obj)

    def __getattr__(self, attr):
        return getattr(self._obj, attr)


class UiHelper:
    """This fun little helper makes sure that we don't wreck the UI"""
    def __init__(self, context):
        self.active_object = context.active_object
        self.selected_objects = context.selected_objects

    def __enter__(self):
        scene = bpy.context.scene
        self.layers = tuple(scene.layers)
        self.frame_num = scene.frame_current
        scene.frame_set(scene.frame_start)
        scene.update()

        # Some operators require there be an active_object even though they
        # don't actually use it...
        if scene.objects.active is None:
            scene.objects.active = scene.objects[0]
        return self

    def __exit__(self, type, value, traceback):
        for i in bpy.data.objects:
            i.select = (i in self.selected_objects)

        scene = bpy.context.scene
        scene.objects.active = self.active_object
        scene.layers = self.layers
        scene.frame_set(self.frame_num)
        scene.update()


def ensure_power_of_two(value):
    return pow(2, math.floor(math.log(value, 2)))

def fetch_fcurves(id_data, data_fcurves=True):
    """Given a Blender ID, yields its FCurves"""
    def _fetch(source):
        if source is not None and source.action is not None:
            for i in source.action.fcurves:
                yield i

    # This seems rather unpythonic IMO
    for i in _fetch(id_data.animation_data):
        yield i
    if data_fcurves:
        for i in _fetch(id_data.data.animation_data):
            yield i

def find_modifier(bo, modid):
    """Given a Blender Object, finds a given modifier and returns it or None"""
    if bo is not None:
        # if they give us the wrong modid, it is a bug and an AttributeError
        return getattr(bo.plasma_modifiers, modid)
    return None

def get_page_type(page: str) -> str:
    all_pages = bpy.context.scene.world.plasma_age.pages
    if page:
        page_type = next((i.page_type for i in all_pages if i.name == page), None)
        if page_type is None:
            raise LookupError(page)
        return page_type
    else:
        # A falsey page name is likely a request for the default page, so look for Page ID 0.
        # If it doesn't exist, that's an implicit default page (a "room" type).
        page_type = next((i.page_type for i in all_pages if i.seq_suffix == 0), None)
        return page_type if page_type is not None else "room"
