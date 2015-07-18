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
import inspect
from nodeitems_utils import NodeCategory, NodeItem
import nodeitems_utils

# Put all Korman node modules here...
from .node_avatar import *
from .node_conditions import *
from .node_core import *
from .node_logic import *
from .node_messages import *
from .node_python import *
from .node_responder import *

class PlasmaNodeCategory(NodeCategory):
    """Plasma Node Category"""

    @classmethod
    def poll(cls, context):
        return (context.space_data.tree_type == "PlasmaNodeTree")

# Here's what you need to know about this...
# If you add a new category, put the pretty name here!
# If you're making a new Node, ensure that your bl_idname attribute is present AND matches
#     the class name. Otherwise, absolutely fascinating things will happen. Don't expect for me
#     to come and rescue you from it, either.
_kategory_names = {
    "AVATAR": "Avatar",
    "CONDITIONS": "Conditions",
    "LOGIC": "Logic",
    "MSG": "Message",
    "PYTHON": "Python",
}

# Now, generate the categories as best we can...
_kategories = {}
for cls in dict(globals()).values():
    if inspect.isclass(cls):
        if not issubclass(cls, PlasmaNodeBase) or not issubclass(cls, bpy.types.Node):
            continue
    else:
        continue
    try:
        _kategories[cls.bl_category].append(cls)
    except LookupError:
        _kategories[cls.bl_category] = [cls,]
_actual_kategories = []
for i in sorted(_kategories.keys(), key=lambda x: _kategory_names[x]):
    # Note that even though we're sorting the category names, Blender appears to not care...
    _kat_items = [NodeItem(j.bl_idname) for j in sorted(_kategories[i], key=lambda x: x.bl_label)]
    _actual_kategories.append(PlasmaNodeCategory(i, _kategory_names[i], items=_kat_items))

def register():
    nodeitems_utils.register_node_categories("PLASMA_NODES", _actual_kategories)

def unregister():
    nodeitems_utils.unregister_node_categories("PLASMA_NODES")
