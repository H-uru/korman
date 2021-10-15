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

from .ui_anim import *
from .ui_camera import *
from .ui_image import *
from .ui_lamp import *
from .ui_list import *
from .ui_menus import *
from .ui_modifiers import *
from .ui_object import *
from .ui_render_layer import *
from .ui_scene import *
from .ui_text import *
from .ui_texture import *
from .ui_toolbox import *
from .ui_world import *


def register():
    ui_menus.register()


def unregister():
    ui_menus.unregister()
