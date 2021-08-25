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

set(korman_EXTERNAL_STAGING_DIR "${PROJECT_BINARY_DIR}/external" CACHE PATH "External project staging directory")
mark_as_advanced(korman_EXTERNAL_STAGING_DIR)

set(korman_HARVEST_DIR "${PROJECT_BINARY_DIR}/harvest" CACHE PATH "")

cmake_dependent_option(
    korman_HARVEST_VCREDIST
    "Harvest the vcredist executable as part of Korman's build process"
    ON
    "MSVC"
    OFF
)

cmake_dependent_option(
    korman_HARVEST_PYTHON22
    "Harvest (read: download) the Python 2.2.3 installer as part of Korman's build process"
    ON
    "WIN32" # If we ever decide to allow NSIS installers, NSIS can run on non-Windows.
    OFF
)

# Since we are (ideally) building everything static, inline right here, we can use IPO on
# all of the static libraries for a uuuuge file size win. Most libs do not do the correct
# CMake magic to turn this on.
include(CheckIPOSupported)
check_ipo_supported(
    RESULT _IPO_SUPPORTED
    OUTPUT _IPO_OUTPUT
)
message(STATUS "Checking for IPO: ${_IPO_SUPPORTED} ${_IPO_OUTPUT}")
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION ${_IPO_SUPPORTED} CACHE BOOL "")

if(WIN32)
    set(_BUILD_SYSTEM_LIBS ON)
else()
    set(_BUILD_SYSTEM_LIBS OFF)
endif()

option(korman_BUILD_HSPLASMA "Build libHSPlasma as part of Korman's build process" ON)
option(korman_BUILD_JPEG "Build libpjeg-turbo as part of Korman's build process" ${_BUILD_SYSTEM_LIBS})
option(korman_BUILD_OGGVORBIS "Build libogg and libvorbis as part of Korman's build process" ${_BUILD_SYSTEM_LIBS})
option(korman_BUILD_PNG "Build libpng as part of Korman's build process" ${_BUILD_SYSTEM_LIBS})
option(korman_BUILD_ZLIB "Build zlib as part of Korman's build process" ${_BUILD_SYSTEM_LIBS})
option(korman_BUILD_STRING_THEORY "Build string_theory as part of Korman's build process" ON)
option(korman_BUILD_ALWAYS_UPDATE "Always run the update phase for external dependencies" OFF)

if(korman_BUILD_HSPLASMA)
    list(APPEND korlib_DEPENDS HSPlasma)
endif()
if(korman_BUILD_JPEG)
    list(APPEND HSPlasma_DEPENDS libjpeg-turbo)
endif()
if(korman_BUILD_OGGVORBIS)
    list(APPEND korlib_DEPENDS libvorbis)
    list(APPEND libvorbis_DEPENDS libogg)
endif()
if(korman_BUILD_STRING_THEORY)
    list(APPEND HSPlasma_DEPENDS string_theory)
endif()
if(korman_BUILD_PNG)
    list(APPEND HSPlasma_DEPENDS libpng)
endif()
if(korman_BUILD_ZLIB)
    list(APPEND HSPlasma_DEPENDS zlib)
    list(APPEND libpng_DEPENDS zlib)
endif()

set(_ExternalProjectCMakeCache
    -DCMAKE_INSTALL_PREFIX:PATH=${korman_HARVEST_DIR}
    -DCMAKE_POLICY_DEFAULT_CMP0069:STRING=NEW
    -DCMAKE_INTERPROCEDURAL_OPTIMIZATION:BOOL=${CMAKE_INTERPROCEDURAL_OPTIMIZATION}
)

include(ExternalProject)
include(FetchContent)

function(korman_add_external_project TARGET)
    set(_args ${ARGN})

    if("GIT_REPOSITORY" IN_LIST _args)
        list(APPEND _args GIT_PROGRESS TRUE)
        if(NOT "GIT_SHALLOW" IN_LIST _args)
            list(APPEND _args GIT_SHALLOW TRUE)
        endif()
    endif()

    list(FIND _args "CMAKE_CACHE_ARGS" _cache_args_idx)
    if(_cache_args_idx EQUAL -1)
        list(APPEND _args CMAKE_CACHE_ARGS ${_ExternalProjectCMakeCache})
    else()
        math(EXPR _cache_insert_pos "${_cache_args_idx} + 1")
        list(INSERT _args ${_cache_insert_pos} ${_ExternalProjectCMakeCache})
    endif()

    set(_builddir "${korman_EXTERNAL_STAGING_DIR}/${TARGET}/src/build")
    if(CMAKE_GENERATOR_PLATFORM)
        string(APPEND _builddir "-${CMAKE_GENERATOR_PLATFORM}")
    endif()

    list(APPEND _args
        PREFIX "${korman_EXTERNAL_STAGING_DIR}"
        BINARY_DIR "${_builddir}"
        DEPENDS ${${TARGET}_DEPENDS}
    )

    ExternalProject_Add(${TARGET} ${_args})
endfunction()

if(korman_BUILD_JPEG)
    korman_add_external_project(libjpeg-turbo
        GIT_REPOSITORY "https://github.com/libjpeg-turbo/libjpeg-turbo.git"
        GIT_TAG 2.1.0
        CMAKE_CACHE_ARGS
            -DBUILD_SHARED_LIBS:BOOL=OFF
            -DENABLE_SHARED:BOOL=FALSE
            -DENABLE_STATIC:BOOL=TRUE
            -DWITH_CRT_DLL:BOOL=ON # WTF libjpeg-turbo, this is a smell.
            -DWITH_JAVA:BOOL=FALSE
            -DWITH_TURBOJPEG:BOOL=FALSE
    )
endif()

