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
import time

from . import explosions
from . import logger
from . import manager
from . import mesh
from . import utils

class Exporter:
    def __init__(self, op):
        self._op = op # Blender export operator
        self._objects = []

    @property
    def age_name(self):
        return os.path.splitext(os.path.split(self._op.filepath)[1])[0]

    def run(self):
        with logger.ExportLogger("{}_export.log".format(self.age_name)) as _log:
            print("Exporting '{}.age'".format(self.age_name))
            start = time.process_time()

            # Step 0: Init export resmgr and stuff
            self.mgr = manager.ExportManager(globals()[self._op.version])
            self.mesh = mesh.MeshConverter(self)
            self.report = logger.ExportAnalysis()

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

            # Step 4: Finalize...
            self.mesh.material.finalize()
            self.mesh.finalize()

            # Step 5: FINALLY. Let's write the PRPs and crap.
            self.mgr.save_age(self._op.filepath)

            # Step 5.1: Save out the export report.
            #           If the export fails and this doesn't save, we have bigger problems than
            #           these little warnings and notices.
            self.report.save()

            # And finally we crow about how awesomely fast we are...
            end = time.process_time()
            print("\nExported {}.age in {:.2f} seconds".format(self.age_name, end-start))

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

    def _export_actor(self, so, bo):
        """Exports a Coordinate Interface if we need one"""
        empty = bo.type in {"CAMERA", "EMPTY", "LAMP"}
        childobj = bo.parent is not None

        if empty or childobj:
            self._export_coordinate_interface(so, bo)

        # If this object has a parent, then we will need to go upstream and add ourselves to the
        # parent's CoordinateInterface... Because life just has to be backwards.
        if childobj:
            parent = bo.parent
            if parent.plasma_object.enabled:
                print("    Attaching to parent SceneObject '{}'".format(parent.name))

                # Instead of exporting a skeleton now, we'll just make an orphaned CI.
                # The bl_obj export will make this work.
                parent_ci = self.mgr.find_create_key(parent, plCoordinateInterface).object
                parent_ci.addChild(so.key)
            else:
                self.report.warn("You have parented Plasma Object '{}' to '{}', which has not been marked for export. \
                                 The object may not appear in the correct location or animate properly.".format(
                                    bo.name, parent.name))

    def _export_coordinate_interface(self, so, bo):
        """Ensures that the SceneObject has a CoordinateInterface"""
        if not so.coord:
            ci = self.mgr.find_create_key(bo, plCoordinateInterface)
            so.coord = ci
            ci = ci.object

            # Now we have the "fun" work of filling in the CI
            ci.worldToLocal = utils.matrix44(bo.matrix_basis)
            ci.localToWorld = ci.worldToLocal.inverse()
            ci.parentToLocal = utils.matrix44(bo.matrix_local)
            ci.localToParent = ci.parentToLocal.inverse()

    def _export_scene_objects(self):
        for bl_obj in self._objects:
            print("\n[SceneObject '{}']".format(bl_obj.name))

            # First pass: do things specific to this object type.
            #             note the function calls: to export a MESH, it's _export_mesh_blobj
            export_fn = "_export_{}_blobj".format(bl_obj.type.lower())
            try:
                export_fn = getattr(self, export_fn)
            except AttributeError:
                print("WARNING: '{}' is a Plasma Object of Blender type '{}'".format(bl_obj.name, bl_obj.type))
                print("... And I have NO IDEA what to do with that! Tossing.")
                continue
            print("    Blender Object '{}' of type '{}'".format(bl_obj.name, bl_obj.type))

            # Create a sceneobject if one does not exist.
            # Before we call the export_fn, we need to determine if this object is an actor of any
            # sort, and barf out a CI.
            sceneobject = self.mgr.find_create_key(bl_obj, plSceneObject).object
            self._export_actor(sceneobject, bl_obj)
            export_fn(sceneobject, bl_obj)

            # And now we puke out the modifiers...
            for mod in bl_obj.plasma_modifiers.modifiers:
                print("    Exporting '{}' modifier as '{}'".format(mod.bl_label, mod.display_name))
                mod.export(self, bl_obj, sceneobject)

    def _export_empty_blobj(self, so, bo):
        # We don't need to do anything here. This function just makes sure we don't error out
        # or add a silly special case :(
        pass

    def _export_mesh_blobj(self, so, bo):
        if bo.data.materials:
            so.draw = self.mesh.export_object(bo)
        else:
            print("    No material(s) on the ObData, so no drawables")
