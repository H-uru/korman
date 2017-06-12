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
import time

_HEADING_SIZE = 50

class ExportLogger:
    def __init__(self, age_path=None):
        self._porting = []
        self._warnings = []
        self._age_path = Path(age_path) if age_path is not None else None
        self._file = None

        self._progress_steps = []
        self._step_id = -1
        self._step_max = 0
        self._step_progress = 0
        self._time_start_overall = 0
        self._time_start_step = 0

    def __enter__(self):
        assert self._age_path is not None

        # Make the log file name from the age file path -- this ensures we're not trying to write
        # the log file to the same directory Blender.exe is in, which might be a permission error
        my_path = self._age_path.with_name("{}_export".format(self._age_path.stem)).with_suffix(".log")
        self._file = open(str(my_path), "w")
        return self

    def __exit__(self, type, value, traceback):
        self._file.close()
        return False

    def progress_add_step(self, name):
        assert self._step_id == -1
        self._progress_steps.append(name)

    def progress_advance(self):
        """Advances the progress bar to the next step"""
        if self._step_id != -1:
            self._progress_print_step(done=True)
        assert self._step_id < len(self._progress_steps)

        self._step_id += 1
        self._step_max = 0
        self._step_progress = 0
        self._time_start_step = time.perf_counter()
        self._progress_print_step()

    def progress_complete_step(self):
        """Manually completes the current step"""
        assert self._step_id != -1
        self._progress_print_step(done=True)

    def progress_end(self):
        self._progress_print_step(done=True)
        assert self._step_id+1 == len(self._progress_steps)

        export_time = time.perf_counter() - self._time_start_overall
        if self._age_path is not None:
            self.msg("\nExported '{}' in {:.2f}s", self._age_path.name, export_time)
            print("\nEXPORTED '{}' IN {:.2f}s".format(self._age_path.name, export_time))
        else:
            print("\nCOMPLETED IN {:.2f}s".format(export_time))
        self._progress_print_heading()
        print()

    def progress_increment(self):
        """Increments the progress of the current step"""
        assert self._step_id != -1
        self._step_progress += 1
        if self._step_max != 0:
            self._progress_print_step()

    def _progress_print_heading(self, text=None):
        if text:
            num_chars = len(text)
            border = "-" * int((_HEADING_SIZE - (num_chars + 2)) / 2)
            pad = " " if num_chars % 2 == 1 else ""
            print(border, " ", pad, text, " ", border, sep="")
        else:
            print("-" * _HEADING_SIZE)

    def _progress_print_step(self, done=False):
        if done:
            stage = "DONE IN {:.2f}s".format(time.perf_counter() - self._time_start_step)
            end = "\n"
        else:
            if self._step_max != 0:
                stage = "{} of {}".format(self._step_progress, self._step_max)
            else:
                stage = ""
            end = "\r"
        print("{}\t(step {}/{}): {}".format(self._progress_steps[self._step_id], self._step_id+1,
                                            len(self._progress_steps), stage),
              end=end)

    def _progress_get_max(self):
        return self._step_max
    def _progress_set_max(self, value):
        assert self._step_id != -1
        self._step_max = value
        self._progress_print_step()
    progress_range = property(_progress_get_max, _progress_set_max)

    def progress_start(self, action):
        if self._age_path is not None:
            self.msg("Exporting '{}'", self._age_path.name)
        self._progress_print_heading("Korman")
        self._progress_print_heading(action)
        self._time_start_overall = time.perf_counter()

    def _progress_get_current(self):
        return self._step_progress
    def _progress_set_current(self, value):
        assert self._step_id != -1
        self._step_progress = value
        if self._step_max != 0:
            self._progress_print_step()
    progress_value = property(_progress_get_current, _progress_set_current)

    def msg(self, *args, **kwargs):
        assert args
        if self._file is not None:
            indent = kwargs.get("indent", 0)
            msg = "{}{}".format("    " * indent, args[0])
            if len(args) > 1:
                msg = msg.format(*args[1:], **kwargs)
            self._file.writelines((msg, "\n"))

    def port(self, *args, **kwargs):
        assert args
        indent = kwargs.get("indent", 0)
        msg = "{}PORTING: {}".format("    " * indent, args[0])
        if len(args) > 1:
            msg = msg.format(*args[1:], **kwargs)
        if self._file is not None:
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
        if self._file is not None:
            self._file.writelines((msg, "\n"))
        self._warnings.append(args[0])
