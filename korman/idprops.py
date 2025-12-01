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

class IDPropMixin:
    """
    So, here's the rub.

    In Blender 2.79, we finally get the ability to use native Blender ID Datablock properties in Python.
    This is great! It will allow us to specify other objects (Blender Objects, Materials, Textures) in
    our plugin as pointer properties. Further, we can even specify a poll method to create a 'search list'
    of valid options.

    Naturally, there are some cons. The con here is that we've been storing object NAMES in string properties
    for several releases now. Therefore, the purpose of this class is simple... It is a mixin to be
    used for silently upgrading these object name properties to ID Properties. You will need to override
    the _idprop_mapping and _idprop_sources methods in your class. The mixin will handle upgrading
    the properties when a derived class is touched.

    Unfortunately, it is not possible to easily batch convert everything on load or save, due to issues
    in the way Blender's Python API functions. Long story short: PropertyGroups do not execute __new__
    or __init__. Furthermore, Blender's UI does not appreciate having ID Datablocks return from
    __getattribute__. To make matters worse, all properties are locked in a read-only state during
    the UI draw stage.
    """

    def __getattribute__(self, attr):
        _getattribute = super().__getattribute__

        # Let's make sure no one is trying to access an old version...
        if attr in _getattribute("_idprop_mapping")().values():
            raise AttributeError("'{}' has been deprecated... Please use the ID Property".format(attr))

        # I have some bad news for you... Unfortunately, this might have been called
        # during Blender's draw() context. Blender locks all properties during the draw loop.
        # HOWEVER!!! There is a solution. Upon inspection of the Blender source code, however, it
        # appears this restriction is temporarily suppressed during property getters... So let's get
        # a property that executes a getter :D
        # ...
        # ...
        # But why not simply proxy requests here, you ask? Ah, young grasshopper... This is the
        # fifth time I have (re-)written this code. Trust me when I say, 'tis a boondoggle.
        assert _getattribute("idprops_upgraded")

        # Must be something regular. Just super it.
        return super().__getattribute__(attr)

    def __setattr__(self, attr, value):
        idprops = super().__getattribute__("_idprop_mapping")()

        # Disallow any attempts to set the old string property
        if attr in idprops.values():
            raise AttributeError("'{}' has been deprecated... Please use the ID Property".format(attr))

        # Inappropriate touching?
        super().__getattribute__("_try_upgrade_idprops")()

        # Now, pass along our update
        super().__setattr__(attr, value)

    @classmethod
    def register(cls):
        if hasattr(super(), "register"):
            super().register()

        cls.idprops_upgraded = BoolProperty(name="INTERNAL: ID Property Upgrader HACK",
                                            description="HAAAX *throws CRT monitor*",
                                            get=cls._try_upgrade_idprops,
                                            options={"HIDDEN"})
        cls.idprops_upgraded_value = BoolProperty(name="INTERNAL: ID Property Upgrade Status",
                                                  description="Have old StringProperties been upgraded to ID Datablock Properties?",
                                                  default=False,
                                                  options={"HIDDEN"})
        for str_prop in cls._idprop_mapping().values():
            setattr(cls, str_prop, StringProperty(description="deprecated"))

    def _try_upgrade_idprops(self):
        _getattribute = super().__getattribute__

        if not _getattribute("idprops_upgraded_value"):
            idprop_map = _getattribute("_idprop_mapping")()
            strprop_src = _getattribute("_idprop_sources")()

            for idprop_name, strprop_name in idprop_map.items():
                if not super().is_property_set(strprop_name):
                    continue
                strprop_value = _getattribute(strprop_name)
                idprop_value = strprop_src[strprop_name].get(strprop_value, None)
                super().__setattr__(idprop_name, idprop_value)
                super().property_unset(strprop_name)
            super().__setattr__("idprops_upgraded_value", True)

        # you should feel like this now... https://youtu.be/1JBSs6MQJeI?t=33s
        return True


class IDPropObjectMixin(IDPropMixin):
    """Like IDPropMixin, but with the assumption that all IDs can be found in bpy.data.objects"""

    def _idprop_sources(self):
        # NOTE: bad problems result when using super() here, so we'll manually reference object
        cls = object.__getattribute__(self, "__class__")
        idprops = cls._idprop_mapping()
        return { i: bpy.data.objects for i in idprops.values() }


def poll_animated_objects(self, value):
    return value.plasma_object.has_animation_data

def poll_camera_objects(self, value):
    return value.type == "CAMERA"

