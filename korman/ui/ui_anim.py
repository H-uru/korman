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

from . import ui_list

class AnimListUI(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        layout.label(item.animation_name, icon="ANIM")


def draw_multi_animation(layout, context_attr, prop_base, anims_collection_name, *, use_box=False, **kwargs):
    # Yeah, I know this looks weird, but it lets us pretend that the PlasmaAnimationCollection
    # is a first class collection property. Fancy.
    anims = getattr(prop_base, anims_collection_name)
    kwargs.setdefault("rows", 2)
    ui_list.draw_list(layout, "AnimListUI", context_attr, anims,
                        "animation_collection", "active_animation_index",
                        name_prop="animation_name", name_prefix="Animation",
                        **kwargs)
    try:
        anim = anims.animation_collection[anims.active_animation_index]
    except IndexError:
        pass
    else:
        sub = layout.box() if use_box else layout
        draw_single_animation(sub, anim)

def draw_single_animation(layout, anim):
    row = layout.row()
    row.enabled = not anim.is_entire_animation
    row.prop(anim, "animation_name", text="Name", icon="ANIM")

    split = layout.split()
    col = split.column()
    col.label("Playback Settings:")
    col.prop(anim, "auto_start")
    col.prop(anim, "loop")
    col = split.column(align=True)
    col.label("Animation Range:")
    col.enabled = not anim.is_entire_animation
    # Not alerting on exceeding the range of the keyframes - that may be intentional.
    col.alert = anim.start >= anim.end
    col.prop(anim, "start")
    col.prop(anim, "end")

    # Only doing this crap for object animations, FTS on material animations.
    if isinstance(anim.id_data, bpy.types.Object):
        action = getattr(anim.id_data.animation_data, "action", None)
        if action:
            layout.separator()
            layout.prop_search(anim, "initial_marker", action, "pose_markers", icon="PMARKER")
            col = layout.column()
            col.active = anim.loop and not anim.sdl_var
            col.prop_search(anim, "loop_start", action, "pose_markers", icon="PMARKER")
            col.prop_search(anim, "loop_end", action, "pose_markers", icon="PMARKER")

    layout.separator()
    layout.prop(anim, "sdl_var")
