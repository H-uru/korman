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

#include "texture.h"
#include "buffer.h"

#ifdef _WIN32
#   define WIN32_LEAN_AND_MEAN
#   define NOMINMAX
#   include <windows.h>
#endif // _WIN32

#include <cmath>
#include <GL/gl.h>
#include <PRP/Surface/plMipmap.h>

#ifndef GL_GENERATE_MIPMAP
#   define GL_GENERATE_MIPMAP 0x8191
#endif // GL_GENERATE_MIPMAP

#define TEXTARGET_TEXTURE_2D 0

static inline bool _get_float(PyObject* source, const char* attr, float& result) {
    PyObjectRef pyfloat = PyObject_GetAttrString(source, attr);
    if (pyfloat) {
        result = (float)PyFloat_AsDouble(pyfloat);
        return PyErr_Occurred() == NULL;
    }
    return false;
}

extern "C" {

enum {
    TEX_DETAIL_ALPHA = 0,
    TEX_DETAIL_ADD = 1,
    TEX_DETAIL_MULTIPLY = 2,
};

typedef struct {
    PyObject_HEAD
    PyObject* m_blenderImage;
    PyObject* m_textureKey;
    bool m_ownIt;
    GLint m_prevImage;
    bool m_changedState;
    GLint m_mipmapState;
} pyGLTexture;

typedef struct {
    PyObject_HEAD
    plMipmap* fThis;
    bool fPyOwned;
} pyMipmap;

static void pyGLTexture_dealloc(pyGLTexture* self) {
    Py_XDECREF(self->m_textureKey);
    Py_XDECREF(self->m_blenderImage);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject* pyGLTexture_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
    pyGLTexture* self = (pyGLTexture*)type->tp_alloc(type, 0);
    self->m_blenderImage = NULL;
    self->m_textureKey = NULL;
    self->m_ownIt = false;
    self->m_prevImage = 0;
    self->m_changedState = false;
    self->m_mipmapState = 0;
    return (PyObject*)self;
}

static int pyGLTexture___init__(pyGLTexture* self, PyObject* args, PyObject* kwds) {
    if (!PyArg_ParseTuple(args, "O", &self->m_textureKey)) {
        PyErr_SetString(PyExc_TypeError, "expected a korman.exporter.material._Texture");
        return -1;
    }
    self->m_blenderImage = PyObject_GetAttrString(self->m_textureKey, "image");
    if (!self->m_blenderImage) {
        PyErr_SetString(PyExc_RuntimeError, "Could not fetch Blender Image");
        return -1;
    }

    Py_INCREF(self->m_textureKey);

    // Done!
    return 0;
}

static PyObject* pyGLTexture__enter__(pyGLTexture* self) {
    // Is the image already loaded?
    PyObjectRef bindcode = PyObject_GetAttrString(self->m_blenderImage, "bindcode");

    // bindcode changed to a sequence in 2.77. We want the first element for a 2D texture.
    // Why did we make this change, exactly?
    if (PySequence_Check(bindcode)) {
        bindcode = PySequence_GetItem(bindcode, TEXTARGET_TEXTURE_2D);
    }

    // Now we should have a GLuint...
    if (!PyLong_Check(bindcode)) {
        PyErr_SetString(PyExc_TypeError, "Image bindcode isn't a long?");
        return NULL;
    }

    glGetIntegerv(GL_TEXTURE_BINDING_2D, &self->m_prevImage);
    GLuint image_bindcode = PyLong_AsUnsignedLong(bindcode);
    self->m_ownIt = image_bindcode == 0;

    // Load image into GL
    if (self->m_ownIt) {
        PyObjectRef new_bind = PyObject_CallMethod(self->m_blenderImage, "gl_load", NULL);
        if (!PyLong_Check(new_bind)) {
            PyErr_SetString(PyExc_TypeError, "gl_load() did not return a long");
            return NULL;
        }
        ssize_t result = PyLong_AsSize_t(new_bind);
        if (result != GL_NO_ERROR) {
            PyErr_Format(PyExc_RuntimeError, "gl_load() error: %d", result);
            return NULL;
        }
        bindcode = PyObject_GetAttrString(self->m_blenderImage, "bindcode");
        if (PySequence_Check(bindcode)) {
            bindcode = PySequence_GetItem(bindcode, TEXTARGET_TEXTURE_2D);
        }
        // Now we should have a GLuint...
        if (!PyLong_Check(bindcode)) {
            PyErr_SetString(PyExc_TypeError, "Image bindcode isn't a long?");
            return NULL;
        }
        image_bindcode = PyLong_AsUnsignedLong(bindcode);
    }

    // Set image as current in GL
    if (self->m_prevImage != image_bindcode) {
        self->m_changedState = true;
        glBindTexture(GL_TEXTURE_2D, image_bindcode);
    }

    // Misc GL state
    glGetTexParameteriv(GL_TEXTURE_2D, GL_GENERATE_MIPMAP, &self->m_mipmapState);

    Py_INCREF(self);
    return (PyObject*)self;
}

static PyObject* pyGLTexture__exit__(pyGLTexture* self, PyObject*) {
    // We don't care about the args here
    glTexParameteri(GL_TEXTURE_2D, GL_GENERATE_MIPMAP, self->m_mipmapState);
    if (self->m_changedState)
        glBindTexture(GL_TEXTURE_2D, self->m_prevImage);
    Py_RETURN_NONE;
}

static PyObject* pyGLTexture_generate_mipmap(pyGLTexture* self) {
    glTexParameteri(GL_TEXTURE_2D, GL_GENERATE_MIPMAP, 1);
    Py_RETURN_NONE;
}

struct _LevelData
{
    GLint   m_width;
    GLint   m_height;
    uint8_t* m_data;
    size_t   m_dataSize;

    _LevelData(GLint w, GLint h, uint8_t* ptr, size_t sz)
        : m_width(w), m_height(h), m_data(ptr), m_dataSize(sz)
    { }
};

static inline int _get_num_levels(pyGLTexture* self) {
    PyObjectRef size = PyObject_GetAttrString(self->m_blenderImage, "size");
    float width = (float)PyFloat_AsDouble(PySequence_GetItem(size, 0));
    float height = (float)PyFloat_AsDouble(PySequence_GetItem(size, 1));

    int num_levels = (int)std::floor(std::log2(std::max(width, height))) + 1;

    // Major Workaround Ahoy
    // There is a bug in Cyan's level size algorithm that causes it to not allocate enough memory
    // for the color block in certain mipmaps. I personally have encountered an access violation on
    // 1x1 DXT5 mip levels -- the code only allocates an alpha block and not a color block. Paradox
    // reports that if any dimension is smaller than 4px in a mip level, OpenGL doesn't like Cyan generated
    // data. So, we're going to lop off the last two mip levels, which should be 1px and 2px as the smallest.
    // This bug is basically unfixable without crazy hacks because of the way Plasma reads in texture data.
    //     "<Deledrius> I feel like any texture at a 1x1 level is essentially academic.  I mean, JPEG/DXT
    //                  doesn't even compress that, and what is it?  Just the average color of the whole
    //                  texture in a single pixel?"
    // :)
    return std::max(num_levels - 2, 2);
}

static int _generate_detail_alpha(pyGLTexture* self, GLint level, float* result) {
    float dropoff_start, dropoff_stop, detail_max, detail_min;
    if (!_get_float(self->m_textureKey, "detail_fade_start", dropoff_start))
        return -1;
    if (!_get_float(self->m_textureKey, "detail_fade_stop", dropoff_stop))
        return -1;
    if (!_get_float(self->m_textureKey, "detail_opacity_start", detail_max))
        return -1;
    if (!_get_float(self->m_textureKey, "detail_opacity_stop", detail_min))
        return -1;

    dropoff_start /= 100.f;
    dropoff_start *= _get_num_levels(self);
    dropoff_stop /= 100.f;
    dropoff_stop *= _get_num_levels(self);
    detail_max /= 100.f;
    detail_min /= 100.f;

    float alpha = (level - dropoff_start) * (detail_min - detail_max) / (dropoff_stop - dropoff_start) + detail_max;
    if (detail_min < detail_max)
        *result = std::min(detail_max, std::max(detail_min, alpha));
    else
        *result = std::min(detail_min, std::max(detail_max, alpha));
    return 0;
}

static int _generate_detail_map(pyGLTexture* self, uint8_t* buf, size_t bufsz, GLint level) {
    float alpha;
    if (_generate_detail_alpha(self, level, &alpha) != 0)
        return -1;
    PyObjectRef pydetail_blend = PyObject_GetAttrString(self->m_textureKey, "detail_blend");
    if (!pydetail_blend)
        return -1;

    size_t detail_blend = PyLong_AsSize_t(pydetail_blend);
    switch (detail_blend) {
    case TEX_DETAIL_ALPHA: {
            for (size_t i = 0; i < bufsz; i += 4) {
                buf[i+3] = (uint8_t)(((float)buf[i+3]) * alpha);
            }
        }
        break;
    case TEX_DETAIL_ADD: {
            for (size_t i = 0; i < bufsz; i += 4) {
                buf[i+0] = (uint8_t)(((float)buf[i+0]) * alpha);
                buf[i+1] = (uint8_t)(((float)buf[i+1]) * alpha);
                buf[i+2] = (uint8_t)(((float)buf[i+2]) * alpha);
            }
        }
        break;
    case TEX_DETAIL_MULTIPLY: {
            float invert_alpha = (1.f - alpha) * 255.f;
            for (size_t i = 0; i < bufsz; i += 4) {
                buf[i+3] = (uint8_t)((invert_alpha + (float)buf[i+3]) * alpha);
            }
        }
        break;
    default:
        return -1;
    }
    return 0;
}

static _LevelData _get_level_data(pyGLTexture* self, GLint level, bool bgra, bool quiet) {
    GLint width, height;
    glGetTexLevelParameteriv(GL_TEXTURE_2D, level, GL_TEXTURE_WIDTH, &width);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, level, GL_TEXTURE_HEIGHT, &height);
    GLenum fmt = bgra ? GL_BGRA_EXT : GL_RGBA;

    if (!quiet)
        PySys_WriteStdout("        Level #%i: %ix%i\n", level, width, height);

    size_t bufsz;
    bufsz = (width * height * 4);
    uint8_t* buf = new uint8_t[bufsz];
    glGetTexImage(GL_TEXTURE_2D, level, fmt, GL_UNSIGNED_BYTE, reinterpret_cast<GLvoid*>(buf));
    return _LevelData(width, height, buf, bufsz);
}

