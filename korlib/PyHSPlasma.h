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

#ifndef _PYHSPLASMA_H
#define _PYHSPLASMA_H

#include "korlib.h"

// ============================================================================

#define PY_WRAP_PLASMA(pyType, plType)                                        \
    class plType;                                                             \
    struct py##pyType {                                                       \
        PyObject_HEAD                                                         \
        plType* fThis;                                                        \
        bool fPyOwned;                                                        \
    };                                                                        \
    extern PyTypeObject* py##pyType##_Type;

#define PY_WRAP_PLASMA_VALUE(pyType, plType)                                  \
    class plType;                                                             \
    struct py##pyType {                                                       \
        PyObject_HEAD                                                         \
        plType* fThis;                                                        \
    };                                                                        \
    extern PyTypeObject* py##pyType##_Type;

#include "PyHSPlasma.inl"

#undef PY_WRAP_PLASMA_VALUE
#undef PY_WRAP_PLASMA

// ============================================================================

bool Init_PyHSPlasma_Types();
void DeInit_PyHSPlasma_Types();

#endif
