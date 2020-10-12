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
import cProfile
from pathlib import Path
from PyHSPlasma import *
import pstats
import subprocess

from ..addon_prefs import game_versions
from .. import exporter
from ..helpers import UiHelper
from .. import korlib, plasma_launcher
from ..properties.prop_world import PlasmaAge

class ExportOperator:
    def _get_default_path(self, context):
        blend_filepath = context.blend_data.filepath
        if not blend_filepath:
            blend_filepath = context.scene.world.plasma_age.age_name
        if not blend_filepath:
            blend_filepath = "Korman"
        return blend_filepath

    @property
    def has_reports(self):
        return hasattr(self.report)

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class PlasmaAgeExportOperator(ExportOperator, bpy.types.Operator):
    """Exports ages for Cyan Worlds' Plasma Engine"""

    bl_idname = "export.plasma_age"
    bl_label = "Export Age"

    # Here's the rub: we define the properties in this dict. We're going to register them as a seekrit
    # over on the PlasmaAge world properties. We've got a helper so we can access them like they're actually on us...
    # If you want a volatile property, register it directly on this operator!
    _properties = {
        "verbose": (BoolProperty, {"name": "Display Verbose Log",
                                   "description": "Shows the verbose export log in the console",
                                   "default": False}),

        "show_console": (BoolProperty, {"name": "Display Log Console",
                                        "description": "Forces the Blender System Console open during the export",
                                        "default": True}),

        "transform_offsets": (BoolProperty, {"name": "Transform Texture Offsets",
                                        "description": "Transforms Blender Texture Offsets to Plasma during the export",
                                        "default": False}),

        "bad_beziers": (BoolProperty, {"name": "Hobble Bezier Animation",
                                        "description": "Forces Worst-Case Beziers during the export",
                                        "default": False}),

        "texcache_path": (StringProperty, {"name": "Texture Cache Path",
                                           "description": "Texture Cache Filepath"}),

        "texcache_method": (EnumProperty, {"name": "Texture Cache",
                                           "description": "Texture Cache Settings",
                                           "items": [("skip", "Don't Use Texture Cache", "The texture cache is neither used nor updated."),
                                                     ("use", "Use Texture Cache", "Use (and update, if needed) cached textures."),
                                                     ("rebuild", "Rebuild Texture Cache", "Rebuilds the texture cache from scratch.")],
                                           "default": "use"}),

        "lighting_method": (EnumProperty, {"name": "Static Lighting",
                                           "description": "Static Lighting Settings",
                                           "items": [("skip", "Don't Bake Lighting", "Static lighting is not baked during this export (fastest export)"),
                                                     ("bake", "Bake Lighting", "Static lighting is baked according to your specifications"),
                                                     ("force_vcol", "Force Vertex Color Bake", "All static lighting is baked as vertex colors (faster export)"),
                                                     ("force_lightmap", "Force Lightmap Bake", "All static lighting is baked as lightmaps (slower export)")],
                                           "default": "bake"}),

        "envmap_method": (EnumProperty, {"name": "Environment Maps",
                                         "description": "Environment Map Settings",
                                         "items": [("skip", "Don't Export EnvMaps", "Environment Maps are not exported"),
                                                   ("dcm2dem", "Downgrade Planar EnvMaps", "When the engine doesn't support them, Planar Environment Maps are downgraded to Cube Maps"),
                                                   ("perengine", "Export Supported EnvMaps", "Only environment maps supported by the selected game engine are exported")],
                                         "default": "dcm2dem"}),

        "python_method": (EnumProperty, {"name": "Python",
                                         "description": "Specifies how Python should be packed",
                                         "items": [("none", "Pack Nothing", "Don't pack any Python files."),
                                                   ("as_requested", "Pack Requested Scripts", "Packs any script both linked as a Text file and requested for packaging."),
                                                   ("all", "Pack All Scripts", "Packs all Python files linked as a Text file.")],
                                         "default": "as_requested",
                                         "options": set()}),

        "export_active": (BoolProperty, {"name": "INTERNAL: Export currently running",
                                         "default": False,
                                         "options": {"SKIP_SAVE"}}),
    }

    # This wigs out and very bad things happen if it's not directly on the operator...
    filepath = StringProperty(subtype="FILE_PATH")
    filter_glob = StringProperty(default="*.age;*.zip", options={'HIDDEN'})

    version = EnumProperty(name="Version",
                           description="Plasma version to export this age for",
                           items=game_versions,
                           default="pvPots",
                           options=set())

    dat_only = BoolProperty(name="Export Only PRPs",
                            description="Only the Age PRPs should be exported",
                            default=True,
                            options={"HIDDEN"})

    actions = EnumProperty(name="Actions",
                           description="Actions for the exporter to perform",
                           default={"EXPORT"},
                           items=[("EXPORT", "Export", "Export the age data"),
                                  ("PROFILE", "Profile", "Profile the exporter"),
                                  ("LAUNCH", "Launch Age", "Launch the age in Plasma")],
                           options={"ENUM_FLAG"})

    ki = IntProperty(name="KI",
                     description="KI Number of the player to use when launching the game",
                     options=set())

    player = StringProperty(name="Player",
                            description="Name of the player to use when launching the game",
                            options=set())

    serverini = StringProperty(name="Server INI",
                               description="Name of the server configuation to use when launching the game",
                               options=set())

    def draw(self, context):
        layout = self.layout
        age = context.scene.world.plasma_age

        # The crazy mess we're doing with props on the fly means we have to explicitly draw them :(
        layout.prop(self, "actions")
        layout.prop(self, "version")
        if "LAUNCH" in self.actions:
            if self.version == "pvMoul":
                layout.alert = not self.ki
                layout.prop(self, "ki")
                layout.alert = False
                layout.prop(self, "serverini")
            else:
                layout.alert = not self.player.strip()
                layout.prop(self, "player")
                layout.alert = False
        layout.prop(age, "texcache_method", text="")
        layout.prop(age, "lighting_method")
        row = layout.row()
        row.enabled = korlib.ConsoleToggler.is_platform_supported()
        row.prop(age, "show_console")
        layout.prop(age, "verbose")

    def __getattr__(self, attr):
        if attr in self._properties:
            return getattr(bpy.context.scene.world.plasma_age, attr)
        raise AttributeError(attr)

    def __setattr__(self, attr, value):
        if attr in self._properties:
            setattr(bpy.context.scene.world.plasma_age, attr, value)
        else:
            super().__setattr__(attr, value)

    def execute(self, context):
        # Before we begin, do some basic sanity checking...
        if not self.actions:
            self.report({"ERROR"}, "Nothing to do?")
            return {"CANCELLED"}

        path = Path(self.filepath)
        if not self.filepath:
            self.error = "No file specified"
            return {"CANCELLED"}
        else:
            if not path.exists:
                try:
                    path.mkdir(parents=True)
                except:
                    self.report({"ERROR"}, "Failed to create export directory")
                    return {"CANCELLED"}
            path.touch()

        # We need to back out of edit mode--this ensures that all changes are committed
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        ageName = path.stem
        if korlib.is_python_keyword(ageName):
            self.report({"ERROR"}, "The Age name conflicts with the Python keyword '{}'".format(ageName))
            return {"CANCELLED"}

        # This prevents us from finding out at the very end that very, very bad things happened...
        if "LAUNCH" in self.actions:
            try:
                self._sanity_check_run_plasma()
            except exporter.ExportError as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

        # Separate blender operator and actual export logic for my sanity
        if "EXPORT" in self.actions:
            with UiHelper(context) as _ui:
                e = exporter.Exporter(self)
                try:
                    self.export_active = True
                    if "PROFILE" in self.actions:
                        profile_path = str(path.with_name("{}_cProfile".format(ageName)))
                        profile = cProfile.runctx("e.run()", globals(), locals(), profile_path)
                    else:
                        e.run()
                except exporter.ExportError as error:
                    self.report({"ERROR"}, str(error))
                    return {"CANCELLED"}
                except exporter.NonfatalExportError as error:
                    self.report({"ERROR"}, str(error))
                else:
                    if "PROFILE" in self.actions:
                        stats_out = path.with_name("{}_profile.log".format(ageName))
                        with open(str(stats_out), "w") as out:
                            stats = pstats.Stats(profile_path, stream=out)
                            stats = stats.sort_stats("time", "calls")
                            stats.print_stats()
                finally:
                    self.export_active = False

        if "LAUNCH" in self.actions:
            try:
                self._run_plasma(context)
            except exporter.ExportError as error:
                self.report({"ERROR"}, str(error))
                return {"CANCELLED"}

        return {"FINISHED"}

    def invoke(self, context, event):
        # Called when a user hits "export" from the menu
        # We will prompt them for the export info, then call execute()
        if not self.filepath:
            bfp = self._get_default_path(context)
            self.filepath = str(Path(bfp).with_suffix(".age"))
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    @classmethod
    def register(cls):
        # BEGIN MAJICK
        # Register the exporter properties such that they will persist
        for name, (prop, options) in cls._properties.items():
            # Hide these settings from being seen on the age properties
            age_options = dict(options)
            bl_options = age_options.setdefault("options", set())
            bl_options.add("HIDDEN")

            # Now do the majick
            setattr(PlasmaAge, name, prop(**age_options))

    def _sanity_check_run_plasma(self):
        if not bpy.app.binary_path_python:
            raise exporter.PlasmaLaunchError("Can't Launch Plasma: No Python executable available")
        if self.version == "pvMoul":
            if not self.ki:
                raise exporter.PlasmaLaunchError("Can't Launch Plasma: Player KI not set")
        else:
            if not self.player:
                raise exporter.PlasmaLaunchError("Can't Launch Plasma: Player Name not set")

    def _run_plasma(self, context):
        path = Path(self.filepath)
        client_dir = path.parent.parent

        # It would be nice to launch URU right here. Unfortunately, for single player URUs, we will
        # need to actually wait for the whole rigamaroll to finish. Therefore, we need to kick
        # open a separate python exe to launch URU and wait.
        args = [bpy.app.binary_path_python, plasma_launcher.__file__,
                str(client_dir), path.stem, self.version]
        if self.version == "pvMoul":
            if self.serverini:
                args.append("--serverini")
                args.append(self.serverini)
            args.append(str(self.ki))
        else:
            args.append(self.player)

        with exporter.ExportVerboseLogger() as log:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=str(client_dir), universal_newlines=True)
            while True:
                line = proc.stdout.readline().strip()
                if line == "DIE":
                    raise exporter.PlasmaLaunchError(proc.stderr.read().strip())
                elif line in {"PLASMA_RUNNING", "DONE"}:
                    break
                elif proc.returncode is not None:
                    break
                elif line:
                    log.msg(line)


