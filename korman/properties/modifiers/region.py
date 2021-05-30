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

import bmesh
import bpy
from bpy.props import *
from PyHSPlasma import *

from ...exporter import ExportError, ExportAssertionError
from ...helpers import bmesh_from_object
from ... import idprops

from .base import PlasmaModifierProperties, PlasmaModifierLogicWiz
from ..prop_camera import PlasmaCameraProperties
from .physics import bounds_types

footstep_surface_ids = {
    "dirt": 0,
    # 1 = NULL
    "puddle": 2,
    # 3 = tile (NULL in MOUL)
    "metal": 4,
    "woodbridge": 5,
    "rope": 6,
    "grass": 7,
    # 8 = NULL
    "woodfloor": 9,
    "rug": 10,
    "stone": 11,
    # 12 = NULL
    # 13 = metal ladder (dupe of metal)
    "woodladder": 14,
    "water": 15,
    # 16 = maintainer's glass (NULL in PotS)
    # 17 = maintainer's metal grating (NULL in PotS)
    # 18 = swimming (why would you want this?)
}

footstep_surfaces = [("dirt", "Dirt", "Dirt"),
                     ("grass", "Grass", "Grass"),
                     ("metal", "Metal", "Metal Catwalk"),
                     ("puddle", "Puddle", "Shallow Water"),
                     ("rope", "Rope", "Rope Ladder"),
                     ("rug", "Rug", "Carpet Rug"),
                     ("stone", "Stone", "Stone Tile"),
                     ("water", "Water", "Deep Water"),
                     ("woodbridge", "Wood Bridge", "Wood Bridge"),
                     ("woodfloor", "Wood Floor", "Wood Floor"),
                     ("woodladder", "Wood Ladder", "Wood Ladder")]

class PlasmaCameraRegion(PlasmaModifierProperties):
    pl_id = "camera_rgn"

    bl_category = "Region"
    bl_label = "Camera Region"
    bl_description = "Camera Region"
    bl_icon = "CAMERA_DATA"

    camera_type = EnumProperty(name="Camera Type",
                               description="What kind of camera should be used?",
                               items=[("auto_follow", "Auto Follow Camera", "Automatically generated follow camera"),
                                      ("manual", "Manual Camera", "User specified camera object")],
                               default="manual",
                               options=set())
    camera_object = PointerProperty(name="Camera",
                                    description="Switches to this camera",
                                    type=bpy.types.Object,
                                    poll=idprops.poll_camera_objects,
                                    options=set())
    auto_camera = PointerProperty(type=PlasmaCameraProperties, options=set())

    def export(self, exporter, bo, so):
        if self.camera_type == "manual":
            if self.camera_object is None:
                raise ExportError("Camera Modifier '{}' does not specify a valid camera object".format(self.id_data.name))
            camera_so_key = exporter.mgr.find_create_key(plSceneObject, bl=self.camera_object)
            camera_props = self.camera_object.data.plasma_camera.settings
        else:
            assert self.camera_type[:4] == "auto"

            # Wheedoggy! We get to export the doggone camera now.
            camera_props = self.auto_camera
            camera_type = self.camera_type[5:]
            exporter.camera.export_camera(so, bo, camera_type, camera_props)
            camera_so_key = so.key

        # Setup physical stuff
        phys_mod = bo.plasma_modifiers.collision
        exporter.physics.generate_physical(bo, so, member_group="kGroupDetector",
                                           report_groups=["kGroupAvatar"],
                                           properties=["kPinned"])

        # I don't feel evil enough to make this generate a logic tree...
        msg = plCameraMsg()
        msg.BCastFlags |= plMessage.kLocalPropagate | plMessage.kBCastByType
        msg.setCmd(plCameraMsg.kRegionPushCamera)
        msg.setCmd(plCameraMsg.kSetAsPrimary, camera_props.primary_camera)
        msg.newCam = camera_so_key

        region = exporter.mgr.find_create_object(plCameraRegionDetector, so=so)
        region.addMessage(msg)

    def harvest_actors(self):
        actors = set()
        if self.camera_type == "manual":
            if self.camera_object is None:
                raise ExportError("Camera Modifier '{}' does not specify a valid camera object".format(self.id_data.name))
            actors.update(self.camera_object.data.plasma_camera.settings.harvest_actors())
        else:
            actors.update(self.auto_camera.harvest_actors())
        return actors

    @property
    def requires_actor(self):
        return self.camera_type == "auto_follow"


