project(korlib)
cmake_minimum_required(VERSION 3.0)

set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

# Stolen shamelessly from PyHSPlasma
find_package(PythonLibs REQUIRED)
# Use only the major.minor version -- no patch, no +, etc
STRING(REGEX REPLACE "([0-9]\\.[0-9])[0-9.+]*" "\\1" PYTHONLIBS_VERSION_STRING_FILTERED "${PYTHONLIBS_VERSION_STRING}")
find_package(PythonInterp "${PYTHONLIBS_VERSION_STRING_FILTERED}" REQUIRED)
# make sure the versions match
STRING(REGEX REPLACE "([0-9]\\.[0-9])[0-9.+]*" "\\1" PYTHON_VERSION_STRING_FILTERED "${PYTHON_VERSION_STRING}")
if (NOT "${PYTHONLIBS_VERSION_STRING_FILTERED}" STREQUAL "${PYTHON_VERSION_STRING_FILTERED}")
    message(FATAL_ERROR "Versions of Python libraries (${PYTHONLIBS_VERSION_STRING_FILTERED}) and Python interpreter (${PYTHON_VERSION_STRING_FILTERED}) do not match. Please configure the paths manually.")
endif()

find_package(HSPlasma REQUIRED)
find_package(Ogg REQUIRED)
find_package(OpenGL REQUIRED)
find_package(string_theory REQUIRED)
find_package(Vorbis REQUIRED)

# Da files
set(korlib_HEADERS
    buffer.h
    bumpmap.h
    korlib.h
    sound.h
    texture.h
)

set(korlib_SOURCES
    buffer.cpp
    bumpmap.cpp
    module.cpp
    sound.cpp
    texture.cpp
)

include_directories(${HSPlasma_INCLUDE_DIRS})
include_directories(${Ogg_INCLUDE_DIR})
include_directories(${OPENGL_INCLUDE_DIR})
include_directories(${PYTHON_INCLUDE_DIRS})
include_directories(${STRING_THEORY_INCLUDE_DIRS})
include_directories(${Vorbis_INCLUDE_DIR})

add_library(_korlib SHARED ${korlib_HEADERS} ${korlib_SOURCES})
set_target_properties(_korlib PROPERTIES PREFIX "")
if(NOT WIN32)
    set_target_properties(_korlib PROPERTIES SUFFIX ".so")
else()
    set_target_properties(_korlib PROPERTIES SUFFIX ".pyd")
endif()
target_link_libraries(_korlib HSPlasma ${Ogg_LIBRARIES} ${OPENGL_LIBRARIES}
                                       ${PYTHON_LIBRARIES} ${STRING_THEORY_LIBRARIES}
                                       ${Vorbis_LIBRARIES})
