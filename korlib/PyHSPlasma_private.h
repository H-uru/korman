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

#ifndef _PYHSPLASMA_PRIVATE_H
#define _PYHSPLASMA_PRIVATE_H

#include "korlib.h"

typedef struct {
    PyObject_HEAD
    class plMipmap* fThis;
    bool fPyOwned;
} pyMipmap;

typedef struct {
    PyObject_HEAD
    class hsStream* fThis;
    bool fPyOwned;
} pyStream;

typedef struct {
    PyObject_HEAD
    class plWAVHeader* fThis;
    bool fPyOwned;
} pyWAVHeader;

#endif
