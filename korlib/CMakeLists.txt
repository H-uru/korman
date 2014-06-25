project(korman)
cmake_minimum_required(VERSION 2.8.9)

find_package(HSPlasma REQUIRED)
find_package(OpenGL REQUIRED)
find_package(PythonLibs REQUIRED)

include_directories(${HSPlasma_INCLUDE_DIRS})
include_directories(${OPENGL_INCLUDE_DIR})
include_directories(${PYTHON_INCLUDE_DIR})

set(korlib_HEADERS
    pyMipmap.h
    utils.hpp
)

set(korlib_SOURCES
    generate_mipmap.cpp
    module.cpp
)

add_library(korlib SHARED ${korlib_HEADERS} ${korlib_SOURCES})
target_link_libraries(korlib HSPlasma ${OPENGL_LIBRARIES} ${PYTHON_LIBRARIES})

if(WIN32)
    set_target_properties(korlib PROPERTIES SUFFIX ".pyd")
endif(WIN32)

source_group("Header Files" FILES ${korlib_HEADERS})
source_group("Source Files" FILES ${korlib_SOURCES})