class PlasmaFootstepRegion(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "footstep"

    bl_category = "Region"
    bl_label = "Footstep"
    bl_description = "Footstep Region"

    surface = EnumProperty(name="Surface",
                           description="What kind of surface are we walking on?",
                           items=footstep_surfaces,
                           default="stone")
    bounds = EnumProperty(name="Region Bounds",
                          description="Physical object's bounds",
                          items=bounds_types,
                          default="hull")

    def export(self, exporter, bo, so):
        with self.generate_logic(bo) as tree:
            tree.export(exporter, bo, so)

    def logicwiz(self, bo, tree):
        nodes = tree.nodes

        # Region Sensor
        volsens = nodes.new("PlasmaVolumeSensorNode")
        volsens.name = "RegionSensor"
        volsens.region_object = bo
        volsens.bounds = self.bounds
        volsens.find_input_socket("enter").allow = True
        volsens.find_input_socket("exit").allow = True

        # Responder
        respmod = nodes.new("PlasmaResponderNode")
        respmod.name = "Resp"
        respmod.link_input(volsens, "satisfies", "condition")
        respstate = nodes.new("PlasmaResponderStateNode")
        respstate.link_input(respmod, "state_refs", "resp")

        # ArmatureEffectStateMsg
        msg = nodes.new("PlasmaFootstepSoundMsgNode")
        msg.link_input(respstate, "msgs", "sender")
        msg.surface = self.surface

    @property
    def key_name(self):
        return "{}_FootRgn".format(self.id_data.name)


class PlasmaPanicLinkRegion(PlasmaModifierProperties):
    pl_id = "paniclink"

    bl_category = "Region"
    bl_label = "Panic Link"
    bl_description = "Panic Link Region"

    play_anim = BoolProperty(name="Play Animation",
                             description="Play the link-out animation when panic linking",
                             default=True)

    def export(self, exporter, bo, so):
        exporter.physics.generate_physical(bo, so, member_group="kGroupDetector",
                                           report_groups=["kGroupAvatar"])

        # Finally, the panic link region proper
        reg = exporter.mgr.add_object(plPanicLinkRegion, name=self.key_name, so=so)
        reg.playLinkOutAnim = self.play_anim

    @property
    def key_name(self):
        return "{}_PanicLinkRgn".format(self.id_data.name)

    @property
    def requires_actor(self):
        return True


reverb_flags = [("kFlagDecayTimeScale", "Decay Time Scale", "Reverberation decay time"),
                ("kFlagReflectionsScale", "Reflections Scale", "Reflection level"),
                ("kFlagReflectionsDelayScale", "Reflections Delay Scale", "Initial reflection delay time"),
                ("kFlagReverbScale", "Reverb Scale", "Reverberation level"),
                ("kFlagReverbDelayScale", "Reverb Delay Scale", "Late reverberation delay time"),
                ("kFlagEchoTimeScale", "Echo Time Scale", "Echo time"),
                ("kFlagModulationTimeScale", "Modulation Time Scale", "Modulation time"),
                ("kFlagDecayHFLimit", "Decay HF Limit", "Limit unnaturally long decay times of high-frequency sounds by forcing a limit to the decay time to be calculated from the Air Absorption HF value")]

class PlasmaReverbRegion(PlasmaModifierProperties):
    pl_id = "reverb"
    pl_depends = {"softvolume"}

    bl_category = "Region"
    bl_label = "Sound Reverb Region"
    bl_description = "Sound Reverberation (EAX) Region"
    bl_icon = "IPO_ELASTIC"

    preset = EnumProperty(name="Environment Preset",
                          description="The type of audio environment to simulate",
                          items=[("GENERIC", "Generic", "A generic-sounding environment with light reverberation"),
                                 ("PADDEDCELL", "Padded cell", ""),
                                 ("ROOM", "Room", ""),
                                 ("BATHROOM", "Bathroom", ""),
                                 ("LIVINGROOM", "Living room", ""),
                                 ("STONEROOM", "Stone room", ""),
                                 ("AUDITORIUM", "Auditorium", ""),
                                 ("CONCERTHALL", "Concert Hall", ""),
                                 ("CAVE", "Cave", ""),
                                 ("ARENA", "Arena", ""),
                                 ("HANGAR", "Hangar", ""),
                                 ("CARPETTEDHALLWAY", "Carpetted hallway", ""),
                                 ("HALLWAY", "Hallway", ""),
                                 ("STONECORRIDOR", "Stone corridor", ""),
                                 ("ALLEY", "Alley", ""),
                                 ("FOREST", "Forest", ""),
                                 ("CITY", "City", ""),
                                 ("MOUNTAINS", "Mountains", ""),
                                 ("QUARRY", "Quarry", ""),
                                 ("PLAIN", "Plain", ""),
                                 ("PARKINGLOT", "Parking lot", ""),
                                 ("SEWERPIPE", "Sewer pipe", ""),
                                 ("UNDERWATER", "Underwater", ""),
                                 ("DRUGGED", "Drugged", ""),
                                 ("DIZZY", "Drizzy", ""),
                                 ("PSYCHOTIC", "Psychotic", ""),
                                 ("MORE", "More choices...", ""),
                                 ("CUSTOM", "Custom", "Setup your own environment")],
                          default="GENERIC",
                          options=set())

    # Thikk list for annoying users.
    preset_more = EnumProperty(name="More Environment Preset",
                               description="Some more environment presets for your convenience",
                               items=[("CASTLE_SMALLROOM", "Castle - Small room", ""),
                                      ("CASTLE_SHORTPASSAGE", "Castle - Short passage", ""),
                                      ("CASTLE_MEDIUMROOM", "Castle - Medium room", ""),
                                      ("CASTLE_LONGPASSAGE", "Castle - Long passage", ""),
                                      ("CASTLE_LARGEROOM", "Castle - Large room", ""),
                                      ("CASTLE_HALL", "Castle - Hall", ""),
                                      ("CASTLE_CUPBOARD", "Castle - Cupboard", ""),
                                      ("CASTLE_COURTYARD", "Castle - Courtyard", ""),
                                      ("CASTLE_ALCOVE", "Castle - Alcove", ""),
                                      ("FACTORY_ALCOVE", "Factory - Alcove", ""),
                                      ("FACTORY_SHORTPASSAGE", "Factory - Short passage", ""),
                                      ("FACTORY_MEDIUMROOM", "Factory - Medium room", ""),
                                      ("FACTORY_LONGPASSAGE", "Factory - Long passage", ""),
                                      ("FACTORY_LARGEROOM", "Factory - Large room", ""),
                                      ("FACTORY_HALL", "Factory - Hall", ""),
                                      ("FACTORY_CUPBOARD", "Factory - Cupboard", ""),
                                      ("FACTORY_COURTYARD", "Factory - Courtyard", ""),
                                      ("FACTORY_SMALLROOM", "Factory - Small room", ""),
                                      ("ICEPALACE_ALCOVE", "Ice palace - Alcove", ""),
                                      ("ICEPALACE_SHORTPASSAGE", "Ice palace - Short passage", ""),
                                      ("ICEPALACE_MEDIUMROOM", "Ice palace - Medium room", ""),
                                      ("ICEPALACE_LONGPASSAGE", "Ice palace - Long passage", ""),
                                      ("ICEPALACE_LARGEROOM", "Ice palace - Large room", ""),
                                      ("ICEPALACE_HALL", "Ice palace - Hall", ""),
                                      ("ICEPALACE_CUPBOARD", "Ice palace - Cupboard", ""),
                                      ("ICEPALACE_COURTYARD", "Ice palace - Courtyard", ""),
                                      ("ICEPALACE_SMALLROOM", "Ice palace - Small room", ""),
                                      ("SPACESTATION_ALCOVE", "Space station - Alcove", ""),
                                      ("SPACESTATION_MEDIUMROOM", "Space station - Medium room", ""),
                                      ("SPACESTATION_SHORTPASSAGE", "Space station - Short passage", ""),
                                      ("SPACESTATION_LONGPASSAGE", "Space station - Long passage", ""),
                                      ("SPACESTATION_LARGEROOM", "Space station - Large room", ""),
                                      ("SPACESTATION_HALL", "Space station - Hall", ""),
                                      ("SPACESTATION_CUPBOARD", "Space station - Cupboard", ""),
                                      ("SPACESTATION_SMALLROOM", "Space station - Small room", ""),
                                      ("WOODEN_ALCOVE", "Wooden alcove", ""),
                                      ("WOODEN_SHORTPASSAGE", "Wooden short passage", ""),
                                      ("WOODEN_MEDIUMROOM", "Wooden medium room", ""),
                                      ("WOODEN_LONGPASSAGE", "Wooden long passage", ""),
                                      ("WOODEN_LARGEROOM", "Wooden large room", ""),
                                      ("WOODEN_HALL", "Wooden hall", ""),
                                      ("WOODEN_CUPBOARD", "Wooden cupboard", ""),
                                      ("WOODEN_SMALLROOM", "Wooden small room", ""),
                                      ("WOODEN_COURTYARD", "Wooden courtyard", ""),
                                      ("SPORT_EMPTYSTADIUM", "Sport - Empty stadium", ""),
                                      ("SPORT_SQUASHCOURT", "Sport - Squash court", ""),
                                      ("SPORT_SMALLSWIMMINGPOOL", "Sport - Small swimming pool", ""),
                                      ("SPORT_LARGESWIMMINGPOOL", "Sport - Large swimming pool", ""),
                                      ("SPORT_GYMNASIUM", "Sport - Gymnasium", ""),
                                      ("SPORT_FULLSTADIUM", "Sport - Full stadium", ""),
                                      ("SPORT_STADIUMTANNOY", "Sport - Stadium tannoy", ""),
                                      ("PREFAB_WORKSHOP", "Prefab - Workshop", ""),
                                      ("PREFAB_SCHOOLROOM", "Prefab - Schoolroom", ""),
                                      ("PREFAB_PRACTISEROOM", "Prefab - Practise room", ""),
                                      ("PREFAB_OUTHOUSE", "Prefab - Outhouse", ""),
                                      ("PREFAB_CARAVAN", "Prefab - Zandi's Trailer", ""),
                                      ("DOME_TOMB", "Tomb dome", ""),
                                      ("DOME_SAINTPAULS", "St Paul's Dome", ""),
                                      ("PIPE_SMALL", "Pipe - small", ""),
                                      ("PIPE_LONGTHIN", "Pipe - long & thin", ""),
                                      ("PIPE_LARGE", "Pipe - large", ""),
                                      ("PIPE_RESONANT", "Pipe - resonant", ""),
                                      ("OUTDOORS_BACKYARD", "Outdoors - Backyard", ""),
                                      ("OUTDOORS_ROLLINGPLAINS", "Outdoors - Rolling plains", ""),
                                      ("OUTDOORS_DEEPCANYON", "Outdoors - Deep canyon", ""),
                                      ("OUTDOORS_CREEK", "Outdoors - Creek", ""),
                                      ("OUTDOORS_VALLEY", "Outdoors - Valley", ""),
                                      ("MOOD_HEAVEN", "Mood - Heaven", ""),
                                      ("MOOD_HELL", "Mood - Hell", ""),
                                      ("MOOD_MEMORY", "Mood - Memory", ""),
                                      ("DRIVING_COMMENTATOR", "Driving - Commentator", ""),
                                      ("DRIVING_PITGARAGE", "Driving - In pit garage", ""),
                                      ("DRIVING_INCAR_RACER", "Driving - In racer car", ""),
                                      ("DRIVING_INCAR_SPORTS", "Driving - In sports car", ""),
                                      ("DRIVING_INCAR_LUXURY", "Driving - In luxury car", ""),
                                      ("DRIVING_FULLGRANDSTAND", "Driving - Full grand stand", ""),
                                      ("DRIVING_EMPTYGRANDSTAND", "Driving - Empty grand stand", ""),
                                      ("DRIVING_TUNNEL", "Driving - Tunnel", ""),
                                      ("CITY_STREETS", "City - Streets", ""),
                                      ("CITY_SUBWAY", "City - Subway", ""),
                                      ("CITY_MUSEUM", "City - Museum", ""),
                                      ("CITY_LIBRARY", "City - Library", ""),
                                      ("CITY_UNDERPASS", "City - Underpass", ""),
                                      ("CITY_ABANDONED", "City - Abandoned", ""),
                                      ("DUSTYROOM", "Dusty room", ""),
                                      ("CHAPEL", "Chapel", ""),
                                      ("SMALLWATERROOM", "Small water room", "")],
                          default="OUTDOORS_ROLLINGPLAINS",
                          options=set())

    environment_size = FloatProperty(name="Environment Size", description="Environment Size",
                                     default=7.5, min=1.0, max=100.0)
    environment_diffusion = FloatProperty(name="Environment Diffusion", description="Environment Diffusion",
                                          default=1.0, min=0.0, max=1.0)
    room = IntProperty(name="Room", description="Room",
                       default=-1000, min=-10000, max=0)
    room_hf = IntProperty(name="Room HF", description="Room High Frequency",
                          default=-100, min=-10000, max=0)
    room_lf = IntProperty(name="Room LF", description="Room Low Frequency",
                          default=0, min=-10000, max=0)
    decay_time = FloatProperty(name="Decay Time", description="Decay Time",
                               default=1.49, min=0.1, max=20.0)
    decay_hf_ratio = FloatProperty(name="Decay HF Ratio", description="Decay High Frequency Ratio",
                                   default=0.83, min=0.1, max=2.0)
    decay_lf_ratio = FloatProperty(name="Decay LF Ratio", description="Decay Low Frequency Ratio",
                                   default=1.0, min=0.1, max=2.0)
    reflections = IntProperty(name="Reflections", description="Reflections",
                              default=-2602, min=-10000, max=1000)
    reflections_delay = FloatProperty(name="Reflections Delay", description="Reflections Delay",
                                      default=0.007, min=0.0, max=0.3)
    reverb = IntProperty(name="Reverb", description="Reverb",
                         default=200, min=-10000, max=2000)
    reverb_delay = FloatProperty(name="Reverb Delay", description="Reverb Delay",
                                 default=0.011, min=0.0, max=0.3)
    echo_time = FloatProperty(name="Echo Time", description="Echo Time",
                              default=0.25, min=0.1, max=0.5)
    echo_depth = FloatProperty(name="Echo Depth", description="Echo Depth",
                               default=0.0, min=0.0, max=1.0)
    modulation_time = FloatProperty(name="Modulation Time", description="Modulation Time",
                                    default=0.25, min=0.1, max=5.0)
    modulation_depth = FloatProperty(name="Modulation Depth", description="Modulation Depth",
                                     default=0.0, min=0.0, max=1.0)
    air_absorption_hf = FloatProperty(name="Air Absorption HF", description="Air Absorption High Frequency",
                                      default=-5.0, min=-10.0, max=0.0)
    hf_reference = FloatProperty(name="HF reference", description="High Frequency Reference",
                                 default=5000.0, min=1000.0, max=20000.0)
    lf_reference = FloatProperty(name="LF reference", description="Low Frequency Reference",
                                 default=250.0, min=20.0, max=1000.0)

    # Room rolloff - always at 0 in all presets, so screw it.
    # room_rolloff_factor = FloatProperty(name="Room Rolloff Factor", description="Room Rolloff Factor",
                                        # default=0.0, min=0.0, max=1.0)

    flags = EnumProperty(name="Flags",
                         description="Reverb flags",
                         items=reverb_flags,
                         default={ "kFlagDecayTimeScale", "kFlagReflectionsScale", "kFlagReflectionsDelayScale",
                                   "kFlagReverbScale", "kFlagReverbDelayScale", "kFlagEchoTimeScale" },
                         options={"ENUM_FLAG"})

    def export(self, exporter, bo, so):
        eax_listener = exporter.mgr.find_create_object(plEAXListenerMod, so=so)
        eax_listener.softRegion = bo.plasma_modifiers.softvolume.get_key(exporter, so)
        if self.preset == "CUSTOM":
            # Someone's feeling exceedingly confident today...
            props = EAXReverbProperties()
            props.environment = 26
            props.environmentSize = self.environment_size
            props.environmentDiffusion = self.environment_diffusion
            props.room = self.room
            props.roomHF = self.room_hf
            props.roomLF = self.room_lf
            props.decayTime = self.decay_time
            props.decayHFRatio = self.decay_hf_ratio
            props.decayLFRatio = self.decay_lf_ratio
            props.reflections = self.reflections
            props.reflectionsDelay = self.reflections_delay
            props.reverb = self.reverb
            props.reverbDelay = self.reverb_delay
            props.echoTime = self.echo_time
            props.echoDepth = self.echo_depth
            props.modulationTime = self.modulation_time
            props.modulationDepth = self.modulation_depth
            props.airAbsorptionHF = self.air_absorption_hf
            props.hfReference = self.hf_reference
            props.lfReference = self.lf_reference
            flags = 0
            for flag in self.flags:
                flags |= getattr(EAXReverbProperties, flag)
            props.flags = flags
            eax_listener.listenerProps = props
        elif self.preset == "MORE":
            eax_listener.listenerProps = getattr(EAXReverbProperties, "REVERB_PRESET_" + self.preset_more)
        else:
            eax_listener.listenerProps = getattr(EAXReverbProperties, "REVERB_PRESET_" + self.preset)


class PlasmaSoftVolume(idprops.IDPropMixin, PlasmaModifierProperties):
    pl_id = "softvolume"

    bl_category = "Region"
    bl_label = "Soft Volume"
    bl_description = "Soft-Boundary Region"

    # Advanced
    use_nodes = BoolProperty(name="Use Nodes",
                             description="Make this a node-based Soft Volume",
                             default=False)
    node_tree = PointerProperty(name="Node Tree",
                                description="Node Tree detailing soft volume logic",
                                type=bpy.types.NodeTree)

    # Basic
    invert = BoolProperty(name="Invert",
                          description="Invert the soft region")
    inside_strength = IntProperty(name="Inside", description="Strength inside the region",
                                  subtype="PERCENTAGE", default=100, min=0, max=100)
    outside_strength = IntProperty(name="Outside", description="Strength outside the region",
                                   subtype="PERCENTAGE", default=0, min=0, max=100)
    soft_distance = FloatProperty(name="Distance", description="Soft Distance",
                                  default=0.0, min=0.0, max=500.0)

    def _apply_settings(self, sv):
        sv.insideStrength = self.inside_strength / 100.0
        sv.outsideStrength = self.outside_strength / 100.0

    def get_key(self, exporter, so=None):
        """Fetches the key appropriate for this Soft Volume"""
        if so is None:
            so = exporter.mgr.find_create_object(plSceneObject, bl=self.id_data)

        if self.use_nodes:
            tree = self.get_node_tree()
            output = tree.find_output("PlasmaSoftVolumeOutputNode")
            if output is None:
                raise ExportError("SoftVolume '{}' Node Tree '{}' has no output node!".format(self.key_name, tree.name))
            return output.get_key(exporter, so)
        else:
            pClass = plSoftVolumeInvert if self.invert else plSoftVolumeSimple
            return exporter.mgr.find_create_key(pClass, bl=self.id_data, so=so)

    def export(self, exporter, bo, so):
        if self.use_nodes:
            self._export_sv_nodes(exporter, bo, so)
        else:
            self._export_convex_region(exporter, bo, so)

    def _export_convex_region(self, exporter, bo, so):
        if bo.type != "MESH":
            raise ExportError("SoftVolume '{}': Simple SoftVolumes can only be meshes!".format(bo.name))

        # Grab the SoftVolume KO
        sv = self.get_key(exporter, so).object
        self._apply_settings(sv)

        # If "invert" was checked, we got a SoftVolumeInvert, but we need to make a Simple for the
        # region data to be exported into..
        if isinstance(sv, plSoftVolumeInvert):
            svSimple = exporter.mgr.find_create_object(plSoftVolumeSimple, bl=bo, so=so)
            self._apply_settings(svSimple)
            sv.addSubVolume(svSimple.key)
            sv = svSimple
        sv.softDist = self.soft_distance

        # Initialize the plVolumeIsect. Currently, we only support convex isects. If you want parallel
        # isects from empties, be my guest...
        with bmesh_from_object(bo) as mesh:
            matrix = bo.matrix_world
            xform = matrix.inverted()
            xform.transpose()

            # Ensure the normals always point inward. This is the same thing that
            # bpy.ops.normals_make_consistent(inside=True) does, just no need to change
            # into the edit mode context (EXPENSIVE!)
            bmesh.ops.recalc_face_normals(mesh, faces=mesh.faces)
            bmesh.ops.reverse_faces(mesh, faces=mesh.faces, flip_multires=True)

            isect = plConvexIsect()
            for ngon in mesh.faces:
                normal = xform * ngon.normal * -1
                normal.normalize()
                normal = hsVector3(*normal)
                for vertex in ngon.verts:
                    pos = matrix * vertex.co
                    isect.addPlane(normal, hsVector3(*pos))
            sv.volume = isect

    def _export_sv_nodes(self, exporter, bo, so):
        tree = self.get_node_tree()
        # Stash for later
        exporter.want_node_trees.setdefault(tree.name, set()).add((bo, so))

    def get_node_tree(self):
        if self.node_tree is None:
            raise ExportError("SoftVolume '{}' does not specify a valid Node Tree!".format(self.key_name))
        return self.node_tree

    @classmethod
    def _idprop_mapping(cls):
        return {"node_tree": "node_tree_name"}

    def _idprop_sources(self):
        return {"node_tree_name": bpy.data.node_groups}


class PlasmaSubworldRegion(PlasmaModifierProperties):
    pl_id = "subworld_rgn"

    bl_category = "Region"
    bl_label = "Subworld Region"
    bl_description = "Subworld transition region"

    subworld = PointerProperty(name="Subworld",
                               description="Subworld to transition into",
                               type=bpy.types.Object,
                               poll=idprops.poll_subworld_objects)
    transition = EnumProperty(name="Transition",
                              description="When to transition to the new subworld",
                              items=[("enter", "On Enter", "Transition when the avatar enters the region"),
                                     ("exit", "On Exit", "Transition when the avatar exits the region")],
                              default="enter",
                              options=set())

    def export(self, exporter, bo, so):
        # Due to the fact that our subworld modifier can produce both RidingAnimatedPhysical
        # and [HK|PX]Subworlds depending on the situation, this could get hairy, fast.
        # Start by surveying the lay of the land.
        from_sub, to_sub = bo.plasma_object.subworld, self.subworld
        from_isded = exporter.physics.is_dedicated_subworld(from_sub)
        to_isded = exporter.physics.is_dedicated_subworld(to_sub)
        if 1:
            def get_log_text(bo, isded):
                main = "[Main World]" if bo is None else bo.name
                sub = "Subworld" if isded or bo is None else "RidingAnimatedPhysical"
                return main, sub
            from_name, from_type = get_log_text(from_sub, from_isded)
            to_name, to_type = get_log_text(to_sub, to_isded)
            exporter.report.msg("Transition from '{}' ({}) to '{}' ({})",
                                 from_name, from_type, to_name, to_type,
                                 indent=2)

        # I think the best solution here is to not worry about the excitement mentioned above.
        # If we encounter anything truly interesting, we can fix it in CWE more easily IMO because
        # the game actually knows more about the avatar's state than we do here in the exporter.
        if to_isded or (from_isded and to_sub is None):
            region = exporter.mgr.find_create_object(plSubworldRegionDetector, so=so)
            if to_sub is not None:
                region.subworld = exporter.mgr.find_create_key(plSceneObject, bl=to_sub)
            region.onExit = self.transition == "exit"
        else:
            msg = plRideAnimatedPhysMsg()
            msg.BCastFlags |= plMessage.kLocalPropagate | plMessage.kPropagateToModifiers
            msg.sender = so.key
            msg.entering = to_sub is not None

            # In Cyan's PlasmaMAX RAP detector, it acts as more of a traditional region
            # that changes us over to a dynamic character controller on region enter and
            # reverts on region exit. We're going for an approach that is backwards compatible
            # with subworlds, so our enter/exit regions are separate. Here, enter/exit message
            # corresponds with when we should trigger the transition.
            region = exporter.mgr.find_create_object(plRidingAnimatedPhysicalDetector, so=so)
            if self.transition == "enter":
                region.enterMsg = msg
            elif self.transition == "exit":
                region.exitMsg = msg
            else:
                raise ExportAssertionError()

        # Fancy pants region collider type shit
        exporter.physics.generate_physical(bo, so, member_group="kGroupDetector",
                                           report_groups=["kGroupAvatar"])
