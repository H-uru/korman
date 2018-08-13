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
import time

from ..ordered_set import OrderedSet
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
        theMod.created()

        # Determine if this modifier has any dependencies and make sure they're enabled
        deps = getattr(theMod, "pl_depends", set())
        for dep in deps:
            depMod = getattr(plmods, dep)
            if not depMod.enabled:
                bpy.ops.object.plasma_modifier_add(types=dep)
        return {"FINISHED"}


class ModifierRemoveOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_remove"
    bl_label = "Remove Modifier"
    bl_description = "Removes this Plasma Modifier"

    active_modifier = IntProperty(name="Modifier Display Order",
                                  default=-1,
                                  options={"HIDDEN"})

    mods2delete = CollectionProperty(type=modifiers.PlasmaModifierSpec, options=set())

    def draw(self, context):
        layout = self.layout
        mods = context.object.plasma_modifiers

        layout.label("This action will remove the following modifiers:")
        layout = layout.column_flow(align=True)
        for i in self.mods2delete:
            mod = getattr(mods, i.name)
            layout.label("    {}".format(mod.bl_label), icon=getattr(mod, "bl_icon", "NONE"))

    def execute(self, context):
        want2delete = set((i.name for i in self.mods2delete))
        mods = sorted(context.object.plasma_modifiers.modifiers, key=lambda x: x.display_order)
        subtract = 0

        for mod in mods:
            if mod.pl_id in want2delete:
                mod.display_order = -1
                mod.destroyed()
                subtract += 1
            else:
                mod.display_order -= subtract
        return {"FINISHED"}

    def invoke(self, context, event):
        assert self.active_modifier >= -1
        mods = context.object.plasma_modifiers
        self.mods2delete.clear()

        want2delete = OrderedSet()
        for i in mods.modifiers:
            if i.display_order == self.active_modifier:
                want2delete.add(i.pl_id)
                break
        else:
            raise IndexError()

        # Here's the rub
        # When we start, we should have just one modifier in want2delete
        # HOWEVER, the mod may have dependencies, which in turn may have more deps
        # So we collect them into the list... you dig?
        for i in want2delete:
            for mod in modifiers.PlasmaModifierProperties.__subclasses__():
                if not getattr(mods, mod.pl_id).enabled:
                    continue
                if i in getattr(mod, "pl_depends", set()):
                    want2delete.add(mod.pl_id)
        for i in want2delete:
            mod = self.mods2delete.add()
            mod.name = i

        if len(want2delete) == 1:
            return self.execute(context)
        else:
            return context.window_manager.invoke_props_dialog(self)


class ModifierResetOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_reset"
    bl_label = "Reset the modifier to its default state?"
    bl_description = "Reset the modifier to its default state"

    active_modifier = IntProperty(name="Modifier Display Order",
                                  default=-1,
                                  options={"HIDDEN"})

    def draw(self, context):
        pass

    def execute(self, context):
        assert self.active_modifier >= 0
        for i in context.object.plasma_modifiers.modifiers:
            if i.display_order == self.active_modifier:
                mod = i
                break
        else:
            raise IndexError(self.active_modifier)

        props = set(mod.keys()) - {"display_order", "display_name"}
        for i in props:
            mod.property_unset(i)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


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


class ModifierLogicWizOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_logicwiz"
    bl_label = "Plasma LogicWiz"
    bl_description = "Generates logic nodes from a given modifier on the active object"

    modifier = StringProperty(name="Modifier", default="footstep")

    def execute(self, context):
        obj = context.active_object
        mod = getattr(obj.plasma_modifiers, self.modifier)

        print("--- Plasma LogicWiz ---")
        print("Object: '{}'".format(obj.name))
        print("Modifier: '{}'".format(self.modifier))
        if not mod.enabled:
            print("WRN: This modifier is not actually enabled!")

        start = time.process_time()
        mod.logicwiz(obj)
        end = time.process_time()
        print("\nLogicWiz finished in {:.2f} seconds".format(end-start))
        return {"FINISHED"}