static PyObject* pyGLTexture_get_level_data(pyGLTexture* self, PyObject* args, PyObject* kwargs) {
    static char* kwlist[] = { _pycs("level"), _pycs("calc_alpha"), _pycs("bgra"),
                              _pycs("quiet"), _pycs("fast"), NULL };
    GLint level = 0;
    bool calc_alpha = false;
    bool bgra = false;
    bool quiet = false;
    bool fast = false;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|ibbbb", kwlist, &level, &calc_alpha, &bgra, &quiet, &fast)) {
        PyErr_SetString(PyExc_TypeError, "get_level_data expects an optional int, bool, bool, bool, bool");
        return NULL;
    }

    _LevelData data = _get_level_data(self, level, bgra, quiet);
    if (fast)
        return pyBuffer_Steal(data.m_data, data.m_dataSize);

    // OpenGL returns a flipped image, so we must reflip it.
    size_t row_stride = data.m_width * 4;
    uint8_t* sptr = data.m_data;
    uint8_t* eptr = data.m_data + (data.m_dataSize - row_stride);
    uint8_t* temp = new uint8_t[row_stride];
    do {
        memcpy(temp, sptr, row_stride);
        memcpy(sptr, eptr, row_stride);
        memcpy(eptr, temp, row_stride);
    } while ((sptr += row_stride) < (eptr -= row_stride));
    delete[] temp;

    // Detail blend
    PyObjectRef is_detail_map = PyObject_GetAttrString(self->m_textureKey, "is_detail_map");
    if (PyLong_AsLong(is_detail_map) != 0) {
        if (_generate_detail_map(self, data.m_data, data.m_dataSize, level) != 0) {
            delete[] data.m_data;
            PyErr_SetString(PyExc_RuntimeError, "error while baking detail map");
            return NULL;
        }
    }

    if (calc_alpha) {
        for (size_t i = 0; i < data.m_dataSize; i += 4)
            data.m_data[i + 3] = (data.m_data[i + 0] + data.m_data[i + 1] + data.m_data[i + 2]) / 3;
    }

    return pyBuffer_Steal(data.m_data, data.m_dataSize);
}

