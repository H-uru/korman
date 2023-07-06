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

from __future__ import annotations

import bpy
from bpy.props import *

import math

from ..exporter.explosions import ExportError
from ..exporter.gui import GuiConverter

class CameraOperator:
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class PlasmaGameGuiCameraOperator(CameraOperator, bpy.types.Operator):
    bl_idname = "camera.plasma_create_game_gui_camera"
    bl_label = "Create Game GUI Camera"

    fov: float = FloatProperty(
        name="Field of View",
        description="",
        subtype="ANGLE",
        default=math.radians(90.0),
        min=0.0,
        max=math.radians(360.0),
        precision=1,
        options=set()
    )
    gui_page: str = StringProperty(
        name="GUI Page",
        description="",
        options={"HIDDEN"}
    )
    scale: float = FloatProperty(
        name="GUI Scale",
        description="",
        default=1.02,
        min=0.001,
        soft_max=2.0,
        precision=2,
        options=set()
    )

    mod_id: str = StringProperty(options={"HIDDEN"})
    cam_prop_name: str = StringProperty(options={"HIDDEN"})

    def execute(self, context):
        # If the modifier has been given to us, select all of the objects in the
        # given GUI page.
        if self.gui_page:
            for i in context.scene.objects:
                i.select = i.plasma_object.page == self.gui_page
            context.scene.update()

        visible_objects = [
            i for i in context.selected_objects
            if i.type in {"MESH", "FONT"}
        ]

        gui = GuiConverter()
        try:
            cam_matrix = gui.calc_camera_matrix(
                context.scene,
                visible_objects,
                self.fov,
                self.scale
            )
        except ExportError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        if self.mod_id and self.cam_prop_name:
            modifier = getattr(context.object.plasma_modifiers, self.mod_id)
            cam_obj = getattr(modifier, self.cam_prop_name)
        else:
            cam_obj = None
        if cam_obj is None:
            if self.gui_page:
                name = f"{self.gui_page}_GUICamera"
            else:
                name = f"{context.object.name}_GUICamera"
            cam_data = bpy.data.cameras.new(name)
            cam_obj = bpy.data.objects.new(name, cam_data)
            context.scene.objects.link(cam_obj)

        cam_obj.matrix_world = cam_matrix
        cam_obj.data.angle = self.fov
        cam_obj.data.lens_unit = "FOV"

        for i in context.scene.objects:
            i.select = i == cam_obj

        if self.mod_id and self.cam_prop_name:
            modifier = getattr(context.object.plasma_modifiers, self.mod_id)
            setattr(modifier, self.cam_prop_name, cam_obj)
        return {"FINISHED"}
