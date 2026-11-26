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

#include "PyHSPlasma.h"

// ============================================================================

#define PY_WRAP_PLASMA(pyType, plType) PyTypeObject* py##pyType##_Type = nullptr;
#define PY_WRAP_PLASMA_VALUE(pyType, plType) PyTypeObject* py##pyType##_Type = nullptr;

#include "PyHSPlasma.inl"

#undef PY_WRAP_PLASMA_VALUE
#undef PY_WRAP_PLASMA

// ============================================================================

bool Init_PyHSPlasma_Types() {
    PyObjectRef mod = PyImport_ImportModule("PyHSPlasma");
    if (!mod)
        return false;

#define PY_WRAP_PLASMA(pyType, plType)                                        \
    {                                                                         \
        PyObjectRef cls = PyObject_GetAttrString(mod, #plType);               \
        if (!cls)                                                             \
            return false;                                                     \
        if (!PyType_Check(cls)) {                                             \
            PyErr_SetString(PyExc_KeyError, "'" #plType "' is not a type in PyHSPlasma"); \
            return false;                                                     \
        }                                                                     \
        py##pyType##_Type = (PyTypeObject*)cls.release();                     \
    }
#define PY_WRAP_PLASMA_VALUE(pyType, plType) PY_WRAP_PLASMA(pyType, plType)

#include "PyHSPlasma.inl"

#undef PY_WRAP_PLASMA_VALUE
#undef PY_WRAP_PLASMA

    return true;
}

// ============================================================================

void DeInit_PyHSPlasma_Types() {
#define PY_WRAP_PLASMA(pyType, plType) Py_CLEAR(py##pyType##_Type);
#define PY_WRAP_PLASMA_VALUE(pyType, plType) Py_CLEAR(py##pyType##_Type);

#include "PyHSPlasma.inl"

#undef PY_WRAP_PLASMA_VALUE
#undef PY_WRAP_PLASMA
}
