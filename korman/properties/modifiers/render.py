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
from PyHSPlasma import *

from .base import PlasmaModifierProperties
from ...exporter import utils
from ...exporter.explosions import ExportError

class PlasmaLightMapGen(PlasmaModifierProperties):
    pl_id = "lightmap"

    bl_category = "Render"
    bl_label = "Lightmap"
    bl_description = "Auto-Bake Lightmap"

    quality = EnumProperty(name="Quality",
                           description="Resolution of lightmap",
                           items=[
                                  ("128", "128px", "128x128 pixels"),
                                  ("256", "256px", "256x256 pixels"),
                                  ("512", "512px", "512x512 pixels"),
                                  ("1024", "1024px", "1024x1024 pixels"),
                            ])

    light_group = StringProperty(name="Light Group",
                                 description="Group that defines the collection of lights to bake")

    uv_map = StringProperty(name="UV Texture",
                            description="UV Texture used as the basis for the lightmap")

    def created(self, obj):
        self.display_name = "{}_LIGHTMAPGEN".format(obj.name)

    def export(self, exporter, bo, so):
        mat_mgr = exporter.mesh.material
        materials = mat_mgr.get_materials(bo)
        lightmap_im = bpy.data.images.get("{}_LIGHTMAPGEN.png".format(bo.name))

        # Find the stupid UVTex
        uvw_src = 0
        for i, uvtex in enumerate(bo.data.tessface_uv_textures):
            if uvtex.name == "LIGHTMAPGEN":
                uvw_src = i
                break
        else:
            # TODO: raise exception
            pass

        for matKey in materials:
            layer = exporter.mgr.add_object(plLayer, name="{}_LIGHTMAPGEN".format(matKey.name), so=so)
            layer.UVWSrc = uvw_src

            # Colors science'd from PRPs
            layer.ambient = hsColorRGBA(1.0, 1.0, 1.0)
            layer.preshade = hsColorRGBA(0.5, 0.5, 0.5)
            layer.runtime = hsColorRGBA(0.5, 0.5, 0.5)

            # GMatState
            gstate = layer.state
            gstate.blendFlags |= hsGMatState.kBlendMult
            gstate.clampFlags |= (hsGMatState.kClampTextureU | hsGMatState.kClampTextureV)
            gstate.ZFlags |= hsGMatState.kZNoZWrite
            gstate.miscFlags |= hsGMatState.kMiscLightMap

            mat = matKey.object
            mat.compFlags |= hsGMaterial.kCompIsLightMapped
            mat.addPiggyBack(layer.key)

            # Mmm... cheating
            mat_mgr.export_prepared_layer(layer, lightmap_im)

    @property
    def resolution(self):
        return int(self.quality)

class PlasmaViewFaceMod(PlasmaModifierProperties):
    pl_id = "viewfacemod"

    bl_category = "Render"
    bl_label = "Swivel"
    bl_description = "Swivel object to face the camera, player, or another object"

    preset_options = EnumProperty(name="Type",
                                  description="Type of Facing",
                                  items=[
                                         ("Billboard", "Billboard", "Face the camera (Y Axis only)"),
                                         ("Sprite", "Sprite", "Face the camera (All Axis)"),
                                         ("Custom", "Custom", "Custom Swivel"),
                                   ])

    follow_mode = EnumProperty(name="Target Type",
                               description="Target of the swivel",
                               items=[
                                      ("kFaceCam", "Camera", "Face the camera"),
                                      ("kFaceList", "Listener", "Face listeners"),
                                      ("kFacePlay", "Player", "Face the local player"),
                                      ("kFaceObj", "Object", "Face an object"),
                                ])
    target_object = StringProperty(name="Target Object",
                                   description="Object to face")

    pivot_on_y = BoolProperty(name="Pivot on local Y",
                              description="Swivel only around the local Y axis",
                              default=False)

    offset = BoolProperty(name="Offset", description="Use offset vector", default=False)
    offset_local = BoolProperty(name="Local", description="Use local coordinates", default=False)
    offset_coord = FloatVectorProperty(name="", subtype="XYZ")

    def created(self, obj):
        self.display_name = obj.name

    def export(self, exporter, bo, so):
        vfm = exporter.mgr.find_create_object(plViewFaceModifier, so=so, name=self.display_name)

        # Set a default scaling (libHSPlasma will set this to 0 otherwise).
        vfm.scale = hsVector3(1,1,1)
        l2p = utils.matrix44(bo.matrix_local)
        vfm.localToParent = l2p
        vfm.parentToLocal = l2p.inverse()

        # Cyan has these as separate components, but they're really just preset
        # options for common swivels.  We've consolidated them both here, along
        # with the fully-customizable swivel as a third option.
        if self.preset_options == "Billboard":
            vfm.setFlag(plViewFaceModifier.kFaceCam, True)
            vfm.setFlag(plViewFaceModifier.kPivotY, True)
        elif self.preset_options == "Sprite":
            vfm.setFlag(plViewFaceModifier.kFaceCam, True)
            vfm.setFlag(plViewFaceModifier.kPivotFace, True)
        elif self.preset_options == "Custom":
            # For the discerning artist, full control over their swivel options!
            vfm.setFlag(getattr(plViewFaceModifier, self.follow_mode), True)

            if self.follow_mode == "kFaceObj":
                # If this swivel is following an object, make sure that the
                # target has been selected and is a valid SO.
                if self.target_object:
                    target_obj = bpy.data.objects.get(self.target_object, None)
                    if target_obj is None:
                        raise ExportError("'{}': Swivel's target object is invalid".format(self.display_name))
                    else:
                        vfm.faceObj = exporter.mgr.find_create_key(plSceneObject, bl=target_obj)
                else:
                    raise ExportError("'{}': Swivel's target object must be selected".format(self.display_name))

            if self.pivot_on_y:
                vfm.setFlag(plViewFaceModifier.kPivotY, True)
            else:
                vfm.setFlag(plViewFaceModifier.kPivotFace, True)

            if self.offset:
                vfm.offset = hsVector3(*self.offset_coord)
                if self.offset_local:
                    vfm.setFlag(plViewFaceModifier.kOffsetLocal, True)

    @property
    def requires_actor(self):
        return True
