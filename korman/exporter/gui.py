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
from PyHSPlasma import *
from typing import *
import weakref

from .explosions import ExportError
from .. import helpers
from . import utils

if TYPE_CHECKING:
    from .convert import Exporter
    from .logger import _ExportLogger as ExportLogger


class Clipping(NamedTuple):
    hither: float
    yonder: float


class PostEffectModMatrices(NamedTuple):
    c2w: hsMatrix44
    w2c: hsMatrix44


class GuiConverter:

    if TYPE_CHECKING:
        _parent: weakref.ref[Exporter] = ...

    def __init__(self, parent: Optional[Exporter] = None):
        self._parent = weakref.ref(parent) if parent is not None else None

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
        scale: float = 1.0,
    ) -> mathutils.Matrix:
        if not objects:
            raise ExportError("No objects specified for GUI Camera generation.")

        class ObjArea(NamedTuple):
            obj: bpy.types.Object
            area: float


        remove_mesh = bpy.data.meshes.remove
        obj_areas: List[ObjArea] = []
        for i in objects:
            mesh = i.to_mesh(bpy.context.scene, True, "RENDER", calc_tessface=False)
            with helpers.TemporaryObject(mesh, remove_mesh):
                utils.transform_mesh(mesh, i.matrix_world)
                obj_areas.append(
                    ObjArea(i, sum((polygon.area for polygon in mesh.polygons)))
                )
        largest_obj = max(obj_areas, key=lambda x: x.area)

        # GUIs are generally flat planes, which, by default in Blender, have their normal pointing
        # in the localspace z axis. Therefore, what we would like to do is have a camera that points
        # at the localspace -Z axis. Where up is the localspace +Y axis. We are already pointing at
        # -Z with +Y being up from what I can tel. So, just use this matrix.
        mat = largest_obj.obj.matrix_world.to_3x3()

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
            bound_boxes = (
                obj.matrix_world * mathutils.Vector(bbox)
                for obj in objects for bbox in obj.bound_box
            )
            co, _ = camera.camera_fit_coords(
                scene,
                # bound_box is a list of vectors of each corner of all the objects' bounding boxes;
                # however, Blender's API wants a sequence of individual channel positions. Therefore,
                # we need to flatten the vectors.
                list(itertools.chain.from_iterable(bound_boxes))
            )

            # Calculate the distance from the largest object to the camera. The scale we were given
            # will be used to push the camera back in the Z+ direction of that object by scale times.
            bvh = mathutils.bvhtree.BVHTree.FromObject(largest_obj.obj, scene)
            loc, normal, index, distance = bvh.find_nearest(co)
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

