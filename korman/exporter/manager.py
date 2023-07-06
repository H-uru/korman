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

import bpy
from PyHSPlasma import *
from typing import *
import weakref

from . import explosions
from ..korlib import replace_python2_identifier
from ..plasma_magic import *

# These objects have to be in the plSceneNode pool in order to be loaded...
# NOTE: We are using Factory indices because I doubt all of these classes are implemented.
_pool_types = (
    plFactory.ClassIndex("plPostEffectMod"),
    plFactory.ClassIndex("pfGUIDialogMod"),
    plFactory.ClassIndex("plMsgForwarder"),
    plFactory.ClassIndex("plClothingItem"),
    plFactory.ClassIndex("plArmatureEffectFootSound"),
    plFactory.ClassIndex("plDynaFootMgr"),
    plFactory.ClassIndex("plDynaRippleMgr"),
    plFactory.ClassIndex("plDynaBulletMgr"),
    plFactory.ClassIndex("plDynaPuddleMgr"),
    plFactory.ClassIndex("plATCAnim"),
    plFactory.ClassIndex("plEmoteAnim"),
    plFactory.ClassIndex("plDynaRippleVSMgr"),
    plFactory.ClassIndex("plDynaTorpedoMgr"),
    plFactory.ClassIndex("plDynaTorpedoVSMgr"),
    plFactory.ClassIndex("plClusterGroup"),
)


