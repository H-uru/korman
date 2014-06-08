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

class PlasmaObject(bpy.types.PropertyGroup):
    def _enabled(self, context):
        # This makes me sad
        if not self.is_inited:
            self._init(context)
            self.is_inited = True

    def _init(self, context):
        o = context.object
        age = context.scene.world.plasma_age

        # We want to encourage the pages = layers paradigm.
        # So, let's see which layers we're on and check for a page whose
        #    suffix matches our layers. We'll take the first match.
        num_layers = len(o.layers)
        for page in age.pages:
            if page.seq_suffix > num_layers:
                continue
            if o.layers[page.seq_suffix - 1]:
                o.plasma_object.page = page.name
                break

    def export(self, exporter, bl_obj):
        """Plasma Object Export"""

        # This is where the magic happens...
        if self.enabled:
            # TODO: Something more useful than a blank object.
            exporter.mgr.add_object(plSceneObject, bl=bl_obj)


    enabled = BoolProperty(name="Export",
                           description="Export this as a discrete object",
                           default=False,
                           update=_enabled)
    page = StringProperty(name="Page",
                          description="Page this object will be exported to")

    # Implementation Details
    is_inited = BoolProperty(description="INTERNAL: Init proc complete",
                             default=False,
                             options={"HIDDEN"})
