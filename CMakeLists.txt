#    This file is part of Korman.
#
#    Korman is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Korman is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Korman.  If not, see <http://www.gnu.org/licenses/>.

cmake_minimum_required(VERSION 3.12)

set(_PROJECT_INFO
    korman
    VERSION 0.13
    DESCRIPTION "Blender plugin for creating ages for Cyan Worlds' proprietary Plasma engine and its open source variant, CyanWorlds.com Engine."
    LANGUAGES CXX # This should probably be NONE, but we need the compiler for string_theory tests
)
project(${_PROJECT_INFO})

include(CMakeDependentOption)

set(CMAKE_MODULE_PATH "${PROJECT_SOURCE_DIR}/cmake")
set(CMAKE_INSTALL_PREFIX "${PROJECT_BINARY_DIR}/install" CACHE PATH "")

# TODO: Maybe use cmake_path (requires CMake 3.21) to ensure Blender_EXECUTABLE is not in the CMAKE_INSTALL_PREFIX?
# That would indicate that we are installing Korman into the blender we found, so no need to install blender.
option(korman_INSTALL_BLENDER "Copy Blender as part of the INSTALL target" ON)
option(korman_INSTALL_SCRIPTS "Copy Korman python scripts as part of the INSTALL target" ON)
option(korman_INSTALL_PACKAGE "Buid Korman CPack installers" ON)

# While, yes, we could tie our build process into Blender's, Blender pulls in
# tons of dependencies and can be quite slow if you start trying to build
# errthang from source. So, we'll jst let you handle that. Good luck!
if(NOT "${Blender_PYTHON_VERSION}" OR korman_INSTALL_BLENDER)
    set(_Blender_REQUIRED "REQUIRED")
elseif("${Blender_PYTHON_VERSION}" AND NOT "${Blender_PYTHON_VERSION}" MATCHES "^[0-9]+\\.[0-9]+$")
    message(FATAL_ERROR "Your manually defined Blender python version ($CACHE{Blender_PYTHON_VERSION}) doesn't pass muster.")
endif()
find_package(Blender 2.79 EXACT ${_Blender_REQUIRED})
if(NOT Blender_FOUND)
    set(Blender_VERSION "2.79")
endif()

# Gotta do this because libHSPlasma is still using the old broke-ass pre-3.12 find modules.
set(Python3_FIND_STRATEGY VERSION)
find_package(Python3 ${Blender_PYTHON_VERSION} EXACT COMPONENTS Development Interpreter REQUIRED)

include(Dependencies)
if(korman_INSTALL_PACKAGE)
    include(Packaging)
endif()

if(korman_INSTALL_SCRIPTS)
    set(korman_INSTALL_SCRIPTS_PATH "${Blender_VERSION}/scripts/addons" CACHE STRING "")
    install(DIRECTORY
        "${CMAKE_SOURCE_DIR}/korman"
        DESTINATION "${korman_INSTALL_SCRIPTS_PATH}"
        COMPONENT "Korman"
        FILES_MATCHING
            PATTERN "*.py"
    )
endif()

# When we update to CMake 3.21, it might be worth separating the dependency build
# and Korman build a little more and using install(TARGETS RUNTIME_DEPENDENCIES). For now,
# this causes no observable problems and gives a good result, so meh.
set(korman_INSTALL_BINARY_DIR "${Blender_VERSION}/python/lib/site-packages" CACHE STRING "")
install(DIRECTORY
    "${korman_HARVEST_DIR}/bin/"
    DESTINATION "${korman_INSTALL_BINARY_DIR}"
    COMPONENT "Korman"
    FILES_MATCHING
        PATTERN "*.dll"
        PATTERN "*.pyd"
        PATTERN "*.so"
)

if(korman_INSTALL_BLENDER)
    get_filename_component(_Blender_PATH "${Blender_EXECUTABLE}" DIRECTORY)
    install(DIRECTORY
        "${_Blender_PATH}/"
        DESTINATION "."
        COMPONENT "Blender"
    )
endif()

if(korman_HARVEST_PYTHON22)
    install(PROGRAMS
        "${korman_HARVEST_DIR}/bin/Python-2.2.3.exe"
        DESTINATION "."
        COMPONENT "Python22"
    )
endif()
