/*    This file is part of Korman.
 *
 *    Korman is free software: you can redistribute it and/or modify
 *    it under the terms of the GNU General Public License as published by
 *    the Free Software Foundation, either version 3 of the License, or
 *    (at your option) any later version.
 *
 *    Korman is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *    GNU General Public License for more details.
 *
 *    You should have received a copy of the GNU General Public License
 *    along with Korman.  If not, see <http://www.gnu.org/licenses/>.
 */

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <tuple>

#ifdef _WINDOWS
#   define NOMINMAX
#   define WIN32_LEAN_AND_MEAN
#   include <windows.h>

#   define GL_GENERATE_MIPMAP 0x8191
#endif // _WINDOWS

#include <gl/gl.h>

#include <ResManager/plFactory.h>
#include <PRP/Surface/plMipmap.h>
#include <Python.h>

#include "pyMipmap.h"
#include "utils.hpp"

// ========================================================================

class gl_loadimage
{
    bool m_weLoadedIt;
    bool m_success;
    GLint m_genMipMapState;
    korlib::pyref m_image;

public:
    gl_loadimage(const korlib::pyref& image) : m_success(true), m_image(image)
    {
        size_t bindcode = korlib::getattr<size_t>(image, "bindcode");
        m_weLoadedIt = (bindcode == 0);
        if (m_weLoadedIt) {
            m_success = (korlib::call_method<size_t>(image, "gl_load") == 0);
            bindcode = korlib::getattr<size_t>(image, "bindcode");
        }
        if (m_success) {
            glBindTexture(GL_TEXTURE_2D, bindcode);
        }

        // We want to gen mipmaps
        // GIANTLY GNARLY DISCLAIMER:
        // This requires OpenGL 1.4, which is above Windows' "built-in" headers (1.1)
        // It was also deprecated in 3.0, and removed in 3.1.
        // In other words, we should probably use glGenerateMipmap (3.0) or Blender's scale function
        glGetTexParameteriv(GL_TEXTURE_2D, GL_GENERATE_MIPMAP, &m_genMipMapState);
        glTexParameteri(GL_TEXTURE_2D, GL_GENERATE_MIPMAP, GL_TRUE);
    }

    ~gl_loadimage()
    {
        if (m_success && m_weLoadedIt)
            korlib::call_method<size_t>(m_image, "gl_free");
        glTexParameteri(GL_TEXTURE_2D, GL_GENERATE_MIPMAP, m_genMipMapState);
    }

    bool success() const { return m_success; }
};

// ========================================================================

typedef std::tuple<size_t, size_t> imagesize_t;

/** Gets the dimensions of a Blender Image in pixels (WxH) */
static imagesize_t get_image_size(PyObject* image)
{
    korlib::pyref size = PyObject_GetAttrString(image, "size");
    size_t width = PyLong_AsSize_t(PySequence_GetItem(size, 0));
    size_t height = PyLong_AsSize_t(PySequence_GetItem(size, 1));

    return std::make_tuple(width, height);
}

static void resize_image(PyObject* image, size_t width, size_t height)
{
    korlib::pyref _w = PyLong_FromSize_t(width);
    korlib::pyref _h = PyLong_FromSize_t(height);
    korlib::pyref callable = korlib::getattr<PyObject*>(image, "scale");
    korlib::pyref result = PyObject_CallFunctionObjArgs(callable, _w, _h);
}

// ========================================================================

static void stuff_mip_level(plMipmap* mipmap, size_t level, PyObject* image, bool calcAlpha)
{
    // How big is this doggone level?
    GLint width, height;
    glGetTexLevelParameteriv(GL_TEXTURE_2D, level, GL_TEXTURE_WIDTH, &width);
    glGetTexLevelParameteriv(GL_TEXTURE_2D, level, GL_TEXTURE_HEIGHT, &height);
    print("    Level %d: %dx%d...", level, width, height);

    // Grab the stuff from the place and the things
    size_t dataSize = width * height * 4;
    uint8_t* data = new uint8_t[dataSize]; // optimization: use stack for small images...
    glGetTexImage(GL_TEXTURE_2D, level, GL_RGBA, GL_UNSIGNED_BYTE, data);

    // Need to calculate alpha?
    if (calcAlpha) {
        uint8_t* ptr = data;
        uint8_t* end = data + dataSize;
        while (ptr < end) {
            uint8_t r = *ptr++;
            uint8_t g = *ptr++;
            uint8_t b = *ptr++;
            *ptr++ = (r + g + b) / 255;
        }
    }

    // Stuff into plMipmap. Unfortunately, it's not smart enough to just work, so we have to do
    // a little bit of TESTing here.
    try {
        mipmap->CompressImage(level, data, dataSize);
    } catch (hsNotImplementedException&) {
        mipmap->setLevelData(level, data, dataSize);
    }
    delete[] data;
}

