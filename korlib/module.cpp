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

#include <Python.h>

// ========================================================================

extern "C" PyObject* generate_mipmap(PyObject*, PyObject*);

// ========================================================================

static struct PyMethodDef s_korlibMethods[] =
{
    { "generate_mipmap", generate_mipmap, METH_VARARGS, "Generates a new plMipmap from a Blender ImageTexture" },
    { nullptr, nullptr, 0, nullptr },
};

static struct PyModuleDef s_korlibModule = {
    PyModuleDef_HEAD_INIT,
    "korlib",
    NULL,
    -1,
    s_korlibMethods
};

#define ADD_CONSTANT(module, name) \
    PyModule_AddIntConstant(module, #name, korlib::name)

PyMODINIT_FUNC PyInit_korlib()
{
    PyObject* module = PyModule_Create(&s_korlibModule);

    // Done!
    return module;
}
