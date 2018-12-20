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

#ifndef _KORLIB_TEXTURE_H
#define _KORLIB_TEXTURE_H

#include "korlib.h"

extern "C" {

PyObject* scale_image(PyObject*, PyObject*, PyObject*);

extern PyTypeObject pyGLTexture_Type;
PyObject* Init_pyGLTexture_Type();

};

#endif // _KORLIB_TEXTURE_H
