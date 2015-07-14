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
import os.path
from PyHSPlasma import *

from .node_core import *

_attrib_colors = {
    "ptAttribActivator": (0.451, 0.0, 0.263, 1.0),
    "ptAttribActivatorList": (0.451, 0.0, 0.263, 1.0),
    "ptAttribBoolean": (0.71, 0.706, 0.655, 1.0),
    "ptAttribFloat": (0.443, 0.439, 0.392, 1.0),
    ("ptAttribFloat", "ptAttribInt"): (0.443, 0.439, 0.392, 1.0),
    "ptAttribInt": (0.443, 0.439, 0.392, 1.0),
    "ptAttribResponder": (0.031, 0.110, 0.290, 1.0),
    "ptAttribResponderList": (0.031, 0.110, 0.290, 1.0),
    "ptAttribString": (0.675, 0.659, 0.494, 1.0),
}

_single_user_attribs = {
    "ptAttribBoolean", "ptAttribInt", "ptAttribFloat", "ptAttribString", "ptAttribDropDownList",
    "ptAttribSceneobject", "ptAttribDynamicMap", "ptAttribGUIDialog", "ptAttribExcludeRegion",
    "ptAttribWaveSet", "ptAttribSwimCurrent", "ptAttribAnimation", "ptAttribBehavior",
    "ptAttribMaterial", "ptAttribMaterialAnimation", "ptAttribGUIPopUpMenu", "ptAttribGUISkin",
    "ptAttribGrassShader",
}

class PlasmaAttribute(bpy.types.PropertyGroup):
    attribute_id = IntProperty()
    attribute_type = StringProperty()
    attribute_name = StringProperty()
    attribute_description = StringProperty()

    # These shall be default values
    value_string = StringProperty()
    value_int = IntProperty()
    value_float = FloatProperty()
    value_bool = BoolProperty()

    _simple_attrs = {
        "ptAttribString": "value_string",
        "ptAttribInt": "value_int",
        "ptAttribFloat": "value_float",
        "ptAttribBoolean": "value_bool",
    }

    @property
    def is_simple_value(self):
        return self.attribute_type in self._simple_attrs

    def _get_simple_value(self):
        return getattr(self, self._simple_attrs[self.attribute_type])
    def _set_simple_value(self, value):
        setattr(self, self._simple_attrs[self.attribute_type], value)
    simple_value = property(_get_simple_value, _set_simple_value)


