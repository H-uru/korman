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
import bgl
import math
import os.path
from PyHSPlasma import *
import weakref

from . import explosions
from . import utils

# BGL doesn't know about this as of Blender 2.71
bgl.GL_GENERATE_MIPMAP = 0x8191

class _GLTexture:
    def __init__(self, blimg):
        self._ownit = (blimg.bindcode == 0)
        if self._ownit:
            if blimg.gl_load() != 0:
                raise explosions.GLLoadError(blimg)
        self._blimg = blimg

    def __del__(self):
        if self._ownit:
            self._blimg.gl_free()

    def __enter__(self):
        """Sets the Blender Image as the active OpenGL texture"""
        self._previous_texture = self._get_integer(bgl.GL_TEXTURE_BINDING_2D)
        self._changed_state = (self._previous_texture != self._blimg.bindcode)
        if self._changed_state:
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, self._blimg.bindcode)
        return self

    def __exit__(self, type, value, traceback):
        mipmap_state = getattr(self, "_mipmap_state", None)
        if mipmap_state is not None:
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_GENERATE_MIPMAP, mipmap_state)

        if self._changed_state:
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, self._previous_texture)

    def generate_mipmap(self):
        """Generates all mip levels for this texture"""
        self._mipmap_state = self._get_tex_param(bgl.GL_GENERATE_MIPMAP)

        # Note that this is a very old feature from OpenGL 1.x -- it's new enough that Windows (and
        # Blender apparently) don't support it natively and yet old enough that it was thrown away
        # in OpenGL 3.0. The new way is glGenerateMipmap, but Blender likes oldgl, so we don't have that
        # function available to us in BGL. I don't want to deal with loading the GL dll in ctypes on
        # many platforms right now (or context headaches). If someone wants to fix this, be my guest!
        # It will simplify our state tracking a bit.
        bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_GENERATE_MIPMAP, 1)

    def get_level_data(self, level, calc_alpha=False):
        """Gets the uncompressed pixel data for a requested mip level, optionally calculating the alpha
           channel from the image color data
        """
        width = self._get_tex_param(bgl.GL_TEXTURE_WIDTH, level)
        height = self._get_tex_param(bgl.GL_TEXTURE_HEIGHT, level)
        print("        Level #{}: {}x{}".format(level, width, height))

        # Grab the image data
        size = width * height * 4
        buf = bgl.Buffer(bgl.GL_BYTE, size)
        bgl.glGetTexImage(bgl.GL_TEXTURE_2D, level, bgl.GL_RGBA, bgl.GL_UNSIGNED_BYTE, buf);

        # Calculate le alphas
        if calc_alpha:
            for i in range(size, 4):
                base = i*4
                r, g, b = buf[base:base+2]
                buf[base+3] = int((r + g + b) / 3)
        return bytes(buf)

    def _get_integer(self, arg):
        buf = bgl.Buffer(bgl.GL_INT, 1)
        bgl.glGetIntegerv(arg, buf)
        return int(buf[0])

    def _get_tex_param(self, param, level=None):
        buf = bgl.Buffer(bgl.GL_INT, 1)
        if level is None:
            bgl.glGetTexParameteriv(bgl.GL_TEXTURE_2D, param, buf)
        else:
            bgl.glGetTexLevelParameteriv(bgl.GL_TEXTURE_2D, level, param, buf)
        return int(buf[0])


class _Texture:
    def __init__(self, texture=None, image=None):
        assert (texture or image)

        if texture is not None:
            self.image = texture.image
            self.calc_alpha = texture.use_calculate_alpha
            self.mipmap = texture.use_mipmap
            self.use_alpha = texture.use_alpha
        if image is not None:
            self.image = image
            self.calc_alpha = False
            self.mipmap = False
            self.use_alpha = image.use_alpha

    def __eq__(self, other):
        if not isinstance(other, _Texture):
            return False

        if self.image == other.image:
            if self.calc_alpha == other.calc_alpha:
                self._update(other)
                return True

    def __hash__(self):
        return hash(self.image.name) ^ hash(self.calc_alpha)

    def __str__(self):
        name = self._change_extension(self.image.name, ".dds")
        if self.calc_alpha:
            name = "ALPHAGEN_{}".format(name)
        return name

    def _change_extension(self, name, newext):
        # Blender likes to add faux extensions such as .001 :(
        if name.find(".") == -1:
            return "{}{}".format(name, newext)
        name, end = os.path.splitext(name)
        if name.find(".") == -1:
            return "{}{}".format(name, newext)
        name, oldext = os.path.splitext(name)
        return "{}{}{}".format(name, end, newext)

    def _update(self, other):
        """Update myself with any props that might be overridable from another copy of myself"""
        if other.use_alpha:
            self.use_alpha = True
        if other.mipmap:
            self.mipmap = True


