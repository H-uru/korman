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
from . import manager

class Exporter:
    # These are objects that we need to export as plSceneObjects
    _objects = []

    def __init__(self, op):
        self._op = op # Blender export operator

    @property
    def age_name(self):
        return os.path.splitext(os.path.split(self._op.filepath)[1])[0]

    def run(self):
        # Step 0: Init export resmgr and stuff
        self.mgr = manager.ExportManager(globals()[self._op.version])

        # Step 1: Gather a list of objects that we need to export
        #         We should do this first so we can sanity check
        #         and give accurate progress reports
        self._collect_objects()

        # Step 2: Create the age info and the pages
        self._export_age_info()

        # Step 2.9: Ensure that all Plasma Objects are in a valid page
        #           This creates the default page if it is used
        self.mgr.sanity_check_object_pages(self.age_name, self._objects)

        # Step 3: Export all the things!
        self._export_scene_objects()

        # Step 4: FINALLY. Let's write the PRPs and crap.
        self.mgr.save_age(self._op.filepath)

    def _collect_objects(self):
        for obj in bpy.data.objects:
            if obj.plasma_object.enabled:
                self._objects.append(obj)

    def _export_age_info(self):
        # Make life slightly easier...
        age_info = bpy.context.scene.world.plasma_age
        age_name = self.age_name
        mgr = self.mgr

        # Generate the plAgeInfo
        mgr.AddAge(age_info.export(self))

        # Create all the pages we need
        for page in age_info.pages:
            mgr.create_page(age_name, page.name, page.seq_suffix)
        mgr.create_builtins(age_name, self._op.use_texture_page)

    def _export_scene_objects(self):
        for bl_obj in self._objects:
            # Naive export all Plasma Objects. They will be responsible for calling back into the
            # exporter to find/create drawable meshes, materials, etc. Not sure if this design will
            # work well, but we're going to go with it for now.
            bl_obj.plasma_object.export(self, bl_obj)