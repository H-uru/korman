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
from bpy.props import *
from bpy.app.handlers import persistent
from PyHSPlasma import *

from .base import PlasmaModifierProperties
from ...exporter import ExportError

class PlasmaSound(bpy.types.PropertyGroup):
    enabled = BoolProperty(name="Enabled", default=True, options=set())
    sound_data = StringProperty(name="Sound", description="Sound Datablock", options=set())


class PlasmaSoundEmitter(PlasmaModifierProperties):
    pl_id = "soundemit"

    bl_category = "Logic"
    bl_label = "Sound Emitter"
    bl_description = "Point at which sound(s) are played"
    bl_icon = "SPEAKER"

    sounds = CollectionProperty(type=PlasmaSound)
    active_sound_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        pass

    @classmethod
    def register(cls):
        bpy.types.Sound.plasma_owned = BoolProperty(default=False, options={"HIDDEN"})

    @property
    def requires_actor(self):
        return True


@persistent
def _toss_orphaned_sounds(scene):
    used_sounds = set()
    for i in bpy.data.objects:
        soundemit = i.plasma_modifiers.soundemit
        used_sounds.update((j.sound_data for j in soundemit.sounds))
    for i in bpy.data.sounds:
        if i.plasma_owned and i.name not in used_sounds:
            i.use_fake_user = False
            i.user_clear()

# collects orphaned Plasma owned sound datablocks
bpy.app.handlers.save_pre.append(_toss_orphaned_sounds)
