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
from PyHSPlasma import *

from ...addon_prefs import game_versions
from .base import PlasmaModifierProperties, PlasmaModifierLogicWiz
from ...exporter import ExportError
from ... import idprops

class PlasmaVersionedNodeTree(idprops.IDPropMixin, bpy.types.PropertyGroup):
    version = EnumProperty(name="Version",
                           description="Plasma versions this node tree exports under",
                           items=game_versions,
                           options={"ENUM_FLAG"},
                           default=set(list(zip(*game_versions))[0]))
    node_tree = PointerProperty(name="Node Tree",
                                description="Node Tree to export",
                                type=bpy.types.NodeTree)

    @classmethod
    def _idprop_mapping(cls):
        return {"node_tree": "node_tree_name"}

    def _idprop_sources(self):
        return {"node_tree_name": bpy.data.node_groups}


class PlasmaAdvancedLogic(PlasmaModifierProperties):
    pl_id = "advanced_logic"

    bl_category = "Logic"
    bl_label = "Advanced"
    bl_description = "Plasma Logic Nodes"
    bl_icon = "NODETREE"

    logic_groups = CollectionProperty(type=PlasmaVersionedNodeTree)
    active_group_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        version = exporter.mgr.getVer()
        for i in self.logic_groups:
            our_versions = [globals()[j] for j in i.version]
            if version in our_versions:
                if i.node_tree is None:
                    raise ExportError("'{}': Advanced Logic is missing a node tree for '{}'".format(bo.name, i.name))

                # Defer node tree export until all trees are harvested.
                exporter.want_node_trees[i.node_tree.name].add((bo, so))

    def harvest_actors(self):
        actors = set()
        for i in self.logic_groups:
            if i.node_tree is not None:
                actors.update(i.node_tree.harvest_actors())
        return actors

    @property
    def requires_actor(self):
        return any((i.node_tree.requires_actor for i in self.logic_groups if i.node_tree))


class PlasmaSpawnPoint(PlasmaModifierProperties):
    pl_id = "spawnpoint"

    bl_category = "Logic"
    bl_label = "Spawn Point"
    bl_description = "Point at which avatars link into the Age"

    def export(self, exporter, bo, so):
        # Not much to this modifier... It's basically a flag that tells the engine, "hey, this is a
        # place the avatar can show up." Nice to have a simple one to get started with.
        spawn = exporter.mgr.add_object(pl=plSpawnModifier, so=so, name=self.key_name)

    @property
    def requires_actor(self):
        return True


class PlasmaMaintainersMarker(PlasmaModifierProperties):
    pl_id = "maintainersmarker"

    bl_category = "Logic"
    bl_label = "Maintainer's Marker"
    bl_description = "Designates an object as the D'ni coordinate origin point of the Age."
    bl_icon = "OUTLINER_DATA_EMPTY"

    calibration = EnumProperty(name="Calibration",
                               description="State of repair for the Marker",
                               items=[
                                  ("kBroken", "Broken",
                                   "A marker which reports scrambled coordinates to the KI."),
                                  ("kRepaired", "Repaired",
                                   "A marker which reports blank coordinates to the KI."),
                                  ("kCalibrated", "Calibrated",
                                   "A marker which reports accurate coordinates to the KI.")
                               ])

    def export(self, exporter, bo, so):
        maintmark = exporter.mgr.add_object(pl=plMaintainersMarkerModifier, so=so, name=self.key_name)
        maintmark.calibration = getattr(plMaintainersMarkerModifier, self.calibration)

    @property
    def requires_actor(self):
        return True


