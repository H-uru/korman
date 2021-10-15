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
import itertools
import pickle


class NodeOperator:
    @classmethod
    def poll(cls, context):
        return context.scene.render.engine == "PLASMA_GAME"


class CreateLinkNodeOperator(NodeOperator, bpy.types.Operator):
    bl_idname = "node.plasma_create_link_node"
    bl_label = "Create Node"
    bl_description = "Create and link a new node to this socket"
    bl_options = {"UNDO", "INTERNAL"}
    bl_property = "node_item"

    node_name = StringProperty()
    sock_ident = StringProperty()
    is_output = BoolProperty()

    # The "official" node search operator does something like this...
    # Documentation seems to indicate this works around poor refcounting.
    _hack = []

    def _link_search_list(self, context):
        CreateLinkNodeOperator._hack = list(
            CreateLinkNodeOperator._link_search_list_imp(self, context)
        )
        return CreateLinkNodeOperator._hack

    def _link_search_list_imp(self, context):
        # NOTE: `self` is not actually an instance of this class. It's a fancy wrapper object
        # whose only members are the above properties...
        tree = context.space_data.edit_tree
        src_node = tree.nodes[self.node_name]
        src_socket = CreateLinkNodeOperator._find_source_socket(self, src_node)

        links = list(
            src_node.generate_valid_links_for(context, src_socket, self.is_output)
        )
        max_node = max((len(i["node_text"]) for i in links)) if links else 0
        for i, link in enumerate(links):
            # Pickle protocol 0 uses only ASCII bytes, so we can pretend it's a string easily...
            id_string = pickle.dumps(link, protocol=0).decode()
            desc_string = "{node}:{node_sock_space}{sock}".format(
                node=link["node_text"],
                node_sock_space=(" " * (max_node - len(link["node_text"]) + 4)),
                sock=link["socket_text"],
            )
            yield (id_string, desc_string, "", i)

    node_item = EnumProperty(items=_link_search_list)

    def _find_source_socket(self, node):
        sockets = node.outputs if self.is_output else node.inputs
        for i in sockets:
            if i.identifier == self.sock_ident:
                return i
        raise LookupError()

    def invoke(self, context, event):
        possible_links = self._link_search_list(context)
        if not possible_links:
            self.report({"WARNING"}, "No nodes can be created.")
            return {"FINISHED"}
        elif len(possible_links) == 1:
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        else:
            context.window_manager.invoke_search_popup(self)
            return {"RUNNING_MODAL"}

    def execute(self, context):
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _create_link_node(self, context, node_item):
        link = pickle.loads(node_item.encode())
        self._hack.clear()

        tree = context.space_data.edit_tree
        dest_node = tree.nodes.new(type=link["node_idname"])
        for attr, value in link.get("node_settings", {}).items():
            setattr(dest_node, attr, value)
        for i in tree.nodes:
            i.select = i == dest_node
        tree.nodes.active = dest_node
        dest_node.location = context.space_data.cursor_location

        src_node = tree.nodes[self.node_name]
        src_socket = self._find_source_socket(src_node)
        # We need to use Korman's functions because they may generate a node socket.
        find_socket = (
            dest_node.find_input_socket
            if self.is_output
            else dest_node.find_output_socket
        )
        dest_socket = find_socket(link["socket_name"], True)

        if self.is_output:
            tree.links.new(src_socket, dest_socket)
        else:
            tree.links.new(dest_socket, src_socket)
        self.finished = True
        return {"FINISHED"}

    def modal(self, context, event):
        # Ugh. The Blender API sucks so much. We can only get the cursor pos from here???
        context.space_data.cursor_location_from_region(
            event.mouse_region_x, event.mouse_region_y
        )
        if len(self._hack) == 1:
            self._create_link_node(context, self._hack[0][0])
            self._hack.clear()
        elif self._hack:
            self._create_link_node(context, self.node_item)
            self._hack.clear()

        if event.type == "MOUSEMOVE":
            tree = context.space_data.edit_tree
            tree.nodes.active.location = context.space_data.cursor_location
        elif event.type in {"ESC", "LEFTMOUSE"}:
            return {"FINISHED"}
        return {"RUNNING_MODAL"}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        # needs active node editor and a tree to add nodes to
        return (
            space.type == "NODE_EDITOR"
            and space.edit_tree
            and not space.edit_tree.library
            and context.scene.render.engine == "PLASMA_GAME"
        )


