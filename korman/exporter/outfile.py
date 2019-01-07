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

from contextlib import contextmanager
import enum
from hashlib import md5
import locale
import os
from pathlib import Path
from PyHSPlasma import *
import shutil
import time
import weakref
import zipfile

_encoding = locale.getpreferredencoding(False)

def _hashfile(filename, hasher, block=0xFFFF):
    with open(str(filename), "rb") as handle:
        h = hasher()
        data = handle.read(block)
        while data:
            h.update(data)
            data = handle.read(block)
        return h.digest()

@enum.unique
class _FileType(enum.Enum):
    generated_dat = 0
    sfx = 1


class _OutputFile:
    def __init__(self, **kwargs):
        self.file_type = kwargs.get("file_type")
        self.dirname = kwargs.get("dirname")
        self.filename = kwargs.get("filename")
        self.skip_hash = kwargs.get("skip_hash", False)

        if self.file_type == _FileType.generated_dat:
            self.file_data = kwargs.get("file_data", None)
            self.file_path = kwargs.get("file_path", None)
            self.mod_time = Path(self.file_path).stat().st_mtime if self.file_path else None

            # need either a data buffer OR a file path
            assert bool(self.file_data) ^ bool(self.file_path)

        if self.file_type == _FileType.sfx:
            self.id_data = kwargs.get("id_data")
            path = Path(self.id_data.filepath).resolve()
            if path.exists():
                self.file_path = str(path)
                self.mod_time = path.stat().st_mtime
            else:
                self.file_path = None
                self.mod_time = None
            if self.id_data.packed_file is not None:
                self.file_data = self.id_data.packed_file.data

    def __eq__(self, rhs):
        return str(self) == str(rhs)

    def __hash__(self):
        return hash(str(self))

    def hash_md5(self):
        if self.file_path is not None:
            with open(self.file_path, "rb") as handle:
                h = md5()
                data = handle.read(0xFFFF)
                while data:
                    h.update(data)
                    data = handle.read(0xFFFF)
                return h.digest()
        elif self.file_data is not None:
            if isinstance(self.file_data, str):
                return md5(self.file_data.encode(_encoding)).digest()
            else:
                return md5(self.file_data).digest()
        else:
            raise RuntimeError()

    def __str__(self):
        return "{}/{}".format(self.dirname, self.filename)


