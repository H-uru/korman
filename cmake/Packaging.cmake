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

set(CPACK_PACKAGE_NAME Korman)
set(CPACK_PACKAGE_VENDOR "Guild of Writers")
set(CPACK_PACKAGE_DIRECTORY "${PROJECT_BINARY_DIR}/package")
set(CPACK_PACKAGE_ICON "${PROJECT_SOURCE_DIR}/installer/Icon.ico")
set(CPACK_THREADS 0) # Allows multi-threaded LZMA compression in CMake 3.21+

find_package(Git)
if(Git_FOUND)
    execute_process(
        COMMAND ${GIT_EXECUTABLE} describe --tags --dirty
        WORKING_DIRECTORY "${PROJECT_SOURCE_DIR}"
        OUTPUT_VARIABLE _korman_rev
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    string(REGEX REPLACE "[\r\n]" " " _korman_rev "${_korman_rev}")
else()
    set(_korman_rev "untracked")
endif()

# Don't rely on the hardwired version number from project() since this may be some rando
# git checkout or CI run. Also, apparently CPACK_SYSTEM_NAME is faulty. Stupid CMake.
if(WIN32)
    if(CMAKE_SIZEOF_VOID_P EQUAL 8)
        set(_korman_system "windows64")
    else()
        set(_korman_system "windows32")
    endif()
else()
    set(_korman_system "${CMAKE_SYSTEM_NAME}")
endif()
set(CPACK_PACKAGE_FILE_NAME "korman-${_korman_rev}-${_korman_system}")

set(CPACK_PACKAGE_CHECKSUM SHA256)

# Generate license file based on the install settings
if(korman_INSTALL_BINARY_DIR OR korman_INSTALL_SCRIPTS)
    set(KORMAN_LICENSE "Korman is licensed under the GNU GPLv3.")
    file(READ "${PROJECT_SOURCE_DIR}/installer/GPLv3.txt" _license)
    string(APPEND LICENSE_TEXT "${_license}\n")
endif()
if(korman_INSTALL_BLENDER)
    set(BLENDER_LICENSE "Blender is licensed under the GNU GPLv2.")
    file(READ "${PROJECT_SOURCE_DIR}/installer/GPLv2.txt" _license)
    string(APPEND LICENSE_TEXT "${_license}\n")
endif()

configure_file(
    "${PROJECT_SOURCE_DIR}/installer/license.txt.in"
    "${PROJECT_BINARY_DIR}/license.txt"
    @ONLY
)
set(CPACK_RESOURCE_FILE_LICENSE "${PROJECT_BINARY_DIR}/license.txt")
install(FILES
    "${PROJECT_BINARY_DIR}/license.txt"
    DESTINATION "."
)

set(CPACK_COMPONENTS_ALL "Korman")
set(CPACK_COMPONENTS_GROUPING "ALL_COMPONENTS_IN_ONE")
set(CPACK_COMPONENT_KORMAN_HIDDEN TRUE)

if(korman_INSTALL_BLENDER)
    list(APPEND CPACK_PACKAGE_EXECUTABLES blender Blender)
    list(APPEND CPACK_COMPONENTS_ALL "Blender")
    set(CPACK_COMPONENT_BLENDER_HIDDEN TRUE)
endif()

if(korman_HARVEST_PYTHON22)
    list(APPEND CPACK_COMPONENTS_ALL "Python22")
    set(CPACK_COMPONENT_PYTHON22_HIDDEN TRUE)
endif()

if(WIN32)
    # We're not actually going to ship this variant, but better prepared than sorry.
    if(korman_HARVEST_VCREDIST)
        set(CPACK_NSIS_EXTRA_INSTALL_COMMANDS
            "ExecWait \\\"$INSTDIR\\\\${VCRedist_NAME} /q /norestart\\\""
        )
    endif()

    set(CPACK_WIX_UPGRADE_GUID 84ef4b1d-27b6-54de-a73b-8fb1beb007ac) # KormanUpgrade
    # I think this should be randomized by CPack and not hardcoded?
    #set(CPACK_WIX_PRODUCT_GUID 74e91f5d-6d09-5d7f-a48f-3d0b011ef2df) # KormanProduct

    find_package(VCRedist COMPONENTS MergeModules REQUIRED)
    configure_file(
        "${PROJECT_SOURCE_DIR}/installer/WiX.template.in"
        "${PROJECT_BINARY_DIR}/WiX.template"
        @ONLY
    )
    set(CPACK_WIX_TEMPLATE "${PROJECT_BINARY_DIR}/WiX.template")

    set(CPACK_WIX_UI_BANNER "${PROJECT_SOURCE_DIR}/installer/WIX_UI_BANNER.bmp")
    set(CPACK_WIX_UI_DIALOG "${PROJECT_SOURCE_DIR}/installer/WIX_UI_DIALOG.bmp")

    set(CPACK_WIX_ROOT_FEATURE_TITLE "Blender for Korman")

    # Great release compression. Change it to "none" to iterate faster.
    set(CPACK_WIX_LIGHT_EXTRA_FLAGS -dcl:high)
endif()

set(CPACK_ARCHIVE_THREADS 0)

# Apparently this has to come last. Shaweet.
include(CPack)
