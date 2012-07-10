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

class ExportError(Exception):
    def __init__(self, value="Undefined Export Error"):
        self.value = value
    def __str__(self):
        return self.value

class Exporter:
    def __init__(self, op):
        self._op = op # Blender operator

        # This stuff doesn't need to be static
        self._objects = []
        self._pages = {}
        self.texture_page = True

    @property
    def age_name(self):
        return os.path.splitext(os.path.split(self._op.filepath)[1])[0]

    def _create_page(self, name, id, builtin=False):
        location = plLocation(self.version)
        location.prefix = bpy.context.scene.world.plasma_age.seq_prefix
        if builtin:
            location.flags |= plLocation.kBuiltIn
        location.page = id
        self._pages[name] = location

        info = plPageInfo()
        info.age = self.age_name
        info.page = name
        info.location = location
        self.mgr.AddPage(info)

        if not builtin:
            self._age_info.addPage((name, id, 0))
            if self.version <= pvPots:
                node = plSceneNode("%s_District_%s" % (self.age_name, name))
            else:
                node = plSceneNode("%s_%s" % (self.age_name, name))
            self.mgr.AddObject(location, node)
        return location

    def get_textures_page(self, obj):
        if self.pages["Textures"] is not None:
            return self.pages["Textures"]
        else:
            return self.pages[obj.plasma_object.page]

    @property
    def version(self):
        # I <3 Python
        return globals()[self._op.version]

    def run(self):
        # Step 0: Init export resmgr and stuff
        self.mgr = plResManager()
        self.mgr.setVer(self.version)

        # Step 1: Gather a list of objects that we need to export
        #         We should do this first so we can sanity check
        #         and give accurate progress reports
        self._collect_objects()

        # Step 2: Collect some age information
        self._grab_age_info() # World Props -> plAgeInfo
        for page in bpy.context.scene.world.plasma_age.pages:
            self._create_page(page.name, page.seq_suffix)
        self._sanity_check_pages()
        self._generate_builtins() # Creates BuiltIn and Textures

        # ... todo ...

        # ... And finally... Write it all out!
        self.mgr.WriteAge(self._op.filepath, self._age_info)
        dir = os.path.split(self._op.filepath)[0]
        for name, loc in self._pages.items():
            page = self.mgr.FindPage(loc) # not cached because it's C++ owned
            # I know that plAgeInfo has its own way of doing this, but we'd have
            # to do some looping and stuff. This is easier.
            if self.version <= pvMoul:
                chapter = "_District_"
            else:
                chapter = "_"
            f = os.path.join(dir, "%s%s%s.prp" % (self.age_name, chapter, name))
            self.mgr.WritePage(f, page)

    def _collect_objects(self):
        for obj in bpy.data.objects:
            if obj.plasma_object.export:
                self._objects.append(obj)

    def _grab_age_info(self):
        self._age_info = bpy.context.scene.world.plasma_age.export()
        self._age_info.name = self.age_name
        self.mgr.AddAge(self._age_info)

    def _sanity_check_pages(self):
        """Ensure all objects are in valid pages and create the Default page if used"""
        for obj in self._objects:
            page = obj.plasma_object.page
            if not page in self._pages and page == "":
                # This object is in the default page... Init that.
                for loc in self._pages.values():
                    if not loc.page:
                        self._pages[""] = loc
                        break
                else:
                    # need to create default page
                    self._pages[""] = self._create_page("Default", 0)
            else:
                # oh dear...
                raise ExportError("Object '%s' in undefined page '%s'" % (obj.name, page))

    def _generate_builtins(self):
        # Find the highest two available negative suffixes for BuiltIn and Textures
        # This should generally always resolve to -2 and -1
        suffixes = []; _s = -1
        while len(suffixes) != 2:
            for location in self._pages.values():
                if location.page == _s:
                    break
            else:
                suffixes.append(_s)
            _s -= 1

        # Grunt work...
        if self.version <= pvMoul:
            builtin = self._create_page("BuiltIn", suffixes[1], True)
            pfm = plPythonFileMod("VeryVerySpecialPythonFileMod")
            pfm.filename = self.age_name
            self.mgr.AddObject(builtin, pfm)
            sdlhook = plSceneObject("AgeSDLHook")
            sdlhook.addModifier(pfm.key)
            self.mgr.AddObject(builtin, sdlhook)
            self._pages["BuiltIn"] = builtin

        if self._op.use_texture_page:
            textures = self._create_page("Textures", suffixes[0], True)
            self._pages["Textures"] = textures
        else:
            self._pages["Textures"] = None # probably easier than looping to find it