class SelectFileOperator(NodeOperator, bpy.types.Operator):
    bl_idname = "file.plasma_file_picker"
    bl_label = "Select"
    bl_description = "Load a file"

    filter_glob = StringProperty(options={"HIDDEN"})
    filepath = StringProperty(subtype="FILE_PATH")
    filename = StringProperty(options={"HIDDEN"})

    data_path = StringProperty(options={"HIDDEN"})
    filepath_property = StringProperty(
        description="Name of property to store filepath in", options={"HIDDEN"}
    )
    filename_property = StringProperty(
        description="Name of property to store filename in", options={"HIDDEN"}
    )

    def execute(self, context):
        if bpy.data.texts.get(self.filename, None) is None:
            bpy.data.texts.load(self.filepath)
        else:
            self.report(
                {"WARNING"},
                "A file named '{}' is already loaded. It will be used.".format(
                    self.filename
                ),
            )

        dest = eval(self.data_path)
        if self.filepath_property:
            setattr(dest, self.filepath_property, self.filepath)
        if self.filename_property:
            setattr(dest, self.filename_property, self.filename)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


pyAttribArgMap = {
    "ptAttribute": ["vislistid", "visliststates"],
    "ptAttribBoolean": ["default"],
    "ptAttribInt": ["default", "rang"],
    "ptAttribFloat": ["default", "rang"],
    "ptAttribString": ["default"],
    "ptAttribDropDownList": ["options"],
    "ptAttribSceneobject": ["netForce"],
    "ptAttribSceneobjectList": ["byObject", "netForce"],
    "ptAttributeKeyList": ["byObject", "netForce"],
    "ptAttribActivator": ["byObject", "netForce"],
    "ptAttribActivatorList": ["byObject", "netForce"],
    "ptAttribResponder": ["stateList", "byObject", "netForce", "netPropagate"],
    "ptAttribResponderList": ["stateList", "byObject", "netForce", "netPropagate"],
    "ptAttribNamedActivator": ["byObject", "netForce"],
    "ptAttribNamedResponder": ["stateList", "byObject", "netForce", "netPropagate"],
    "ptAttribDynamicMap": ["netForce"],
    "ptAttribAnimation": ["byObject", "netForce"],
    "ptAttribBehavior": ["netForce", "netProp"],
    "ptAttribMaterialList": ["byObject", "netForce"],
}


class PlPyAttributeNodeOperator(NodeOperator, bpy.types.Operator):
    bl_idname = "node.plasma_attributes_to_node"
    bl_label = "Refresh Sockets"
    bl_description = "Refresh the Python File node's attribute sockets"
    bl_options = {"INTERNAL"}

    text_path = StringProperty()
    node_path = StringProperty()

    def execute(self, context):
        from ..plasma_attributes import get_attributes_from_str

        text_id = bpy.data.texts[self.text_path]
        attribs = get_attributes_from_str(text_id.as_string())

        node = eval(self.node_path)
        node_attrib_map = node.attribute_map
        node_attribs = node.attributes

        # Remove any that p00fed
        for cached in node.attributes:
            if cached.attribute_id not in attribs:
                node_attribs.remove(cached)

        # Update or create
        for idx, attrib in attribs.items():
            cached = node_attrib_map.get(idx, None)
            if cached is None:
                cached = node_attribs.add()
            cached.attribute_id = idx
            cached.attribute_type = attrib["type"]
            cached.attribute_name = attrib["name"]
            cached.attribute_description = attrib["desc"]
            default = attrib.get("default", None)
            if default is not None and cached.is_simple_value:
                cached.simple_value = default

            argmap = {}
            args = attrib.get("args", None)
            # Load our default argument mapping
            if args is not None:
                if cached.attribute_type in pyAttribArgMap.keys():
                    argmap.update(
                        dict(zip(pyAttribArgMap[cached.attribute_type], args))
                    )
                else:
                    print(
                        "Found ptAttribute type '{}' with unknown arguments: {}".format(
                            cached.attribute_type, args
                        )
                    )
            # Add in/set any arguments provided by keyword
            if cached.attribute_type in pyAttribArgMap.keys() and not set(
                pyAttribArgMap[cached.attribute_type]
            ).isdisjoint(attrib.keys()):
                argmap.update(
                    {
                        key: attrib[key]
                        for key in attrib
                        if key in pyAttribArgMap[cached.attribute_type]
                    }
                )
            # Attach the arguments to the attribute
            if argmap:
                cached.attribute_arguments.set_arguments(argmap)

        node.update()
        return {"FINISHED"}
