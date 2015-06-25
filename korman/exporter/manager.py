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
import os.path
from PyHSPlasma import *
import weakref

from . import explosions

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

        # cheap inheritance
        for i in dir(self.mgr):
            if not hasattr(self, i):
                setattr(self, i, getattr(self.mgr, i))

    def AddAge(self, info):
        # There's only ever one age being exported, so hook the call and hang onto the plAgeInfo
        # We'll save from our reference later. Forget grabbing this from C++
        self._age_info = info
        self.mgr.AddAge(info)

    def add_object(self, pl, name=None, bl=None, loc=None, so=None):
        """Automates adding a converted Blender object to our Plasma Resource Manager"""
        assert (bl or loc or so)
        if loc is not None:
            location = loc
        elif so is not None:
            location = so.key.location
        else:
            location = self._pages[bl.plasma_object.page]

        # pl can be a class or an instance.
        # This is one of those "sanity" things to ensure we don't suddenly startpassing around the
        # key of an uninitialized object.
        if isinstance(pl, type(object)):
            assert name or bl
            if name is None:
                name = bl.name
            pl = pl(name)

        self.mgr.AddObject(location, pl)
        node = self._nodes[location]
        if node: # All objects must be in the scene node
            if isinstance(pl, plSceneObject):
                node.addSceneObject(pl.key)
                pl.sceneNode = node.key
            elif pl.ClassIndex() in _pool_types:
                node.addPoolObject(pl.key)

        if isinstance(pl, plObjInterface):
            if so is None:
                key = self.find_key(plSceneObject, bl, name)
                # prevent race conditions
                if key is None:
                    so = self.add_object(plSceneObject, name=name, loc=location)
                    key = so.key
                else:
                    so = key.object
                pl.owner = key
            else:
                pl.owner = so.key

            # The things I do to make life easy...
            # This is something of a God function now.
            if isinstance(pl, plAudioInterface):
                so.audio = pl.key
            elif isinstance(pl, plCoordinateInterface):
                so.coord = pl.key
            elif isinstance(pl, plDrawInterface):
                so.draw = pl.key
            elif isinstance(pl, plSimulationInterface):
                so.sim = pl.key
            else:
                so.addInterface(pl.key)
        elif isinstance(pl, plModifier):
            so.addModifier(pl.key)

        # And we're done!
        return pl

    def create_builtins(self, age, textures):
        # BuiltIn.prp
        if bpy.context.scene.world.plasma_age.age_sdl:
            builtin = self.create_page(age, "BuiltIn", -2, True)
            sdl = self.add_object(plSceneObject, name="AgeSDLHook", loc=builtin)
            pfm = self.add_object(plPythonFileMod, name="VeryVerySpecialPythonFileMod", so=sdl)
            pfm.filename = age

        # Textures.prp
        if textures:
            self.create_page(age, "Textures", -1, True)

    def create_page(self, age, name, id, builtin=False):
        location = plLocation(self.mgr.getVer())
        location.prefix = bpy.context.scene.world.plasma_age.seq_prefix
        if builtin:
            location.flags |= plLocation.kBuiltIn
        location.page = id
        self._pages[name] = location

        # If the page ID is 0, this is the default page... Any page with an empty string name
        # is the default, so bookmark it!
        if id == 0:
            self._pages[""] = location

        info = plPageInfo()
        info.age = age
        info.page = name
        info.location = location
        self.mgr.AddPage(info)

        if not builtin:
            self._age_info.addPage((name, id, 0))
            if self.getVer() <= pvPots:
                node = plSceneNode("{}_District_{}".format(age, name))
            else:
                node = plSceneNode("{}_{}".format(age, name))
            self._nodes[location] = node
            self.mgr.AddObject(location, node)
        else:
            self._nodes[location] = None
        return location

    def find_create_key(self, pClass, bl=None, name=None, so=None):
        key = self.find_key(pClass, bl, name, so)
        if key is None:
            key = self.add_object(pl=pClass, name=name, bl=bl, so=so).key
        return key

    def find_key(self, pClass, bl=None, name=None, so=None):
        """Given a blender Object and a Plasma class, find (or create) an exported plKey"""
        assert (bl or name) and (bl or so)

        if so is None:
            location = self._pages[bl.plasma_object.page]
        else:
            location = so.key.location
        if name is None:
            name = bl.name

        index = plFactory.ClassIndex(pClass.__name__)
        for key in self.mgr.getKeys(location, index):
            if name == key.name:
                return key
        return None

    def get_location(self, bl):
        """Returns the Page Location of a given Blender Object"""
        return self._pages[bl.plasma_object.page]

    def get_scene_node(self, location=None, bl=None):
        """Gets a Plasma Page's plSceneNode key"""
        assert (location is not None) ^ (bl is not None)

        if location is None:
            location = self._pages[bl.plasma_object.page]
        return self._nodes[location].key

    def get_textures_page(self, key):
        """Gets the appropriate page for a texture for a given plLayer"""
        # The point of this is to account for per-page textures...
        if "Textures" in self._pages:
            return self._pages["Textures"]
        else:
            return key.location

    def has_coordiface(self, bo):
        if bo.type in {"CAMERA", "EMPTY", "LAMP"}:
            return True
        if bo.parent is not None:
            return True

        for mod in bo.plasma_modifiers.modifiers:
            if mod.enabled:
                if mod.requires_actor:
                    return True
        return False

    def save_age(self, path):
        relpath, ageFile = os.path.split(path)
        ageName = os.path.splitext(ageFile)[0]
        sumfile = self._exporter().sumfile

        sumfile.append(path)
        self.mgr.WriteAge(path, self._age_info)
        self._write_fni(relpath, ageName)
        self._write_pages(relpath, ageName)

        if self.getVer() != pvMoul:
            sumpath = os.path.join(relpath, "{}.sum".format(ageName))
            sumfile.write(sumpath, self.getVer())

    def _write_fni(self, path, ageName):
        if self.mgr.getVer() <= pvMoul:
            enc = plEncryptedStream.kEncXtea
        else:
            enc = plEncryptedStream.kEncAES
        fname = os.path.join(path, "{}.fni".format(ageName))

        with plEncryptedStream(self.mgr.getVer()).open(fname, fmWrite, enc) as stream:
            fni = bpy.context.scene.world.plasma_fni
            stream.writeLine("Graphics.Renderer.SetClearColor {} {} {}".format(*fni.clear_color))
            if fni.fog_method != "none":
                stream.writeLine("Graphics.Renderer.Fog.SetDefColor {} {} {}".format(*fni.fog_color))
            if fni.fog_method == "linear":
                stream.writeLine("Graphics.Renderer.Fog.SetDefLinear {} {} {}".format(fni.fog_start, fni.fog_end, fni.fog_density))
            elif fni.fog_method == "exp2":
                stream.writeLine("Graphics.Renderer.Fog.SetDefExp2 {} {}".format(fni.fog_end, fni.fog_density))
            stream.writeLine("Graphics.Renderer.SetYon {}".format(fni.yon))
        self._exporter().sumfile.append(fname)

    def _write_pages(self, path, ageName):
        for loc in self._pages.values():
            page = self.mgr.FindPage(loc) # not cached because it's C++ owned
            # I know that plAgeInfo has its own way of doing this, but we'd have
            # to do some looping and stuff. This is easier.
            if self.mgr.getVer() <= pvMoul:
                chapter = "_District_"
            else:
                chapter = "_"
            f = os.path.join(path, "{}{}{}.prp".format(ageName, chapter, page.page))
            self.mgr.WritePage(f, page)
            self._exporter().sumfile.append(f)
