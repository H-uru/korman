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

cmake_policy(PUSH)
cmake_policy(SET CMP0057 NEW) # if(IN_LIST)

function(_get_subdirectories RESULT DIRECTORY)
    file(GLOB children INCLUDE_DIRECTORIES RELATIVE "${DIRECTORY}" "${DIRECTORY}/*")
    foreach(child IN LISTS children)
        if(IS_DIRECTORY "${DIRECTORY}/${child}")
            list(APPEND subdirectories "${child}")
        endif()
    endforeach()
    set(${RESULT} ${subdirectories} PARENT_SCOPE)
endfunction()

# Is this even legal?
if(NOT VCRedist_FIND_COMPONENTS)
    set(VCRedist_FIND_COMPONENTS Executable MergeModules)
endif()

if(MSVC)
    # The parens in this env variable give CMake heartburn, so we whisper sweet nothings.
    set(_PROGRAMFILES_X86 "PROGRAMFILES(X86)")
    set(_PROGRAMFILES_X86 "$ENV{${_PROGRAMFILES_X86}}")

    # TODO: support non visual studio generators
    set(_vs_install_root "${CMAKE_VS_DEVENV_COMMAND}/../../../")
    get_filename_component(_vs_install_root "${_vs_install_root}" ABSOLUTE)

    # Valid paths:
    # 2013, 2015: VC/redist/1033/<exe>
    # 2017, 2019: VC/redist/MSVC/<MSVC VERSION>/<exe>
    # 2019: VC/redist/MSVC/<toolset version>/<exe>
    set(_redist_dir "${_vs_install_root}/VC/redist")
    _get_subdirectories(_msvc_subdirs "${_redist_dir}/MSVC")
    foreach(_subdir IN LISTS _msvc_subdirs)
        list(APPEND _redist_paths "${_redist_dir}/MSVC/${_subdir}")
    endforeach()

    # These are known, valid locations, so we prefer them first.
    list(INSERT _redist_paths 0 "${_redist_dir}/1033" "${_redist_dir}/MSVC/v${MSVC_TOOLSET_VERSION}")
    list(REMOVE_DUPLICATES _redist_paths)

    if(CMAKE_SIZEOF_VOID_P EQUAL 8)
        set(_redist_arch x64)
    else()
        set(_redist_arch x86)
    endif()

    if("Executable" IN_LIST VCRedist_FIND_COMPONENTS)
        list(APPEND _required_vars "VCRedist_EXECUTABLE")

        find_program(VCRedist_EXECUTABLE
            NAMES "vcredist_${_redist_arch}" "vc_redist.${_redist_arch}"
            PATHS ${_redist_paths}
        )

        mark_as_advanced(VCRedist_EXECUTABLE)
        set(VCRedist_NAME "vcredist_${_redist_arch}.exe")
        if(EXISTS "${VCRedist_EXECUTABLE}")
            set(VCRedist_Executable_FOUND TRUE)
        endif()
    endif()

    # Valid Paths:
    # Visual Studio <= 2015: <Program Files (x86)>/Common Files/Merge Modules/
    # Visual Studio >= 2017: <Visual Studio root>/VC/<MSVC or toolset version>/MergeModules/
    if("MergeModules" IN_LIST VCRedist_FIND_COMPONENTS)
        list(APPEND _merge_module_paths "${_PROGRAMFILES_X86}/Common Files" ${_redist_paths})
        set(_merge_module_suffixes "Merge Modules" "MergeModules")

        # We'll flip it OFF if anything is missing
        set(VCRedist_MergeModules_FOUND TRUE)
        function(_find_merge_module MODULE_NAME)
            string(TOUPPER "${MODULE_NAME}" _module_name_upper)
            set(VARIABLE "VCRedist_${_module_name_upper}_MERGE_MODULE")
            find_file(${VARIABLE}
                NAMES  "Microsoft_VC${MSVC_TOOLSET_VERSION}_${MODULE_NAME}_${_redist_arch}.msm"
                PATHS ${_merge_module_paths}
                PATH_SUFFIXES ${_merge_module_suffixes}
            )
            mark_as_advanced(${VARIABLE})
            set(_required_vars ${_required_vars} ${VARIABLE} PARENT_SCOPE)
            if(EXISTS "${${VARIABLE}}")
                set(VCRedist_MERGE_MODULES ${VCRedist_MERGE_MODULES} "${${VARIABLE}}" PARENT_SCOPE)
            else()
                set(VCRedist_MergeModules_FOUND FALSE PARENT_SCOPE)
            endif()
        endfunction()

        _find_merge_module(CRT)
        _find_merge_module(MFC)
        _find_merge_module(MFCLOC)
        _find_merge_module(OpenMP)
        if(MSVC_TOOLSET_VERSION GREATER_EQUAL 110)
            _find_merge_module(CXXAMP)
        endif()
    endif()
endif()

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(VCRedist
    REQUIRED_VARS ${_required_vars} # Optional in CMake 3.18+, but we only require 3.12
    HANDLE_COMPONENTS
)

cmake_policy(POP)
