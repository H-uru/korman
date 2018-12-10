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
#include "sound.h"
#include "texture.h"

extern "C" {

static PyMethodDef korlib_Methods[] = {
    { _pycs("create_bump_LUT"), (PyCFunction)create_bump_LUT, METH_VARARGS, NULL },
    { _pycs("inspect_vorbisfile"), (PyCFunction)inspect_vorbisfile, METH_VARARGS, NULL },
    { _pycs("scale_image"), (PyCFunction)scale_image, METH_KEYWORDS | METH_VARARGS, NULL },

    { NULL, NULL, 0, NULL },
};

static PyModuleDef korlib_Module = {
    PyModuleDef_HEAD_INIT,      /* m_base */
    "_korlib",                  /* m_name */
    "C++ korlib implementation",/* m_doc */
    0,                          /* m_size */
    korlib_Methods,             /* m_methods */
    NULL,                       /* m_reload */
    NULL,                       /* m_traverse */
    NULL,                       /* m_clear */
    NULL,                       /* m_free */
};

PyMODINIT_FUNC PyInit__korlib() {
    PyObject* module = PyModule_Create(&korlib_Module);

    // Module classes...
    PyModule_AddObject(module, "GLTexture", Init_pyGLTexture_Type());

    return module;
}

};