// ========================================================================

extern "C" PyObject* generate_mipmap(PyObject*, PyObject* args)
{
    // Convert some of this Python nonsense to good old C
    PyObject* blTexImage = nullptr; // unchecked... better be right
    PyObject* pymm = nullptr;
    if (PyArg_ParseTuple(args, "OO", &blTexImage, &pymm) && blTexImage && pymm) {
        // Since we can't link with PyHSPlasma easily, let's do some roundabout type-checking
        korlib::pyref classindex = PyObject_CallMethod(pymm, "ClassIndex", "");
        static short mipmap_classindex = plFactory::ClassIndex("plMipmap");

        if (PyLong_AsLong(classindex) != mipmap_classindex) {
            PyErr_SetString(PyExc_TypeError, "generate_mipmap expects a Blender ImageTexture and a plMipmap");
            return nullptr;
        }
    } else {
        PyErr_SetString(PyExc_TypeError, "generate_mipmap expects a Blender ImageTexture and a plMipmap");
        return nullptr;
    }

    // Grab the important stuff
    plMipmap* mipmap = ((pyMipmap*)pymm)->fThis;
    korlib::pyref blImage = korlib::getattr<PyObject*>(blTexImage, "image");
    bool makeMipMap = korlib::getattr<bool>(blTexImage, "use_mipmap");
    bool useAlpha = korlib::getattr<bool>(blTexImage, "use_alpha");
    bool calcAlpha = korlib::getattr<bool>(blTexImage, "use_calculate_alpha");

    // Okay, so, here are the assumptions.
    // We assume that the Korman Python code as already created the mipmap's key and named it appropriately
    // So, if we're mipmapping nb01StoneSquareCobble.tga -> nb01StoneSquareCobble.dds as the key name
    // What we now need to do:
    //     1) Make sure this is a POT texture (if not, call scale on the Blender Image)
    //     2) Check calcAlpha and all that rubbish--det DXT1/DXT5/uncompressed
    //     3) "Create" the plMipmap--this allocates internal buffers and such
    //     4) Loop through the levels, going down through the POTs and fill in the pixel data
    // The reason we do this in C instead of python is because it's a lot of iterating over a lot of
    // floating point data (we have to convert to RGB8888, joy). Should be faster here!
    print("Exporting '%s'...", mipmap->getKey()->getName().cstr());

    // Step 1: Resize to POT (if needed) -- don't rely on GLU for this because it may not suppport
    //         NPOT if we're being run on some kind of dinosaur...
    imagesize_t dimensions = get_image_size(blImage);
    size_t width = pow(2., korlib::log2(static_cast<double>(std::get<0>(dimensions))));
    size_t height = pow(2., korlib::log2(static_cast<double>(std::get<1>(dimensions))));
    if (std::get<0>(dimensions) != width || std::get<1>(dimensions) != height) {
        print("\tImage is not a POT (%dx%d)... resizing to %dx%d", std::get<0>(dimensions),
              std::get<1>(dimensions), width, height);
        resize_image(blImage, width, height);
    }

    // Steps 2+3: Translate flags and pass to plMipmap::Create
    // TODO: PNG compression for lossless images
    uint8_t numLevels = (makeMipMap) ? 0 : 1; // 0 means "you figure it out"
    uint8_t compType = (makeMipMap) ? plBitmap::kDirectXCompression : plBitmap::kUncompressed;
    bool alphaChannel = useAlpha || calcAlpha;
    mipmap->Create(width, height, numLevels, compType, plBitmap::kRGB8888, alphaChannel ? plBitmap::kDXT5 : plBitmap::kDXT1);

    // Step 3.9: Load the image into OpenGL
    gl_loadimage guard(blImage);
    if (!guard.success()) {
        PyErr_SetString(PyExc_RuntimeError, "failed to load image into OpenGL");
        return nullptr;
    }

    // Step 4: Now it's a matter of looping through all the levels and exporting the image
    for (size_t i = 0; i < mipmap->getNumLevels(); ++i) {
        stuff_mip_level(mipmap, i, blImage, calcAlpha);
    }

    Py_RETURN_NONE;
}