def poll_drawable_objects(self, value):
    return value.type == "MESH" and any(value.data.materials)

def poll_dynamic_objects(self, value):
    return value.plasma_modifiers.collision.enabled and value.plasma_modifiers.collision.dynamic

def poll_empty_objects(self, value):
    return value.type == "EMPTY"

def poll_mesh_objects(self, value):
    return value.type == "MESH"

def poll_object_dyntexts(self, value):
    if value.type != "IMAGE":
        return False
    if value.image is not None:
        return False
    tex_materials = frozenset(value.users_material)
    obj_materials = frozenset(filter(None, (i.material for i in self.id_data.material_slots)))
    return bool(tex_materials & obj_materials)

def poll_object_image_textures(self, value):
    if value.type != "IMAGE":
        return False
    tex_materials = frozenset(value.users_material)
    obj_materials = frozenset(filter(None, (i.material for i in self.id_data.material_slots)))
    return bool(tex_materials & obj_materials)

def poll_softvolume_objects(self, value):
    return value.plasma_modifiers.softvolume.enabled

def poll_subworld_objects(self, value):
    return value.plasma_modifiers.subworld_def.enabled

def poll_visregion_objects(self, value):
    return value.plasma_modifiers.visregion.enabled

def poll_envmap_textures(self, value):
    return isinstance(value, bpy.types.EnvironmentMapTexture)

def triprop_material(object_attr: str, material_attr: str, texture_attr: str, **kwargs) -> bpy.types.Material:
    user_poll = kwargs.pop("poll", None)

    def poll_proc(self, value: bpy.types.Material) -> bool:
        target_object = getattr(self, object_attr)
        if target_object is None:
            target_object = getattr(self, "id_data", None)

        # Don't filter materials by texture - this would (potentially) result in surprising UX
        # in that you would have to clear the texture selection before being able to select
        # certain materials.
        if target_object is not None:
            object_materials = (slot.material for slot in target_object.material_slots if slot and slot.material)
            result = value in object_materials
        else:
            result = True

        # Downstream processing, if any.
        if result and user_poll is not None:
            result = user_poll(self, value)
        return result

    assert not "type" in kwargs
    return PointerProperty(
        type=bpy.types.Material,
        poll=poll_proc,
        **kwargs
    )

def triprop_object(object_attr: str, material_attr: str, texture_attr: str, **kwargs) -> bpy.types.Texture:
    assert not "type" in kwargs
    if not "poll" in kwargs:
        kwargs["poll"] = poll_drawable_objects
    return PointerProperty(
        type=bpy.types.Object,
        **kwargs
    )

def triprop_texture(object_attr: str, material_attr: str, texture_attr: str, **kwargs) -> bpy.types.Object:
    user_poll = kwargs.pop("poll", None)

    def poll_proc(self, value: bpy.types.Texture) -> bool:
        target_material = getattr(self, material_attr)
        target_object = getattr(self, object_attr)
        if target_object is None:
            target_object = getattr(self, "id_data", None)

        # must be a legal option... but is it a member of this material... or, if no material,
        # any of the materials attached to the object?
        if target_material is not None:
            result = value.name in target_material.texture_slots
        elif target_object is not None:
            for i in (slot.material for slot in target_object.material_slots if slot and slot.material):
                if value in (slot.texture for slot in i.texture_slots if slot and slot.texture):
                    result = True
                    break
            else:
                result = False
        else:
            result = False

        # Is it animated?
        if result and target_material is not None:
            result = (
                (target_material.animation_data is not None and target_material.animation_data.action is not None)
                or (value.animation_data is not None and value.animation_data.action is not None)
            )

        # Downstream processing, if any.
        if result and user_poll:
            result = user_poll(self, value)
        return result

    assert not "type" in kwargs
    return PointerProperty(
        type=bpy.types.Texture,
        poll=poll_proc,
        **kwargs
    )

@bpy.app.handlers.persistent
def _upgrade_node_trees(dummy):
    """
    Logic node haxxor incoming!
    Logic nodes appear to have issues with silently updating themselves. I expect that Blender is
    doing something strange in the UI code that causes our metaprogramming tricks to be bypassed.
    Therefore, we will loop through all Plasma node trees and forcibly update them on blend load.
    """

    for tree in bpy.data.node_groups:
        if tree.bl_idname != "PlasmaNodeTree":
            continue
        for node in tree.nodes:
            if isinstance(node, IDPropMixin):
                assert node._try_upgrade_idprops()
bpy.app.handlers.load_post.append(_upgrade_node_trees)
