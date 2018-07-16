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

class CameraButtonsPanel:
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return (context.camera and context.scene.render.engine == "PLASMA_GAME")


class PlasmaCameraPanel(CameraButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Camera"

    def draw(self, context):
        camera = context.camera.plasma_camera
        layout = self.layout

        layout.prop(camera, "camera_type")
        layout.separator()
        draw_camera_properties(camera.camera_type, camera.settings, layout, context)


class PlasmaCameraTransitionPanel(CameraButtonsPanel, bpy.types.Panel):
    bl_label = "Plasma Transitions"

    def draw(self, context):
        pass


def draw_camera_properties(cam_type, props, layout, context, force_no_anim=False):
    trans = props.transition

    def _draw_gated_prop(layout, props, gate_prop, actual_prop):
        row = layout.row(align=True)
        row.prop(props, gate_prop, text="")
        row = row.row(align=True)
        row.active = getattr(props, gate_prop)
        row.prop(props, actual_prop)
    def _is_camera_animated(cam_type, props, context, force_no_anim):
        if force_no_anim or cam_type == "rail":
            return False
        # Check for valid animation data on either the object or the camera
        # TODO: Should probably check for valid FCurve channels at some point???
        for i in (props.id_data, context.object):
            if i.animation_data is None:
                continue
            if i.animation_data.action is not None:
                return True
        return False

    # Point of Attention
    split = layout.split()
    col = split.column()
    col.label("Camera Mode:")
    col = col.column()
    col.alert = cam_type != "fixed" and props.poa_type == "none"
    col.prop(props, "poa_type", text="")
    col.alert = False
    row = col.row()
    row.active = props.poa_type == "object"
    row.prop(props, "poa_object", text="")
    col.separator()
    col.prop(props, "primary_camera")

    # Miscellaneous
    col = split.column()
    col.label("Tracking Settings:")
    col.prop(props, "maintain_los")
    col.prop(props, "fall_vertical")
    col.prop(props, "fast_run")
    col.prop(props, "ignore_subworld")

    # PoA Tracking
    layout.separator()
    split = layout.split()
    col = split.column()
    col.label("Default Tracking Transition:")
    col.prop(trans, "poa_acceleration", text="Acceleration")
    col.prop(trans, "poa_deceleration", text="Deceleration")
    col.prop(trans, "poa_velocity", text="Maximum Velocity")
    col.prop(trans, "poa_cut")

    # PoA Offset
    col = split.column()
    col.label("Point of Attention Offset:")
    col.prop(props, "poa_offset", text="")
    col.prop(props, "poa_worldspace")

    # Position Tracking (only for follow cams)
    layout.separator()
    split = layout.split()
    col = split.column()

    # Position Transitions
    col.active = cam_type != "circle"
    col.label("Default Position Transition:")
    col.prop(trans, "pos_acceleration", text="Acceleration")
    col.prop(trans, "pos_deceleration", text="Deceleration")
    col.prop(trans, "pos_velocity", text="Maximum Velocity")
    col.prop(trans, "pos_cut")

    # Position Offsets
    col = split.column()
    col.active = cam_type == "follow"
    col.label("Position Offset:")
    col.prop(props, "pos_offset", text="")
    col.prop(props, "pos_worldspace")

    # Camera Panning
    layout.separator()
    split = layout.split()
    col = split.column()
    col.label("Limit Panning:")
    col.prop(props, "x_pan_angle")
    col.prop(props, "y_pan_angle")

    # Camera Zoom
    col = split.column()
    col.label("Field of View:")
    col.prop(props, "fov")
    _draw_gated_prop(col, props, "limit_zoom", "zoom_min")
    _draw_gated_prop(col, props, "limit_zoom", "zoom_max")
    _draw_gated_prop(col, props, "limit_zoom", "zoom_rate")

    # Circle Camera Stuff
    layout.separator()
    split = layout.split()
    col = split.column()
    col.active = cam_type == "circle"
    col.label("Circle Camera:")
    col.prop(props, "circle_center", text="")
    col.prop(props, "circle_pos", text="")
    col.prop(props, "circle_velocity")
    row = col.row(align=True)
    row.active = props.circle_center is None
    row.prop(props, "circle_radius_ui")

    # Animated Camera Stuff
    col = split.column()
    col.active = _is_camera_animated(cam_type, props, context, force_no_anim)
    col.label("Animation:")
    col.prop(props, "start_on_push")
    col.prop(props, "stop_on_pop")
    col.prop(props, "reset_on_pop")
