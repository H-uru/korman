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
#include "PyHSPlasma_private.h"

#ifdef _WIN32
#   define WIN32_LEAN_AND_MEAN
#   define NOMINMAX
#   include <windows.h>
#endif // _WIN32

#include <cmath>
#include <GL/gl.h>
#include <PRP/Surface/plMipmap.h>

#define TEXTARGET_TEXTURE_2D 0

// ===============================================================================================

static inline void _ensure_copy_bytes(PyObject* parent, PyObject*& data) {
    // PyBytes objects are immutable and ought not to be changed once they are returned to Python
    // code. Therefore, this tests to see if the given bytes object is the same as one we're holding.
    // If so, a new copy is constructed seamlessly.
    if (parent == data) {
        Py_ssize_t size;
        char* buf;
        PyBytes_AsStringAndSize(parent, &buf, &size);
        data = PyBytes_FromStringAndSize(buf, size);
        Py_DECREF(parent);
    }
}

template<typename T>
static T _ensure_power_of_two(T value) {
    return static_cast<T>(std::pow(2, std::floor(std::log2(value))));
}

static void _flip_image(size_t width, size_t dataSize, uint8_t* data) {
    // OpenGL returns a flipped image, so we must reflip it.
    size_t row_stride = width * 4;
    uint8_t* sptr = data;
    uint8_t* eptr = data + (dataSize - row_stride);
    uint8_t* temp = new uint8_t[row_stride];
    do {
        memcpy(temp, sptr, row_stride);
        memcpy(sptr, eptr, row_stride);
        memcpy(eptr, temp, row_stride);
    } while ((sptr += row_stride) < (eptr -= row_stride));
    delete[] temp;
}

static inline bool _get_float(PyObject* source, const char* attr, float& result) {
    if (source) {
        PyObjectRef pyfloat = PyObject_GetAttrString(source, attr);
        if (pyfloat) {
            result = (float)PyFloat_AsDouble(pyfloat);
            return PyErr_Occurred() == NULL;
        }
    }
    return false;
}

static inline int _get_num_levels(size_t width, size_t height) {
    int num_levels = (int)std::floor(std::log2(std::max((float)width, (float)height))) + 1;

    // Major Workaround No More!
    // Previously, we lopped off the last two mip levels. DXT compression acts on 4x4 blocks, so
    // it's not possible to DXT compress anything smaller than that. libHSPlasma used to not take
    // that into account and would try to allocate memory for things like 2x2 and 1x1 mip levels.
    // These allocations were never correct, and would crash the exporter when libHSPlasma tried to
    // compress those too-small mip levels. As of libHSPlasma#298, mip levels smaller than 4x4 are
    // stored uncompressed, so we can now use the technically correct level calculation from above.
    // Technically correct is often the best kind of correct, but this is still relevant:
    //     "<Deledrius> I feel like any texture at a 1x1 level is essentially academic.  I mean, JPEG/DXT
    //                  doesn't even compress that, and what is it?  Just the average color of the whole
    //                  texture in a single pixel?"
    // :)
    return num_levels;
}

static void _scale_image(const uint8_t* srcBuf, const size_t srcW, const size_t srcH, 
                         uint8_t* dstBuf, const size_t dstW, const size_t dstH) {
    float scaleX = static_cast<float>(srcW) / static_cast<float>(dstW);
    float scaleY = static_cast<float>(srcH) / static_cast<float>(dstH);
    float filterW = std::max(scaleX, 1.f);
    float filterH = std::max(scaleY, 1.f);
    size_t srcRowspan = srcW * sizeof(uint32_t);
    size_t dstIdx = 0;

    for (size_t dstY = 0; dstY < dstH; ++dstY) {
        float srcY = dstY * scaleY;
        ssize_t srcY_start = std::max(static_cast<ssize_t>(srcY - filterH),
                                     static_cast<ssize_t>(0));
        ssize_t srcY_end = std::min(static_cast<ssize_t>(srcY + filterH),
                                   static_cast<ssize_t>(srcH - 1));

        float weightsY[16];
        for (ssize_t i = srcY_start; i <= srcY_end && i - srcY_start < arrsize(weightsY); ++i)
            weightsY[i - srcY_start] = 1.f - std::abs((i - srcY) / filterH);

        for (size_t dstX = 0; dstX < dstW; ++dstX) {
            float srcX = dstX * scaleX;
            ssize_t srcX_start = std::max(static_cast<ssize_t>(srcX - filterW),
                                          static_cast<ssize_t>(0));
            ssize_t srcX_end = std::min(static_cast<ssize_t>(srcX + filterW),
                                        static_cast<ssize_t>(srcW - 1));

            float weightsX[16];
            for (ssize_t i = srcX_start; i <= srcX_end && i - srcX_start < arrsize(weightsX); ++i)
                weightsX[i - srcX_start] = 1.f - std::abs((i - srcX) / filterW);

            float accum_color[] = { 0.f, 0.f, 0.f, 0.f };
            float weight_total = 0.f;
            for (size_t i = srcY_start; i <= srcY_end; ++i) {
                float weightY;
                if (i - srcY_start < arrsize(weightsY))
                    weightY = weightsY[i - srcY_start];
                else
                    weightY = 1.f - std::abs((i - srcY) / filterH);

                if (weightY <= 0.f)
                    continue;

                size_t srcIdx = ((i * srcRowspan) + (srcX_start * sizeof(uint32_t)));
                for (size_t j = srcX_start; j <= srcX_end; ++j, srcIdx += sizeof(uint32_t)) {
                    float weightX;
                    if (j - srcX_start < arrsize(weightsX))
                        weightX = weightsX[j - srcX_start];
                    else
                        weightX = 1.f - std::abs((j - srcX) / filterW);
                    float weight = weightX * weightY;

                    if (weight > 0.f) {
                        for (size_t k = 0; k < sizeof(uint32_t); ++k)
                            accum_color[k] += (static_cast<float>(srcBuf[srcIdx+k]) / 255.f) * weight;
                        weight_total += weight;
                    }
                }
            }

            for (size_t k = 0; k < sizeof(uint32_t); ++k)
                accum_color[k] *= 1.f / weight_total;

            // Whew.
            for (size_t k = 0; k < sizeof(uint32_t); ++k)
                dstBuf[dstIdx+k] = static_cast<uint8_t>(accum_color[k] * 255.f);
            dstIdx += sizeof(uint32_t);
        }
    }
}

