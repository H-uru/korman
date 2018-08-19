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

    def create_bump_LUT(mipmap):
        kLUTHeight = 16
        kLUTWidth = 16

        buf = bytearray(kLUTHeight * kLUTWidth * 4)

        denom = kLUTWidth - 1
        delH = (kLUTHeight - 1) // 5
        startH = delH // 2 + 1
        doneH = 0

        doneH = startH * kLUTWidth * 4
        buf[0:doneH] = [b for x in range(kLUTWidth) for b in (0, 0, int((x / denom) * 255.9), 255)] * startH

        startH = doneH
        doneH += delH * kLUTWidth * 4
        buf[startH:doneH] = [b for x in range(kLUTWidth) for b in (127, 127, int((x / denom) * 255.9), 255)] * delH

        startH = doneH
        doneH += delH * kLUTWidth * 4
        buf[startH:doneH] = [b for x in range(kLUTWidth) for b in (0, int((x / denom) * 255.9), 0, 255)] * delH

        startH = doneH
        doneH += delH * kLUTWidth * 4
        buf[startH:doneH] = [b for x in range(kLUTWidth) for b in (127, int((x / denom) * 255.9), 127, 255)] * delH

        startH = doneH
        doneH += delH * kLUTWidth * 4
        buf[startH:doneH] = [b for x in range(kLUTWidth) for b in (int((x / denom) * 255.9), 0, 0, 255)] * delH

        startH = doneH
        doneH += delH * kLUTWidth * 4
        buf[startH:doneH] = [b for x in range(kLUTWidth) for b in (int((x / denom) * 255.9), 127, 127, 255)] * startH

        mipmap.setRawImage(bytes(buf))

    def inspect_voribsfile(stream, header):
        raise NotImplementedError("Ogg Vorbis not supported unless _korlib is compiled")

    def is_c_library():
        return False
else:
    def is_c_library():
        return True
finally:
    from .console import ConsoleToggler
    from .texture import TEX_DETAIL_ALPHA, TEX_DETAIL_ADD, TEX_DETAIL_MULTIPLY

    def _wave_chunks(stream):
        while not stream.eof():
            chunk_name = stream.read(4)
            chunk_size = stream.readInt()
            chunk_offset = stream.pos
            stream.skip(chunk_size)
            yield {"name": chunk_name, "offset": chunk_offset, "size": chunk_size}

    def inspect_wavefile(stream, header):
        assert stream.read(4) == b"RIFF"
        stream.readInt()
        assert stream.read(4) == b"WAVE"

        # Read through the chunks until we find "fmt" and "data"
        chunks = {}
        for chunk in _wave_chunks(stream):
            if chunk["name"] in {b"fmt ", b"data"}:
                chunks[chunk["name"]] = chunk
        assert chunks[b"fmt "]
        assert chunks[b"data"]

        stream.seek(chunks[b"fmt "]["offset"])
        header.read(stream)

        return chunks[b"data"]["size"]
