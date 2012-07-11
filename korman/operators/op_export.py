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
import os, os.path
from .. import exporter

class ExportOperator(bpy.types.Operator):
    """Exports ages for Cyan Worlds' Plasma Engine"""

    bl_idname = "export.plasma_age"
    bl_label = "Export Age"
    bl_options = {"BLOCKING"}

    # Export specific props
    version = bpy.props.EnumProperty(
        name="Version",
        description="Version of the Plasma Engine to target",
        default="pvPots", # This should be changed when moul is easier to target!
        items=[
            ("pvPrime", "Ages Beyond Myst (63.11)", "Targets the original Uru (Live) game", 2),
            ("pvPots", "Path of the Shell (63.12)", "Targets the most recent offline expansion pack", 1),
            ("pvMoul", "Myst Online: Uru Live (70)", "Targets the most recent online game", 0),
            # I see no reason to even offer Myst 5...
        ]
    )
    optimize = bpy.props.BoolProperty(name="Optimize Age",
                                      description="Optimizes your age to run faster. This slows down export.")
    save_state = bpy.props.BoolProperty(name="Save State",
                                        description="Saves your age's state to the server for subsequent link ins.",
                                        default=True)
    use_texture_page = bpy.props.BoolProperty(name="Use Texture Page",
                                              description="Exports all textures to a dedicated Textures page",
                                              default=True)
    filepath = bpy.props.StringProperty(subtype="FILE_PATH")

    @property
    def has_reports(self):
        return hasattr(self.report)

    @classmethod
    def poll(cls, context):
        if context.object is not None:
            return context.scene.render.engine == "PLASMA_GAME"

    def execute(self, context):
        # Before we begin, do some basic sanity checking...
        if self.filepath == "":
            self.error = "No file specified"
            return {"CANCELLED"}
        else:
            dir = os.path.split(self.filepath)[0]
            if not os.path.exists(dir):
                try:
                    os.mkdirs(dir)
                except os.error:
                    self.report({"ERROR"}, "Failed to create export directory")
                    return {"CANCELLED"}

        # Separate blender operator and actual export logic for my sanity
        e = exporter.Exporter(self)
        try:
            e.run()
        except exporter.ExportError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        else:
            return {"FINISHED"}

    def invoke(self, context, event):
        # Called when a user hits "export" from the menu
        # We will prompt them for the export info, then call execute()
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# Add the export operator to the Export menu :)
def menu_cb(self, context):
    if context.scene.render.engine == "PLASMA_GAME":
        self.layout.operator_context = "INVOKE_DEFAULT"
        self.layout.operator(ExportOperator.bl_idname, text="Plasma Age (.age)")
def register():
    bpy.types.INFO_MT_file_export.append(menu_cb)
