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
import korlib
from PyHSPlasma import *
import weakref

from . import explosions
from . import utils

class MaterialConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self._hsbitmaps = {}

    def export_material(self, bo, bm):
        """Exports a Blender Material as an hsGMaterial"""
        print("    Exporting Material '{}'".format(bm.name))

        hsgmat = self._mgr.add_object(hsGMaterial, name=bm.name, bl=bo)
        self._export_texture_slots(bo, bm, hsgmat)

        # Plasma makes several assumptions that every hsGMaterial has at least one layer. If this
        # material had no Textures, we will need to initialize a default layer
        if not hsgmat.layers:
            layer = self._mgr.add_object(plLayer, name="{}_AutoLayer".format(bm.name), bl=bo)
            self._propagate_material_settings(bm, layer)
            hsgmat.addLayer(layer.key)

        # Looks like we're done...
        return hsgmat.key

    def _export_texture_slots(self, bo, bm, hsgmat):
        for slot in bm.texture_slots:
            if slot is None or not slot.use:
                continue

            name = "{}_{}".format(bm.name, slot.name)
            print("        Exporting Plasma Layer '{}'".format(name))
            layer = self._mgr.add_object(plLayer, name=name, bl=bo)
            self._propagate_material_settings(bm, layer)

            # UVW Channel
            for i, uvchan in enumerate(bo.data.tessface_uv_textures):
                if uvchan.name == slot.uv_layer:
                    layer.UVWSrc = i
                    print("            Using UV Map #{} '{}'".format(i, name))
                    break
            else:
                print("            No UVMap specified... Blindly using the first one, maybe it exists :|")

            # General texture flags and such
            texture = slot.texture
            # ...

            # Export the specific texture type
            export_fn = "_export_texture_type_{}".format(texture.type.lower())
            if not hasattr(self, export_fn):
                raise explosions.UnsupportedTextureError(texture, bm)
            getattr(self, export_fn)(bo, hsgmat, layer, texture)
            hsgmat.addLayer(layer.key)

    def _export_texture_type_image(self, bo, hsgmat, layer, texture):
        """Exports a Blender ImageTexture to a plLayer"""

        # First, let's apply any relevant flags
        state = layer.state
        if texture.invert_alpha:
            state.blendFlags |= hsGMatState.kBlendInvertAlpha

        # Now, let's export the plBitmap
        # If the image is None (no image applied in Blender), we assume this is a plDynamicTextMap
        # Otherwise, we create a plMipmap and call into korlib to export the pixel data
        if texture.image is None:
            bitmap = self.add_object(plDynamicTextMap, name="{}_DynText".format(layer.key.name), bl=bo)
        else:
            # blender likes to create lots of spurious .0000001 objects :/
            name = texture.image.name
            name = name[:name.find('.')]
            if texture.use_mipmap:
                name = "{}.dds".format(name)
            else:
                name = "{}.bmp".format(name)

            if name in self._hsbitmaps:
                # well, that was easy...
                print("            Using '{}'".format(name))
                layer.texture = self._hsbitmaps[name].key
                return
            else:
                location = self._mgr.get_textures_page(bo)
                bitmap = self._mgr.add_object(plMipmap, name=name, loc=location)
                korlib.generate_mipmap(texture, bitmap)

        # Store the created plBitmap and toss onto the layer
        self._hsbitmaps[name] = bitmap
        layer.texture = bitmap.key

    def _export_texture_type_none(self, bo, hsgmat, layer, texture):
        # We'll allow this, just for sanity's sake...
        pass

    @property
    def _mgr(self):
        return self._exporter().mgr

    def _propagate_material_settings(self, bm, layer):
        """Converts settings from the Blender Material to corresponding plLayer settings"""
        state = layer.state

        # Shade Flags
        if not bm.use_mist:
            state.shadeFlags |= hsGMatState.kShadeNoFog # Dead in CWE
            state.shadeFlags |= hsGMatState.kShadeReallyNoFog

        # Colors
        layer.ambient = utils.color(bpy.context.scene.world.ambient_color)
        layer.preshade = utils.color(bm.diffuse_color)
        layer.runtime = utils.color(bm.diffuse_color)
        layer.specular = utils.color(bm.specular_color)
