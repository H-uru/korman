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

#ifndef _KORLIB_H
#define _KORLIB_H

#define NOMINMAX

#include <Python.h>

// ============================================================================

#define _pycs(x) const_cast<char*>(x)

// ============================================================================

class PyObjectRef {
    PyObject* m_object;

public:
    PyObjectRef() : m_object() { }
    PyObjectRef(PyObject* o) : m_object(o) { }
    PyObjectRef(const PyObjectRef& copy) = delete;
    PyObjectRef(PyObjectRef&& move) noexcept {
        m_object = move.m_object;
        move.m_object = nullptr;
    }

    ~PyObjectRef() { Py_XDECREF(m_object); }

    operator PyObject*() const { return m_object; }

    PyObjectRef& operator =(PyObject* rhs) {
        Py_XDECREF(m_object);
        m_object = rhs;
        return *this;
    }

    PyObjectRef& operator =(PyObjectRef&& move) noexcept {
        Py_XDECREF(m_object);
        m_object = move.m_object;
        move.m_object = nullptr;
        return *this;
    }

    PyObjectRef& operator =(const PyObjectRef& copy) = delete;
};

#endif // _KORLIB_H
