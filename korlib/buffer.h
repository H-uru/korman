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

#ifndef _KORLIB_BUFFER_H
#define _KORLIB_BUFFER_H

#include "korlib.h"

extern "C" {

typedef struct {
    PyObject_HEAD
    uint8_t* m_buffer;
    size_t m_size;
} pyBuffer;

extern PyTypeObject pyBuffer_Type;
PyObject* Init_pyBuffer_Type();
int pyBuffer_Check(PyObject*);
PyObject* pyBuffer_Steal(uint8_t*, size_t);

}

#endif // _KORLIB_BUFFER_H