// ===============================================================================================

PyObject* scale_image(PyObject*, PyObject* args, PyObject* kwargs) {
    static char* kwlist[] = { _pycs("buf"), _pycs("srcW"), _pycs("srcH"),
                              _pycs("dstW"), _pycs("dstH"), NULL };
    const uint8_t* srcBuf;
    int srcBufSz;
    uint32_t srcW, srcH, dstW, dstH;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "y#IIII", kwlist, &srcBuf, &srcBufSz, &srcW, &srcH, &dstW, &dstH)) {
        PyErr_SetString(PyExc_TypeError, "scale_image expects a bytes object, int, int, int int");
        return NULL;
    }

    int expectedBufSz = srcW * srcH * sizeof(uint32_t);
    if (srcBufSz != expectedBufSz) {
        PyErr_Format(PyExc_ValueError, "buf size (%i bytes) incorrect (expected: %i bytes)", srcBufSz, expectedBufSz);
        return NULL;
    }

    PyObject* dst = PyBytes_FromStringAndSize(NULL, dstW * dstH * sizeof(uint32_t));
    uint8_t* dstBuf = reinterpret_cast<uint8_t*>(PyBytes_AS_STRING(dst));
    _scale_image(srcBuf, srcW, srcH, dstBuf, dstW, dstH);
    return dst;
}

// ===============================================================================================

enum {
    TEX_DETAIL_ALPHA = 0,
    TEX_DETAIL_ADD = 1,
    TEX_DETAIL_MULTIPLY = 2,
};

enum {
    kOpaque = 0,
    kOnOff = 1,
    kFull = 2,
};

typedef struct {
    PyObject_HEAD
    PyObject* m_blenderImage;
    PyObject* m_textureKey;
    PyObject* m_imageData;
    GLint m_width;
    GLint m_height;
    bool m_bgra;
    bool m_imageInverted;
} pyGLTexture;

// ===============================================================================================

static void pyGLTexture_dealloc(pyGLTexture* self) {
    Py_CLEAR(self->m_textureKey);
    Py_CLEAR(self->m_blenderImage);
    Py_CLEAR(self->m_imageData);
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject* pyGLTexture_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
    pyGLTexture* self = (pyGLTexture*)type->tp_alloc(type, 0);
    self->m_blenderImage = NULL;
    self->m_textureKey = NULL;
    self->m_imageData = NULL;
    self->m_width = 0;
    self->m_height = 0;
    self->m_bgra = false;
    self->m_imageInverted = false;
    return (PyObject*)self;
}

