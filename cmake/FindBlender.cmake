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

# The parens in this env variable give CMake heartburn, so we whisper sweet nothings.
set(_PROGRAMFILES_X86 "PROGRAMFILES(X86)")
set(_PROGRAMFILES_X86 "$ENV{${_PROGRAMFILES_X86}}")

find_program(Blender_EXECUTABLE
    NAMES blender
    PATHS
        "${Blender_ROOT}"
        "$ENV{PROGRAMFILES}/Blender Foundation/Blender"
        "${_PROGRAMFILES_X86}/Blender Foundation/Blender"
)

# Hacky? On Windows, we want to make sure that the Blender EXE matches sizeof void*
# Yes, this has bitten me. If it bites you, the result will be "Import Error: PyHSPlasma is not a
# valid Win32 application." That's hardly useful...
if(WIN32 AND EXISTS "${Blender_EXECUTABLE}")
    find_package(dumpbin)
    if(dumpbin_FOUND)
        execute_process(
            COMMAND "${dumpbin_EXECUTABLE}" /headers "${Blender_EXECUTABLE}"
            RESULTS_VARIABLE _RETURNCODE
            OUTPUT_VARIABLE _dumpbin_output
            ERROR_VARIABLE _dumpbin_error
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_STRIP_TRAILING_WHITESPACE
        )
        if(_RETURNCODE EQUAL 0)
            if(CMAKE_SIZEOF_VOID_P EQUAL 8)
                set(_expected_arch "machine \\(x64\\)")
            else()
                set(_expected_arch "machine \\(x86\\)")
            endif()
            if(NOT "${_dumpbin_output}" MATCHES "${_expected_arch}")
                unset(Blender_EXECUTABLE CACHE)
            endif()
        else()
            message(WARNING "dumpbin failed ${_dumpbin_error}")
        endif()
    else()
        message(WARNING "dumpbin not found, not verifying blender executable")
    endif()
endif()

if(EXISTS "${Blender_EXECUTABLE}")
    # Starting Blender is noisy on stdout, so all the extra characters will make sure things go right.
    # https://youtu.be/SlQFIsQ0dbs?t=19
    set(_Blender_PYTHON_EXPR
        "import sys; print('!!! OOGABOOGA {}.{} AGOOBAGOO !!!'.format(sys.version_info[0], sys.version_info[1]))"
    )
    execute_process(
        COMMAND "${Blender_EXECUTABLE}" -b --python-expr "${_Blender_PYTHON_EXPR}"
        RESULTS_VARIABLE _RETURNCODE
        OUTPUT_VARIABLE _Blender_VERSION_OUTPUT
        ERROR_VARIABLE _Blender_VERSION_OUTPUT
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_STRIP_TRAILING_WHITESPACE
    )
    string(REGEX MATCH [[Blender ([0-9]+\.[0-9]+)]] _match "${_Blender_VERSION_OUTPUT}")
    set(Blender_VERSION "${CMAKE_MATCH_1}")
    string(REGEX MATCH [[!!! OOGABOOGA ([0-9]+\.[0-9]+) AGOOBAGOO !!!]] _match "${_Blender_VERSION_OUTPUT}")
    set(Blender_PYTHON_VERSION "${CMAKE_MATCH_1}")
endif()

mark_as_advanced(Blender_EXECUTABLE)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(Blender
    REQUIRED_VARS Blender_EXECUTABLE Blender_VERSION Blender_PYTHON_VERSION
    VERSION_VAR Blender_VERSION
)
