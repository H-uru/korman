project(korlib)
cmake_minimum_required(VERSION 3.0)

set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

# Stolen shamelessly from PyHSPlasma
find_package(PythonLibs REQUIRED)
find_package(PythonInterp "3.5" REQUIRED)
find_package(HSPlasma REQUIRED)
find_package(Ogg REQUIRED)
find_package(OpenGL REQUIRED)
find_package(string_theory REQUIRED)
find_package(Vorbis REQUIRED)

if(CMAKE_COMPILER_IS_GNUCXX OR "${CMAKE_CXX_COMPILER_ID}" MATCHES ".*Clang")
    set(CMAKE_CXX_FLAGS "-Wall -Wextra -Wno-unused-parameter ${CMAKE_CXX_FLAGS}")
endif()

# Da files
set(korlib_HEADERS
    bumpmap.h
    korlib.h
    PyHSPlasma_private.h
    sound.h
    texture.h
)

set(korlib_SOURCES
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
