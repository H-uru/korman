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

import itertools
import time
from typing import *

from ..properties import modifiers
from ..helpers import find_modifier

class ModifierOperator:
    def _get_modifier(self, context) -> modifiers.PlasmaModifierProperties:
        if self.active_modifier == -1:
            return None
        pl_mods = context.object.plasma_modifiers.modifiers
        pl_mod = next((i for i in pl_mods if self.active_modifier == i.display_order), None)
        if pl_mod is None:
            raise IndexError(self.active_modifier)
        return pl_mod

    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class ModifierAddOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_add"
    bl_label = "Add Modifier"
    bl_description = "Adds a Plasma Modifier"

    def _fetch_modifiers(self, context):
        items = []

        def filter_mod_name(mod):
            # The modifier might include the cateogry name in its name, so we'll strip that.
            if mod.bl_label != mod.bl_category:
                if mod.bl_label.startswith(mod.bl_category):
                    return mod.bl_label[len(mod.bl_category)+1:]
                if mod.bl_label.endswith(mod.bl_category):
                    return mod.bl_label[:-len(mod.bl_category)-1]
            return mod.bl_label

        sorted_modifiers = sorted(
            modifiers.PlasmaModifierProperties.__subclasses__(),
            key=lambda x: f"{x.bl_category} - {filter_mod_name(x)}"
        )
        last_category = None
        for i, mod in enumerate(sorted_modifiers):
            # Some modifiers aren't permissible in certain situations. Hide them.
            if not find_modifier(context.object, mod.pl_id).allowed:
                continue
            if mod.bl_category != last_category:
                items.append(("", mod.bl_category, ""))
                last_category = mod.bl_category
            items.append(
                (mod.pl_id, filter_mod_name(mod), mod.bl_description,
                getattr(mod, "bl_icon", ""), i)
            )

        return items

    types = EnumProperty(
        name="Modifier Type",
        description="The type of modifier we add to the list",
        items=_fetch_modifiers
    )

    def execute(self, context):
        modifier = getattr(context.object.plasma_modifiers, self.types)
        modifier.enabled = True

        return {"FINISHED"}


class ModifierClipboard:
    def _paste_modifier(self, src_object, dst_object, pl_mod_id):
        src_mod = getattr(src_object.plasma_modifiers, pl_mod_id)
        dst_mod = getattr(dst_object.plasma_modifiers, pl_mod_id)

        if not src_mod.enabled:
            return

        # The modifier index needs to be refigured, otherwise, bad things will happen
        # when the user tries to use the modifier operators again.
        mod_id = dst_object.plasma_modifiers.determine_next_id()

        # NOTE: Usage of keys vs items is intentional because the value returned by items may
        #       not be accepted as a valid type for assignment. Sounds like a blender bug IMO.
        for i in src_mod.rna_type.properties:
            self._paste_property(src_mod, dst_mod, i)

        # See above, ensure no id collisions
        dst_mod.display_order = mod_id

    def _paste_property(self, src, dst, prop):
        prop_name = prop.identifier
        if prop_name in {"rna_type"}:
            return

        # Old properties? Discard their asses.
        if not hasattr(dst, prop_name):
            return

        # Collection and pointer properties must be manually copied...
        if prop.type == "COLLECTION":
            dst_prop, src_prop = getattr(dst, prop_name), getattr(src, prop_name)
            dst_prop.clear()
            for src_item in src_prop:
                dst_item = dst_prop.add()
                for item_prop in src_item.rna_type.properties:
                    self._paste_property(src_item, dst_item, item_prop)
        elif prop.type == "POINTER" and prop.fixed_type.base.name != "ID":
            dst_prop, src_prop = getattr(dst, prop_name), getattr(src, prop_name)
            for subprop_name in src_prop.rna_type.properties:
                self._paste_property(src_prop, dst_prop, subprop_name)
        else:
            try:
                if src.is_property_set(prop_name):
                    setattr(dst, prop_name, getattr(src, prop_name))
                else:
                    dst.property_unset(prop_name)
            except AttributeError:
                pass


class ModifierCopyOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_copy"
    bl_label = "Copy Modifiers"
    bl_description = "Copy Modifiers from an Object"

    active_modifier = IntProperty(name="Modifier Display Order",
                                  default=-1,
                                  options={"HIDDEN"})

    def execute(self, context):
        pl_scene = context.scene.plasma_scene
        pl_scene.modifier_copy_object = context.object
        pl_mod = self._get_modifier(context)
        if pl_mod is None:
            pl_scene.property_unset("modifier_copy_id")
        else:
            pl_scene.modifier_copy_id = pl_mod.pl_id
        return {"FINISHED"}


class ModifierCopyToOperator(ModifierClipboard, ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_copy_to_selection"
    bl_label = "Copy Modifiers to Selection"
    bl_description = "Copy Modifiers from the active Object to all selected Objects"

    def _iter_objects(self, context):
        for i in context.selected_objects:
            if i != context.active_object:
                yield i

    def execute(self, context):
        if not any(self._iter_objects(context)):
            self.report({"WARNING"}, "No objects are selected to copy to.")
            return {"CANCELLED"}
        for i in self._iter_objects(context):
            for mod_cls in modifiers.PlasmaModifierProperties.__subclasses__():
                self._paste_modifier(context.active_object, i, mod_cls.pl_id)
        self.report({"INFO"}, "Copied Plasma Modifers to selection.")
        return {"FINISHED"}


class ModifierPasteOperator(ModifierClipboard, ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_paste"
    bl_label = "Paste Modifier"
    bl_description = "Paste Modifier(s) to another Object"

    def execute(self, context):
        pl_scene = context.scene.plasma_scene
        if not pl_scene.is_property_set("modifier_copy_object"):
            raise RuntimeError()

        dst_object, src_object = context.object, pl_scene.modifier_copy_object
        pl_mod_id = pl_scene.modifier_copy_id

        if pl_mod_id:
            self._paste_modifier(src_object, dst_object, pl_mod_id)
        else:
            for mod_cls in modifiers.PlasmaModifierProperties.__subclasses__():
                self._paste_modifier(src_object, dst_object, mod_cls.pl_id)
        return {"FINISHED"}

    @classmethod
    def poll(cls, context):
        pl_scene = context.scene.plasma_scene
        return super().poll(context) and pl_scene.is_property_set("modifier_copy_object")


class ModifierRemoveOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_remove"
    bl_label = "Remove Modifier"
    bl_description = "Removes this Plasma Modifier"

    active_modifier = IntProperty(
        name="Modifier Display Order",
        default=-1,
        options={"HIDDEN"}
    )

    def draw(self, context):
        layout = self.layout
        pl_mods = context.object.plasma_modifiers
        mod = self._get_modifier(context)
        mods_to_delete = itertools.chain(
            (getattr(pl_mods, i) for i in mod.get_dependents()),
            [mod]
        )

        layout.label("This action will remove the following modifiers:")
        layout = layout.column_flow(align=True)
        for mod in filter(lambda x: x.enabled, mods_to_delete):
            layout.label(f"    {mod.bl_label}", icon=getattr(mod, "bl_icon", "NONE"))

    def execute(self, context):
        self._get_modifier(context).enabled = False
        return {"FINISHED"}

    def invoke(self, context, event):
        has_dependents = any(
            getattr(context.object.plasma_modifiers, i).enabled
            for i in self._get_modifier(context).get_dependents()
        )
        if not has_dependents:
            return self.execute(context)
        else:
            return context.window_manager.invoke_props_dialog(self)


class ModifierResetOperator(ModifierOperator, bpy.types.Operator):
    bl_idname = "object.plasma_modifier_reset"
    bl_label = "Reset the modifier(s) to the default state?"
    bl_description = "Reset the modifier(s) to the default state"

    active_modifier = IntProperty(name="Modifier Display Order",
                                  default=-1,
                                  options={"HIDDEN"})

    def draw(self, context):
        pass

    def execute(self, context):
        if self.active_modifier == -1:
            for i in context.object.plasma_modifiers.modifiers:
                self._reset(i)
        else:
            self._reset(self._get_modifier(context))
        return {"FINISHED"}

    def _reset(self, modifier):
        props = set(modifier.keys()) - {"display_order", "display_name"}
        for i in props:
            modifier.property_unset(i)

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
        mod.create_logic(obj)
        end = time.process_time()
        print("\nLogicWiz finished in {:.2f} seconds".format(end-start))
        return {"FINISHED"}
