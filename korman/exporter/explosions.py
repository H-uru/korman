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

class NonfatalExportError(Exception):
    def __init__(self, *args, **kwargs):
        assert args
        if len(args) > 1:
            super().__init__(args[0].format(*args[1:], **kwargs))
        else:
            super().__init__(args[0])


class ExportError(Exception):
    def __init__(self, *args, **kwargs):
        if not args:
            super().__init__("Undefined Export Error")
        elif len(args) > 1:
            super().__init__(args[0].format(*args[1:], **kwargs))
        else:
            super().__init__(args[0])


class BlendNotSupported(ExportError):
    def __init__(self, progression, axis):
        super().__init__(f"Alpha Blend not supported: {progression}, {axis}")


class BlenderOptionNotSupportedError(ExportError):
    def __init__(self, opt):
        super().__init__(f"Unsupported Blender Option: '{opt}'")


class ExportAssertionError(ExportError):
    def __init__(self):
        super().__init__("Assertion failed")


class PlasmaLaunchError(ExportError):
    def __init__(self, *args, **kwargs):
        if not args:
            super().__init__("Failed to start Plasma")
        else:
            super().__init__(*args, **kwargs)


class TooManyUVChannelsError(ExportError):
    def __init__(self, obj, mat, numUVTexs, maxUVTexCount=8):
        super().__init__(
            f"There are too many UV Textures on the material '{mat.name}' "
            f"associated with object '{obj.name}'. You can have at most {maxUVTexCount} "
            f"(there are {numUVTexs})"
        )


class TooManyVerticesError(ExportError):
    def __init__(self, mesh, matname, vertcount):
        super().__init__(
            f"There are too many vertices ({vertcount}) on the mesh data "
            f"'{mesh}' associated with material '{matname}'"
        )


class UnsupportedTextureError(ExportError):
    def __init__(self, texture, material):
        super().__init__(
            f"Cannot export texture '{texture.name}' on material "
            f"'{material.name}' -- unsupported type '{texture.type}'"
        )
