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

import os.path
import sys

class ExportAnalysis:
    """This is used to collect artist action items from the export process. You can warn about
       portability issues, possible oversights, etc. The benefit here is that the user doesn't have
       to look through all of the gobbledygook in the export log.
    """

    _porting = []
    _warnings = []

    def save(self):
        # TODO
        pass

    def port(self, message):
        self._porting.append(message)
        print("PORTING: {}".format(message))

    def warn(self, message):
        self._warnings.append(message)
        print("WARNING: {}".format(message))


class ExportLogger:
    """Yet Another Logger(TM)"""

    def __init__(self, ageFile):
        # Make the log file name from the age file path -- this ensures we're not trying to write
        # the log file to the same directory Blender.exe is in, which might be a permission error
        path, ageFile = os.path.split(ageFile)
        ageName, _crap = os.path.splitext(ageFile)
        fn = os.path.join(path, "{}_export.log".format(ageName))
        self._file = open(fn, "w")

        for i in dir(self._file):
            if not hasattr(self, i):
                setattr(self, i, getattr(self._file, i))

    def __enter__(self):
        self._stdout, sys.stdout = sys.stdout, self._file
        self._stderr, sys.stderr = sys.stderr, self._file

    def __exit__(self, type, value, traceback):
        sys.stdout = self._stdout
        sys.stderr = self._stderr

    def flush(self):
        self._file.flush()
        self._stdout.flush()
        self._stderr.flush()

    def write(self, str):
        self._file.write(str)
        self._stdout.write(str)

    def writelines(self, seq):
        self._file.writelines(seq)
        self._stdout.writelines(seq)