if(korman_BUILD_OGGVORBIS)
    korman_add_external_project(libogg
        GIT_REPOSITORY "https://github.com/xiph/ogg.git"
        GIT_TAG v1.3.5
        CMAKE_CACHE_ARGS
            -DBUILD_SHARED_LIBS:BOOL=OFF
            -DBUILD_TESTING:BOOL=OFF
            -DINSTALL_DOCS:BOOL=OFF
    )
    korman_add_external_project(libvorbis
        GIT_REPOSITORY "https://github.com/xiph/vorbis.git"
        GIT_TAG v1.3.7
        CMAKE_CACHE_ARGS
            -DBUILD_SHARED_LIBS:BOOL=OFF
    )
endif()

if(korman_BUILD_STRING_THEORY)
    # Woe betide us if comaptibility breaks...
    if(MSVC AND MSVC_VERSION LESS 1900)
        set(_string_theory_tag 2.4)
    else()
        set(_string_theory_tag 3.4)
    endif()

    korman_add_external_project(string_theory
        GIT_REPOSITORY "https://github.com/zrax/string_theory.git"
        GIT_TAG ${_string_theory_tag}
        CMAKE_CACHE_ARGS
            -DST_BUILD_TESTS:BOOL=OFF
            -DST_BUILD_STATIC:BOOL=ON # string_theory < 3.0
    )
endif()

if(korman_BUILD_ZLIB)
    # Using zlib-ng instead of zlib because the latter's CMakeLists is a pile of steaming garbage
    # in that it always produces a shared library if BUILD_SHARED_LIBS=OFF, and bad problems when
    # `if(UNIX)` -> TRUE. Grrr.
    if(MSVC AND MSVC_TOOLSET_VERSION LESS 140)
        list(APPEND _zlib_extra_args
            -DCMAKE_C_FLAGS:STRING=/Dinline=__inline # VS2013's C99 support is incomplete.
            -DWITH_AVX2:BOOL=OFF # Triggers downstream linker errors
            -DWITH_SSE2:BOOL=OFF # Broken
        )
    endif()
    korman_add_external_project(zlib
        GIT_REPOSITORY "https://github.com/zlib-ng/zlib-ng.git"
        GIT_TAG 2.0.5
        CMAKE_CACHE_ARGS
            -DBUILD_SHARED_LIBS:BOOL=OFF
            -DZLIB_COMPAT:BOOL=ON
            -DZLIB_ENABLE_TESTS:BOOL=OFF
            ${_zlib_extra_args}
    )
endif()

if(korman_BUILD_PNG)
    korman_add_external_project(libpng
        URL "https://sourceforge.net/projects/libpng/files/libpng16/1.6.37/libpng-1.6.37.tar.gz/download"
        DOWNLOAD_NAME "libpng-1.6.37.tar.gz"
        URL_HASH "SHA256=daeb2620d829575513e35fecc83f0d3791a620b9b93d800b763542ece9390fb4"
        CMAKE_CACHE_ARGS
            -DBUILD_SHARED_LIBS:BOOL=OFF
            -DPNG_EXECUTABLES:BOOL=OFF
            -DPNG_SHARED:BOOL=OFF
            -DPNG_TESTS:BOOL=OFF
    )
endif()

if(korman_BUILD_HSPLASMA)
    korman_add_external_project(HSPlasma
        GIT_REPOSITORY "https://github.com/H-uru/libhsplasma.git"
        # Be sure to increase this as the feature set used by Korman increases
        GIT_TAG d248e0111f21305b916f40289cdb993a6545e67a
        # We can only do shallow checkouts if the above is a branch or tag.
        GIT_SHALLOW FALSE
        CMAKE_CACHE_ARGS
            -DCMAKE_UNITY_BUILD:BOOL=ON
            -DENABLE_NET:BOOL=OFF
            -DENABLE_PHYSX:BOOL=OFF
            -DENABLE_PYTHON:BOOL=ON
            -DENABLE_TOOLS:BOOL=OFF
            -DPYTHON_INCLUDE_DIR:PATH=${Python3_INCLUDE_DIRS}
            -DPYTHON_LIBRARY:FILEPATH=${Python3_LIBRARIES}
    )
endif()

korman_add_external_project(korlib
    SOURCE_DIR "${PROJECT_SOURCE_DIR}/korlib"
    CMAKE_CACHE_ARGS
        -Dkorlib_PYTHON_VERSION:STRING=${Blender_PYTHON_VERSION}
        -DPython3_ROOT:PATH=${Python3_ROOT} # Passthru helper
)

if(korman_HARVEST_VCREDIST)
    find_package(VCRedist COMPONENTS Executable REQUIRED)
    set(_vcredist_destination "${korman_HARVEST_DIR}/bin/${VCRedist_NAME}")
    add_custom_target(VCRedist
        ALL
        COMMAND "${CMAKE_COMMAND}" -E make_directory "${korman_HARVEST_DIR}"
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different "${VCRedist_EXECUTABLE}" "${_vcredist_destination}"
        BYPRODUCTS "${_vcredist_destination}"
    )
    install(
        PROGRAMS
        "${_vcredist_destination}"
        DESTINATION "."
    )
endif()

FetchContent_Declare(Python22
    URL "https://www.python.org/ftp/python/2.2.3/Python-2.2.3.exe"
    URL_HASH MD5=d76e774a4169794ae0d7a8598478e69e
    DOWNLOAD_DIR "${korman_HARVEST_DIR}/bin"
    DOWNLOAD_NAME "Python-2.2.3.exe"
    DOWNLOAD_NO_EXTRACT TRUE # Why is this not a flag? Yes, that bit me.
)
if(korman_HARVEST_PYTHON22 AND NOT Python22_POPULATED)
    FetchContent_Populate(Python22)
endif()