static int pyGLTexture___init__(pyGLTexture* self, PyObject* args, PyObject* kwds) {
    static char* kwlist[] = { _pycs("texkey"), _pycs("image"), _pycs("bgra"), _pycs("fast"), NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OObb", kwlist, &self->m_textureKey, &self->m_blenderImage,
                                     &self->m_bgra, &self->m_imageInverted)) {
        PyErr_SetString(PyExc_TypeError, "expected a korman.exporter.material._Texture or a bpy.types.Image");
        return -1;
    }
    if (!self->m_blenderImage && !self->m_textureKey) {
        PyErr_SetString(PyExc_TypeError, "expected a korman.exporter.material._Texture or a bpy.types.Image");
        return -1;
    }

    Py_XINCREF(self->m_blenderImage);
    Py_XINCREF(self->m_textureKey);
    if (!self->m_blenderImage) {
        self->m_blenderImage = PyObject_GetAttrString(self->m_textureKey, "image");
    }
    if (!self->m_blenderImage) {
        PyErr_SetString(PyExc_RuntimeError, "Could not fetch Blender Image");
        return -1;
    }

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

    GLint prevImage;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &prevImage);
    GLuint image_bindcode = PyLong_AsUnsignedLong(bindcode);
    bool ownit = image_bindcode == 0;

    // Load image into GL
    if (ownit) {
        PyObjectRef new_bind = PyObject_CallMethod(self->m_blenderImage, "gl_load", NULL);
        if (!new_bind)
            return NULL;

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
    bool changedState = prevImage != image_bindcode;
    if (changedState)
        glBindTexture(GL_TEXTURE_2D, image_bindcode);

    // Now we can load the image data...
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_WIDTH, &self->m_width);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, 0, GL_TEXTURE_HEIGHT, &self->m_height);

    size_t bufsz = self->m_width * self->m_height * sizeof(uint32_t);
    self->m_imageData = PyBytes_FromStringAndSize(NULL, bufsz);
    char* imbuf = PyBytes_AS_STRING(self->m_imageData);
    GLint fmt = self->m_bgra ? GL_BGRA_EXT : GL_RGBA;
    glGetTexImage(GL_TEXTURE_2D, 0, fmt, GL_UNSIGNED_BYTE, reinterpret_cast<GLvoid*>(imbuf));

    // OpenGL returns image data flipped upside down. We'll flip it to be correct, if requested.
    if (!self->m_imageInverted)
        _flip_image(self->m_width, bufsz, reinterpret_cast<uint8_t*>(imbuf));

    // If we had to play with ourse^H^H^H^H^Hblender's image state, let's reset it
    if (changedState)
        glBindTexture(GL_TEXTURE_2D, prevImage);
    if (ownit)
        PyObjectRef result = PyObject_CallMethod(self->m_blenderImage, "gl_free", NULL);

    Py_INCREF(self);
    return (PyObject*)self;
}

static PyObject* pyGLTexture__exit__(pyGLTexture* self, PyObject*) {
    Py_CLEAR(self->m_imageData);
    Py_RETURN_NONE;
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
    dropoff_start *= _get_num_levels(self->m_width, self->m_height);
    dropoff_stop /= 100.f;
    dropoff_stop *= _get_num_levels(self->m_width, self->m_height);
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
    PyObjectRef pydetail_blend;
    if (self->m_textureKey)
        pydetail_blend = PyObject_GetAttrString(self->m_textureKey, "detail_blend");
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

static PyObject* pyGLTexture_get_level_data(pyGLTexture* self, PyObject* args, PyObject* kwargs) {
    static char* kwlist[] = { _pycs("level"), _pycs("calc_alpha"), _pycs("report"),
                              _pycs("indent"), _pycs("fast"), NULL };
    GLint level = 0;
    bool calc_alpha = false;
    PyObject* report = nullptr;
    int indent = 2;
    bool fast = false;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|ibOib", kwlist, &level, &calc_alpha, &report, &indent, &fast)) {
        PyErr_SetString(PyExc_TypeError, "get_level_data expects an optional int, bool, obejct, int, bool");
        return NULL;
    }

    // We only ever want to return POT images for use in Plasma
    auto eWidth = _ensure_power_of_two(self->m_width) >> level;
    auto eHeight = _ensure_power_of_two(self->m_height) >> level;
    bool is_og = eWidth == self->m_width && eHeight == self->m_height;
    size_t bufsz = eWidth * eHeight * sizeof(uint32_t);

    // Print out the debug message
    if (report && report != Py_None) {
        PyObjectRef msg_func = PyObject_GetAttrString(report, "msg");
        PyObjectRef args = Py_BuildValue("siii", "Level #{}: {}x{}", level, eWidth, eHeight);
        PyObjectRef kwargs = Py_BuildValue("{s:i}", "indent", indent);
        PyObjectRef result = PyObject_Call(msg_func, args, kwargs);
    }

    PyObject* data;
    if (is_og) {
        Py_INCREF(self->m_imageData);
        data = self->m_imageData;
    } else {
        data = PyBytes_FromStringAndSize(NULL, bufsz);
        uint8_t* dstBuf = reinterpret_cast<uint8_t*>(PyBytes_AsString(data)); // AS_STRING :(
        uint8_t* srcBuf = reinterpret_cast<uint8_t*>(PyBytes_AsString(self->m_imageData));
        _scale_image(srcBuf, self->m_width, self->m_height, dstBuf, eWidth, eHeight);
    }

    // Make sure the level data is not flipped upside down...
    if (self->m_imageInverted && !fast) {
        _ensure_copy_bytes(self->m_blenderImage, data);
        _flip_image(eWidth, bufsz, reinterpret_cast<uint8_t*>(PyBytes_AS_STRING(data)));
    }

    // Detail blend
    if (self->m_textureKey) {
        PyObjectRef is_detail_map = PyObject_GetAttrString(self->m_textureKey, "is_detail_map");
        if (PyLong_AsLong(is_detail_map) != 0) {
            _ensure_copy_bytes(self->m_imageData, data);
            uint8_t* buf = reinterpret_cast<uint8_t*>(PyBytes_AS_STRING(data));
            if (_generate_detail_map(self, buf, bufsz, level) != 0) {
                PyErr_SetString(PyExc_RuntimeError, "error while baking detail map");
                Py_DECREF(data);
                return NULL;
            }
        }
    }

    if (calc_alpha) {
        _ensure_copy_bytes(self->m_imageData, data);
        char* buf = PyBytes_AS_STRING(data);
        for (size_t i = 0; i < bufsz; i += 4)
            buf[i + 3] = (buf[i + 0] + buf[i + 1] + buf[i + 2]) / 3;
    }

    return data;
}

