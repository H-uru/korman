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
import mathutils

from contextlib import contextmanager, ExitStack
import itertools
import math
from PyHSPlasma import *
from typing import *
import weakref

from .explosions import ExportError
from .. import helpers
from . import utils

if TYPE_CHECKING:
    from .convert import Exporter
    from .logger import _ExportLogger as ExportLogger
    from ..properties.modifiers.game_gui import *


class Clipping(NamedTuple):
    hither: float
    yonder: float


class PostEffectModMatrices(NamedTuple):
    c2w: hsMatrix44
    w2c: hsMatrix44


class GuiConverter:

    if TYPE_CHECKING:
        _parent: weakref.ref[Exporter] = ...
        _pages: Dict[str, Any] = ...
        _mods_exported: Set[str] = ...

    def __init__(self, parent: Optional[Exporter] = None):
        self._parent = weakref.ref(parent) if parent is not None else None
        self._pages = {}
        self._mods_exported = set()

        # Go ahead and prepare the GUI transparent material for future use.
        if parent is not None:
            self._transp_material = parent.exit_stack.enter_context(
                helpers.TemporaryObject(
                    bpy.data.materials.new("GUITransparent"),
                    bpy.data.materials.remove
                )
            )
            self._transp_material.diffuse_color = mathutils.Vector((1.0, 1.0, 0.0))
            self._transp_material.use_mist = False

            # Cyan's transparent GUI materials just set an opacity of 0%
            tex_slot = self._transp_material.texture_slots.add()
            tex_slot.texture = parent.exit_stack.enter_context(
                helpers.TemporaryObject(
                    bpy.data.textures.new("AutoTransparentLayer", "NONE"),
                    bpy.data.textures.remove
                )
            )
            tex_slot.texture.plasma_layer.opacity = 0.0
        else:
            self._transp_material = None

    def calc_camera_matrix(
        self,
        scene: bpy.types.Scene,
        objects: Sequence[bpy.types.Object],
        fov: float,
        scale: float = 0.75
    ) -> mathutils.Matrix:
        if not objects:
            raise ExportError("No objects specified for GUI Camera generation.")

        # Generally, GUIs are flat planes. However, we are not Cyan, so artists cannot walk down
        # the hallway to get smacked on the knuckles by programmers. This means that they might
        # give us some three dimensional crap as a GUI. Therefore, to come up with a camera matrix,
        # we'll use the average area-weighted inverse normal of all the polygons they give us. That
        # way, the camera *always* should face the GUI as would be expected.
        remove_mesh = bpy.data.meshes.remove
        avg_normal = mathutils.Vector()
        for i in objects:
            mesh = i.to_mesh(bpy.context.scene, True, "RENDER", calc_tessface=False)
            with helpers.TemporaryObject(mesh, remove_mesh):
                utils.transform_mesh(mesh, i.matrix_world)
                for polygon in mesh.polygons:
                    avg_normal += (polygon.normal * polygon.area)
        avg_normal.normalize()
        avg_normal *= -1.0

        # From the inverse area weighted normal we found above, get the rotation from the up axis
        # (that is to say, the +Z axis) and create our rotation matrix.
        axis = mathutils.Vector((avg_normal.x, avg_normal.y, 0.0))
        axis.normalize()
        angle = math.acos(avg_normal.z)
        mat = mathutils.Matrix.Rotation(angle, 3, axis)

        # Now, we know the rotation of the camera. Great! What we need to do now is ensure that all
        # of the objects in question fit within the view of a 4:3 camera rotated as above. Blender
        # helpfully provides us with the localspace bounding boxes of all the objects and an API to
        # fit points into the camera view.
        with ExitStack() as stack:
            stack.enter_context(self.generate_camera_render_settings(scene))

            # Create a TEMPORARY camera object so we can use a certain Blender API.
            camera = stack.enter_context(utils.temporary_camera_object(scene, "GUICameraTemplate"))
            camera.matrix_world = mat.to_4x4()
            camera.data.angle = fov
            camera.data.lens_unit = "FOV"

            # Get all of the bounding points and make sure they all fit inside the camera's view frame.
            bound_boxes = [
                obj.matrix_world * mathutils.Vector(bbox)
                for obj in objects for bbox in obj.bound_box
            ]
            co, _ = camera.camera_fit_coords(
                scene,
                # bound_box is a list of vectors of each corner of all the objects' bounding boxes;
                # however, Blender's API wants a sequence of individual channel positions. Therefore,
                # we need to flatten the vectors.
                list(itertools.chain.from_iterable(bound_boxes))
            )

            # This generates a list of 6 faces per bounding box, which we then flatten out and pass
            # into the BVHTree constructor. This is to calculate the distance from the camera to the
            # "entire GUI" - which we can then use to apply the scale given to us.
            if scale != 1.0:
                bvh = mathutils.bvhtree.BVHTree.FromPolygons(
                    bound_boxes,
                    list(itertools.chain.from_iterable(
                        [(i + 0, i + 1, i + 5, i + 4),
                         (i + 1, i + 2, i + 5, i + 6),
                         (i + 3, i + 2, i + 6, i + 7),
                         (i + 0, i + 1, i + 2, i + 3),
                         (i + 0, i + 3, i + 7, i + 4),
                         (i + 4, i + 5, i + 6, i + 7),
                        ] for i in range(0, len(bound_boxes), 8)
                    ))
                )
                loc, normal, index, distance = bvh.find_nearest(co)

                # Sometimes, Blender gives us back a zero length normal.
                # This (obviously) causes the scale calculation to fail.
                # Debounce that.
                if normal.length_squared == 0.0:
                    normal = loc - co
                    normal.normalize()
                    assert normal.length_squared != 0.0

                co += normal * distance * (scale - 1.0)

            # ...
            mat.resize_4x4()
            mat.translation = co
            return mat

    def calc_clipping(
            self,
            pose: mathutils.Matrix,
            scene: bpy.types.Scene,
            objects: Sequence[bpy.types.Object],
            fov: float
        ) -> Clipping:
        with ExitStack() as stack:
            stack.enter_context(self.generate_camera_render_settings(scene))
            camera = stack.enter_context(utils.temporary_camera_object(scene, "GUICameraTemplate"))
            camera.matrix_world = pose
            camera.data.angle = fov
            camera.data.lens_unit = "FOV"

            # Determine the camera plane's normal so we can do a distance check against the
            # bounding boxes of the objects shown in the GUI.
            view_frame = [i * pose for i in camera.data.view_frame(scene)]
            cam_plane = mathutils.geometry.normal(view_frame)
            bound_boxes = (
                obj.matrix_world * mathutils.Vector(bbox)
                for obj in objects for bbox in obj.bound_box
            )
            pos = pose.to_translation()
            bounds_dists = [
                abs(mathutils.geometry.distance_point_to_plane(i, pos, cam_plane))
                for i in bound_boxes
            ]

            # Offset them by some epsilon to ensure the objects are rendered.
            hither, yonder = min(bounds_dists), max(bounds_dists)
            if yonder - 0.5 < hither:
                hither -= 0.25
                yonder += 0.25
            return Clipping(hither, yonder)

    def convert_post_effect_matrices(self, camera_matrix: mathutils.Matrix) -> PostEffectModMatrices:
        # PostEffectMod matrices face *away* from the GUI... For some reason.
        # See plPostEffectMod::SetWorldToCamera()
        c2w = utils.matrix44(camera_matrix)
        w2c = utils.matrix44(camera_matrix.inverted())
        for i in range(4):
            c2w[i, 2] *= -1.0
            w2c[2, i] *= -1.0
        return PostEffectModMatrices(c2w, w2c)

    def check_pre_export(self, name: str, **kwargs):
        previous = self._pages.setdefault(name, kwargs)
        if previous != kwargs:
            diff = set(previous.items()) - set(kwargs.items())
            raise ExportError(f"GUI Page '{name}' has target modifiers with conflicting settings:\n{diff}")

    def create_note_gui(self, gui_page: str, gui_camera: bpy.types.Object):
        if not gui_page in self._mods_exported:
            guidialog_object = utils.create_empty_object(f"{gui_page}_NoteDialog")
            guidialog_object.plasma_object.enabled = True
            guidialog_object.plasma_object.page = gui_page
            yield guidialog_object

            guidialog_mod: PlasmaGameGuiDialogModifier = guidialog_object.plasma_modifiers.gui_dialog
            guidialog_mod.enabled = True
            guidialog_mod.is_modal = True
            if gui_camera is not None:
                guidialog_mod.camera_object = gui_camera
            else:
                # Abuse the GUI Dialog's lookat caLculation to make us a camera that looks at everything
                # the artist has placed into the GUI page. We want to do this NOW because we will very
                # soon be adding more objects into the GUI page.
                camera_object = yield utils.create_camera_object(f"{gui_page}_GUICamera")
                camera_object.data.angle = math.radians(45.0)
                camera_object.data.lens_unit = "FOV"

                visible_objects = [
                    i for i in self._parent().get_objects(gui_page)
                    if i.type == "MESH" and i.data.materials
                ]
                camera_object.matrix_world = self.calc_camera_matrix(
                    bpy.context.scene,
                    visible_objects,
                    camera_object.data.angle
                )
                clipping = self.calc_clipping(
                    camera_object.matrix_world,
                    bpy.context.scene,
                    visible_objects,
                    camera_object.data.angle
                )
                camera_object.data.clip_start = clipping.hither
                camera_object.data.clip_end = clipping.yonder
                guidialog_mod.camera_object = camera_object

            # Begin creating the object for the clickoff plane. We want to yield it immediately
            # to the exporter in case something goes wrong during the export, allowing the stale
            # object to be cleaned up.
            click_plane_object = utils.BMeshObject(f"{gui_page}_Exit")
            click_plane_object.matrix_world = guidialog_mod.camera_object.matrix_world
            click_plane_object.plasma_object.enabled = True
            click_plane_object.plasma_object.page = gui_page
            yield click_plane_object

            # We have a camera on guidialog_mod.camera_object. We will now use it to generate the
            # points for the click-off plane button.
            # TODO: Allow this to be configurable to 4:3, 16:9, or 21:9?
            with ExitStack() as stack:
                stack.enter_context(self.generate_camera_render_settings(bpy.context.scene))
                toggle = stack.enter_context(helpers.GoodNeighbor())

                # Temporarily adjust the clipping plane out to the farthest point we can find to ensure
                # that the click-off button ecompasses everything. This is a bit heavy-handed, but if
                # you want more refined control, you won't be using this helper.
                clipping = max((guidialog_mod.camera_object.data.clip_start, guidialog_mod.camera_object.data.clip_end))
                toggle.track(guidialog_mod.camera_object.data, "clip_start", clipping - 0.1)
                view_frame = guidialog_mod.camera_object.data.view_frame(bpy.context.scene)

            click_plane_object.data.materials.append(self.transparent_material)
            with click_plane_object as click_plane_mesh:
                verts = [click_plane_mesh.verts.new(i) for i in view_frame]
                face = click_plane_mesh.faces.new(verts)
                # TODO: Ensure the face is pointing toward the camera!
                # I feel like we should be fine by assuming that Blender returns the viewframe
                # verts in the correct order, but this is Blender... So test that assumption carefully.
                # TODO: Apparently not!
                face.normal_flip()

            # We've now created the mesh object - handle the GUI Button stuff
            click_plane_object.plasma_modifiers.gui_button.enabled = True

            # NOTE: We will be using xDialogToggle.py, so we use a special tag ID instead of the
            # close dialog procedure.
            click_plane_object.plasma_modifiers.gui_control.tag_id = 99

        self._mods_exported.add(gui_page)

    @contextmanager
    def generate_camera_render_settings(self, scene: bpy.types.Scene) -> Iterator[None]:
        # Set the render info to basically TV NTSC 4:3, which will set Blender's camera
        # viewport up as a 4:3 thingy to match Plasma.
        with helpers.GoodNeighbor() as toggle:
            toggle.track(scene.render, "resolution_x", 720)
            toggle.track(scene.render, "resolution_y", 486)
            toggle.track(scene.render, "pixel_aspect_x", 10.0)
            toggle.track(scene.render, "pixel_aspect_y", 11.0)
            yield

    @property
    def _report(self) -> ExportLogger:
        return self._parent().report

    @property
    def transparent_material(self) -> bpy.types.Material:
        assert self._transp_material is not None
        return self._transp_material

