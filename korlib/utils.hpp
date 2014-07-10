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

#ifndef __KORLIB_UTILS_HPP
#define __KORLIB_UTILS_HPP

#include <Python.h>

#define print(fmt, ...) PySys_WriteStdout("            " fmt "\n", __VA_ARGS__)

namespace korlib
{
    /** RAII for PyObject pointers */
    class pyref
    {
        PyObject* _ref;
    public:
        pyref(PyObject* o) : _ref(o) { }
        pyref(const pyref& copy) : _ref((PyObject*)copy)
        {
            Py_INCREF(_ref);
        }

        ~pyref()
        {
            Py_XDECREF(_ref);
        }

        operator PyObject*() const { return _ref; }
    };

    template<typename T>
    T call_method(PyObject* o, const char* method);

    template<>
    size_t call_method(PyObject* o, const char* method)
    {
        pyref retval = PyObject_CallMethod(o, const_cast<char*>(method), "");
        if ((PyObject*)retval)
            return PyLong_AsSize_t(retval);
        else
            return static_cast<size_t>(-1);
    }

    template<typename T>
    T getattr(PyObject* o, const char* name);

    template<>
    bool getattr(PyObject* o, const char* name)
    {
        pyref attr = PyObject_GetAttrString(o, name);
        return PyLong_AsLong(attr) != 0;
    }

    template<>
    PyObject* getattr(PyObject* o, const char* name)
    {
        return PyObject_GetAttrString(o, name);
    }

    template<>
    size_t getattr(PyObject* o, const char* name)
    {
        pyref attr = PyObject_GetAttrString(o, name);
        return PyLong_AsSize_t(attr);
    }
};

#endif // __KORLIB_UTILS_HPP
