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

from ..properties import modifiers

def _fetch_modifiers():
    items = []

    mapping = modifiers.modifier_mapping()
    for i in sorted(mapping.keys()):
        items.append(("", i, ""))
        items.extend(mapping[i])
        #yield ("", i, "")
        #yield mapping[i]
    return items

class ModifierOperator:
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class ModifierAddOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_add"
    bl_label = "Add Modifier"
    bl_description = "Adds a Plasma Modifier"

    types = EnumProperty(name="Modifier Type",
                         description="The type of modifier we add to the list",
                         items=_fetch_modifiers())

    def execute(self, context):
        plmods = context.object.plasma_modifiers
        myType = self.types
        theMod = getattr(plmods, myType)

        theMod.display_order = plmods.determine_next_id()
        theMod.created(context.object)
        return {"FINISHED"}


class ModifierRemoveOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_remove"
    bl_label = "Remove Modifier"
    bl_description = "Removes this Plasma Modifier"

    active_modifier = IntProperty(name="Modifier Display Order",
                                  default=-1,
                                  options={"HIDDEN"})

    def execute(self, context):
        assert self.active_modifier >= 0

        for mod in context.object.plasma_modifiers.modifiers:
            if mod.display_order == self.active_modifier:
                mod.display_order = -1
                mod.destroyed()
            elif mod.display_order > self.active_modifier:
                mod.display_order -= 1
        return {"FINISHED"}


class ModifierMoveOperator(ModifierOperator):
    def swap_modifier_ids(self, mods, s1, s2):
        done = 0
        for mod in mods.modifiers:
            if mod.display_order == s1:
                mod.display_order = s2
                done += 1
            elif mod.display_order == s2:
                mod.display_order = s1
                done += 1
            if done == 2:
                break


class ModifierMoveUpOperator(ModifierMoveOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_move_up"
    bl_label = "Move Up"
    bl_description = "Move the modifier up in the stack"

    active_modifier = IntProperty(name="Modifier Display Order",
                                  default=-1,
                                  options={"HIDDEN"})

    def execute(self, context):
        assert self.active_modifier >= 0
        if self.active_modifier > 0:
            plmods = context.object.plasma_modifiers
            self.swap_modifier_ids(plmods, self.active_modifier, self.active_modifier-1)
        return {"FINISHED"}


class ModifierMoveDownOperator(ModifierMoveOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_move_down"
    bl_label = "Move Down"
    bl_description = "Move the modifier down in the stack"

    active_modifier = IntProperty(name="Modifier Display Order",
                                  default=-1,
                                  options={"HIDDEN"})

    def execute(self, context):
        assert self.active_modifier >= 0

        plmods = context.object.plasma_modifiers
        last = max([mod.display_order for mod in plmods.modifiers])
        if self.active_modifier < last:
            self.swap_modifier_ids(plmods, self.active_modifier, self.active_modifier+1)
        return {"FINISHED"}
