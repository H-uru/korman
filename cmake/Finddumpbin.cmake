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


get_filename_component(_linker_dir "${CMAKE_LINKER}" DIRECTORY)

# In Visual Studio 2013, the dumpbin.exe in the linker directory is missing an important DLL.
# But, it's present in the parent directory, so prefer that one.
get_filename_component(_msvc_bin_dir "${_linker_dir}/../" ABSOLUTE)

find_program(dumpbin_EXECUTABLE
    NAMES dumpbin
    PATHS "${_msvc_bin_dir}" "${_linker_dir}"
)

mark_as_advanced(dumpbin_EXECUTABLE)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(dumpbin REQUIRED_VARS dumpbin_EXECUTABLE)
