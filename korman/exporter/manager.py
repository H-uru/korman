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

from . import explosions

class ExportManager:
    """Friendly resource-managing helper class."""

    _nodes = {}
    _pages = {}

    def __init__(self, version):
        self.mgr = plResManager()
        self.mgr.setVer(version)

        # cheap inheritance
        for i in dir(self.mgr):
            if not hasattr(self, i):
                setattr(self, i, getattr(self.mgr, i))

    def AddAge(self, info):
        # There's only ever one age being exported, so hook the call and hang onto the plAgeInfo
        # We'll save from our reference later. Forget grabbing this from C++
        self._age_info = info
        self.mgr.AddAge(info)

    def add_object(self, pl, name=None, bl=None, loc=None):
        """Automates adding a converted Blender object to our Plasma Resource Manager"""
        assert (bl or loc)
        if loc:
            location = loc
        else:
            location = self._pages[bl.plasma_object.page]

        # pl can be a class or an instance.
        # This is one of those "sanity" things to ensure we don't suddenly
        # passing around the key of an uninitialized object.
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
            else:
                # FIXME: determine which types belong here...
                # Probably anything that's not a plModifier or a plBitmap...
                # Remember that the idea is that Plasma needs to deliver refs to load the age.
                # It's harmless to have too many refs here (though the file size will be big, heh)
                node.addPoolObject(pl.key)
        return pl # we may have created it...

    def create_builtins(self, age, textures):
        # BuiltIn.prp
        if bpy.context.scene.world.plasma_age.age_sdl:
            builtin = self.create_page(age, "BuiltIn", -1, True)
            pfm = self.add_object(plPythonFileMod, name="VeryVerySpecialPythonFileMod", loc=builtin)
            pfm.filename = age
            sdl = self.add_object(plSceneObject, name="AgeSDLHook", loc=builtin)
            sdl.addModifier(pfm.key)

        # Textures.prp
        if textures:
            self.create_page(age, "Textures", -2, True)

    def create_page(self, age, name, id, builtin=False):
        location = plLocation(self.mgr.getVer())
        location.prefix = bpy.context.scene.world.plasma_age.seq_prefix
        if builtin:
            location.flags |= plLocation.kBuiltIn
        location.page = id
        self._pages[name] = location

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

    def find_key(self, bl_obj, index):
        """Given a blender Object and a pCre index, find an exported plKey"""
        location = self._pages[bl_obj.plasma_object.page]

        # NOTE: may need to replace with a python side dict for faster lookups
        #       evaluate when exporter has been fleshed out
        for key in self.mgr.getKeys(location, index):
            if bl_obj.name == key.name:
                return key
        return None

    def get_textures_page(self, obj):
        """Returns the page that Blender Object obj's textures should be exported to"""
        # The point of this is to account for per-page textures...
        if "Textures" in self._pages:
            return self._pages["Textures"]
        else:
            return self._pages[obj.plasma_object.page]

    def sanity_check_object_pages(self, age, objects):
        """Ensure all objects are in valid pages and create the Default page if used"""

        error = explosions.UndefinedPageError()
        for obj in objects:
            page = obj.plasma_object.page
            if page in self._pages:
                # good. keep trying.
                continue
            elif page == "":
                # This object is in the default page... Init that.
                for loc in self._pages.values():
                    if not loc.page:
                        self.mgr._pages[""] = loc
                        break
                else:
                    # need to create default page
                    self._pages[""] = self.create_page("Default", 0)
            else:
                error.add(page, obj.name)
        error.raise_if_error()

    def save_age(self, path):
        relpath, ageFile = os.path.split(path)
        ageName = os.path.splitext(ageFile)[0]

        self.mgr.WriteAge(path, self._age_info)
        self._write_fni(relpath, ageName)
        self._write_pages(relpath, ageName)

    def _write_fni(self, path, ageName):
        if self.mgr.getVer() <= pvMoul:
            enc = plEncryptedStream.kEncXtea
        else:
            enc = plEncryptedStream.kEncAES
        fname = os.path.join(path, "{}.fni".format(ageName))
        stream = plEncryptedStream()
        stream.open(fname, fmWrite, enc)

        # Write out some stuff
        fni = bpy.context.scene.world.plasma_fni
        stream.writeLine("Graphics.Renderer.Fog.SetClearColor %f %f %f" % tuple(fni.clear_color))
        if fni.fog_method != "none":
            stream.writeLine("Graphics.Renderer.Fog.SetDefColor %f %f %f" % tuple(fni.fog_color))
        if fni.fog_method == "linear":
            stream.writeLine("Graphics.Renderer.Fog.SetDefLinear %f %f %f" % (fni.fog_start, fni.fog_end, fni.fog_density))
        elif fni.fog_method == "exp2":
            stream.writeLine("Graphics.Renderer.Fog.SetDefExp2 %f %f" % (fni.fog_end, fni.fog_density))
        stream.writeLine("Graphics.Renderer.Setyon %f" % fni.yon)
        stream.close()

    def _write_pages(self, path, ageName):
        for name, loc in self._pages.items():
            page = self.mgr.FindPage(loc) # not cached because it's C++ owned
            # I know that plAgeInfo has its own way of doing this, but we'd have
            # to do some looping and stuff. This is easier.
            if self.mgr.getVer() <= pvMoul:
                chapter = "_District_"
            else:
                chapter = "_"
            f = os.path.join(path, "{}{}{}.prp".format(ageName, chapter, name))
            self.mgr.WritePage(f, page)
