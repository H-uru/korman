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

try:
    from _korlib import *
except ImportError:
    from .texture import *

    def inspect_voribsfile(stream, header):
        raise NotImplementedError("Ogg Vorbis not supported unless _korlib is compiled")

    def inspect_wavefile(stream, header):
        assert stream.read(4) == b"RIFF"
        stream.readInt()
        assert stream.read(4) == b"WAVE"
        assert stream.read(3) == b"fmt"
        header.read(stream)

        # read thru the chunks until we find "data"
        while stream.read(4) != b"data" and not stream.eof():
            stream.skip(stream.readInt())
        assert not stream.eof()
        size = stream.readInt()
        return (header, size)
