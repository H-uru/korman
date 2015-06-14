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

import hashlib
import os.path
from PyHSPlasma import *

def _hashfile(filename, hasher, block=0xFFFF):
    with open(filename, "rb") as handle:
        h = hasher()
        data = handle.read(block)
        while data:
            h.update(data)
            data = handle.read(block)
        return h.digest()

class SumFile:
    def __init__(self):
        self._files = set()

    def append(self, filename):
        self._files.add(filename)

    def _collect_files(self, version):
        files = []
        for file in self._files:
            filename = os.path.split(file)[1]
            extension = os.path.splitext(filename)[1].lower()
            if extension in {".age", ".csv", ".fni", ".loc", ".node", ".p2f", ".pfp", ".sub"}:
                filename = os.path.join("dat", filename)
            elif extension == ".prp" and version > pvPrime:
                # ABM and UU don't want the directory for PRPs... Bug?
                filename = os.path.join("dat", filename)
            elif extension in {".pak", ".py"}:
                filename = os.path.join("Python", filename)
            elif extension in {".avi", ".bik", ".oggv", ".webm"}:
                filename = os.path.join("avi", filename)
            elif extension in {".ogg", ".opus", ".wav"}:
                filename = os.path.join("sfx", filename)
            elif extension == ".sdl":
                filename = os.path.join("SDL", filename)
            # else the filename has no directory prefix... oh well

            md5 = _hashfile(file, hashlib.md5)
            timestamp = os.path.getmtime(file)
            files.append((filename, md5, int(timestamp)))
        return files


    def write(self, sumpath, version):
        """Writes a .sum file for Uru ABM, PotS, Myst 5, etc."""
        files = self._collect_files(version)
        enc = plEncryptedStream.kEncAes if version >= pvEoa else plEncryptedStream.kEncXtea

        with plEncryptedStream(version).open(sumpath, fmWrite, enc) as stream:
            stream.writeInt(len(files))
            stream.writeInt(0)
            for file in files:
                stream.writeSafeStr(file[0])
                stream.write(file[1])
                stream.writeInt(file[2])
                stream.writeInt(0)
