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

from __future__ import annotations

import bpy
from bpy.props import *
from bpy.app.handlers import persistent
from contextlib import contextmanager
import math
from PyHSPlasma import *
from typing import *

from ... import korlib
from .base import PlasmaModifierProperties
from .physics import surface_types
from ...exporter import ExportError
from ...helpers import duplicate_object, GoodNeighbor, TemporaryCollectionItem
from ... import idprops

_randomsound_modes = {
    "normal": plRandomSoundMod.kNormal,
    "norepeat": plRandomSoundMod.kNoRepeats,
    "coverall": plRandomSoundMod.kCoverall | plRandomSoundMod.kNoRepeats,
    "sequential": plRandomSoundMod.kSequential
}

class PlasmaRandomSound(PlasmaModifierProperties):
    pl_id = "random_sound"
    pl_depends = {"soundemit"}

    bl_category = "Logic"
    bl_label = "Random Sound"
    bl_description = ""

    mode = EnumProperty(name="Mode",
                        description="Playback Type",
                        items=[("random", "Random Time", "Plays a random sound from the emitter at a random time"),
                               ("collision", "Collision Surface", "Plays a random sound when the object's parent collides")],
                        default="random",
                        options=set())

    # Physical (read: collision) sounds
    play_on = EnumProperty(name="Play On",
                           description="Play sounds on this collision event",
                           items=[("slide", "Slide", "Plays a random sound on object slide"),
                                  ("impact", "Impact", "Plays a random sound on object slide")],
                           options=set())
    surfaces = EnumProperty(name="Play Against",
                            description="Sounds are played on collision against these surfaces",
                            items=surface_types[1:],
                            options={"ENUM_FLAG"})

    # Timed random sounds
    auto_start = BoolProperty(name="Auto Start",
                              description="Start playing when the Age loads",
                              default=True,
                              options=set())
    play_mode = EnumProperty(name="Play Mode",
                             description="",
                             items=[("normal", "Any", "Plays any attached sound"),
                                    ("norepeat", "No Repeats", "Do not replay a sound immediately after itself"),
                                    ("coverall", "Full Set", "Once a sound is played, do not replay it until after all sounds are played"),
                                    ("sequential", "Sequential", "Play sounds in the order they appear in the emitter")],
                             default="norepeat",
                             options=set())
    stop_after_set = BoolProperty(name="Stop After Set",
                                  description="Stop playing after all sounds are played",
                                  default=False,
                                  options=set())
    stop_after_play = BoolProperty(name="Stop After Play",
                                   description="Stop playing after one sound is played",
                                   default=False,
                                   options=set())
    min_delay = FloatProperty(name="Min Delay",
                              description="Minimum delay length",
                              min=0.0,
                              subtype="TIME", unit="TIME",
                              options=set())
    max_delay = FloatProperty(name="Max Delay",
                              description="Maximum delay length",
                              min=0.0,
                              subtype="TIME", unit="TIME",
                              options=set())

    def export(self, exporter, bo, so):
        rndmod = exporter.mgr.find_create_object(plRandomSoundMod, bl=bo, so=so)
        if self.mode == "random":
            if not self.auto_start:
                rndmod.state = plRandomSoundMod.kStopped
            if self.stop_after_play:
                rndmod.mode |= plRandomSoundMod.kOneCmd
            else:
                rndmod.minDelay = min(self.min_delay, self.max_delay)
                rndmod.maxDelay = max(self.min_delay, self.max_delay)
                # Delaying from the start makes ZERO sense. Screw that.
                rndmod.mode |= plRandomSoundMod.kDelayFromEnd
            rndmod.mode |= _randomsound_modes[self.play_mode]
            if self.stop_after_set:
                rndmod.mode |= plRandomSoundMod.kOneCycle
        elif self.mode == "collision":
            rndmod.mode = plRandomSoundMod.kNoRepeats | plRandomSoundMod.kOneCmd
            rndmod.state = plRandomSoundMod.kStopped
        else:
            raise RuntimeError()

    def post_export(self, exporter, bo, so):
        if self.mode == "collision" and self.surfaces:
            parent_bo = bo.parent
            if parent_bo is None:
                raise ExportError("[{}]: Collision sound objects MUST be parented directly to the collider object.", bo.name)
            phys = exporter.mgr.find_object(plGenericPhysical, bl=parent_bo)
            if phys is None:
                raise ExportError("[{}]: Collision sound objects MUST be parented directly to the collider object.", bo.name)

            # The soundGroup on the physical may or may not be the generic "this is my surface type"
            # soundGroup with no actual sounds attached. So, we need to lookup the actual one.
            sndgroup = exporter.mgr.find_create_object(plPhysicalSndGroup, bl=parent_bo)
            sndgroup.group = getattr(plPhysicalSndGroup, parent_bo.plasma_modifiers.collision.surface)
            phys.soundGroup = sndgroup.key

            rndmod = exporter.mgr.find_key(plRandomSoundMod, bl=bo, so=so)
            if self.play_on == "slide":
                groupattr = "slideSounds"
            elif self.play_on == "impact":
                groupattr = "impactSounds"
            else:
                raise RuntimeError()

            sounds = { i: sound for i, sound in enumerate(getattr(sndgroup, groupattr)) }
            for surface_name in self.surfaces:
                surface_id = getattr(plPhysicalSndGroup, surface_name)
                if surface_id in sounds:
                    exporter.report.warn("Overwriting physical {} surface '{}' ID:{}",
                                         groupattr, surface_name, surface_id)
                else:
                    exporter.report.msg("Got physical {} surface '{}' ID:{}",
                                        groupattr, surface_name, surface_id)
                sounds[surface_id] = rndmod
            # Keeps the LUT (or should that be lookup vector?) as small as possible
            setattr(sndgroup, groupattr, [sounds.get(i) for i in range(max(sounds.keys()) + 1)])