class MaterialConverter:
    def __init__(self, exporter):
        self._obj2mat = {}
        self._exporter = weakref.ref(exporter)
        self._pending = {}

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

        # Cache this material for later
        if bo in self._obj2mat:
            self._obj2mat[bo].append(hsgmat.key)
        else:
            self._obj2mat[bo] = [hsgmat.key]

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
        # Otherwise, we toss this layer and some info into our pending texture dict and process it
        #     when the exporter tells us to finalize all our shit
        if texture.image is None:
            bitmap = self.add_object(plDynamicTextMap, name="{}_DynText".format(layer.key.name), bl=bo)
        else:
            key = _Texture(texture=texture)
            if key not in self._pending:
                print("            Stashing '{}' for conversion as '{}'".format(texture.image.name, str(key)))
                self._pending[key] = [layer,]
            else:
                print("            Found another user of '{}'".format(texture.image.name))
                self._pending[key].append(layer)

    def _export_texture_type_none(self, bo, hsgmat, layer, texture):
        # We'll allow this, just for sanity's sake...
        pass

    def export_prepared_layer(self, layer, image):
        """This exports an externally prepared layer and image"""
        key = _Texture(image=image)
        if key not in self._pending:
            print("        Stashing '{}' for conversion as '{}'".format(image.name, str(key)))
            self._pending[key] = [layer,]
        else:
            print("        Found another user of '{}'".format(image.name))
            self._pending[key].append(layer)

    def finalize(self):
        for key, layers in self._pending.items():
            name = str(key)
            print("\n[Mipmap '{}']".format(name))

            image = key.image
            oWidth, oHeight = image.size
            eWidth = pow(2, math.floor(math.log(oWidth, 2)))
            eHeight = pow(2, math.floor(math.log(oHeight, 2)))
            if (eWidth != oWidth) or (eHeight != oHeight):
                print("    Image is not a POT ({}x{}) resizing to {}x{}".format(oWidth, oHeight, eWidth, eHeight))
                self._resize_image(image, eWidth, eHeight)

            # Some basic mipmap settings.
            numLevels = math.floor(math.log(max(eWidth, eHeight), 2)) + 1 if key.mipmap else 1
            compression = plBitmap.kDirectXCompression
            dxt = plBitmap.kDXT5 if key.use_alpha or key.calc_alpha else plBitmap.kDXT1

            # Grab the image data from OpenGL and stuff it into the plBitmap
            with _GLTexture(image) as glimage:
                if key.mipmap:
                    print("    Generating mip levels")
                    glimage.generate_mipmap()
                else:
                    print("    Stuffing image data")

                # Hold the uncompressed level data for now. We may have to make multiple copies of
                # this mipmap for per-page textures :(
                data = []
                for i in range(numLevels):
                    data.append(glimage.get_level_data(i, key.calc_alpha))

            # Be a good citizen and reset the Blender Image to pre-futzing state
            image.reload()

            # Now we poke our new bitmap into the pending layers. Note that we have to do some funny
            # business to account for per-page textures
            mgr = self._mgr
            pages = {}

            print("    Adding to Layer(s)")
            for layer in layers:
                print("        {}".format(layer.key.name))
                page = mgr.get_textures_page(layer) # Layer's page or Textures.prp

                # If we haven't created this plMipmap in the page (either layer's page or Textures.prp),
                # then we need to do that and stuff the level data. This is a little tedious, but we
                # need to be careful to manage our resources correctly
                if page not in pages:
                    mipmap = plMipmap(name=name, width=eWidth, height=eHeight, numLevels=numLevels,
                                      compType=compression, format=plBitmap.kRGB8888, dxtLevel=dxt)
                    func = mipmap.CompressImage if compression == plBitmap.kDirectXCompression else mipmap.setLevel
                    for i, level in enumerate(data):
                        func(i, level)
                    mgr.AddObject(page, mipmap)
                    pages[page] = mipmap
                else:
                    mipmap = pages[page]
                layer.texture = mipmap.key

    def get_materials(self, bo):
        return self._obj2mat[bo]

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

    def _resize_image(self, image, width, height):
        image.scale(width, height)

        # If the image is already loaded into OpenGL, we need to refresh it to get the scaling.
        if image.bindcode != 0:
            image.gl_free()
            image.gl_load()
