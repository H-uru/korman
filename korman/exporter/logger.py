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

from pathlib import Path
import sys

class ExportLogger:
    def __init__(self, age_path=None):
        self._porting = []
        self._warnings = []
        self._age_path = age_path
        self._file = None

    def __enter__(self):
        assert self._age_path is not None

        # Make the log file name from the age file path -- this ensures we're not trying to write
        # the log file to the same directory Blender.exe is in, which might be a permission error
        my_path = Path(self._age_path)
        my_path = my_path.with_name("{}_export".format(my_path.stem)).with_suffix(".log")
        self._file = open(str(my_path), "w")
        return self

    def __exit__(self, type, value, traceback):
        self._file.close()
        return False

    def msg(self, *args, **kwargs):
        assert args
        indent = kwargs.get("indent", 0)
        msg = "{}{}".format("    " * indent, args[0])
        if len(args) > 1:
            msg = msg.format(*args[1:], **kwargs)
        if self._file is None:
            print(msg)
        else:
            self._file.writelines((msg, "\n"))

    def port(self, *args, **kwargs):
        assert args
        indent = kwargs.get("indent", 0)
        msg = "{}PORTING: {}".format("    " * indent, args[0])
        if len(args) > 1:
            msg = msg.format(*args[1:], **kwargs)
        if self._file is None:
            print(msg)
        else:
            self._file.writelines((msg, "\n"))
        self._porting.append(args[0])

    def save(self):
        # TODO
        pass

    def warn(self, *args, **kwargs):
        assert args
        indent = kwargs.get("indent", 0)
        msg = "{}WARNING: {}".format("    " * indent, args[0])
        if len(args) > 1:
            msg = msg.format(*args[1:], **kwargs)
        if self._file is None:
            print(msg)
        else:
            self._file.writelines((msg, "\n"))
        self._warnings.append(args[0])