class PlasmaSfxFade(bpy.types.PropertyGroup):
    fade_type = EnumProperty(name="Type",
                             description="Fade Type",
                             items=[("NONE", "[Disable]", "Don't fade"),
                                    ("kLinear", "Linear", "Linear fade"),
                                    ("kLogarithmic", "Logarithmic", "Log fade"),
                                    ("kExponential", "Exponential", "Exponential fade")],
                             options=set())
    length = FloatProperty(name="Length",
                           description="Seconds to spend fading",
                           default=1.0, min=0.0,
                           options=set(), subtype="TIME", unit="TIME")


class PlasmaSound(idprops.IDPropMixin, bpy.types.PropertyGroup):
    @contextmanager
    def _lock_sound(self):
        exclusive = not self.updating_sound
        self.updating_sound = True
        try:
            yield exclusive
        finally:
            if exclusive:
                self.updating_sound = False

    def _update_sound(self, value):
        with self._lock_sound() as exclusive:
            if exclusive:
                if not value:
                    self.name = "[Empty]"
                    return

                try:
                    header, size = self._get_sound_info()
                except Exception as e:
                    self.is_valid = False
                    # this might be perfectly acceptable... who knows?
                    # user consumable error report to be handled by the UI code
                    print("---Invalid SFX selection---\n{}\n------".format(str(e)))
                else:
                    self.is_valid = True
                    self.is_stereo = header.numChannels == 2
                self._update_name()

    def _update_name(self, context=None):
        if self.is_stereo and self.channel != {"L", "R"}:
            self.name = "{}:{}".format(self._sound_name, "L" if "L" in self.channel else "R")
        else:
            self.name = self._sound_name

    enabled = BoolProperty(name="Enabled", default=True, options=set())
    sound = PointerProperty(name="Sound",
                            description="Sound Datablock",
                            type=bpy.types.Sound,
                            update=_update_sound)
    updating_sound = BoolProperty(default=False,
                                  options={"HIDDEN", "SKIP_SAVE"})

    is_stereo = BoolProperty(default=True, options={"HIDDEN"})
    is_valid = BoolProperty(default=False, options={"HIDDEN"})

    sfx_region = PointerProperty(name="Soft Volume",
                                 description="Soft region this sound can be heard in",
                                 type=bpy.types.Object,
                                 poll=idprops.poll_softvolume_objects)

    sfx_type = EnumProperty(name="Category",
                            description="Describes the purpose of this sound",
                            items=[("kSoundFX", "3D", "3D Positional SoundFX"),
                                   ("kAmbience", "Ambience", "Ambient Sounds"),
                                   ("kBackgroundMusic", "Music", "Background Music"),
                                   ("kGUISound", "GUI", "GUI Effect"),
                                   ("kNPCVoices", "NPC", "NPC Speech")],
                            options=set())
    channel = EnumProperty(name="Channel",
                           description="Which channel(s) to play",
                           items=[("L", "Left", "Left Channel"),
                                  ("R", "Right", "Right Channel")],
                           options={"ENUM_FLAG"},
                           default={"L", "R"},
                           update=_update_name)

    auto_start = BoolProperty(name="Auto Start",
                              description="Start playing when the age is loaded",
                              default=False,
                              options=set())
    incidental = BoolProperty(name="Incidental",
                              description="Sound is a low-priority incident and the engine may forgo playback",
                              default=False,
                              options=set())
    loop = BoolProperty(name="Loop",
                        description="Loop the sound",
                        default=False,
                        options=set())
    local_only = BoolProperty(name="Local Only",
                              description="Sounds only plays for local avatar",
                              default=False,
                              options=set())

    inner_cone = FloatProperty(name="Inner Angle",
                               description="Angle of the inner cone from the negative Z-axis",
                               min=0, max=math.radians(360), default=0, step=100,
                               options=set(),
                               subtype="ANGLE")
    outer_cone = FloatProperty(name="Outer Angle",
                               description="Angle of the outer cone from the negative Z-axis",
                               min=0, max=math.radians(360), default=math.radians(360), step=100,
                               options=set(),
                               subtype="ANGLE")
    outside_volume = IntProperty(name="Outside Volume",
                         description="Sound's volume when outside the outer cone",
                         min=0, max=100, default=100,
                         options=set(),
                         subtype="PERCENTAGE")

    min_falloff = IntProperty(name="Begin Falloff",
                              description="Distance where volume attenuation begins",
                              min=0, max=1000000000, default=1,
                              options=set(),
                              subtype="DISTANCE")
    max_falloff = IntProperty(name="End Falloff",
                              description="Distance where the sound is inaudible",
                              min=0, max=1000000000, default=1000,
                              options=set(),
                              subtype="DISTANCE")
    volume = IntProperty(name="Volume",
                         description="Volume to play the sound",
                         min=0, max=100, default=100,
                         options={"ANIMATABLE"},
                         subtype="PERCENTAGE")

    fade_in = PointerProperty(type=PlasmaSfxFade, options=set())
    fade_out = PointerProperty(type=PlasmaSfxFade, options=set())

    def _get_package_value(self):
        if self.sound is not None:
            self.package_value = self.sound.plasma_sound.package
        return self.package_value

    def _set_package_value(self, value):
        if self.sound is not None:
            self.sound.plasma_sound.package = value

    # This is really a property of the sound itself, not of this particular emitter instance.
    # However, to prevent weird UI inconsistencies where the button might be missing or change
    # states when clearing the sound pointer, we'll cache the actual value here.
    package = BoolProperty(name="Export",
                           description="Package this file in the age export",
                           get=_get_package_value, set=_set_package_value,
                           options=set())
    package_value = BoolProperty(options={"HIDDEN", "SKIP_SAVE"})

    @property
    def channel_override(self):
        if self.is_stereo and len(self.channel) == 1:
            return min(self.channel)
        else:
            return None

    def convert_sound(self, exporter, so, audible):
        header, dataSize = self._get_sound_info()
        length = dataSize / header.avgBytesPerSec

        # HAX: Ensure that the sound file is copied to game, if applicable.
        if self._sound.plasma_sound.package:
            exporter.output.add_sfx(self._sound)

        # There is some bug in the MOUL code that causes a crash if this does not match the expected
        # result. Worse, PotS seems to not like static sounds that are brand-new to it. Possibly because
        # it needs to be decompressed outside of game. There's no sense in debugging any of that
        # though--the user should never specify streaming vs static. That's an implementation detail.
        if exporter.mgr.getVer() != pvMoul and self._sound.plasma_sound.package:
            pClass = plWin32StreamingSound
        else:
            pClass = plWin32StreamingSound if length > 4.0 else plWin32StaticSound

        # OK. Any Plasma engine that uses OpenAL (MOUL) is subject to this restriction.
        # 3D Positional audio MUST... and I mean MUST... have mono emitters.
        # That means if the user has specified 3D and a stereo sound AND both channels, we MUST
        # export two emitters from here. Otherwise, it's no biggie. Wheeeeeeeeeeeeeeeeeeeeeeeee
        if self.is_3d_stereo or (self.is_stereo and len(self.channel) == 1):
            header.avgBytesPerSec = int(header.avgBytesPerSec / 2)
            header.numChannels = int(header.numChannels / 2)
            header.blockAlign = int(header.blockAlign / 2)
            dataSize = int(dataSize / 2)
        if self.is_3d_stereo:
            audible.addSound(self._convert_sound(exporter, so, pClass, header, dataSize, channel="L"))
            audible.addSound(self._convert_sound(exporter, so, pClass, header, dataSize, channel="R"))
        else:
            audible.addSound(self._convert_sound(exporter, so, pClass, header, dataSize, channel=self.channel_override))

    def _convert_sound(self, exporter, so, pClass, wavHeader, dataSize, channel=None):
        if channel is None:
            name = "Sfx-{}_{}".format(so.key.name, self._sound_name)
        else:
            name = "Sfx-{}_{}:{}".format(so.key.name, self._sound_name, channel)
        exporter.report.msg("[{}] {}", pClass.__name__[2:], name)
        sound = exporter.mgr.find_create_object(pClass, so=so, name=name)

        # If this object is a soft volume itself, we will use our own soft region.
        # Otherwise, check what they specified...
        sv_mod, sv_key = self.id_data.plasma_modifiers.softvolume, None
        if sv_mod.enabled:
            sv_key = sv_mod.get_key(exporter, so)
        elif self.sfx_region:
            sv_mod = self.sfx_region.plasma_modifiers.softvolume
            if not sv_mod.enabled:
                raise ExportError("'{}': SoundEmit '{}', '{}' is not a SoftVolume".format(self.id_data.name, self._sound_name, self.sfx_region.name))
            sv_key = sv_mod.get_key(exporter)
        if sv_key is not None:
            sv_key.object.listenState |= plSoftVolume.kListenCheck | plSoftVolume.kListenDirty | plSoftVolume.kListenRegistered
            sound.softRegion = sv_key

        # Sound
        sound.type = getattr(plSound, self.sfx_type)
        if sound.type == plSound.kSoundFX:
            sound.properties |= plSound.kPropIs3DSound
        if self.auto_start:
            sound.properties |= plSound.kPropAutoStart
        if self.loop:
            sound.properties |= plSound.kPropLooping
        if self.incidental:
            sound.properties |= plSound.kPropIncidental
        if self.local_only:
            sound.properties |= plSound.kPropLocalOnly
        sound.dataBuffer = self._find_sound_buffer(exporter, so, wavHeader, dataSize, channel)

        # Cone effect
        # I have observed that Blender 2.77's UI doesn't show the appropriate unit (degrees) for
        # IntProperty angle subtypes. So, we're storing the angles as floats in Blender even though
        # Plasma only wants integers. Sigh.
        sound.innerCone = int(math.degrees(self.inner_cone))
        sound.outerCone = int(math.degrees(self.outer_cone))
        sound.outerVol = self.outside_volume

        # Falloff
        sound.desiredVolume = self.volume / 100.0
        sound.minFalloff = self.min_falloff
        sound.maxFalloff = self.max_falloff

        # Fade FX
        fade_in, fade_out = sound.fadeInParams, sound.fadeOutParams
        for blfade, plfade in ((self.fade_in, fade_in), (self.fade_out, fade_out)):
            if blfade.fade_type == "NONE":
                plfade.lengthInSecs = 0.0
            else:
                plfade.lengthInSecs = blfade.length
                plfade.type = getattr(plSound.plFadeParams, blfade.fade_type)
            plfade.currTime = -1.0

        # Some manual fiddling -- this is hidden deep inside the 3dsm exporter...
        # Kind of neat how it's all generic though :)
        fade_in.volStart = 0.0
        fade_in.volEnd = 1.0
        fade_out.volStart = 1.0
        fade_out.volEnd = 0.0
        fade_out.stopWhenDone = True

        # Some last minute buffer tweaking based on our props here...
        buffer = sound.dataBuffer.object
        if isinstance(sound, plWin32StreamingSound):
            buffer.flags |= plSoundBuffer.kStreamCompressed
        if sound.type == plSound.kBackgroundMusic:
            buffer.flags |= plSoundBuffer.kAlwaysExternal

        # Win32Sound
        if channel == "L":
            sound.channel = plWin32Sound.kLeftChannel
        else:
            sound.channel = plWin32Sound.kRightChannel

        # Whew, that was a lot of work!
        return sound.key

    def _get_sound_info(self):
        """Generates a tuple (plWAVHeader, PCMsize) from the current sound"""
        sound = self._sound
        if sound.packed_file is None:
            stream = hsFileStream()
            try:
                stream.open(bpy.path.abspath(sound.filepath), fmRead)
            except IOError:
                self._raise_error("failed to open file")
        else:
            stream = hsRAMStream()
            stream.buffer = sound.packed_file.data

        try:
            magic = stream.read(4)
            stream.rewind()

            header = plWAVHeader()
            if magic == b"RIFF":
                size = korlib.inspect_wavefile(stream, header)
                return (header, size)
            elif magic == b"OggS":
                size = korlib.inspect_vorbisfile(stream, header)
                return (header, size)
            else:
                raise NotSupportedError("unsupported audio format")
        except Exception as e:
            self._raise_error(str(e))
        finally:
            stream.close()

    def _find_sound_buffer(self, exporter, so, wavHeader, dataSize, channel):
        # First, cleanup the file path to not have directories
        filename = bpy.path.basename(self._sound.filepath)
        if channel is None:
            key_name = filename
        else:
            key_name = "{}:{}".format(filename, channel)

        key = exporter.mgr.find_key(plSoundBuffer, so=so, name=key_name)
        if key is None:
            sound = exporter.mgr.add_object(plSoundBuffer, so=so, name=key_name)
            sound.header = wavHeader
            sound.fileName = filename
            sound.dataLength = dataSize
            # Maybe someday we will allow packed sounds? I'm in no hurry...
            sound.flags |= plSoundBuffer.kIsExternal
            if channel == "L":
                sound.flags |= plSoundBuffer.kOnlyLeftChannel
            elif channel == "R":
                sound.flags |= plSoundBuffer.kOnlyRightChannel
            key = sound.key
        return key

    @classmethod
    def _idprop_mapping(cls):
        return {"sound": "sound_data",
                "sfx_region": "soft_region"}

    def _idprop_sources(self):
        return {"sound_data": bpy.data.sounds,
                "soft_region": bpy.data.objects}

    @property
    def is_3d_stereo(self):
        return self.sfx_type == "kSoundFX" and self.channel == {"L", "R"} and self.is_stereo

    def _raise_error(self, msg):
        if self.sound:
            raise ExportError("SoundEmitter '{}': Sound '{}' {}".format(self.id_data.name, self.sound.name, msg))
        else:
            raise ExportError("SoundEmitter '{}': {}".format(self.id_data.name, msg))

    @property
    def _sound(self):
        if not self.sound:
            self._raise_error("has an invalid sound specified")
        return self.sound

    @property
    def _sound_name(self):
        if self.sound:
            return self.sound.name
        return ""