static PyObject* pyGLTexture_store_in_mipmap(pyGLTexture* self, PyObject* args) {
    pyMipmap* pymipmap;
    PyObject* levels;
    size_t compression;
    if (!PyArg_ParseTuple(args, "OOn", &pymipmap, &levels, &compression) || !PySequence_Check(levels)) {
        PyErr_SetString(PyExc_TypeError, "store_in_mipmap expects a plMipmap, sequence of Buffer and int");
        return NULL;
    }

    // Since we actually have no way of knowing if that really is a pyMipmap...
    plMipmap* mipmap = plMipmap::Convert(pymipmap->fThis, false);
    if (!mipmap) {
        PyErr_SetString(PyExc_TypeError, "store_in_mipmap expects a plMipmap, sequence of Buffer and int");
        return NULL;
    }

    for (Py_ssize_t i = 0; i < PySequence_Size(levels); ++i) {
        pyBuffer* item = (pyBuffer*)PySequence_GetItem(levels, i);
        if (!pyBuffer_Check((PyObject*)item)) {
            PyErr_SetString(PyExc_TypeError, "store_in_mipmap expects a plMipmap, sequence of Buffer and int");
            return NULL;
        }

        if (compression == plBitmap::kDirectXCompression)
            mipmap->CompressImage(i, item->m_buffer, item->m_size);
        else
            mipmap->setLevelData(i, item->m_buffer, item->m_size);
    }

    Py_RETURN_NONE;
}