class ExportManager:
    """Friendly resource-managing helper class."""

    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self.mgr = plResManager()
        self.mgr.setVer(globals()[exporter._op.version])

        self._nodes = {}
        self._pages = {}
        self._keys = {}

        # cheap inheritance
        for i in dir(self.mgr):
            if not hasattr(self, i):
                setattr(self, i, getattr(self.mgr, i))

    def AddAge(self, info):
        # There's only ever one age being exported, so hook the call and hang onto the plAgeInfo
        # We'll save from our reference later. Forget grabbing this from C++
        self._age_info = info
        self.mgr.AddAge(info)

    def AddObject(self, location, obj):
        """Overloads the plResManager AddObject so we can insert the object into our hashtable"""
        key = obj.key
        self._keys[(location, obj.__class__, key.name)] = key
        self.mgr.AddObject(location, obj)

    def add_object(self, pl, name=None, bl=None, loc=None, so=None):
        """Automates adding a converted Blender object to our Plasma Resource Manager"""
        if loc is not None:
            location = loc
        elif so is not None:
            location = so.key.location
        elif bl is not None:
            page_name = bl.plasma_object.page
            location = self._pages.get(page_name)

            # location can be None if we've been passed an object in a disabled page, or, in some
            # cases, a disabled object in the default page. If we got this far, someone is demanding
            # that this object be created, so we need its page to exist, no matter what the user
            # otherwise requested.
            if location is None:
                location = self._force_create_page(page_name, bl.name)
        else:
            raise ValueError("bl, so, or loc must be specified.")

        # pl can be a class or an instance.
        # This is one of those "sanity" things to ensure we don't suddenly startpassing around the
        # key of an uninitialized object.
        if isinstance(pl, type(object)):
            assert name or bl or so
            if name is None:
                if bl is not None:
                    name = bl.name
                else:
                    name = so.key.name
            assert issubclass(pl, hsKeyedObject)
            pl = pl(self._fixup_key_name(pl, name))

        self.AddObject(location, pl)
        node = self._nodes[location]
        if node: # All objects must be in the scene node
            if isinstance(pl, plSceneObject):
                node.addSceneObject(pl.key)
                pl.sceneNode = node.key
            elif pl.ClassIndex() in _pool_types:
                node.addPoolObject(pl.key)

        if so is None and isinstance(pl, (plObjInterface, plModifier)):
            assert bl

            # Don't use find_create_object because we want to specify the location... Also, we're
            # in a modifier, so the name we're given might be for a modifier, not the SO
            key = self.find_key(plSceneObject, bl)
            if key is None:
                so = self.add_object(plSceneObject, bl=bl, loc=location)
            else:
                so = key.object

        if isinstance(pl, plObjInterface):
            pl.owner = so.key

            # The things I do to make life easy... This is something of a God function now.
            if isinstance(pl, plAudioInterface):
                so.audio = pl.key
            elif isinstance(pl, plCoordinateInterface):
                so.coord = pl.key
            elif isinstance(pl, plDrawInterface):
                so.draw = pl.key
            elif isinstance(pl, plSimulationInterface):
                so.sim = pl.key
            elif pl.ClassIndex() not in _pool_types:
                so.addInterface(pl.key)
        elif isinstance(pl, plModifier) and pl.ClassIndex() not in _pool_types:
            so.addModifier(pl.key)

        # And we're done!
        return pl

    def create_builtins(self, age, textures):
        # WARNING: Path of the Shell expects for all builtin pages to be at bare minimum
        #          present and valid. They do not have to have any contents. See AvatarCustomization.
        # BuiltIn.prp
        want_pysdl = bpy.context.scene.world.plasma_age.age_sdl
        builtin = self.create_page(age, "BuiltIn", -2, builtin=True)
        if want_pysdl:
            self._pack_agesdl_hook(age)
            sdl = self.add_object(plSceneObject, name="AgeSDLHook", loc=builtin)
            pfm = self.add_object(plPythonFileMod, name="VeryVerySpecialPythonFileMod", so=sdl)
            pfm.filename = replace_python2_identifier(age)

        # Textures.prp
        # FIXME: unconditional creation will overwrite any existing textures PRP. This should
        # be addressed by a successful implementation of #145.
        self.create_page(age, "Textures", -1, builtin=True)

    def create_page(self, age, name, id, *, builtin=False, external=False):
        location = plLocation(self.mgr.getVer())
        location.prefix = bpy.context.scene.world.plasma_age.seq_prefix
        if builtin:
            location.flags |= plLocation.kBuiltIn
        location.page = id
        if not external:
            self._pages[name] = location

        # If the page ID is 0, this is the default page... Any page with an empty string name
        # is the default, so bookmark it!
        if id == 0:
            assert not external, "The default page cannot be external!"
            self._pages[""] = location

        if not external:
            info = plPageInfo()
            info.age = age
            info.page = name
            info.location = location
            self.mgr.AddPage(info)

        if not builtin:
            self._age_info.addPage((name, id, 0))
            if not external:
                if self.getVer() <= pvPots:
                    node = plSceneNode(f"{age}_District_{name}")
                else:
                    node = plSceneNode(f"{age}_{name}")
                self.mgr.AddObject(location, node)
            else:
                node = None
        else:
            node = None

        self._nodes[location] = node
        return location

    @property
    def _encryption(self):
        if self.mgr.getVer() == pvEoa:
            return plEncryptedStream.kEncAes
        else:
            return plEncryptedStream.kEncXtea

    def find_interfaces(self, pClass, so : plSceneObject) -> Iterable[plObjInterface]:
        assert issubclass(pClass, plObjInterface)

        for i in (i.object for i in so.interfaces):
            if isinstance(i, pClass):
                yield i

    def find_create_key(self, pClass: Type[KeyedT], bl=None, name=None, so=None) -> plKey[KeyedT]:
        key = self.find_key(pClass, bl, name, so)
        if key is None:
            key = self.add_object(pl=pClass, name=name, bl=bl, so=so).key
        return key

    def find_key(self, pClass: Type[KeyedT], bl=None, name=None, so=None, loc=None) -> Optional[plKey[KeyedT]]:
        """Given a blender Object and a Plasma class, find (or create) an exported plKey"""
        if loc is not None:
            location = loc
        elif so is not None:
            location = so.key.location
        elif bl is not None:
            location = self._pages.get(bl.plasma_object.page)
            if location is None:
                # This page has never been created, so the key search will obviously fail.
                return None
        else:
            raise ValueError("bl, so, or loc must be specified.")

        if name is None:
            if bl is not None:
                name = bl.name
            else:
                name = so.key.name
        name = self._fixup_key_name(pClass, name)

        key = self._keys.get((location, pClass, name), None)
        if key is not None and so is not None:
            # Purposefully not checking for plObjInterface -- they should never be shared.
            if issubclass(pClass, plModifier):
                if key not in so.modifiers:
                    # We really shouldn't add plSingleModifiers to multiple objects. This may
                    # potentially cause URU to crash. I'm uncertain though, so we'll just warn
                    # for now.
                    if issubclass(pClass, plSingleModifier):
                        self._exporter().report.warn("Adding SingleModifier '{}' (type: '{}'') to another SceneObject '{}'",
                                                     key.name, pClass.__name__[2:], so.key.name)
                    so.addModifier(key)
        return key

    def find_create_object(
            self, pClass: Type[KeyedT], bl: bpy.types.Object = None,
            name: Optional[str] = None, so: Optional[plSceneObject] = None
        ) -> KeyedT:
        key = self.find_key(pClass, bl, name, so)
        if key is None:
            return self.add_object(pl=pClass, name=name, bl=bl, so=so)
        return key.object

    def find_object(self, pClass: Type[KeyedT], bl=None, name=None, so=None, loc=None) -> Optional[KeyedT]:
        key = self.find_key(pClass, bl, name, so, loc)
        if key is not None:
            return key.object
        return None

    def _fixup_key_name(self, pClass, name):
        if pClass in {plSceneObject, plPythonFileMod}:
            return replace_python2_identifier(name)
        return name

    def _force_create_page(self, page_name: str, requestor_name: str) -> plLocation:
        """Forcibly creates a page (that you KNOW does not exist yet) during the convert process."""
        age_name = self._exporter().age_name
        if page_name:
            # This page has a name, but hasn't yet been created.
            self._exporter().report.warn(
                "'{}': trying to export into an unknown, potentially disabled page '{}'. Attempting to create it.",
                requestor_name,
                page_name
            )
            age_info = bpy.context.scene.world.plasma_age
            page_info = next((i for i in age_info.pages if i.name == page_name), None)
            if page_info is None:
                error = explosions.UndefinedPageError()
                error.add(page_name, requestor_name)
                error.raise_if_error()
            location = self.create_page(age_name, page_name, page_info.id)
        else:
            # This is a default page that wasn't exported... for some reason...
            self._exporter().report.warn(
                "'{}': trying to export into the default page, but it seems to not exist. Attempting to create it.",
                requestor_name
            )

            # See if a default page exists by name. That means that it doesn't have ID = 0.
            location = next((j for i, j in self._pages.items() if i.lower() == "default"), None)
            if location is None:
                # OK, we can be fairly certain that page ID 0 and page name "Default" don't exist.
                location = self.create_page(age_name, "Default", 0)
            else:
                # Avoid doing this stupid lookup in the future.
                self._pages[""] = location
        return location

    def get_location(self, bl) -> plLocation:
        """Returns the Page Location of a given Blender Object"""
        return self._pages[bl.plasma_object.page]

    def get_scene_node(
            self, location: Optional[plLocation] = None,
            bl: Optional[bpy.types.Object]=None
        ) -> plKey[plSceneNode]:
        """Gets a Plasma Page's plSceneNode key"""
        assert (location is not None) ^ (bl is not None)

        if location is None:
            location = self._pages[bl.plasma_object.page]
        return self._nodes[location].key

    def get_textures_page(self, key: plKey) -> plLocation:
        """Gets the appropriate page for a texture for a given plLayer"""
        # The point of this is to account for per-page textures...
        if bpy.context.scene.world.plasma_age.use_texture_page:
            return self._pages["Textures"]
        else:
            return key.location

    def _pack_agesdl_hook(self, age):
        output = self._exporter().output

        def get_text(name):
            namei = name.lower()
            generator = (i for i in bpy.data.texts if i.name.lower() == namei)
            result, collision = next(generator, None), next(generator, None)
            if collision is not None:
                raise explosions.ExportError("There are multiple copies of case insensitive text block '{}'.", name)
            return result

        # AgeSDL Hook Python
        fixed_agename = replace_python2_identifier(age)
        py_filename = "{}.py".format(fixed_agename)
        age_py = get_text(py_filename)
        if output.want_py_text(age_py):
            py_code = age_py.as_string()
        else:
            py_code = very_very_special_python.format(age_name=fixed_agename).lstrip()
        output.add_python_mod(py_filename, text_id=age_py, str_data=py_code)

        # AgeSDL
        sdl_filename = "{}.sdl".format(fixed_agename)
        age_sdl = get_text(sdl_filename)
        if age_sdl is None:
            sdl_code = very_very_special_sdl.format(age_name=fixed_agename).lstrip()
            age_sdl = bpy.data.texts.new(sdl_filename)
            age_sdl.from_string(sdl_code)
        output.add_sdl(sdl_filename, text_id=age_sdl)

    def save_age(self):
        self._write_age()
        self._write_fni()
        self._write_pages()

    def _write_age(self):
        f = "{}.age".format(self._age_info.name)
        output = self._exporter().output

        with output.generate_dat_file(f, enc=self._encryption) as stream:
            self._age_info.writeToStream(stream)

    def _write_fni(self):
        f = "{}.fni".format(self._age_info.name)
        output = self._exporter().output

        with output.generate_dat_file(f, enc=self._encryption) as stream:
            fni = bpy.context.scene.world.plasma_fni
            stream.writeLine("Graphics.Renderer.SetClearColor {:.2f} {:.2f} {:.2f}".format(*fni.clear_color))
            stream.writeLine("Graphics.Renderer.SetYon {:.1f}".format(fni.yon))
            if fni.fog_method == "none":
                stream.writeLine("Graphics.Renderer.Fog.SetDefLinear 0 0 0")
            else:
                stream.writeLine("Graphics.Renderer.Fog.SetDefColor {:.2f} {:.2f} {:.2f}".format(*fni.fog_color))
                if fni.fog_method == "linear":
                    stream.writeLine("Graphics.Renderer.Fog.SetDefLinear {:.2f} {:.2f} {:.2f}".format(fni.fog_start, fni.fog_end, fni.fog_density))
                elif fni.fog_method == "exp":
                    stream.writeLine("Graphics.Renderer.Fog.SetDefExp {:.2f} {:.2f}".format(fni.fog_end, fni.fog_density))
                elif fni.fog_method == "exp2":
                    stream.writeLine("Graphics.Renderer.Fog.SetDefExp2 {:.2f} {:.2f}".format(fni.fog_end, fni.fog_density))

    def _write_pages(self):
        age_name = self._age_info.name
        output = self._exporter().output
        for loc in self._pages.values():
            page = self.mgr.FindPage(loc) # not cached because it's C++ owned
            chapter = "_District_" if self.mgr.getVer() <= pvMoul else "_"
            f = "{}{}{}.prp".format(age_name, chapter, page.page)

            with output.generate_dat_file(f) as stream:
                self.mgr.WritePage(stream, page)
