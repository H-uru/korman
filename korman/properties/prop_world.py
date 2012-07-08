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

class PlasmaFni(bpy.types.PropertyGroup):
    bl_idname = "world.plasma_fni"

    fog_color = FloatVectorProperty(name="Fog Color",
                                    description="The default fog color used in your age",
                                    default=(0.3, 0.2, 0.05),
                                    subtype="COLOR")
    clear_color = FloatVectorProperty(name="Clear Color",
                                      description="The default background color rendered in your age",
                                      subtype="COLOR")
    yon = IntProperty(name="Draw Distance",
                      description="The distance (in feet) Plasma will draw",
                      default=100000,
                      soft_min=100,
                      min=1)
    # TODO: density

class PlasmaPage(bpy.types.PropertyGroup):
    def _check_suffix(self, context):
        """Verifies that a suffix change does not conflict"""
        old = self.last_seq_suffix
        self.last_seq_suffix = self.seq_suffix
        if not self.check_suffixes:
            return None

        for page in context.world.plasma_age.pages:
            if page.seq_suffix == self.seq_suffix and page != self:
                # Need to supress checking while we override the suffix
                page.check_suffixes = False
                page.seq_suffix = old
                page.check_suffixes = True
                break
        return None

    def _rename_page(self, context):
        # Need to init?
        if self.last_name == "" and self.name:
            self.last_name = self.name
            return None

        # Empty page names not allowed!
        if self.name == "":
            self.make_default_name(self.seq_suffix)
            return None

        # Since many objects will have page names attached to them, we'll be
        # very nice and handle renames for the user.
        for obj in bpy.data.objects:
            if obj.plasma_object.page == self.last_name:
                obj.plasma_object.page = self.name
        self.last_name = self.name
        return None

    def make_default_name(self, suffix):
        self.seq_suffix = suffix
        self.name = "Page%02i" % suffix
        self.check_suffixes = True

    name = StringProperty(name="Name",
                          description="Name of the specified page",
                          update=_rename_page)
    seq_suffix = IntProperty(name="ID",
                             description="A numerical ID for this page",
                             soft_min=0, # Negatives indicate global--advanced users only
                             default=0, # The add operator will autogen a default
                             update=_check_suffix)
    auto_load = BoolProperty(name="Auto Load",
                             description="Load this page on link-in",
                             default=True)

    # Implementation details...
    last_name = StringProperty(description="INTERNAL: Cached page name",
                               options={"HIDDEN"})
    last_seq_suffix = IntProperty(description="INTERNAL: Cached sequence suffix",
                                  options={"HIDDEN"})
    check_suffixes = BoolProperty(description="INTERNAL: Should we sanity-check suffixes?",
                                  options={"HIDDEN"},
                                  default=False)


class PlasmaAge(bpy.types.PropertyGroup):
    day_length = FloatProperty(name="Day Length",
                               description="Length of a day (in hours) on this age",
                               default=24.0,
                               soft_min=0.1,
                               min=0.0)
    seq_prefix = IntProperty(name="Sequence Prefix",
                             description="A unique numerical ID for this age",
                             soft_min=0, # Negative indicates global--advanced users only
                             default=100)
    pages = CollectionProperty(name="Pages",
                               description="Registry pages for this age",
                               type=PlasmaPage)

    # Implementation details
    active_page_index = IntProperty(name="Active Page Index")