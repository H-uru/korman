/* This file is part of Korman.
 *
 * Korman is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * Korman is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Korman.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "bumpmap.h"
#include "PyHSPlasma_private.h"

#include <PRP/Surface/plMipmap.h>

static uint32_t MakeUInt32Color(float r, float g, float b, float a) {
    return  (uint32_t(a * 255.9f) << 24) |
            (uint32_t(r * 255.9f) << 16) |
            (uint32_t(g * 255.9f) << 8) |
            (uint32_t(b * 255.9f) << 0);
}

PyObject* create_funky_ramp(PyObject*, PyObject* args) {
    static const int kLUTHeight = 16;
    static const int kLUTWidth = 16;
    static const int kBufSz = kLUTWidth * kLUTHeight * sizeof(uint32_t);

    pyMipmap* pymipmap;
    bool additive = false;
    if (!PyArg_ParseTuple(args, "O|b", &pymipmap, &additive)) {
        PyErr_SetString(PyExc_TypeError, "create_funky_ramp expects a plMipmap and an optional boolean");
        return NULL;
    }

    plMipmap* texture = plMipmap::Convert(pymipmap->fThis, false);
    if (!texture) {
        PyErr_SetString(PyExc_TypeError, "create_funky_ramp expects a plMipmap");
        return NULL;
    }

    texture->Create(kLUTWidth, kLUTHeight, 1, plBitmap::kUncompressed, plBitmap::kRGB8888);

    uint8_t data[kBufSz];
    uint32_t* pix = (uint32_t*)data;

    for (int i = 0; i < kLUTHeight; ++i) {
        for (int j = 0; j < kLUTWidth; ++j) {
            float x = float(j) / (kLUTWidth - 1);
            float y = float(i) / (kLUTHeight - 1);

            if (additive) {
                *pix++ = MakeUInt32Color(1.0f, 1.0f, 1.0f, std::max(x, y));
            } else {
                *pix++ = MakeUInt32Color(1.0f, 1.0f, 1.0f, x * y);
            }
        }
    }

    texture->setImageData(data, kBufSz);

    Py_RETURN_NONE;
}

PyObject* create_bump_LUT(PyObject*, PyObject* args) {
    static const int kLUTHeight = 16;
    static const int kLUTWidth = 16;
    static const int kBufSz = kLUTWidth * kLUTHeight * sizeof(uint32_t);

    pyMipmap* pymipmap;
    if (!PyArg_ParseTuple(args, "O", &pymipmap)) {
        PyErr_SetString(PyExc_TypeError, "create_bump_LUT expects a plMipmap");
        return NULL;
    }

    plMipmap* texture = plMipmap::Convert(pymipmap->fThis, false);
    if (!texture) {
        PyErr_SetString(PyExc_TypeError, "create_bump_LUT expects a plMipmap");
        return NULL;
    }

    texture->Create(kLUTWidth, kLUTHeight, 1, plBitmap::kUncompressed, plBitmap::kRGB8888);

    int delH = (kLUTHeight - 1) / 5;
    int startH = delH / 2 + 1;
    int doneH = 0;

    uint8_t data[kBufSz];
    uint32_t* pix = (uint32_t*)data;
    int i;

    // Red ramps, one with G,B = 0,0, one with G,B = 127,127
    for (i = 0; i < startH; ++i) {
        for(int j = 0; j < kLUTWidth; ++j) {
            float x = float(j) / (kLUTWidth - 1);
            *pix++ = MakeUInt32Color(x, 0.0f, 0.0f, 1.0f);
        }
    }
    doneH = i;
    for (i = i; i < doneH + delH; ++i) {
        for (int j = 0; j < kLUTWidth; ++j) {
            float x = float(j) / (kLUTWidth - 1);
            *pix++ = MakeUInt32Color(x, 0.5f, 0.5f, 1.0f);
        }
    }
    doneH = i;

    // Green ramps, one with R,B = 0,0, one with R,B = 127,127
    for (i = i; i < doneH + delH; ++i) {
        for (int j = 0; j < kLUTWidth; ++j) {
            float x = float(j) / (kLUTWidth - 1);
            *pix++ = MakeUInt32Color(0.0f, x, 0.0f, 1.0f);
        }
    }
    doneH = i;
    for (i = i; i < doneH + delH; ++i) {
        for (int j = 0; j < kLUTWidth; ++j) {
            float x = float(j) / (kLUTWidth - 1);
            *pix++ = MakeUInt32Color(0.5f, x, 0.5f, 1.0f);
        }
    }
    doneH = i;

    // Blue ramps, one with R,G = 0,0, one with R,G = 127,127
    for (i = i; i < doneH + delH; ++i) {
        for (int j = 0; j < kLUTWidth; ++j) {
            float x = float(j) / (kLUTWidth - 1);
            *pix++ = MakeUInt32Color(0.0f, 0.0f, x, 1.0f);
        }
    }
    doneH = i;
    for (i = i; i < kLUTHeight; ++i) {
        for (int j = 0; j < kLUTWidth; ++j) {
            float x = float(j) / (kLUTWidth - 1);
            *pix++ = MakeUInt32Color(0.5f, 0.5f, x, 1.0f);
        }
    }

    texture->setImageData(data, kBufSz);

    Py_RETURN_NONE;
}