class PlasmaPythonFileNode(PlasmaNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaPythonFileNode"
    bl_label = "Python File"
    bl_width_default = 210

    def _update_pyfile(self, context):
        # Changing the file path? let's start anew.
        self.attributes.clear()
        self.inputs.clear()

        # Now populate that BAMF
        bpy.ops.node.plasma_attributes_to_node(node_path=self.node_path, python_path=self.filepath)

    filename = StringProperty(name="File",
                              description="Python Filename")
    filepath = StringProperty(update=_update_pyfile,
                              options={"HIDDEN"})

    attributes = CollectionProperty(type=PlasmaAttribute, options={"HIDDEN"})
    dirty_attributes = BoolProperty(options={"HIDDEN"})

    @property
    def attribute_map(self):
        return { i.attribute_id: i for i in self.attributes }

    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        if self.filename:
            row.prop(self, "filename")
            operator = row.operator("node.plasma_attributes_to_node", icon="FILE_REFRESH", text="")
            operator.python_path = self.filepath
            operator.node_path = self.node_path

        op_text = "" if self.filename else "Select"
        operator = row.operator("file.plasma_file_picker", icon="SCRIPT", text=op_text)
        operator.filter_glob = "*.py"
        operator.data_path = self.node_path
        operator.filepath_property = "filepath"
        operator.filename_property = "filename"

    def _get_attrib_sockets(self, idx):
        for i in self.inputs:
            if i.attribute_id == idx:
                yield i

    def _make_attrib_socket(self, attrib, is_init=False):
        new_pos = len(self.inputs)
        if not is_init:
            for i, socket in enumerate(self.inputs):
                if attrib.attribute_id < socket.attribute_id:
                    new_pos = i
                    break
        old_pos = len(self.inputs)
        socket = self.inputs.new("PlasmaPythonFileNodeSocket", "", "")
        socket.attribute_id = attrib.attribute_id
        if not is_init and new_pos != old_pos:
            self.inputs.move(old_pos, new_pos)

    def update(self):
        attribs = self.attribute_map
        empty = not self.inputs
        for idx in sorted(attribs):
            attrib = attribs[idx]

            # Delete any attribute sockets whose type changed
            for i in self._get_attrib_sockets(attrib.attribute_id):
                if i.attribute_type != attrib.attribute_type:
                    self.inputs.remove(i)

            # Fetch the list of sockets again because we may have nuked some
            inputs = list(self._get_attrib_sockets(attrib.attribute_id))
            if not inputs:
                self._make_attrib_socket(attrib, empty)
            elif attrib.attribute_type not in _single_user_attribs:
                unconnected = [socket for socket in inputs if not socket.is_linked]
                if not unconnected:
                    self._make_attrib_socket(attrib, empty)
                while len(unconnected) > 1:
                    self.inputs.remove(unconnected.pop())


class PlasmaPythonFileNodeSocket(bpy.types.NodeSocket):
    attribute_id = IntProperty(options={"HIDDEN"})

    @property
    def attribute_description(self):
        return self.node.attribute_map[self.attribute_id].attribute_description

    @property
    def attribute_name(self):
        return self.node.attribute_map[self.attribute_id].attribute_name

    @property
    def attribute_type(self):
        return self.node.attribute_map[self.attribute_id].attribute_type

    def draw(self, context, layout, node, text):
        layout.alignment = "LEFT"
        layout.label("ID: {}".format(self.attribute_id))
        layout.label(self.attribute_description)

    def draw_color(self, context, node):
        return _attrib_colors.get(self.attribute_type, (0.0, 0.0, 0.0, 1.0))

    @property
    def is_simple_value(self):
        return self.node.attribute_map[self.attribute_id].is_simple_value

    @property
    def simple_value(self):
        return self.node.attribute_map[self.attribute_id].simple_value


class PlasmaPythonAttribNodeSocket(bpy.types.NodeSocket):
    def draw(self, context, layout, node, text):
        attrib = node.to_socket
        if attrib is None:
            layout.label(text)
        else:
            layout.label("ID: {}".format(attrib.attribute_id))

    def draw_color(self, context, node):
        return _attrib_colors.get(node.pl_attrib, (0.0, 0.0, 0.0, 1.0))


class PlasmaPythonReferenceNodeSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    bl_color = (0.031, 0.110, 0.290, 1.0)


class PlasmaAttribNodeBase(PlasmaNodeBase):
    def init(self, context):
        self.outputs.new("PlasmaPythonAttribNodeSocket", "Python File", "pfm")

    @property
    def attribute_name(self):
        attr = self.to_socket
        return "Value" if attr is None else attr.attribute_name

    @property
    def to_socket(self):
        """Returns the socket linked to IF only one link has been made"""
        socket = self.outputs[0]
        if len(socket.links) == 1:
            return socket.links[0].to_socket
        return None

    def update(self):
        pl_id = self.pl_attrib
        socket = self.outputs[0]
        for link in socket.links:
            if link.to_node.bl_idname != "PlasmaPythonFileNode":
                self.id_data.links.remove(link)
            if isinstance(pl_id, tuple):
                if link.to_socket.attribute_type not in pl_id:
                    self.id_data.links.remove(link)
            else:
                if pl_id != link.to_socket.attribute_type:
                    self.id_data.links.remove(link)


class PlasmaAttribBoolNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribBoolNode"
    bl_label = "Boolean Attribute"

    def _on_update(self, context):
        self.inited = True

    pl_attrib = "ptAttribBoolean"
    value = BoolProperty()
    inited = BoolProperty(options={"HIDDEN"})

    def draw_buttons(self, context, layout):
        layout.prop(self, "value", text=self.attribute_name)

    def update(self):
        super().update()
        attrib = self.to_socket
        if attrib is not None and not self.inited:
            self.value = attrib.simple_value
            self.inited = True


class PlasmaAttribNumericNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribIntNode"
    bl_label = "Numeric Attribute"

    def _on_update_int(self, context):
        self.value_float = float(self.value_int)
        self.inited = True

    def _on_update_float(self, context):
        self.value_int = int(self.value_float)
        self.inited = True

    pl_attrib = ("ptAttribFloat", "ptAttribInt")
    value_int = IntProperty(update=_on_update_int, options={"HIDDEN"})
    value_float = FloatProperty(update=_on_update_float, options={"HIDDEN"})
    inited = BoolProperty(options={"HIDDEN"})

    def init(self, context):
        super().init(context)
        # because we're trying to be for both int and float...
        self.outputs[0].link_limit = 1

    def draw_buttons(self, context, layout):
        attrib = self.to_socket
        if attrib is None:
            layout.prop(self, "value_int", text="Value")
        elif attrib.attribute_type == "ptAttribFloat":
            layout.prop(self, "value_float", text=attrib.name)
        elif attrib.attribute_type == "ptAttribInt":
            layout.prop(self, "value_int", text=attrib.name)
        else:
            raise RuntimeError()

    def update(self):
        super().update()
        attrib = self.to_socket
        if attrib is not None and not self.inited:
            self.value = attrib.simple_value
            self.inited = True


class PlasmaAttribStringNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribStringNode"
    bl_label = "String Attribute"

    pl_attrib = "ptAttribString"
    value = StringProperty()

    def draw_buttons(self, context, layout):
        layout.prop(self, "value", text=self.attribute_name)

    def update(self):
        super().update()
        attrib = self.to_socket
        if attrib is not None:
            self.value = attrib.simple_value
