cmake_minimum_required(VERSION 3.12)
project(korlib)

set(CMAKE_INSTALL_PREFIX "${CMAKE_CURRENT_BINARY_DIR}/install" CACHE PATH "")
set(CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

set(korlib_PYTHON_VERSION "" CACHE STRING "Exact Python3 version to find")
if(korlib_PYTHON_VERSION)
    set(_Python3_find_version ${korlib_PYTHON_VERSION} EXACT)
endif()
set(Python3_FIND_STRATEGY VERSION)
find_package(Python3 ${_Python3_find_version} COMPONENTS Development REQUIRED)

find_package(HSPlasma REQUIRED)
find_package(Ogg REQUIRED)
find_package(OpenGL REQUIRED)
find_package(string_theory REQUIRED)
find_package(Vorbis REQUIRED)

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

Python3_add_library(_korlib MODULE ${korlib_HEADERS} ${korlib_SOURCES})
target_link_libraries(_korlib
    PRIVATE
        HSPlasma
        Ogg::ogg
        OpenGL::GL
        string_theory
        Vorbis::vorbisfile
)
install(TARGETS _korlib DESTINATION "bin")
