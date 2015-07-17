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

#include "buffer.h"

extern "C" {

static void pyBuffer_dealloc(pyBuffer* self) {
    delete[] self->m_buffer;
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject* pyBuffer_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
    PyErr_SetString(PyExc_RuntimeError, "Buffers cannot be created by mere mortals");
    return NULL;
}

PyTypeObject pyBuffer_Type = {
    PyVarObject_HEAD_INIT(NULL, 0)
    "_korlib.Buffer",                   /* tp_name */
    sizeof(pyBuffer),                   /* tp_basicsize */
    0,                                  /* tp_itemsize */

    (destructor)pyBuffer_dealloc,       /* tp_dealloc */
    NULL,                               /* tp_print */
    NULL,                               /* tp_getattr */
    NULL,                               /* tp_setattr */
    NULL,                               /* tp_compare */
    NULL,                               /* tp_repr */
    NULL,                               /* tp_as_number */
    NULL,                               /* tp_as_sequence */
    NULL,                               /* tp_as_mapping */
    NULL,                               /* tp_hash */
    NULL,                               /* tp_call */
    NULL,                               /* tp_str */
    NULL,                               /* tp_getattro */
    NULL,                               /* tp_setattro */
    NULL,                               /* tp_as_buffer */

    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /* tp_flags */
    "Buffer",                                 /* tp_doc */

    NULL,                               /* tp_traverse */
    NULL,                               /* tp_clear */
    NULL,                               /* tp_richcompare */
    0,                                  /* tp_weaklistoffset */
    NULL,                               /* tp_iter */
    NULL,                               /* tp_iternext */

    NULL,                               /* tp_methods */
    NULL,                               /* tp_members */
    NULL,                               /* tp_getset */
    NULL,                               /* tp_base */
    NULL,                               /* tp_dict */
    NULL,                               /* tp_descr_get */
    NULL,                               /* tp_descr_set */
    0,                                  /* tp_dictoffset */

    NULL,                               /* tp_init */
    NULL,                               /* tp_alloc */
    pyBuffer_new,                       /* tp_new */
    NULL,                               /* tp_free */
    NULL,                               /* tp_is_gc */

    NULL,                               /* tp_bases */
    NULL,                               /* tp_mro */
    NULL,                               /* tp_cache */
    NULL,                               /* tp_subclasses */
    NULL,                               /* tp_weaklist */

    NULL,                               /* tp_del */
    0,                                  /* tp_version_tag */
    NULL,                               /* tp_finalize */
};

PyObject* Init_pyBuffer_Type() {
    if (PyType_Ready(&pyBuffer_Type) < 0)
        return NULL;

    Py_INCREF(&pyBuffer_Type);
    return (PyObject*)&pyBuffer_Type;
}

int pyBuffer_Check(PyObject* obj) {
    if (obj->ob_type == &pyBuffer_Type
        || PyType_IsSubtype(obj->ob_type, &pyBuffer_Type))
        return 1;
    return 0;
}

PyObject* pyBuffer_Steal(uint8_t* buffer, size_t size) {
    pyBuffer* obj = PyObject_New(pyBuffer, &pyBuffer_Type);
    obj->m_buffer = buffer;
    obj->m_size = size;
    return (PyObject*)obj;
}

};
