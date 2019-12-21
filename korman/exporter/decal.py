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
from collections import defaultdict
import itertools
from PyHSPlasma import *
import weakref

from ..exporter.explosions import ExportError

def _get_puddle_class(exporter, name, vs):
    if vs:
        # sigh... thou shalt not...
        exporter.report.warn("'{}': Cannot use 'Water Ripple (Shallow) on a waveset--forcing to 'Water Ripple (Deep)", name)
        return plDynaRippleVSMgr
    return plDynaPuddleMgr

def _get_footprint_class(exporter, name, vs):
    if vs:
        raise ExportError("'{}': Footprints cannot be attached to wavesets", name)
    return plDynaFootMgr

class DecalConverter:
    _decal_lookup = {
        "footprint_dry": _get_footprint_class,
        "footprint_wet": _get_footprint_class,
        "puddle": _get_puddle_class,
        "ripple": lambda e, name, vs: plDynaRippleVSMgr if vs else plDynaRippleMgr,
    }

    def __init__(self, exporter):
        self._decal_managers = defaultdict(list)
        self._exporter = weakref.ref(exporter)
        self._notifies = defaultdict(set)

    def add_dynamic_decal_receiver(self, so, decal_name):
        # One decal manager in Blender can map to many Plasma decal managers.
        # The case we care about: a single water decal exporting to multiple DynaDecalMgrs
        #                         eg two wavesets (two mgrs) and two water planes (one mgr)
        # We don't care about: DynaDecalMgrs in another page.
        decal_mgrs, so_key = self._decal_managers.get(decal_name), so.key
        if decal_mgrs is None:
            raise ExportError("'{}': Invalid decal manager '{}'", so_key.name, decal_name)

        # If we are waveset water, then we can only have one target...
        waveset_id = plFactory.ClassIndex("plWaveSet7")
        waveset = next((i for i in so.modifiers if i.type == waveset_id), None)

        so_loc = so_key.location
        for key, decal_mgr in ((i, i.object) for i in decal_mgrs):
            if key.location == so_loc and getattr(decal_mgr, "waveSet", None) == waveset:
                decal_mgr.addTarget(so_key)

        # HACKAGE: Add the wet/dirty notifes now that we know about all the decal managers.
        notify_names = self._notifies[decal_name]
        notify_keys = itertools.chain.from_iterable((self._decal_managers[i] for i in notify_names))
        for notify_key in notify_keys:
            for i in (i.object for i in decal_mgrs):
                i.addNotify(notify_key)
        # Don't need to do that again.
        del self._notifies[decal_name]

    def export_active_print_shape(self, print_shape, decal_name):
        decal_mgrs = self._decal_managers.get(decal_name)
        if decal_mgrs is None:
            raise ExportError("'{}': Invalid decal manager '{}'", print_shape.key.name, decal_name)
        for i in decal_mgrs:
            print_shape.addDecalMgr(i)

    def export_static_decal(self, bo):
        mat_mgr = self._exporter().mesh.material
        mat_keys = mat_mgr.get_materials(bo)
        if not mat_keys:
            raise ExportError("'{}': Cannot print decal onto object with no materials", bo.name)

        zFlags = hsGMatState.kZIncLayer | hsGMatState.kZNoZWrite
        for material in (i.object for i in mat_keys):
            # Only useful in a debugging context
            material.compFlags |= hsGMaterial.kCompDecal

            # zFlags should only be applied to the material's base layer
            # note: changing blend flags is unsafe here -- so don't even think about it!
            layer = mat_mgr.get_base_layer(material)
            layer.state.ZFlags |= zFlags

    def generate_dynamic_decal(self, bo, decal_name):
        decal = next((i for i in bpy.context.scene.plasma_scene.decal_managers if i.name == decal_name), None)
        if decal is None:
            raise ExportError("'{}': Invalid decal manager '{}'", bo.name, decal_name)

        exporter = self._exporter()
        decal_type = decal.decal_type
        is_waveset = bo.plasma_modifiers.water_basic.enabled
        pClass = self._decal_lookup[decal_type](exporter, decal_name, is_waveset)

        # DynaDecal Managers generate geometry at runtime, so we need to share them as much as
        # possible. However, it is best to keep things page local. Furthermore, wavesets cannot
        # share decal managers due to vertex shaders being used.
        name = "{}_{}".format(decal_name, bo.name) if is_waveset else decal_name
        decal_mgr = exporter.mgr.find_object(pClass, bl=bo, name=name)
        if decal_mgr is None:
            self._report.msg("Exporing decal manager '{}' to '{}'", decal_name, name, indent=2)

            decal_mgr = exporter.mgr.add_object(pClass, bl=bo, name=name)
            self._decal_managers[decal_name].append(decal_mgr.key)

            # Certain decals are required to be squares
            if decal_type in {"footprint_dry", "footprint_wet", "wake"}:
                length, width = decal.length / 100.0, decal.width / 100.0
            else:
                length = max(decal.length, decal.width) / 100.0
                width = max(decal.length, decal.width) / 100.0

            image = decal.image
            if image is None:
                raise ExportError("'{}': decal manager '{}' has no image set", bo.name, decal_name)

            blend = getattr(hsGMatState, decal.blend)
            mats = exporter.mesh.material.export_print_materials(bo, image, name, blend)
            decal_mgr.matPreShade, decal_mgr.matRTShade = mats

            # Hardwired values from PlasmaMAX
            decal_mgr.maxNumVerts = 1000
            decal_mgr.maxNumIdx = 1000
            decal_mgr.intensity = decal.intensity / 100.0
            decal_mgr.gridSizeU = 2.5
            decal_mgr.gridSizeV = 2.5
            decal_mgr.scale = hsVector3(length, width, 1.0)

            # Hardwired calculations from PlasmaMAX
            if decal_type in {"footprint_dry", "footprint_wet", "bullet"}:
                decal_mgr.rampEnd = 0.1
                decal_mgr.decayStart = decal.life_span - (decal.life_span * 0.25)
                decal_mgr.lifeSpan = decal.life_span
            elif decal_type in {"puddle", "ripple", "torpedo", "wake"}:
                decal_mgr.rampEnd = 0.25
                life_span = decal.life_span if decal_type == "torpedo" else length / 2.0
                decal_mgr.decayStart = life_span * 0.8
                decal_mgr.lifeSpan = life_span
            else:
                raise RuntimeError()

            # While any decal manager can be wet/dry, it really makes the most sense to only
            # expose wet footprints. In the future, we could expose the plDynaDecalEnableMsg
            # to nodes for advanced hacking.
            decal_mgr.waitOnEnable = decal_type == "footprint_wet"
            if decal_type in {"puddle", "ripple"}:
                decal_mgr.wetLength = decal.wet_time
                self._notifies[decal_name].update((i.name for i in decal.wet_managers
                                                          if i.enabled and i.name != decal_name))

            # UV Animations are hardcoded in PlasmaMAX. Any reason why we should expose this?
            # I can't think of any presently... Note testing the final instance instead of the
            # artist setting in case that gets overridden (puddle -> ripple)
            if isinstance(decal_mgr, plDynaPuddleMgr):
                decal_mgr.initUVW = hsVector3(5.0, 5.0, 5.0)
                decal_mgr.finalUVW = hsVector3(1.0, 1.0, 1.0)
            elif isinstance(decal_mgr, plDynaRippleMgr):
                # wakes, torpedos, and ripples...
                decal_mgr.initUVW = hsVector3(3.0, 3.0, 3.0)
                decal_mgr.finalUVW = hsVector3(1.0, 1.0, 1.0)

            if isinstance(decal_mgr, (plDynaRippleVSMgr, plDynaTorpedoVSMgr)):
                decal_mgr.waveSet = exporter.mgr.find_create_key(plWaveSet7, bl=bo)

    @property
    def _mgr(self):
        return self._exporter().mgr

    @property
    def _report(self):
        return self._exporter().report
