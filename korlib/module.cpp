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

#include <stdexcept>
#include <tuple>
#include <vector>

#include "korlib.h"
#include "PyHSPlasma.h"

// ============================================================================

// This konstant is compared against that in the Python module to prevent sneaky errors...
#define KORLIB_API_VERSION 2

// ============================================================================

static void korlib_free(void*);

static PyModuleDef s_moduleDef{
    PyModuleDef_HEAD_INIT,      /* m_base */
    "_korlib",                  /* m_name */
    "C++ korlib implementation",/* m_doc */
    0,                          /* m_size */
    nullptr,                    /* m_methods */
    nullptr,                    /* m_reload */
    nullptr,                    /* m_traverse */
    nullptr,                    /* m_clear */
    korlib_free,                /* m_free */
};

// ============================================================================

static void korlib_free(void*) {
    DeInit_PyHSPlasma_Types();
    s_moduleDef.m_methods = nullptr;
}

// ============================================================================

namespace {
    static inline std::vector<PyMethodDef>& IMethodDefs() {
        static std::vector<PyMethodDef> s_methodDefs;
        return s_methodDefs;
    }

    static inline std::vector<std::tuple<const char*, PyType_Spec*>>& ITypeSpecs() {
        static std::vector<std::tuple<const char*, PyType_Spec*>> s_typeSpecs;
        return s_typeSpecs;
    }
};

// ============================================================================

static inline bool Init_KorlibFunctions() {
    PyMethodDef* lastDef = nullptr;
    if (!IMethodDefs().empty())
        lastDef = &(IMethodDefs().back());

    // Ensure the last entry in the methods table is the end sentry
    if (lastDef == nullptr || lastDef->ml_meth != nullptr)
        IMethodDefs().emplace_back(PyMethodDef{ nullptr, nullptr, 0, nullptr });

    s_moduleDef.m_methods = IMethodDefs().data();
    return true;
}

static inline bool Init_KorlibTypes(PyObject* mod) {
    for (auto [name, spec] : ITypeSpecs()) {
        PyObject* newType = PyType_FromSpec(spec);
        if (!newType)
            return false;

        if (PyModule_AddObject(mod, name, newType) != 0) {
            // Failed to add type, reference not stolen.
            Py_XDECREF(newType);
            return false;
        }
    }

    return true;
}

static inline bool Init_KorlibConstants(PyObject* mod) {
    if (PyModule_AddIntConstant(mod, "_KORLIB_API_VERSION", KORLIB_API_VERSION) != 0)
        return false;
    return true;
}

static inline PyObject* Init_Korlib() {
    if (!Init_PyHSPlasma_Types())
        return nullptr;
    if (!Init_KorlibFunctions())
        return nullptr;

    PyObjectRef mod = PyModule_Create(&s_moduleDef);
    if (!mod)
        return nullptr;
    if (!Init_KorlibTypes(mod))
        return nullptr;
    if (!Init_KorlibConstants(mod))
        return nullptr;

    return mod.release();
}

extern "C" { PyMODINIT_FUNC PyInit__korlib() { return Init_Korlib(); } };

// ============================================================================

_detail::KorlibFunction::KorlibFunction(const char* name, PyCFunction func, int flags, const char* doc) {
    if (s_moduleDef.m_methods != nullptr)
        throw std::runtime_error("Cannot add a new function after the module has initialized");

    IMethodDefs().emplace_back(PyMethodDef{ name, func, flags, doc });
}

_detail::KorlibType::KorlibType(const char* name, PyType_Spec* spec) {
    if (s_moduleDef.m_methods != nullptr)
        throw std::runtime_error("Cannot add a new type after the module has initialized");

    ITypeSpecs().emplace_back(std::make_tuple(name, spec));
}