# Let's set up the xSimpleImager.py scripting
imager_pfms = {
    "filename": "xSimpleImager.py",
    "attribs": (
        { 'id':  1, 'type': "ptAttribString", 'name': "ImagerName" },
        { 'id':  2, 'type': "ptAttribDynamicMap", 'name': "ImagerMap" },
        { 'id':  3, 'type': "ptAttribActivator", 'name': "ImagerRegion" },
        { 'id':  4, 'type': "ptAttribInt", 'name': "ImagerTime" },
        { 'id':  5, 'type': "ptAttribBoolean", 'name': "ImagerMembersOnly" },
        { 'id':  6, 'type': "ptAttribSceneobject", 'name': "ImagerObject" },
        { 'id':  7, 'type': "ptAttribInt", 'name': "ImagerMax" },
        { 'id':  8, 'type': "ptAttribResponder", 'name': "ImagerButtonResp" },
        { 'id':  9, 'type': "ptAttribString", 'name': "ImagerInboxVariable" },
        { 'id': 10, 'type': "ptAttribBoolean", 'name': "ImagerPelletUpload" },
        { 'id': 11, 'type': "ptAttribSceneobject", 'name': "ImagerClueObject" },
        { 'id': 12, 'type': "ptAttribInt", 'name': "ImagerClueTime" },
        { 'id': 13, 'type': "ptAttribInt", 'name': "ImagerRandomTime" },
    )
}


pl_attrib = ("ptAttribMaterial", "ptAttribMaterialList",
             "ptAttribDynamicMap", "ptAttribMaterialAnimation")


