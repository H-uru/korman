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
from PyHSPlasma import *

class PlasmaExporter(bpy.types.Operator):
    """Exports ages for Cyan Worlds' Plasma Engine"""

    bl_idname = "export.plasma_age"
    bl_label = "Export Age"

    # Export specific props
    pl_version = bpy.props.EnumProperty(
        name="Version",
        description="Version of the Plasma Engine to target",
        default="pots", # This should be changed when moul is easier to target!
        items=[
            ("abm", "Ages Beyond Myst (63.11)", "Targets the original Uru (Live) game", 2),
            ("pots", "Path of the Shell (63.12)", "Targets the most recent offline expansion pack", 1),
            ("moul", "Myst Online: Uru Live (70.2)", "Targets the most recent online game", 0),
            # I see no reason to even offer Myst 5...
        ]
    )

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        # TODO
        return {"FINISHED"}

    def invoke(self, context, event):
        # Called when a user hits "export" from the menu
        # We will prompt them for the export info, then call execute()
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# Add the export operator to the Export menu :)
def menu_cb(self, context):
    self.layout.operator_context = "INVOKE_DEFAULT"
    self.layout.operator(PlasmaExporter.bl_idname, text="Plasma Age (.age)")
bpy.types.INFO_MT_file_export.append(menu_cb)
