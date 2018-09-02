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

import bgl
import math
from PyHSPlasma import plBitmap

# BGL doesn't know about this as of Blender 2.74
bgl.GL_GENERATE_MIPMAP = 0x8191
bgl.GL_BGRA = 0x80E1

# Some texture generation flags
TEX_DETAIL_ALPHA = 0
TEX_DETAIL_ADD = 1
TEX_DETAIL_MULTIPLY = 2

class GLTexture:
    def __init__(self, texkey=None):
        self._texkey = texkey
        self._ownit = (self._blimg.bindcode[0] == 0)

    @property
    def _blimg(self):
        return self._texkey.image

    def __enter__(self):
        """Sets the Blender Image as the active OpenGL texture"""
        if self._ownit:
            if self._blimg.gl_load() != 0:
                raise RuntimeError("failed to load image")

        self._previous_texture = self._get_integer(bgl.GL_TEXTURE_BINDING_2D)
        self._changed_state = (self._previous_texture != self._blimg.bindcode[0])
        if self._changed_state:
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, self._blimg.bindcode[0])
        return self

    def __exit__(self, type, value, traceback):
        mipmap_state = getattr(self, "_mipmap_state", None)
        if mipmap_state is not None:
            bgl.glTexParameteri(bgl.GL_TEXTURE_2D, bgl.GL_GENERATE_MIPMAP, mipmap_state)
        if self._changed_state:
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, self._previous_texture)
        if self._ownit:
            self._blimg.gl_free()

    @property
    def _detail_falloff(self):
        num_levels = self.num_levels
        return ((self._texkey.detail_fade_start / 100.0) * num_levels,
                (self._texkey.detail_fade_stop / 100.0) * num_levels,
                 self._texkey.detail_opacity_start / 100.0,
                 self._texkey.detail_opacity_stop / 100.0)

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

    def get_level_data(self, level=0, calc_alpha=False, bgra=False, report=None, fast=False):
        """Gets the uncompressed pixel data for a requested mip level, optionally calculating the alpha
           channel from the image color data
        """
        width = self._get_tex_param(bgl.GL_TEXTURE_WIDTH, level)
        height = self._get_tex_param(bgl.GL_TEXTURE_HEIGHT, level)
        if report is not None:
            report.msg("Level #{}: {}x{}", level, width, height, indent=2)

        # Grab the image data
        size = width * height * 4
        buf = bgl.Buffer(bgl.GL_BYTE, size)
        fmt = bgl.GL_BGRA if bgra else bgl.GL_RGBA
        bgl.glGetTexImage(bgl.GL_TEXTURE_2D, level, fmt, bgl.GL_UNSIGNED_BYTE, buf);
        if fast:
            return bytes(buf)

        # OpenGL returns the images upside down, so we're going to rotate it in memory.
        finalBuf = bytearray(size)
        row_stride = width * 4
        for i in range(height):
            src, dst = i * row_stride, (height - (i+1)) * row_stride
            finalBuf[dst:dst+row_stride] = buf[src:src+row_stride]

        # If this is a detail map, then we need to bake that per-level here.
        if self._texkey.is_detail_map:
            detail_blend = self._texkey.detail_blend
            if detail_blend == TEX_DETAIL_ALPHA:
                self._make_detail_map_alpha(finalBuf, level)
            elif detail_blend == TEX_DETAIL_ADD:
                self._make_detail_map_alpha(finalBuf, level)
            elif detail_blend == TEX_DETAIL_MULTIPLY:
                self._make_detail_map_mult(finalBuf, level)

        # Do we need to calculate the alpha component?
        if calc_alpha:
            for i in range(0, size, 4):
                finalBuf[i+3] = int(sum(finalBuf[i:i+3]) / 3)
        return bytes(finalBuf)

    def _get_detail_alpha(self, level, dropoff_start, dropoff_stop, detail_max, detail_min):
        alpha = (level - dropoff_start) * (detail_min - detail_max) / (dropoff_stop - dropoff_start) + detail_max
        if detail_min < detail_max:
            return min(detail_max, max(detail_min, alpha))
        else:
            return min(detail_min, max(detail_max, alpha))

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

    @property
    def has_alpha(self):
        data = self.get_level_data(report=None, fast=True)
        for i in range(3, len(data), 4):
            if data[i] != 255:
                return True
        return False

    def _make_detail_map_add(self, data, level):
        dropoff_start, dropoff_stop, detail_max, detail_min = self._detail_falloff
        alpha = self._get_detail_alpha(level, dropoff_start, dropoff_stop, detail_max, detail_min)
        for i in range(0, len(data), 4):
            data[i] = int(data[i] * alpha)
            data[i+1] = int(data[i+1] * alpha)
            data[i+2] = int(data[i+2] * alpha)

    def _make_detail_map_alpha(self, data, level):
        dropoff_start, dropoff_end, detail_max, detail_min = self._detail_falloff
        alpha = self._get_detail_alpha(level, dropoff_start, dropoff_end, detail_max, detail_min)
        for i in range(0, len(data), 4):
            data[i+3] = int(data[i+3] * alpha)

    def _make_detail_map_mult(self, data, level):
        dropoff_start, dropoff_end, detail_max, detail_min = self._detail_falloff
        alpha = self._get_detail_alpha(level, dropoff_start, dropoff_end, detail_max, detail_min)
        invert_alpha = (1.0 - alpha) * 255.0
        for i in range(0, len(data), 4):
            data[i+3] = int(invert_alpha + data[i+3] * alpha)

    @property
    def num_levels(self):
        numLevels = math.floor(math.log(max(self._blimg.size), 2)) + 1

        # Major Workaround Ahoy
        # There is a bug in Cyan's level size algorithm that causes it to not allocate enough memory
        # for the color block in certain mipmaps. I personally have encountered an access violation on
        # 1x1 DXT5 mip levels -- the code only allocates an alpha block and not a color block. Paradox
        # reports that if any dimension is smaller than 4px in a mip level, OpenGL doesn't like Cyan generated
        # data. So, we're going to lop off the last two mip levels, which should be 1px and 2px as the smallest.
        # This bug is basically unfixable without crazy hacks because of the way Plasma reads in texture data.
        #     "<Deledrius> I feel like any texture at a 1x1 level is essentially academic.  I mean, JPEG/DXT
        #                  doesn't even compress that, and what is it?  Just the average color of the whole
        #                  texture in a single pixel?"
        # :)
        return max(numLevels - 2, 2)