class PlasmaLocalizationExportOperator(ExportOperator, bpy.types.Operator):
    bl_idname = "export.plasma_loc"
    bl_label = "Export Localization"
    bl_description = "Export Age localization data"

    filepath = StringProperty(subtype="DIR_PATH")
    filter_glob = StringProperty(default="*.pak", options={'HIDDEN'})

    version = EnumProperty(name="Version",
                           description="Plasma version to export this age for",
                           items=game_versions,
                           default="pvPots",
                           options=set())

    def execute(self, context):
        path = Path(self.filepath)
        if not self.filepath:
            self.report({"ERROR"}, "No file specified")
            return {"CANCELLED"}
        else:
            if not path.exists:
                try:
                    path.mkdir(parents=True)
                except OSError:
                    self.report({"ERROR"}, "Failed to create export directory")
                    return {"CANCELLED"}

        # Age names cannot be python keywords
        age_name = context.scene.world.plasma_age.age_name
        if korlib.is_python_keyword(age_name):
            self.report({"ERROR"}, "The Age name conflicts with the Python keyword '{}'".format(age_name))
            return {"CANCELLED"}

        # Bonus Fun: Implement Profile-mode here (later...)
        e = exporter.LocalizationConverter(age_name=age_name, path=self.filepath,
                                           version=globals()[self.version])
        try:
            e.run()
        except exporter.ExportError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        except exporter.NonfatalExportError as error:
            self.report({"WARNING"}, str(error))
            return {"FINISHED"}
        else:
            return {"FINISHED"}


