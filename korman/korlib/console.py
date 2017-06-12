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

import bpy
import ctypes
import math
import sys

class ConsoleToggler:
    _instance = None

    def __init__(self, want_console=None):
        if want_console is not None:
            self._console_wanted = want_console

    def __new__(cls, want_console=None):
        if cls._instance is None:
            assert want_console is not None
            cls._instance = object.__new__(cls)
            cls._instance._console_was_visible = cls.is_console_visible()
            cls._instance._console_wanted = want_console
            cls._instance._context_active = False
            cls._instance.keep_console = False
        return cls._instance

    def __enter__(self):
        if self._context_active:
            raise RuntimeError("ConsoleToggler context manager is not reentrant")
        self._console_visible = self.is_console_visible()
        self._context_active = True
        self.activate_console()
        return self

    def __exit__(self, type, value, traceback):
        if not self._console_was_visible and self._console_wanted:
            if self.keep_console:
                # Blender thinks the console is currently not visible. However, it actually is.
                # So, we will fire off the toggle operator to keep Blender's internal state valid
                bpy.ops.wm.console_toggle()
            else:
                self.hide_console()
        self._context_active = False
        self.keep_console = False
        return False

    def activate_console(self):
        if sys.platform == "win32":
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if self._console_wanted:
                ctypes.windll.user32.ShowWindow(hwnd, 1)
            if self._console_was_visible or self._console_wanted:
                ctypes.windll.user32.BringWindowToTop(hwnd)

    @staticmethod
    def hide_console():
        if sys.platform == "win32":
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            ctypes.windll.user32.ShowWindow(hwnd, 0)

    @staticmethod
    def is_console_visible():
        if sys.platform == "win32":
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            return bool(ctypes.windll.user32.IsWindowVisible(hwnd))

    @staticmethod
    def is_platform_supported():
        # If you read Blender's source code, GHOST_toggleConsole (the "Toggle System Console" menu
        # item) is only implemented on Windows. The majority of our audience is on Windows as well,
        # so I honestly don't see this as an issue...
        return sys.platform == "win32"