class PlasmaSoundEmitter(PlasmaModifierProperties):
    pl_id = "soundemit"

    bl_category = "Logic"
    bl_label = "Sound Emitter"
    bl_description = "Point at which sound(s) are played"
    bl_icon = "SPEAKER"

    sounds = CollectionProperty(type=PlasmaSound)
    active_sound_index = IntProperty(options={"HIDDEN"})

    stereize_left = PointerProperty(type=bpy.types.Object, options={"HIDDEN", "SKIP_SAVE"})
    stereize_right = PointerProperty(type=bpy.types.Object, options={"HIDDEN", "SKIP_SAVE"})

    def sanity_check(self):
        modifiers = self.id_data.plasma_modifiers

        # Sound emitters can potentially export sounds to more than one emitter SceneObject. Currently,
        # this happens for 3D stereo sounds. That means that any modifier that expects for all of
        # this emitter's sounds to be attached to this plAudioInterface might have a bad time.
        if self.have_3d_stereo and modifiers.random_sound.enabled:
            raise ExportError(f"{self.id_data.name}: Random Sound modifier cannot be applied to a Sound Emitter with 3D Stereo sounds.")

    @contextmanager
    def _generate_stereized_emitter(self, exporter, bo: bpy.types.Object, channel: str, attr: str):
        # Duplicate the current sound emitter as a non-linked object so that we have all the
        # information that the parent emitter has, but we're free to turn off things as needed.
        with duplicate_object(bo) as emitter_obj:
            emitter_obj.location = (0.0, 0.0, 0.0)
            emitter_obj.name = f"{bo.name}_Stereo-Ize:{channel}"
            emitter_obj.parent = bo

            # In case some bozo is using a visual mesh as a sound emitter, clear the materials
            # off the duplicate to prevent it from being visible in the world.
            if emitter_obj.type == "MESH":
                emitter_obj.data.materials.clear()

            # We want to allow animations and sounds to export from the new emitter.
            bad_mods = filter(
                lambda x: x.pl_id not in {"animation", "soundemit"},
                emitter_obj.plasma_modifiers.modifiers
            )
            for i in bad_mods:
                i.enabled = False

            # But only 3D stereo sounds!
            soundemit_mod = emitter_obj.plasma_modifiers.soundemit
            for sound in soundemit_mod.sounds:
                if sound.is_3d_stereo:
                    sound.channel = set(channel)
                else:
                    sound.enabled = False

            # And only sound volume animations!
            if emitter_obj.animation_data is not None and emitter_obj.animation_data.action is not None:
                action = emitter_obj.animation_data.action
                volume_paths = frozenset((i.path_from_id("volume") for i in soundemit_mod.sounds if i.enabled))
                toasty_fcurves = [i for i, fcurve in enumerate(action.fcurves) if fcurve.data_path not in volume_paths]
                for i in reversed(toasty_fcurves):
                    action.fcurves.remove(i)

            # Again, only sound volume animations, which are handled above.
            emitter_obj_data = emitter_obj.data
            if emitter_obj_data is not None and emitter_obj_data.animation_data is not None and emitter_obj_data.animation_data.action is not None:
                emitter_obj_data.animation_data.action.fcurves.clear()

            # Temporarily save a pointer to this generated emitter object so that the parent soundemit
            # modifier can redirect requests to 3D sounds to the generated emitters.
            setattr(self, attr, emitter_obj)
            try:
                yield emitter_obj
            finally:
                self.property_unset(attr)

    def _find_animation_groups(self, bo: bpy.types.Object):
        is_anim_group = lambda x: (
            x is not bo and
            x.plasma_object.enabled and
            x.plasma_modifiers.animation_group.enabled
        )
        for i in filter(is_anim_group, bpy.data.objects):
            group = i.plasma_modifiers.animation_group
            for child in group.children:
                if child.child_anim == self.id_data:
                    yield child

    def _add_child_animation(self, exporter, group, bo: bpy.types.Object, temporary=False):
        if temporary:
            child = exporter.exit_stack.enter_context(TemporaryCollectionItem(group.children))
        else:
            child = group.children.add()
        child.child_anim = bo

    def pre_export(self, exporter, bo: bpy.types.Object):
        # Stereo 3D sounds are a very, very special case. We need to export mono sound sources.
        # However, to get Plasma's Stereo-Ize feature to work, they need to be completely separate
        # objects that the engine can move around itself. Those need to be duplicates of this
        # blender object so that all animation data and whatnot remains.
        if self.have_3d_stereo:
            toggle = exporter.exit_stack.enter_context(GoodNeighbor())

            # Find any animation groups that we're a part of - we need to be a member of those,
            # or create one *if* any animations
            yield self._generate_stereized_emitter(exporter, bo, "L", "stereize_left")
            yield self._generate_stereized_emitter(exporter, bo, "R", "stereize_right")

            # If some animation data persisted on the new emitters, then we need to make certain
            # that those animations are targetted by anyone trying to control us. That's an
            # animation group modifier (plMsgForwarder) for anyone playing along at home.
            if self.stereize_left.plasma_object.has_animation_data or self.stereize_right.plasma_object.has_animation_data:
                my_anim_groups = list(self._find_animation_groups(bo))

                # If no one contains this sound emitter, then we need to be an animation group.
                if not my_anim_groups:
                    group = bo.plasma_modifiers.animation_group
                    if not group.enabled:
                        toggle.track(group, "enabled", True)
                        for i in group.children:
                            toggle.track(i, "enabled", False)
                    my_anim_groups.append(group)

                # Now that we have the animation groups, feed in the generated emitter objects
                # as ephemeral child animations. They should be removed from the modifier when the
                # export finishes.
                for anim_group in my_anim_groups:
                    self._add_child_animation(exporter, anim_group, self.stereize_left, True)
                    self._add_child_animation(exporter, anim_group, self.stereize_right, True)

            # Temporarily disable the 3D stereo sounds on this emitter during the export - so
            # this emitter will export everything that isn't 3D stereo.
            for i in filter(lambda x: x.is_3d_stereo, self.sounds):
                toggle.track(i, "enabled", False)

    def export(self, exporter, bo, so):
        if any((i.enabled for i in self.sounds)):
            winaud = exporter.mgr.find_create_object(plWinAudible, so=so, name=self.key_name)
            winaud.sceneNode = exporter.mgr.get_scene_node(so.key.location)
            aiface = exporter.mgr.find_create_object(plAudioInterface, so=so, name=self.key_name)
            aiface.audible = winaud.key

            # Pass this off to each individual sound for conversion
            for i in filter(lambda x: x.enabled, self.sounds):
                i.convert_sound(exporter, so, winaud)

        # Back to our faked emitters for 3D stereo sounds... Create the stereo-ize object
        # that will cause Plasma to move the object around in the 3D world. In the future,
        # this should probably be split out to a separate modifier.
        if self.stereize_left and self.stereize_right:
            self._convert_stereize(exporter, self.stereize_left, "L")
            self._convert_stereize(exporter, self.stereize_right, "R")

    def post_export(self, exporter, bo: bpy.types.Object, so: plSceneObject):
        if self.stereize_left and self.stereize_right:
            self._handle_stereize_lfm(exporter, self.stereize_left, so)
            self._handle_stereize_lfm(exporter, self.stereize_right, so)

    def _convert_stereize(self, exporter, bo: bpy.types.Object, channel: str) -> None:
        # TODO: This should probably be moved into a Stereo-Ize modifier of some sort
        stereoize = exporter.mgr.find_create_object(plStereizer, bl=bo)
        stereoize.setFlag(plStereizer.kLeftChannel, channel == "L")
        stereoize.ambientDist = 50.0
        stereoize.sepDist = (5.0, 100.0)
        stereoize.transition = 25.0
        stereoize.tanAng = math.radians(30.0)

    def _handle_stereize_lfm(self, exporter, child_bo: bpy.types.Object, parent_so: plSceneObject) -> None:
        # TODO: This should probably be moved into a Stereo-Ize modifier of some sort
        stereizer = exporter.mgr.find_object(plStereizer, bl=child_bo)
        for lfm_key in filter(lambda x: isinstance(x.object, plLineFollowMod), parent_so.modifiers):
            stereizer.setFlag(plStereizer.kHasMaster, True)
            lfm_key.object.addStereizer(stereizer.key)

    def get_sound_keys(self, exporter, name=None, sound=None) -> Iterator[Tuple[plKey, int]]:
        assert name or sound
        if sound is None:
            sound = next((i for i in self.sounds if i._sound_name == name), None)
            if sound is None:
                raise ValueError(name)

        if sound.is_3d_stereo:
            yield from self.stereize_left.plasma_modifiers.soundemit.get_sound_keys(exporter, sound.name)
            yield from self.stereize_right.plasma_modifiers.soundemit.get_sound_keys(exporter, sound.name)
        else:
            for i, j in enumerate(filter(lambda x: x.enabled, self.sounds)):
                if sound == j:
                    yield exporter.mgr.find_create_key(plAudioInterface, bl=self.id_data), i

    @property
    def have_3d_stereo(self) -> bool:
        return any((i.is_3d_stereo for i in self.sounds if i.enabled))

    @property
    def requires_actor(self):
        return True