static uint32_t MakeUInt32Color(float r, float g, float b, float a)
{
    return  (uint32_t(a * 255.9f) << 24) |
            (uint32_t(r * 255.9f) << 16) |
            (uint32_t(g * 255.9f) << 8) |
            (uint32_t(b * 255.9f) << 0);
}

static PyObject* pyGLTexture_create_bump_LUT(pyGLTexture* self, PyObject* args) {
    const int kLUTHeight = 16;
    const int kLUTWidth = 16;

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

    uint8_t* data = new uint8_t[texture->getTotalSize()];
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

    texture->setImageData(data, texture->getTotalSize());

    Py_RETURN_NONE;
}

static PyMethodDef pyGLTexture_Methods[] = {
    { _pycs("__enter__"), (PyCFunction)pyGLTexture__enter__, METH_NOARGS, NULL },
    { _pycs("__exit__"), (PyCFunction)pyGLTexture__enter__, METH_VARARGS, NULL },

    { _pycs("create_bump_LUT"), (PyCFunction)pyGLTexture_create_bump_LUT, METH_STATIC | METH_VARARGS, NULL },
    { _pycs("generate_mipmap"), (PyCFunction)pyGLTexture_generate_mipmap, METH_NOARGS, NULL },
    { _pycs("get_level_data"), (PyCFunction)pyGLTexture_get_level_data, METH_KEYWORDS | METH_VARARGS, NULL },
    { _pycs("store_in_mipmap"), (PyCFunction)pyGLTexture_store_in_mipmap, METH_VARARGS, NULL },
    { NULL, NULL, 0, NULL }
};

static PyObject* pyGLTexture_get_has_alpha(pyGLTexture* self, void*) {
    _LevelData data = _get_level_data(self, 0, false, true);
    for (size_t i = 3; i < data.m_dataSize; i += 4) {
        if (data.m_data[i] != 255) {
            delete[] data.m_data;
            return PyBool_FromLong(1);
        }
    }
    delete[] data.m_data;
    return PyBool_FromLong(0);
}

static PyObject* pyGLTexture_get_num_levels(pyGLTexture* self, void*) {
    return PyLong_FromLong(_get_num_levels(self));
}

static PyGetSetDef pyGLTexture_GetSet[] = {
    { _pycs("has_alpha"), (getter)pyGLTexture_get_has_alpha, NULL, NULL, NULL },
    { _pycs("num_levels"), (getter)pyGLTexture_get_num_levels, NULL, NULL, NULL },
    { NULL, NULL, NULL, NULL, NULL }
};

PyTypeObject pyGLTexture_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "_korlib.GLTexture",                /* tp_name */
    sizeof(pyGLTexture),                /* tp_basicsize */
    0,                                  /* tp_itemsize */

    (destructor)pyGLTexture_dealloc,    /* tp_dealloc */
    NULL,                               /* tp_print */
    NULL,                               /* tp_getattr */
    NULL,                               /* tp_setattr */
    NULL,                               /* tp_compare */
    NULL,                               /* tp_repr */
    NULL,                               /* tp_as_number */
    NULL,                               /* tp_as_sequence */
    NULL,                               /* tp_as_mapping */
    NULL,                               /* tp_hash */
    NULL,                               /* tp_call */
    NULL,                               /* tp_str */
    NULL,                               /* tp_getattro */
    NULL,                               /* tp_setattro */
    NULL,                               /* tp_as_buffer */

    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /* tp_flags */
    "GLTexture",                              /* tp_doc */

    NULL,                               /* tp_traverse */
    NULL,                               /* tp_clear */
    NULL,                               /* tp_richcompare */
    0,                                  /* tp_weaklistoffset */
    NULL,                               /* tp_iter */
    NULL,                               /* tp_iternext */

    pyGLTexture_Methods,                /* tp_methods */
    NULL,                               /* tp_members */
    pyGLTexture_GetSet,                 /* tp_getset */
    NULL,                               /* tp_base */
    NULL,                               /* tp_dict */
    NULL,                               /* tp_descr_get */
    NULL,                               /* tp_descr_set */
    0,                                  /* tp_dictoffset */

    (initproc)pyGLTexture___init__,     /* tp_init */
    NULL,                               /* tp_alloc */
    pyGLTexture_new,                    /* tp_new */
    NULL,                               /* tp_free */
    NULL,                               /* tp_is_gc */

    NULL,                               /* tp_bases */
    NULL,                               /* tp_mro */
    NULL,                               /* tp_cache */
    NULL,                               /* tp_subclasses */
    NULL,                               /* tp_weaklist */

    NULL,                               /* tp_del */
    0,                                  /* tp_version_tag */
    NULL,                               /* tp_finalize */
};

PyObject* Init_pyGLTexture_Type() {
    if (PyType_Ready(&pyGLTexture_Type) < 0)
        return NULL;

    Py_INCREF(&pyGLTexture_Type);
    return (PyObject*)&pyGLTexture_Type;
}

};