class PlasmaPythonExportOperator(ExportOperator, bpy.types.Operator):
    bl_idname = "export.plasma_pak"
    bl_label = "Export Python Scripts"
    bl_description = "Export Age python script package"

    filepath = StringProperty(subtype="FILE_PATH")
    filter_glob = StringProperty(default="*.pak", options={'HIDDEN'})

    version = EnumProperty(name="Version",
                           description="Plasma version to export this age for",
                           items=game_versions,
                           default="pvPots",
                           options=set())

    def draw(self, context):
        layout = self.layout
        age = context.scene.world.plasma_age

        # The crazy mess we're doing with props on the fly means we have to explicitly draw them :(
        row = layout.row()
        row.alert = age.python_method == "none"
        row.prop(age, "python_method")
        layout.prop(self, "version")
        row = layout.row()
        row.enabled = korlib.ConsoleToggler.is_platform_supported()
        row.prop(age, "show_console")
        layout.prop(age, "verbose")       

    def execute(self, context):
        path = Path(self.filepath)
        if not self.filepath:
            self.report({"ERROR"}, "No file specified")
            return {"CANCELLED"}
        else:
            if not path.exists:
                try:
                    path.mkdir(parents=True)
                except OSError:
                    self.report({"ERROR"}, "Failed to create export directory")
                    return {"CANCELLED"}
            path.touch()

        # Age names cannot be python keywords
        age_name = context.scene.world.plasma_age.age_name
        if korlib.is_python_keyword(age_name):
            self.report({"ERROR"}, "The Age name conflicts with the Python keyword '{}'".format(age_name))
            return {"CANCELLED"}

        # Bonus Fun: Implement Profile-mode here (later...)
        e = exporter.PythonPackageExporter(filepath=self.filepath,
                                           version=globals()[self.version])
        try:
            e.run()
        except exporter.ExportError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        except korlib.PythonNotAvailableError as error:
            self.report({"ERROR"}, "Python Version {} not found".format(error))
            return {"CANCELLED"}
        except exporter.NonfatalExportError as error:
            self.report({"WARNING"}, str(error))
            return {"FINISHED"}
        else:
            return {"FINISHED"}

    def invoke(self, context, event):
        if not self.filepath:
            bfp = self._get_default_path(context)
            self.filepath = str(Path(bfp).with_suffix(".pak"))
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# Add the export operator to the Export menu :)
def menu_cb(self, context):
    if context.scene.render.engine == "PLASMA_GAME":
        self.layout.operator_context = "INVOKE_DEFAULT"
        self.layout.operator(PlasmaAgeExportOperator.bl_idname, text="Plasma Age (.age)")
        self.layout.operator(PlasmaPythonExportOperator.bl_idname, text="Plasma Scripts (.pak)")


def register():
    bpy.types.INFO_MT_file_export.append(menu_cb)

def unregister():
    bpy.types.INFO_MT_file_export.remove(menu_cb)
