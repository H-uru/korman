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