static PyMethodDef pyGLTexture_Methods[] = {
    { _pycs("__enter__"), (PyCFunction)pyGLTexture__enter__, METH_NOARGS, NULL },
    { _pycs("__exit__"), (PyCFunction)pyGLTexture__exit__, METH_VARARGS, NULL },

    { _pycs("get_level_data"), (PyCFunction)pyGLTexture_get_level_data, METH_KEYWORDS | METH_VARARGS, NULL },
    { NULL, NULL, 0, NULL }
};

static PyObject* pyGLTexture_get_has_alpha(pyGLTexture* self, void*) {
    char* data = PyBytes_AsString(self->m_imageData);
    size_t bufsz = self->m_width * self->m_height * sizeof(uint32_t);
    bool transparency = false;

    uint32_t* datap = reinterpret_cast<uint32_t*>(data);
    uint32_t* endp = reinterpret_cast<uint32_t*>(data + bufsz);
    while (datap < endp) {
        uint8_t alpha = ((*datap & 0xFF000000) >> 24);
        if (alpha == 0x00)
            transparency = true;
        else if (alpha != 0xFF)
            return PyLong_FromLong(kFull);
        datap++;
    }
    return PyLong_FromLong(transparency ? kOnOff : kOpaque);
}

static PyObject* pyGLTexture_get_image_data(pyGLTexture* self, void*) {
    Py_XINCREF(self->m_imageData);
    return Py_BuildValue("iiO", self->m_width, self->m_height, self->m_imageData);
}

static int pyGLTexture_set_image_data(pyGLTexture* self, PyObject* value, void*) {
    PyObject* data;
    // Requesting a Bytes object "S" instead of a buffer "y#" so we can just increment the reference
    // count on a buffer that already exists, instead of doing a memcpy.
    if (!PyArg_ParseTuple(value, "iiS", &self->m_width, &self->m_height, &data)) {
        PyErr_SetString(PyExc_TypeError, "image_data should be a sequence of int, int, bytes");
        return -1;
    }

    Py_XDECREF(self->m_imageData);
    Py_XINCREF(data);
    self->m_imageData = data;
    return 0;
}

static PyObject* pyGLTexture_get_num_levels(pyGLTexture* self, void*) {
    return PyLong_FromLong(_get_num_levels(self->m_width, self->m_height));
}

static PyObject* pyGLTexture_get_size_npot(pyGLTexture* self, void*) {
    return Py_BuildValue("ii", self->m_width, self->m_height);
}

static PyObject* pyGLTexture_get_size_pot(pyGLTexture* self, void*) {
    size_t width = _ensure_power_of_two(self->m_width);
    size_t height = _ensure_power_of_two(self->m_height);
    return Py_BuildValue("ii", width, height);
}

static PyGetSetDef pyGLTexture_GetSet[] = {
    { _pycs("has_alpha"), (getter)pyGLTexture_get_has_alpha, NULL, NULL, NULL },
    { _pycs("image_data"), (getter)pyGLTexture_get_image_data, (setter)pyGLTexture_set_image_data, NULL, NULL },
    { _pycs("num_levels"), (getter)pyGLTexture_get_num_levels, NULL, NULL, NULL },
    { _pycs("size_npot"), (getter)pyGLTexture_get_size_npot, NULL, NULL, NULL },
    { _pycs("size_pot"), (getter)pyGLTexture_get_size_pot, NULL, NULL, NULL },
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
