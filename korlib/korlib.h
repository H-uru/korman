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

namespace _detail {
    class KorlibFunction {
    public:
        KorlibFunction(const char* name, PyCFunction func, int flags, const char* doc = nullptr);
        KorlibFunction(const KorlibFunction&) = delete;
        KorlibFunction(KorlibFunction&&) = delete;
    };

    class KorlibType {
    public:
        KorlibType(const char* name, PyType_Spec* spec);
        KorlibType(const KorlibType&) = delete;
        KorlibType(KorlibType&&) = delete;
    };
};

#define _KORLIB_FUNCTION(x, flags)                                            \
    namespace {                                                               \
        _detail::KorlibFunction py##x##_FuncInit(#x, (PyCFunction)x, flags);  \
    }

#define KORLIB_FUNCTION_NOARGS(x) _KORLIB_FUNCTION(x, METH_NOARGS)
#define KORLIB_FUNCTION_VARARGS(x) _KORLIB_FUNCTION(x, METH_VARARGS)
#define KORLIB_FUNCTION_KWARGS(x) _KORLIB_FUNCTION(x, METH_VARARGS | METH_KEYWORDS)

#define KORLIB_TYPE(x)                                                        \
    namespace {                                                               \
        _detail::KorlibType py##x##_TypeInit(#x, &py##x##_Spec);              \
    }

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

    PyObject* release() {
        PyObject* o = m_object;
        m_object = nullptr;
        return o;
    }

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
