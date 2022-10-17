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
from .base import PlasmaModifierProperties
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


clothing_pfms = {
    "filename": "xTakableClothing.py",
    "attribs": (
        { 'id':  1, 'type': "ptAttribString", 'name': "stringVarName" },
        { 'id':  2, 'type': "ptAttribBoolean", 'name': "boolShowOnTrue" },
        { 'id':  3, 'type': "ptAttribActivator", 'name': "actClickable" },
        { 'id':  4, 'type': "ptAttribString", 'name': "stringFClothingName" },
        { 'id':  5, 'type': "ptAttribString", 'name': "stringMClothingName" },
        { 'id':  6, 'type': "ptAttribBoolean", 'name': "boolHasHairColor" },
        { 'id':  7, 'type': "ptAttribString", 'name': "stringChanceSDLName" },
        { 'id':  8, 'type': "ptAttribInt", 'name': "intTint1Red" },
        { 'id':  9, 'type': "ptAttribInt", 'name': "intTint1Green" },
        { 'id': 10, 'type': "ptAttribInt", 'name': "intTint1Blue" },
        { 'id': 11, 'type': "ptAttribInt", 'name': "intTint2Red" },
        { 'id': 12, 'type': "ptAttribInt", 'name': "intTint2Green" },
        { 'id': 13, 'type': "ptAttribInt", 'name': "intTint2Blue" },
        { 'id': 14, 'type': "ptAttribBoolean", 'name': "boolStayVisible" },
        { 'id': 15, 'type': "ptAttribBoolean", 'name': "boolFirstUpdate" },
    )
}


class PlasmaTakeClothing(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "clothing"

    bl_category = "Logic"
    bl_label = "Takable Clothing"
    bl_description = "Set up clickable mesh for a collectable clothing item."
    bl_icon = "POSE_HLT"

    clickable_object = PointerProperty(name="Clickable",
                                       description="Clickable mesh object for clothing item.",
                                       options=set(),
                                       type=bpy.types.Object,
                                       poll=idprops.poll_mesh_objects)
    clickable_region = PointerProperty(name="Region",
                                       description="Region to activate clickable.",
                                       options=set(),
                                       type=bpy.types.Object,
                                       poll=idprops.poll_mesh_objects)
    clothing_sdl = StringProperty(name="SDL Variable",
                                  description="SDL variable associated with the clothing item.",
                                  options=set())
    clothing_show = BoolProperty(name="Show on true?",
                                 description="Have the clothing only appear when the SDL variable is true.",
                                 default=False,
                                 options=set())
    clothing_male = StringProperty(name="Male ID",
                                   description="ID name for male version of clothing.",
                                   options=set())
    clothing_female = StringProperty(name="Female ID",
                                     description="ID name for female version of clothing.",
                                     options=set())
    clothing_chance = StringProperty(name="Chance SDL (optional)",
                                     description="SDL variable for chance appearance of clothing.",
                                     options=set())
    clothing_tint1red = IntProperty(name="Tint 1 Red",
                                    description="Red setting for first tint.",
                                    min=0, max=255, default=255,
                                    options=set())
    clothing_tint1green = IntProperty(name="Tint 1 Green",
                                    description="Green setting for first tint.",
                                    min=0, max=255, default=255,
                                    options=set())
    clothing_tint1blue = IntProperty(name="Tint 1 Blue",
                                    description="Blue setting for first tint.",
                                    min=0, max=255, default=255,
                                    options=set())
    clothing_tint2on = BoolProperty(name="Second Tint?",
                                    description="Does the clothing item have a second tint color?",
                                    default=False,
                                    options=set())
    clothing_tint2red = IntProperty(name="Tint 2 Red",
                                    description="Red setting for second tint.",
                                    min=0, max=255, default=255,
                                    options=set())
    clothing_tint2green = IntProperty(name="Tint 2 Green",
                                    description="Green setting for second tint.",
                                    min=0, max=255, default=255,
                                    options=set())
    clothing_tint2blue = IntProperty(name="Tint 2 Blue",
                                    description="Blue setting for second tint.",
                                    min=0, max=255, default=255,
                                    options=set())
    clothing_stayvis = BoolProperty(name="Stay Visible After Click?",
                                    description="Should the clothing stay visible after first clicking?",
                                    default=False,
                                    options=set())

    def logicwiz(self, bo, tree):
        nodes = tree.nodes

        clothing_pfm = clothing_pfms
        clothingnode = self._create_python_file_node(tree, clothing_pfm["filename"], clothing_pfm["attribs"])
        self._create_clothing_nodes(bo, tree.nodes, imagernode)

    def _create_clothing_node(self, clickable_object, nodes, clothingnode):
        # Clickable
        clickable = nodes.new("PlasmaClickableNode")
        clickable.clickable_object = self.clickable_object
        clickable.allow_simple = False
        clickable.link_output(clothingnode, "satisfies", "actClickable")

        # Region
        clothingrgn = nodes.new("PlasmaClickableRegionNode")
        clothingrgn.region_object = self.clickable_region
        clothingrgn.link_output(clickable, "satisfies", "region")

        # SDL Variable
        clothingsdlvar = nodes.new("PlasmaAttribStringNode")
        clothingsdlvar.value = self.clothing_sdl
        clothingsdlvar.link_output(clothingnode, "pfm", "stringVarName")

        # Show On True?
        clothingshow = nodes.new("PlasmaAttribBoolNode")
        clothingshow.value = self.clothing_show
        clothingshow.link_output(clothingnode, "pfm", "boolShowOnTrue")

        clothingfemale = nodes.new("PlasmaAttribStringNode")
        clothingfemale.value = self.clothing_female
        clothingfemale.link_output(clothingnode, "pfm", "stringFClothingName")

        clothingmale = nodes.new("PlasmaAttribStringNode")
        clothingmale.value = self.clothing_male
        clothingmale.link_output(clothingnode, "pfm", "stringMClothingName")

        clothingred1 = nodes.new("PlasmaAttribIntNode")
        clothingred1.value_int = clothing_tint1red
        clothingred1.link_output(clothingnode, "pfm", "intTint1Red")

        clothinggreen1 = nodes.new("PlasmaAttribIntNode")
        clothinggreen1.value_int = clothing_tint1green
        clothinggreen1.link_output(clothingnode, "pfm", "intTint1Green")

        clothingblue1 = nodes.new("PlasmaAttribIntNode")
        clothingblue1.value_int = clothing_tint1blue
        clothingblue1.link_output(clothingnode, "pfm", "intTint1Blue")

        clothingred2 = nodes.new("PlasmaAttribIntNode")
        clothingred2.value_int = clothing_tint2red
        clothingred2.link_output(clothingnode, "pfm", "intTint2Red")

        clothinggreen2 = nodes.new("PlasmaAttribIntNode")
        clothinggreen2.value_int = clothing_tint2green
        clothinggreen2.link_output(clothingnode, "pfm", "intTint2Green")

        clothingblue2 = nodes.new("PlasmaAttribIntNode")
        clothingblue2.value_int = clothing_tint2blue
        clothingblue2.link_output(clothingnode, "pfm", "intTint2Blue")

        clothingvis = nodes.new("PlasmaAttribBoolNode")
        clothingvis.value = self.clothing_stayvis
        clothingvis.link_output(clothingnode, "pfm", "boolStayVisible")

        clothingeval = nodes.new("PlasmaAttribBoolNode")
        clothingeval.value = False
        clothingeval.link_output(clothingnode, "pfm", "boolFirstUpdate")

