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