class OutputFiles:
    def __init__(self, exporter, path):
        self._exporter = weakref.ref(exporter)
        self._export_file = Path(path).resolve()
        if exporter.dat_only:
            self._export_path = self._export_file.parent
        else:
            self._export_path = self._export_file.parent.parent
        self._files = set()
        self._is_zip = self._export_file.suffix.lower() == ".zip"
        self._time = time.time()

    def add_python(self, filename, text_id=None, str_data=None):
        of = _OutputFile(file_type=_FileType.python_code,
                         dirname="Python", filename=filename,
                         id_data=text_id, file_data=str_data,
                         skip_hash=True)
        self._files.add(of)

    def add_sdl(self, filename, text_id=None, str_data=None):
        version = self._version
        if version == pvEoa:
            enc = plEncryptedStream.kEncAes
        elif version == pvMoul:
            enc = None
        else:
            enc = plEncryptedStream.kEncXtea

        of = _OutputFile(file_type=_FileType.sdl,
                         dirname="SDL", filename=filename,
                         id_data=text_id, file_data=str_data,
                         enc=enc)
        self._files.add(of)


    def add_sfx(self, sound_id):
        of = _OutputFile(file_type=_FileType.sfx,
                         dirname="sfx", filename=sound_id.name,
                         id_data=sound_id)
        self._files.add(of)

    @contextmanager
    def generate_dat_file(self, filename, **kwargs):
        if self._is_zip:
            stream = hsRAMStream(self._version)
        else:
            file_path = str(self._export_file.parent / filename)
            stream = hsFileStream(self._version)
            stream.open(file_path, fmCreate)
        backing_stream = stream

        enc = kwargs.get("enc", None)
        if enc is not None:
            stream = plEncryptedStream(self._version)
            stream.open(backing_stream, fmCreate, enc)

        # The actual export code is run at the "yield" statement. If an error occurs, we
        # do not want to track this file. Note that the except block is required for the
        # else block to be legal. ^_^
        try:
            yield stream
        except:
            raise
        else:
            # Must call the EncryptedStream close to actually encrypt the data
            stream.close()
            if not stream is backing_stream:
                backing_stream.close()

            kwargs = {
                "file_type": _FileType.generated_dat,
                "dirname": "dat",
                "filename": filename,
                "skip_hash": skip_hash,
            }
            if isinstance(backing_stream, hsRAMStream):
                kwargs["file_data"] = backing_stream.buffer
            else:
                kwargs["file_path"] = file_path
            self._files.add(_OutputFile(**kwargs))

    def _generate_files(self, func=None):
        dat_only = self._exporter().dat_only
        for i in self._files:
            if dat_only and i.dirname != "dat":
                continue
            if func is not None:
                if func(i):
                    yield i
            else:
                yield i

    def save(self):
        # At this stage, all Plasma data has been generated from whatever crap is in
        # Blender. The only remaining part is to make sure any external dependencies are
        # copied or packed into the appropriate format OR the asset hashes are generated.

        # Step 1: Handle Python
        # ... todo ...

        # Step 2: Generate sumfile
        if self._version != pvMoul:
            self._write_sumfile()

        # Step 3: Ensure errbody is gut
        if self._is_zip:
            self._write_zipfile()
        else:
            self._write_deps()

    def _write_deps(self):
        func = lambda x: x.file_type == _FileType.sfx
        times = (self._time, self._time)

        for i in self._generate_files(func):
            # Will only ever run for non-"dat" directories.
            dst_path = str(self._export_path / i.dirname / i.filename)
            if i.file_path:
                shutil.copy2(i.file_path, dst_path)
            elif i.file_data:
                mode = "w" if isinstance(i.file_data, str) else "wb"
                with open(dst_path, mode) as handle:
                    handle.write(i.file_data)
                os.utime(dst_path, times)
            else:
                raise RuntimeError()

    def _write_sumfile(self):
        version = self._version
        dat_only = self._exporter().dat_only
        enc = plEncryptedStream.kEncAes if version >= pvEoa else plEncryptedStream.kEncXtea
        filename = "{}.sum".format(self._exporter().age_name)
        if dat_only:
            func = lambda x: not x.skip_hash and x.dirname == "dat"
        else:
            func = lambda x: not x.skip_hash

        with self.generate_dat_file(filename, enc=enc, skip_hash=True) as stream:
            files = list(self._generate_files(func))
            stream.writeInt(len(files))
            stream.writeInt(0)
            for i in files:
                # ABM and UU don't want the directory for PRPs... Bug?
                extension = Path(i.filename).suffix.lower()
                if extension == ".prp" and version < pvPots:
                    filename = i.filename
                else:
                    filename = "{}\\{}".format(i.dirname, i.filename)
                mod_time = i.mod_time if i.mod_time else self._time
                hash_md5 = i.hash_md5()

                stream.writeSafeStr(filename)
                stream.write(hash_md5)
                stream.writeInt(int(mod_time))
                stream.writeInt(0)

    def _write_zipfile(self):
        dat_only = self._exporter().dat_only
        export_time = time.localtime(self._time)[:6]
        if dat_only:
            func = lambda x: x.dirname == "dat"
        else:
            func = None

        with zipfile.ZipFile(str(self._export_file), 'w', zipfile.ZIP_DEFLATED) as zf:
            for i in self._generate_files(func):
                arcpath = i.filename if dat_only else "{}/{}".format(i.dirname, i.filename)
                if i.file_path:
                    zf.write(i.file_path, arcpath)
                elif i.file_data:
                    if isinstance(i.file_data, str):
                        data = i.file_data.encode(_encoding)
                    else:
                        data = i.file_data
                    zi = zipfile.ZipInfo(arcpath, export_time)
                    zf.writestr(zi, data)

    @property
    def _version(self):
        return self._exporter().mgr.getVer()