class PlasmaImager(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "imager"

    bl_category = "Logic"
    bl_label = "Imager"
    bl_description = "Set up an imager for posting or visitor list."
    bl_icon = "IMAGE_DATA"

    # Shameless copy paste ahead.
    def _poll_material(self, value: bpy.types.Material) -> bool:
        # Don't filter materials by texture - this would (potentially) result in surprising UX
        # in that you would have to clear the texture selection before being able to select
        # certain materials.
        if self.imager_object is not None:
            object_materials = (slot.material for slot in self.imager_object.material_slots if slot and slot.material)
            return value in object_materials
        return True

    def _poll_texture(self, value: bpy.types.Texture) -> bool:
        if self.imager_material is not None:
            return value.name in self.imager_material.texture_slots
        elif self.imager_object is not None:
            for i in (slot.material for slot in self.imager_object.material_slots if slot and slot.material):
                if value in (slot.texture for slot in i.texture_slots if slot and slot.texture):
                    return True
            return False
        else:
            return True

    imager_name = StringProperty(name="Imager Name",
                                 description="Name of the imager referenced by KI and scripts (case sensitive for the latter).",
                                 options=set())
    imager_object = PointerProperty(name="Imager Object",
                                    description="Imager mesh object.",
                                    options=set(),
                                    type=bpy.types.Object,
                                    poll=idprops.poll_drawable_objects)
    imager_material = PointerProperty(name="Material",
                                      description="Material containing the imager texture.",
                                      type=bpy.types.Material,
                                      poll=_poll_material)
    imager_texture = PointerProperty(name="Texture",
                                     description="Texture slot used for the imager.",
                                     type=bpy.types.Texture,
                                     poll=_poll_texture)
    imager_type = EnumProperty(name="Imager Type",
                               description="Type of imager object will be.",
                               items=[("POSTABLE", "Postable", "Imager to post pictures and text."),
                                      ("VISITOR", "Visitor", "Imager to display visitors to your Age.")],
                               options=set())
    imager_region = PointerProperty(name="Imager Region (optional)",
                                    description="Activation region for postable imager.",
                                    options=set(),
                                    type=bpy.types.Object,
                                    poll=idprops.poll_mesh_objects)
    imager_time = IntProperty(name="Image View Time",
                              description="Number of seconds each image or text is viewed",
                              min=1, soft_max=10, default=10,
                              options=set())
    imager_membersonly = BoolProperty(name="Only Members Can Post?",
                                      description="Sets if the imager is only postable by members (false is recommended)",
                                      default=False,
                                      options=set())
    imager_maximum = IntProperty(name="Image Limit",
                                 description="Sets the maximum number of images and texts the imager can hold.",
                                 min=1, soft_max=10, default=10,
                                 options=set())
    imager_pellets = BoolProperty(name="Pellet Imager?",
                                  description="Enable if you'd like the imager to post and keep pellet scores.",
                                  default=False,
                                  options=set())
    imager_clueobject = PointerProperty(name="Clue Imager Object",
                                        description="Mesh Object that will pop up intermittently.",
                                        options=set(),
                                        type=bpy.types.Object,
                                        poll=idprops.poll_drawable_objects)
    imager_cluetime = IntProperty(name="Clue Time",
                                  description="Time the clue will appear in seconds.",
                                  min=1, soft_max=870, default=870,
                                  options=set())
    imager_randomtime = IntProperty(name="Randomizer Time",
                                    description="Time in seconds that will randomize the clue appearance.",
                                    min=0, soft_max=870, default=0,
                                    options=set())

    def logicwiz(self, bo, tree):
        nodes = tree.nodes

        imager_pfm = imager_pfms
        imagernode = self._create_python_file_node(tree, imager_pfm["filename"], imager_pfm["attribs"])
        self._create_imager_nodes(bo, tree.nodes, imagernode)


    def _create_imager_nodes(self, imager_object, nodes, imagernode):
        #Imager Name
        imagername = nodes.new("PlasmaAttribStringNode")
        imagername.value = self.imager_name
        imagername.link_output(imagernode, "pfm", "ImagerName")

        # Texture
        imagertext = nodes.new("PlasmaAttribTextureNode")
        imagertext.target_object = self.imager_object
        imagertext.material = self.imager_material
        imagertext.texture = self.imager_texture
        imagertext.link_output(imagernode, "pfm", "ImagerMap")

        # Region Object if we want one
        if self.imager_region and self.imager_type == "POSTABLE":
            imagerregion = nodes.new("PlasmaVolumeSensorNode")
            imagerregion.region_object = self.imager_region
            for i in imagerregion.inputs:
                i.allow = True
            imagerregion.link_output(imagernode, "satisfies", "ImagerRegion")

        # Seconds between posts
        imagersec = nodes.new("PlasmaAttribIntNode")
        imagersec.value_int = self.imager_time
        imagersec.link_output(imagernode, "pfm", "ImagerTime")

        # Members only?
        imagermember = nodes.new("PlasmaAttribBoolNode")
        if self.imager_type == "POSTABLE":
            imagermember.value = self.imager_membersonly
        else:
            imagermember.value = True
        imagermember.link_output(imagernode, "pfm", "ImagerMembersOnly")

        # Imager Mesh Object
        imagerobject = nodes.new("PlasmaAttribObjectNode")
        imagerobject.target_object = self.imager_object
        imagerobject.link_output(imagernode, "pfm", "ImagerObject")

        # Maximum Images
        imagermax = nodes.new("PlasmaAttribIntNode")
        imagermax.value_int = self.imager_maximum
        imagermax.link_output(imagernode, "pfm", "ImagerMax")

        # Optional SDL placeholder (needed?)
        if self.imager_type == "POSTABLE":
            imagersdl = nodes.new("PlasmaAttribStringNode")
            imagersdl.link_output(imagernode, "pfm", "ImagerInboxVariable")

        # Pellet Imager?
        imagerpellet = nodes.new("PlasmaAttribBoolNode")
        if self.imager_type == "POSTABLE":
            imagerpellet.value = self.imager_pellets
        else:
            imagerpellet.value = False
        imagerpellet.link_output(imagernode, "pfm", "ImagerPelletUpload")

        # Puzzle Imager Object if we have one
        if self.imager_clueobject and self.imager_type == "POSTABLE":
            imagerclueobj = nodes.new("PlasmaAttribObjectNode")
            imagerclueobj.target_object = self.imager_clueobject
            imagerclueobj.link_output(imagernode, "pfm", "ImagerClueObject")

            # Clue Time
            imagercluetime = nodes.new("PlasmaAttribIntNode")
            imagercluetime.value_int = self.imager_cluetime
            imagercluetime.link_output(imagernode, "pfm", "ImagerClueTime")

            # Random Clue Time
            imagerrandomtime = nodes.new("PlasmaAttribIntNode")
            imagerrandomtime.value_int = self.imager_randomtime
            imagerrandomtime.link_output(imagernode, "pfm", "ImagerRandomTime")
