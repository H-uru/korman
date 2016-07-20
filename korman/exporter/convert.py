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
from pathlib import Path
from PyHSPlasma import *
import time

from . import animation
from . import explosions
from . import etlight
from . import logger
from . import manager
from . import mesh
from . import physics
from . import rtlight
from . import sumfile
from . import utils

class Exporter:
    def __init__(self, op):
        self._op = op # Blender export operator
        self._objects = []
        self.actors = set()
        self.node_trees_exported = set()
        self.want_node_trees = {}

    @property
    def age_name(self):
        return Path(self._op.filepath).stem

    def run(self):
        with logger.ExportLogger(self._op.filepath) as _log:
            print("Exporting '{}.age'".format(self.age_name))
            start = time.perf_counter()

            # Step 0: Init export resmgr and stuff
            self.mgr = manager.ExportManager(self)
            self.mesh = mesh.MeshConverter(self)
            self.report = logger.ExportAnalysis()
            self.physics = physics.PhysicsConverter(self)
            self.light = rtlight.LightConverter(self)
            self.animation = animation.AnimationConverter(self)
            self.sumfile = sumfile.SumFile()

            # Step 1: Create the age info and the pages
            self._export_age_info()

            # Step 2: Gather a list of objects that we need to export, given what the user has told
            #         us to export (both in the Age and Object Properties)... fun
            self._collect_objects()

            # Step 2.5: Run through all the objects we collected in Step 2 and see if any relationships
            #           that the artist made requires something to have a CoordinateInterface
            self._harvest_actors()

            # Step 2.9: It is assumed that static lighting is available for the mesh exporter.
            #           Indeed, in PyPRP it was a manual step. So... BAKE NAO!
            if self._op.bake_lighting:
                self._bake_static_lighting()

            # Step 3: Export all the things!
            self._export_scene_objects()

            # Step 3.1: Ensure referenced logic node trees are exported
            self._export_referenced_node_trees()

            # Step 3.2: Now that all Plasma Objects (save Mipmaps) are exported, we do any post
            #          processing that needs to inspect those objects
            self._post_process_scene_objects()

            # Step 4: Finalize...
            self.mesh.material.finalize()
            self.mesh.finalize()

            # Step 5: FINALLY. Let's write the PRPs and crap.
            self.mgr.save_age(Path(self._op.filepath))

            # Step 5.1: Save out the export report.
            #           If the export fails and this doesn't save, we have bigger problems than
            #           these little warnings and notices.
            self.report.save()

            # And finally we crow about how awesomely fast we are...
            end = time.perf_counter()
            print("\nExported {}.age in {:.2f} seconds".format(self.age_name, end-start))

    def _bake_static_lighting(self):
        oven = etlight.LightBaker()
        oven.bake_static_lighting(self._objects)

    def _collect_objects(self):
        # Grab a naive listing of enabled pages
        age = bpy.context.scene.world.plasma_age
        pages_enabled = frozenset([page.name for page in age.pages if page.enabled])
        all_pages = frozenset([page.name for page in age.pages])

        # Because we can have an unnamed or a named default page, we need to see if that is enabled...
        for page in age.pages:
            if page.seq_suffix == 0:
                default_enabled = page.enabled
                default_inited = True
                break
        else:
            default_enabled = True
            default_inited = False

        # Now we loop through the objects with some considerations:
        #     - The default page may or may not be defined. If it is, it can be disabled. If not, it
        #       can only ever be enabled.
        #     - Don't create the Default page unless it is used (implicit or explicit). It is a failure
        #       to export a useless file.
        #     - Any arbitrary page can be disabled, so check our frozenset.
        #     - Also, someone might have specified an invalid page, so keep track of that.
        error = explosions.UndefinedPageError()
        for obj in bpy.data.objects:
            if obj.plasma_object.enabled:
                page = obj.plasma_object.page
                if not page and not default_inited:
                    self.mgr.create_page(self.age_name, "Default", 0)
                    default_inited = True

                if (default_enabled and not page) or (page in pages_enabled):
                    self._objects.append(obj)
                elif page not in all_pages:
                    error.add(page, obj.name)
        error.raise_if_error()

    def _export_age_info(self):
        # Make life slightly easier...
        age_info = bpy.context.scene.world.plasma_age
        age_name = self.age_name
        mgr = self.mgr

        # Generate the plAgeInfo
        mgr.AddAge(age_info.export(self))

        # Create all the pages we need
        for page in age_info.pages:
            if page.enabled:
                mgr.create_page(age_name, page.name, page.seq_suffix)
        mgr.create_builtins(age_name, age_info.use_texture_page)

    def _export_actor(self, so, bo):
        """Exports a Coordinate Interface if we need one"""
        if self.has_coordiface(bo):
            self._export_coordinate_interface(so, bo)

        # If this object has a parent, then we will need to go upstream and add ourselves to the
        # parent's CoordinateInterface... Because life just has to be backwards.
        parent = bo.parent
        if parent is not None:
            if parent.plasma_object.enabled:
                print("    Attaching to parent SceneObject '{}'".format(parent.name))
                parent_ci = self._export_coordinate_interface(None, parent)
                parent_ci.addChild(so.key)
            else:
                self.report.warn("You have parented Plasma Object '{}' to '{}', which has not been marked for export. \
                                 The object may not appear in the correct location or animate properly.".format(
                                    bo.name, parent.name))

    def _export_coordinate_interface(self, so, bl):
        """Ensures that the SceneObject has a CoordinateInterface"""
        if so is None:
            so = self.mgr.find_create_object(plSceneObject, bl=bl)
        if so.coord is None:
            ci = self.mgr.add_object(plCoordinateInterface, bl=bl, so=so)

            # Now we have the "fun" work of filling in the CI
            ci.localToWorld = utils.matrix44(bl.matrix_basis)
            ci.worldToLocal = ci.localToWorld.inverse()
            ci.localToParent = utils.matrix44(bl.matrix_local)
            ci.parentToLocal = ci.localToParent.inverse()
            return ci
        return so.coord.object

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
            sceneobject = self.mgr.find_create_object(plSceneObject, bl=bl_obj)
            self._export_actor(sceneobject, bl_obj)
            export_fn(sceneobject, bl_obj)
            self.animation.convert_object_animations(bl_obj, sceneobject)

            # And now we puke out the modifiers...
            for mod in bl_obj.plasma_modifiers.modifiers:
                print("    Exporting '{}' modifier as '{}'".format(mod.bl_label, mod.key_name))
                mod.export(self, bl_obj, sceneobject)

    def _export_empty_blobj(self, so, bo):
        # We don't need to do anything here. This function just makes sure we don't error out
        # or add a silly special case :(
        pass

    def _export_lamp_blobj(self, so, bo):
        # We'll just redirect this to the RT Light converter...
        self.light.export_rtlight(so, bo)

    def _export_mesh_blobj(self, so, bo):
        if bo.data.materials:
            self.mesh.export_object(bo)
        else:
            print("    No material(s) on the ObData, so no drawables")

    def _export_referenced_node_trees(self):
        print("\nChecking Logic Trees...")
        need_to_export = ((name, bo, so) for name, (bo, so) in self.want_node_trees.items()
                                         if name not in self.node_trees_exported)
        for tree, bo, so in need_to_export:
            print("    NodeTree '{}'".format(tree))
            bpy.data.node_groups[tree].export(self, bo, so)

    def _harvest_actors(self):
        for bl_obj in self._objects:
            for mod in bl_obj.plasma_modifiers.modifiers:
                if mod.enabled:
                    self.actors.update(mod.harvest_actors())

        # This is a little hacky, but it's an edge case... I guess?
        # We MUST have CoordinateInterfaces for EnvironmentMaps (DCMs, bah)
        for texture in bpy.data.textures:
            envmap = getattr(texture, "environment_map", None)
            if envmap is not None:
                viewpt = envmap.viewpoint_object
                if viewpt is not None:
                    self.actors.add(viewpt.name)

    def has_coordiface(self, bo):
        if bo.type in {"CAMERA", "EMPTY", "LAMP"}:
            return True
        if bo.parent is not None:
            return True
        if bo.name in self.actors:
            return True
        if bo.plasma_object.has_transform_animation:
            return True

        for mod in bo.plasma_modifiers.modifiers:
            if mod.enabled:
                if mod.requires_actor:
                    return True
        return False

    def _post_process_scene_objects(self):
        print("\nPostprocessing SceneObjects...")

        mat_mgr = self.mesh.material
        for bl_obj in self._objects:
            sceneobject = self.mgr.find_object(plSceneObject, bl=bl_obj)
            if sceneobject is None:
                # no SO? fine then. turd.
                continue

            # Synchronization is applied for the root SO and all animated layers (WTF)
            # So, we have to keep in mind shared layers (whee) in the synch options kode
            net = bl_obj.plasma_net
            net.propagate_synch_options(sceneobject, sceneobject)
            for mat in mat_mgr.get_materials(bl_obj):
                for layer in mat.object.layers:
                    layer = layer.object
                    if isinstance(layer, plLayerAnimation):
                        net.propagate_synch_options(sceneobject, layer)

            # Modifiers don't have to expose post-processing, but if they do, run it
            for mod in bl_obj.plasma_modifiers.modifiers:
                proc = getattr(mod, "post_export", None)
                if proc is not None:
                    print("    '{}' modifier '{}'".format(bl_obj.name, mod.key_name))
                    proc(self, bl_obj, sceneobject)
