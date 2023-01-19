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


clothing_pfm = {
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
                                       type=bpy.types.Object,
                                       poll=idprops.poll_mesh_objects)
    clickable_region = PointerProperty(name="Region",
                                       description="Region to activate clickable.",
                                       type=bpy.types.Object,
                                       poll=idprops.poll_mesh_objects)
    clothing_sdl = StringProperty(name="SDL Variable",
                                  description="SDL variable associated with the clothing item.",
                                  options=set())
    clothing_show = BoolProperty(name="Show on true?",
                                 description="Have the clothing only appear when the SDL variable is true.",
                                 default=False,
                                 options=set())
    clothing_hair = BoolProperty(name="Changes hair color?",
                                 description="Should the hair change too?",
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
    clothing_tint1 = FloatVectorProperty(name="Tint 1",
                                         description="Sets the default color of the first tint in clothing.",
                                         subtype="COLOR",
                                         min=0.0, max=1.0,
                                         default=(1.0, 1.0, 1.0))
    clothing_tint2 = FloatVectorProperty(name="Tint 2",
                                         description="Sets the default color of the second tint in clothing.",
                                         subtype="COLOR",
                                         min=0.0, max=1.0,
                                         default=(1.0, 1.0, 1.0))
    clothing_stayvis = BoolProperty(name="Stay Visible After Click?",
                                    description="Should the clothing stay visible after first clicking?",
                                    default=False,
                                    options=set())

    def logicwiz(self, bo, tree):
        nodes = tree.nodes
        colortint1 = self.clothing_tint1
        colortint2 = self.clothing_tint2

        # Create Python File node
        clothingpynode = self._create_python_file_node(tree, clothing_pfm["filename"], clothing_pfm["attribs"])

        # Clickable
        clickable = nodes.new("PlasmaClickableNode")
        clickable.clickable_object = self.clickable_object
        for i in clickable.inputs:
            i.allow_simple = False
        clickable.link_output(clothingpynode, "satisfies", "actClickable")

        # Region
        clothingrgn = nodes.new("PlasmaClickableRegionNode")
        clothingrgn.region_object = self.clickable_region
        clothingrgn.link_output(clickable, "satisfies", "region")

        # SDL Variable
        clothingsdlvar = nodes.new("PlasmaAttribStringNode")
        clothingsdlvar.value = self.clothing_sdl
        clothingsdlvar.link_output(clothingpynode, "pfm", "stringVarName")

        # Show On True?
        clothingshow = nodes.new("PlasmaAttribBoolNode")
        clothingshow.value = self.clothing_show
        clothingshow.link_output(clothingpynode, "pfm", "boolShowOnTrue")

        # Hair color?
        clothinghair = nodes.new("PlasmaAttribBoolNode")
        clothinghair.value = self.clothing_hair
        clothinghair.link_output(clothingpynode, "pfm", "boolHasHairColor")

        # Chance SDL
        clothingchance = nodes.new("PlasmaAttribStringNode")
        clothingchance.value = self.clothing_chance
        clothingchance.link_output(clothingpynode, "pfm", "stringChanceSDLName")

        # Colors, man!
        clothingfemale = nodes.new("PlasmaAttribStringNode")
        clothingfemale.value = self.clothing_female
        clothingfemale.link_output(clothingpynode, "pfm", "stringFClothingName")

        clothingmale = nodes.new("PlasmaAttribStringNode")
        clothingmale.value = self.clothing_male
        clothingmale.link_output(clothingpynode, "pfm", "stringMClothingName")

        clothingred1 = nodes.new("PlasmaAttribIntNode")
        clothingred1.value_int = (255 * colortint1.r)
        clothingred1.link_output(clothingpynode, "pfm", "intTint1Red")

        clothinggreen1 = nodes.new("PlasmaAttribIntNode")
        clothinggreen1.value_int = (255 * colortint1.g)
        clothinggreen1.link_output(clothingpynode, "pfm", "intTint1Green")

        clothingblue1 = nodes.new("PlasmaAttribIntNode")
        clothingblue1.value_int = (255 * colortint1.b)
        clothingblue1.link_output(clothingpynode, "pfm", "intTint1Blue")

        clothingred2 = nodes.new("PlasmaAttribIntNode")
        clothingred2.value_int = (255 * colortint2.r)
        clothingred2.link_output(clothingpynode, "pfm", "intTint2Red")

        clothinggreen2 = nodes.new("PlasmaAttribIntNode")
        clothinggreen2.value_int = (255 * colortint2.g)
        clothinggreen2.link_output(clothingpynode, "pfm", "intTint2Green")

        clothingblue2 = nodes.new("PlasmaAttribIntNode")
        clothingblue2.value_int = (255 * colortint2.b)
        clothingblue2.link_output(clothingpynode, "pfm", "intTint2Blue")

        # Misc
        clothingvis = nodes.new("PlasmaAttribBoolNode")
        clothingvis.value = self.clothing_stayvis
        clothingvis.link_output(clothingpynode, "pfm", "boolStayVisible")

        clothingeval = nodes.new("PlasmaAttribBoolNode")
        clothingeval.value = False
        clothingeval.link_output(clothingpynode, "pfm", "boolFirstUpdate")
