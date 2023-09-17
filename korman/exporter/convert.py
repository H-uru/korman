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

from collections import defaultdict
from contextlib import ExitStack
import functools
import inspect
from pathlib import Path
from typing import *

from ..helpers import TemporaryObject
from ..korlib import ConsoleToggler

from PyHSPlasma import *

from .animation import AnimationConverter
from .camera import CameraConverter
from .decal import DecalConverter
from . import explosions
from .etlight import LightBaker
from .gui import GuiConverter
from .image import ImageCache
from .locman import LocalizationConverter
from . import logger
from .manager import ExportManager
from .mesh import MeshConverter
from .outfile import OutputFiles
from .physics import PhysicsConverter
from .rtlight import LightConverter
from . import utils

class Exporter:

    if TYPE_CHECKING:
        _objects: List[bpy.types.Object] = ...
        actors: Set[str] = ...
        want_node_trees: defaultdict[Set[str]] = ...
        report: logger._ExportLogger = ...
        exit_stack: ExitStack = ...
        mgr: ExportManager = ...
        mesh: MeshConverter = ...
        physics: PhysicsConverter = ...
        light: LightConverter = ...
        animation: AnimationConverter = ...
        output: OutputFiles = ...
        camera: CameraConverter = ...
        image: ImageCache = ...
        locman: LocalizationConverter = ...
        decal: DecalConverter = ...
        oven: LightBaker = ...
        gui: GuiConverter

    def __init__(self, op):
        self._op = op # Blender export operator
        self._objects = []
        self.actors = set()
        self.want_node_trees = defaultdict(set)
        self.exported_nodes = {}

    def run(self):
        log = logger.ExportVerboseLogger if self._op.verbose else logger.ExportProgressLogger
        with ConsoleToggler(self._op.show_console), log(self._op.filepath) as self.report, ExitStack() as self.exit_stack:
            # Step 0: Init export resmgr and stuff
            self.mgr = ExportManager(self)
            self.mesh = MeshConverter(self)
            self.physics = PhysicsConverter(self)
            self.light = LightConverter(self)
            self.animation = AnimationConverter(self)
            self.output = OutputFiles(self, self._op.filepath)
            self.camera = CameraConverter(self)
            self.image = ImageCache(self)
            self.locman = LocalizationConverter(self)
            self.decal = DecalConverter(self)
            self.oven = LightBaker(mesh=self.mesh, report=self.report)
            self.gui = GuiConverter(self)

            # Step 0.8: Init the progress mgr
            self.mesh.add_progress_presteps(self.report)
            self.report.progress_add_step("Collecting Objects")
            self.report.progress_add_step("Verify Competence")
            self.report.progress_add_step("Touching the Intangible")
            self.report.progress_add_step("Unifying Superstrings")
            self.report.progress_add_step("Harvesting Actors")
            if self._op.lighting_method != "skip":
                LightBaker.add_progress_steps(self.report)
            self.report.progress_add_step("Exporting Scene Objects")
            self.report.progress_add_step("Exporting Logic Nodes")
            self.report.progress_add_step("Finalizing Plasma Logic")
            self.report.progress_add_step("Handling Snakes")
            self.report.progress_add_step("Exporting Textures")
            self.report.progress_add_step("Composing Geometry")
            self.report.progress_add_step("Saving Age Files")
            self.report.progress_add_step("Cleaning Up")
            self.report.progress_start("EXPORTING AGE")

            # Step 0.9: Apply modifiers to all meshes temporarily.
            with self.mesh:
                # Step 1: Create the age info and the pages
                self._export_age_info()

                # Step 2: Gather a list of objects that we need to export, given what the user has told
                #         us to export (both in the Age and Object Properties)... fun
                self._collect_objects()

                # Step 2.1: Run through all the objects we collected in Step 2 and make sure there
                #           is no ruddy funny business going on.
                self._check_sanity()

                # Step 2.2: Run through all the objects again and ask them to "pre_export" themselves.
                #           In other words, generate any ephemeral Blender objects that need to be exported.
                self._pre_export_scene_objects()

                # Step 2.3: Run through all the objects and export localization.
                self._export_localization()

                # Step 2.5: Run through all the objects we collected in Step 2 and see if any relationships
                #           that the artist made requires something to have a CoordinateInterface
                self._harvest_actors()

                # Step 2.9: It is assumed that static lighting is available for the mesh exporter.
                #           Indeed, in PyPRP it was a manual step. So... BAKE NAO!
                self._bake_static_lighting()

                # Step 3: Export all the things!
                self._export_scene_objects()

                # Step 3.1: Ensure referenced logic node trees are exported
                self._export_referenced_node_trees()

                # Step 3.2: Now that all Plasma Objects (save Mipmaps) are exported, we do any post
                #          processing that needs to inspect those objects
                self._post_process_scene_objects()

                # Step 3.3: Ensure any helper Python files are packed
                self._pack_ancillary_python()

                # Step 4: Finalize...
                self.mesh.material.finalize()
                self.mesh.finalize()

                # Step 5: FINALLY. Let's write the PRPs and crap.
                self._save_age()

                # Step 5.1: Save out the export report.
                #           If the export fails and this doesn't save, we have bigger problems than
                #           these little warnings and notices.
                self.report.progress_advance()
                self.report.progress_end()
                self.report.save()

                # Step 5.2: If any nonfatal errors were encountered during the export, we will
                #           raise them here, now that everything is finished, to draw attention
                #           to whatever the problem might be.
                self.report.raise_errors()

    def _bake_static_lighting(self):
        if self._op.lighting_method != "skip":
            self.oven.bake_static_lighting(self._objects)

    def _collect_objects(self):
        scene = bpy.context.scene
        self.report.progress_advance()
        self.report.progress_range = len(scene.objects)
        inc_progress = self.report.progress_increment

        # Grab a naive listing of enabled pages
        age = scene.world.plasma_age
        pages_enabled = frozenset((page.name for page in age.pages if page.enabled and self._op.version in page.version))
        external_pages = frozenset((page.name for page in age.pages if page.page_type == "external"))
        pages_enabled -= external_pages
        all_pages = frozenset((page.name for page in age.pages))

        # Because we can have an unnamed or a named default page, we need to see if that is enabled...
        for page in age.pages:
            if page.seq_suffix == 0:
                if page.page_type != "room":
                    raise explosions.ExportError(f"Default page '{page.name}' must be a Room page!")
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
        for obj in scene.objects:
            if obj.plasma_object.enabled:
                page = obj.plasma_object.page
                if not page and not default_inited:
                    self.mgr.create_page(self.age_name, "Default", 0)
                    default_inited = True

                if (default_enabled and not page) or (page in pages_enabled):
                    self._objects.append(obj)
                elif page not in all_pages or page in external_pages:
                    error.add(page, obj.name)
            inc_progress()
        error.raise_if_error()

    def _check_sanity(self):
        self.report.progress_advance()
        self.report.progress_range = len(self._objects)
        inc_progress = self.report.progress_increment

        self.report.msg("\nEnsuring Age is sane...")
        with self.report.indent():
            for bl_obj in self._objects:
                for mod in bl_obj.plasma_modifiers.modifiers:
                    fn = getattr(mod, "sanity_check", None)
                    if fn is not None:
                        fn()
                inc_progress()
        self.report.msg("... Age is grinning and holding a spatula. Must be OK, then.")

    def _export_age_info(self):
        # Make life slightly easier...
        age_info = bpy.context.scene.world.plasma_age
        age_name = self.age_name
        mgr = self.mgr

        # Generate the plAgeInfo
        mgr.AddAge(age_info.export(self))

        # Create all the pages we need
        ver = self._op.version
        for page in age_info.pages:
            if page.enabled and ver in page.version:
                external = page.page_type == "external"
                mgr.create_page(age_name, page.name, page.seq_suffix, external=external)
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
                self.report.msg(f"Attaching to parent SceneObject '{parent.name}'")
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
            ci_cls = bl.plasma_object.ci_type
            ci = self.mgr.add_object(ci_cls, bl=bl, so=so)

            # Now we have the "fun" work of filling in the CI
            ci.localToWorld = utils.matrix44(bl.matrix_world)
            ci.worldToLocal = ci.localToWorld.inverse()
            ci.localToParent = utils.matrix44(bl.matrix_local)
            ci.parentToLocal = ci.localToParent.inverse()
            return ci
        return so.coord.object

    def _export_localization(self):
        self.report.progress_advance()
        self.report.progress_range = len(self._objects)
        inc_progress = self.report.progress_increment

        self.report.msg("\nExporting localization...")

        with self.report.indent():
            for bl_obj in self._objects:
                for mod in filter(lambda x: hasattr(x, "export_localization"), bl_obj.plasma_modifiers.modifiers):
                    mod.export_localization(self)
                inc_progress()

    def _export_scene_objects(self):
        self.report.progress_advance()
        self.report.progress_range = len(self._objects)
        inc_progress = self.report.progress_increment
        log_msg = self.report.msg
        indent = self.report.indent

        for bl_obj in self._objects:
            log_msg(f"\n[SceneObject '{bl_obj.name}']")

            with indent():
                # First pass: do things specific to this object type.
                #             note the function calls: to export a MESH, it's _export_mesh_blobj
                export_fn = "_export_{}_blobj".format(bl_obj.type.lower())
                try:
                    export_fn = getattr(self, export_fn)
                except AttributeError:
                    self.report.warn("""'{}' is a Plasma Object of Blender type '{}'
                                    ... And I have NO IDEA what to do with that! Tossing.""".format(bl_obj.name, bl_obj.type))
                    continue
                log_msg(f"Blender Object '{bl_obj.name}' of type '{bl_obj.type}'")

                # Create a sceneobject if one does not exist.
                # Before we call the export_fn, we need to determine if this object is an actor of any
                # sort, and barf out a CI.
                sceneobject = self.mgr.find_create_object(plSceneObject, bl=bl_obj)
                self._export_actor(sceneobject, bl_obj)
                with indent():
                    export_fn(sceneobject, bl_obj)

                # And now we puke out the modifiers...
                for mod in bl_obj.plasma_modifiers.modifiers:
                    log_msg(f"Exporting '{mod.bl_label}' modifier")
                    with indent():
                        mod.export(self, bl_obj, sceneobject)
            inc_progress()

    def _export_camera_blobj(self, so, bo):
        # Hey, guess what? Blender's camera data is utter crap!
        camera = bo.data.plasma_camera
        self.camera.export_camera(so, bo, camera.camera_type, camera.settings, camera.transitions)

    def _export_empty_blobj(self, so, bo):
        pass

    def _export_lamp_blobj(self, so, bo):
        self.light.export_rtlight(so, bo)

    def _export_mesh_blobj(self, so, bo):
        if bo.data.materials:
            self.mesh.export_object(bo, so)
        else:
            self.report.msg("No material(s) on the ObData, so no drawables")

    def _export_font_blobj(self, so, bo):
        with utils.temporary_mesh_object(bo) as meshObj:
            if bo.data.materials:
                self.mesh.export_object(meshObj, so)
            else:
                self.report.msg("No material(s) on the ObData, so no drawables")

    def _export_referenced_node_trees(self):
        self.report.progress_advance()
        self.report.progress_range = len(self.want_node_trees)
        inc_progress = self.report.progress_increment
        log_msg = self.report.msg
        indent = self.report.indent

        log_msg("\nChecking Logic Trees...")
        with indent():
            for tree_name, references in self.want_node_trees.items():
                log_msg(f"NodeTree '{tree_name}'")
                with indent():
                    tree = bpy.data.node_groups[tree_name]
                    for bo, so in references:
                        tree.export(self, bo, so)
                inc_progress()

    def get_objects(self, page: Optional[str]) -> Iterator[bpy.types.Object]:
        yield from filter(
            lambda x: x.plasma_object.page == page,
            self._objects
        )

    def _harvest_actors(self):
        self.report.progress_advance()
        self.report.progress_range = len(self._objects) + len(bpy.data.textures)
        inc_progress = self.report.progress_increment

        for bl_obj in self._objects:
            for mod in bl_obj.plasma_modifiers.modifiers:
                if mod.enabled:
                    self.actors.update(mod.harvest_actors())
            inc_progress()

        # This is a little hacky, but it's an edge case... I guess?
        # We MUST have CoordinateInterfaces for EnvironmentMaps (DCMs, bah)
        for texture in bpy.data.textures:
            envmap = getattr(texture, "environment_map", None)
            if envmap is not None:
                viewpt = envmap.viewpoint_object
                if viewpt is not None:
                    self.actors.add(viewpt.name)
            inc_progress()

    def has_coordiface(self, bo):
        if bo.type in {"CAMERA", "EMPTY", "LAMP"}:
            return True
        if bo.parent is not None or bo.children:
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
        self.report.progress_advance()
        self.report.progress_range = len(self._objects)
        inc_progress = self.report.progress_increment
        log_msg = self.report.msg
        indent = self.report.indent

        log_msg("\nPost-Processing SceneObjects...")
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
            with indent():
                for mod in bl_obj.plasma_modifiers.modifiers:
                    proc = getattr(mod, "post_export", None)
                    if proc is not None:
                        self.report.msg(f"Post processing '{bl_obj.name}' modifier '{mod.bl_label}'")
                        with indent():
                            proc(self, bl_obj, sceneobject)
            inc_progress()

    def _pre_export_scene_objects(self):
        self.report.progress_advance()
        self.report.progress_range = len(self._objects)
        inc_progress = self.report.progress_increment
        log_msg = self.report.msg
        indent = self.report.indent
        log_msg("\nGenerating export dependency objects...")

        # New objects may be generate during this process; they will be appended at the end.
        new_objects = []

        @functools.singledispatch
        def handle_temporary(temporary, parent):
            # Maybe this was an embedded context manager?
            if hasattr(temporary, "__enter__"):
                ctx_temporary = self.exit_stack.enter_context(temporary)
                if ctx_temporary is not None:
                    return handle_temporary(ctx_temporary, parent)
            else:
                raise RuntimeError("Temporary object of type '{}' generated by '{}' was unhandled".format(temporary.__class__, parent.name))

        @handle_temporary.register(utils.BMeshObject)
        def _(temporary, parent):
            return handle_temporary(temporary.release(), parent)

        @handle_temporary.register(bpy.types.Action)
        def _(temporary, parent):
            self.exit_stack.enter_context(TemporaryObject(temporary, bpy.data.actions.remove))
            log_msg(f"'{parent.name}': generated Action '{temporary.name}'")
            return temporary

        @handle_temporary.register(bpy.types.Object)
        def _(temporary, parent):
            self.exit_stack.enter_context(TemporaryObject(temporary, bpy.data.objects.remove))
            log_msg(
                f"'{parent.name}': generated Object '{temporary.name}' "
                f"(Plasma Object: {temporary.plasma_object.enabled})",
            )
            if temporary.plasma_object.enabled:
                new_objects.append(temporary)

                # If the object is marked as a Plasma Object, be sure that we go into the same page
                # as the requestor, unless the modifier decided it knows better.
                if not temporary.plasma_object.is_property_set("page"):
                    temporary.plasma_object.page = parent.plasma_object.page

                # Wow, recursively generated objects. Aren't you special?
                with indent():
                    for mod in temporary.plasma_modifiers.modifiers:
                        mod.sanity_check()
                    do_pre_export(temporary)
            return temporary

        @handle_temporary.register(bpy.types.NodeTree)
        def _(temporary, parent):
            self.exit_stack.enter_context(TemporaryObject(temporary, bpy.data.node_groups.remove))
            log_msg(f"'{parent.name}' generated NodeTree '{temporary.name}'")
            if temporary.bl_idname == "PlasmaNodeTree":
                parent_so = self.mgr.find_create_object(plSceneObject, bl=parent)
                self.want_node_trees[temporary.name].add((parent, parent_so))
            return temporary

        def do_pre_export(bo):
            for mod in bo.plasma_modifiers.modifiers:
                proc = getattr(mod, "pre_export", None)
                if proc is not None:
                    # pre_export() should be a *generator*. Generators are bidirectional, although
                    # trivial usages simply yield values for the consumer. What we want to do here
                    # is use the bidirectional nature of generators to simplify the code in pre_export().
                    # We will pump the pre_export generator. With each pump, we will send the generator
                    # the very thing it gave us. That way, if pre_export needs to do some work on
                    # the object it generated, then it can do:
                    # ```
                    # my_object = yield create_something()
                    # my_object.foo = bar
                    # ```
                    # instead of the more verbose
                    # ```
                    # my_object = create_something()
                    # yield my_object
                    # my_object.foo = bar
                    # ```
                    pre_result = proc(self, bo)
                    assert (
                        inspect.isgenerator(pre_result) or pre_result is None,
                        "pre_export() should return a generator or None"
                    )
                    try:
                        gen_result = None
                        while pre_result is not None:
                            gen_result = pre_result.send(gen_result)
                            if gen_result is not None:
                                gen_result = handle_temporary(gen_result, bo)
                    except StopIteration as e:
                        if e.value is not None:
                            handle_temporary(e.value, bo)
                    finally:
                        if pre_result is not None:
                            pre_result.close()

        with indent():
            for bl_obj in self._objects:
                do_pre_export(bl_obj)
                inc_progress()

        log_msg(f"... {len(new_objects)} new object(s) were generated!")
        self._objects += new_objects

    def _pack_ancillary_python(self):
        texts = bpy.data.texts
        self.report.progress_advance()
        self.report.progress_range = len(texts)
        inc_progress = self.report.progress_increment

        for i in texts:
            if i.name.endswith(".py") and self.output.want_py_text(i):
                self.output.add_python_code(i.name, text_id=i)
            inc_progress()

    def _save_age(self):
        self.report.progress_advance()
        self.report.msg("\nWriting Age data...")

        # If something bad happens in the final flush, it would be a shame to
        # simply toss away the potentially freshly regenerated texture cache.
        with self.report.indent():
            try:
                self.locman.save()
                self.mgr.save_age()
                self.output.save()
            finally:
                self.image.save()

    @property
    def age_name(self):
        if self._op.dat_only:
            return Path(self._op.filepath).stem
        else:
            return bpy.context.scene.world.plasma_age.age_name

    @property
    def dat_only(self):
        return self._op.dat_only

    @property
    def envmap_method(self):
        return bpy.context.scene.world.plasma_age.envmap_method

    @property
    def python_method(self):
        return bpy.context.scene.world.plasma_age.python_method

    @property
    def texcache_path(self):
        age = bpy.context.scene.world.plasma_age
        filepath = age.texcache_path
        try:
            valid_path = filepath and Path(filepath).is_file()
        except OSError:
            valid_path = False

        if not valid_path:
            filepath = bpy.context.blend_data.filepath
            if not filepath:
                filepath = self._op.filepath
            filepath = str(Path(filepath).with_suffix(".ktc"))
            age.texcache_path = filepath
        return filepath

    @property
    def texcache_method(self):
        return bpy.context.scene.world.plasma_age.texcache_method
