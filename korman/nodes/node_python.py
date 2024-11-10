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

from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import *

from PyHSPlasma import *

from .. import enum_props
from .node_core import *
from .node_deprecated import PlasmaDeprecatedNode, PlasmaVersionedNode
from .. import idprops
from ..plasma_attributes import get_attributes_from_str

_single_user_attribs = {
    "ptAttribBoolean", "ptAttribInt", "ptAttribFloat", "ptAttribString", "ptAttribDropDownList",
    "ptAttribSceneobject", "ptAttribDynamicMap", "ptAttribGUIDialog", "ptAttribExcludeRegion",
    "ptAttribWaveSet", "ptAttribSwimCurrent", "ptAttribAnimation", "ptAttribBehavior",
    "ptAttribMaterial", "ptAttribMaterialAnimation", "ptAttribGUIPopUpMenu", "ptAttribGUISkin",
    "ptAttribGrassShader",
}

_attrib2param = {
    "ptAttribInt": plPythonParameter.kInt,
    "ptAttribFloat": plPythonParameter.kFloat,
    "ptAttribBoolean": plPythonParameter.kBoolean,
    "ptAttribString": plPythonParameter.kString,
    "ptAttribDropDownList": plPythonParameter.kString,
    "ptAttribSceneobject": plPythonParameter.kSceneObject,
    "ptAttribSceneobjectList": plPythonParameter.kSceneObjectList,
    "ptAttribActivator": plPythonParameter.kActivator,
    "ptAttribActivatorList": plPythonParameter.kActivator,
    "ptAttribNamedActivator": plPythonParameter.kActivator,
    "ptAttribResponder": plPythonParameter.kResponder,
    "ptAttribResponderList": plPythonParameter.kResponder,
    "ptAttribNamedResponder": plPythonParameter.kResponder,
    "ptAttribDynamicMap": plPythonParameter.kDynamicText,
    "ptAttribGUIDialog": plPythonParameter.kGUIDialog,
    "ptAttribExcludeRegion": plPythonParameter.kExcludeRegion,
    "ptAttribAnimation": plPythonParameter.kAnimation,
    "ptAttribBehavior": plPythonParameter.kBehavior,
    "ptAttribMaterial": plPythonParameter.kMaterial,
    "ptAttribMaterialList": plPythonParameter.kMaterial,
    "ptAttribGUIPopUpMenu": plPythonParameter.kGUIPopUpMenu,
    "ptAttribGUISkin": plPythonParameter.kGUISkin,
    "ptAttribWaveSet": plPythonParameter.kWaterComponent,
    "ptAttribSwimCurrent": plPythonParameter.kSwimCurrentInterface,
    "ptAttribClusterList": plPythonParameter.kClusterComponent,
    "ptAttribMaterialAnimation": plPythonParameter.kMaterialAnimation,
    "ptAttribGrassShader": plPythonParameter.kGrassShaderComponent,
}

_attrib_key_types = {
    "ptAttribSceneobject": plFactory.ClassIndex("plSceneObject"),
    "ptAttribSceneobjectList": plFactory.ClassIndex("plSceneObject"),
    "ptAttribActivator": (plFactory.ClassIndex("plLogicModifier"),
                          plFactory.ClassIndex("plPythonFileMod")),
    "ptAttribActivatorList": (plFactory.ClassIndex("plLogicModifier"),
                              plFactory.ClassIndex("plPythonFileMod")),
    "ptAttribNamedActivator": (plFactory.ClassIndex("plLogicModifier"),
                               plFactory.ClassIndex("plPythonFileMod")),
    "ptAttribResponder": plFactory.ClassIndex("plResponderModifier"),
    "ptAttribResponderList": plFactory.ClassIndex("plResponderModifier"),
    "ptAttribNamedResponder": plFactory.ClassIndex("plResponderModifier"),
    "ptAttribDynamicMap": plFactory.ClassIndex("plDynamicTextMap"),
    "ptAttribGUIDialog": plFactory.ClassIndex("pfGUIDialogMod"),
    "ptAttribExcludeRegion": plFactory.ClassIndex("plExcludeRegionMod"),
    "ptAttribAnimation": (plFactory.ClassIndex("plAGMasterMod"),
                          plFactory.ClassIndex("plMsgForwarder")),
    "ptAttribBehavior": plFactory.ClassIndex("plMultistageBehMod"),
    "ptAttribMaterial": plFactory.ClassIndex("plLayer"),
    "ptAttribMaterialList": plFactory.ClassIndex("plLayer"),
    "ptAttribGUIPopUpMenu": plFactory.ClassIndex("pfGUIPopUpMenu"),
    "ptAttribGUISkin": plFactory.ClassIndex("pfGUISkin"),
    "ptAttribWaveSet": plFactory.ClassIndex("plWaveSet7"),
    "ptAttribSwimCurrent": (plFactory.ClassIndex("plSwimRegionInterface"),
                            plFactory.ClassIndex("plSwimCircularCurrentRegion"),
                            plFactory.ClassIndex("plSwimStraightCurrentRegion")),
    "ptAttribClusterList": plFactory.ClassIndex("plClusterGroup"),
    "ptAttribMaterialAnimation": plFactory.ClassIndex("plLayerAnimation"),
    "ptAttribGrassShader": plFactory.ClassIndex("plGrassShaderMod"),
}


class StringVectorProperty(bpy.types.PropertyGroup):
    value = StringProperty()


class PlasmaAttributeArguments(bpy.types.PropertyGroup):
    byObject = BoolProperty()
    default = StringProperty()
    options = CollectionProperty(type=StringVectorProperty)
    range_values = FloatVectorProperty(size=2)
    netForce = BoolProperty()
    netPropagate = BoolProperty()
    stateList = CollectionProperty(type=StringVectorProperty)
    visListId = IntProperty()
    visListStates = CollectionProperty(type=StringVectorProperty)

    def set_arguments(self, args):
        for name in args:
            if name == "byObject":
                self.byObject = bool(args[name])
            elif name == "default":
                self.default = str(args[name])
            elif name == "options":
                for option in args[name]:
                    item = self.options.add()
                    item.value = str(option)
            elif name in ("range", "rang"):
                self.range_values = args[name]
            elif name == "netForce":
                self.netForce = bool(args[name])
            elif name in ("netPropagate", "netProp"):
                self.netPropagate = bool(args[name])
            elif name == "stateList":
                for state in args[name]:
                    item = self.stateList.add()
                    item.value = str(state)
            elif name == "vislistid":
                self.visListId = int(args[name])
            elif name == "visliststates":
                for state in args[name]:
                    item = self.visListStates.add()
                    item.value = str(state)
            else:
                print("Unknown argument '{}' with value '{}'!".format(name, args[name]))


class PlasmaAttribute(bpy.types.PropertyGroup):
    # This is thy lookup helper
    type_LUT = {
        bool: "ptAttribBoolean",
        float: "ptAttribFloat",
        int: "ptAttribInt",
        str: "ptAttribString",
    }

    attribute_id = IntProperty()
    attribute_type = StringProperty()
    attribute_name = StringProperty()
    attribute_description = StringProperty()

    # These shall be default values
    value_string = StringProperty()
    value_int = IntProperty()
    value_float = FloatProperty()
    value_bool = BoolProperty()

    # Special Arguments
    attribute_arguments = PointerProperty(type=PlasmaAttributeArguments)

    _simple_attrs = {
        "ptAttribString": "value_string",
        "ptAttribDropDownList": "value_string",
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


class PlasmaPythonFileNode(PlasmaVersionedNode, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaPythonFileNode"
    bl_label = "Python File"
    bl_width_default = 290

    # Yas, a PythonFileMod can activate another PythonFileMod
    pl_attrib = {"ptAttribActivator", "ptAttribActivatorList", "ptAttribNamedActivator"}

    output_sockets: dict[str, dict[str, Any]] = {
        "satisfies": {
            "text": "Satisfies",
            "type": "PlasmaConditionSocket",
            "valid_link_nodes": "PlasmaPythonFileNode",
        },
    }

    def _poll_pytext(self, value):
        return value.name.endswith(".py")

    def _update_pyfile(self, context):
        if self.no_update:
            return
        text_id = bpy.data.texts.get(self.filename, None)
        if text_id:
            self.text_id = text_id

    def _update_pytext(self, context):
        if self.no_update:
            return
        with self.NoUpdate():
            self.filename = self.text_id.name if self.text_id is not None else ""
            self.attributes.clear()
            self.inputs.clear()
        if self.text_id is not None:
            bpy.ops.node.plasma_attributes_to_node(node_path=self.node_path, text_path=self.text_id.name)

    filename = StringProperty(name="File Name",
                              description="Python Filename",
                              update=_update_pyfile)
    filepath = StringProperty(options={"HIDDEN"})
    text_id = PointerProperty(name="Script File",
                              description="Script file datablock",
                              type=bpy.types.Text,
                              poll=_poll_pytext,
                              update=_update_pytext)

    # This property exists for UI purposes ONLY
    package = BoolProperty(options={"HIDDEN", "SKIP_SAVE"})

    attributes = CollectionProperty(type=PlasmaAttribute, options={"HIDDEN"})
    no_update = BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    @property
    def attribute_map(self):
        return { i.attribute_id: i for i in self.attributes }

    def draw_buttons(self, context, layout):
        main_row = layout.row(align=True)
        row = main_row.row(align=True)
        row.alert = self.text_id is None and bool(self.filename)
        row.prop(self, "text_id", text="Script")

        # open operator
        sel_text = "Load Script" if self.text_id is None else ""
        operator = main_row.operator("file.plasma_file_picker", icon="FILESEL", text=sel_text)
        operator.filter_glob = "*.py"
        operator.data_path = self.node_path
        operator.filename_property = "filename"

        if self.text_id is not None:
            # package button
            row = main_row.row(align=True)
            if self.text_id is not None:
                row.enabled = True
                icon = "PACKAGE" if self.text_id.plasma_text.package else "UGLYPACKAGE"
                row.prop(self.text_id.plasma_text, "package", icon=icon, text="")
            else:
                row.enabled = False
                row.prop(self, "package", text="", icon="UGLYPACKAGE")
            # rescan operator
            row = main_row.row(align=True)
            row.enabled = self.text_id is not None
            operator = row.operator("node.plasma_attributes_to_node", icon="FILE_REFRESH", text="")
            if self.text_id is not None:
                operator.text_path = self.text_id.name
                operator.node_path = self.node_path

        # This could happen on an upgrade
        if self.text_id is None and self.filename:
            layout.label(text="Script '{}' is not loaded in Blender".format(self.filename), icon="ERROR")

    def get_key(self, exporter, so):
        return self._find_create_key(plPythonFileMod, exporter, so=so)

    def export(self, exporter, bo, so):
        pfm = self.get_key(exporter, so).object

        # Special PFM-SO handling ahoy - be sure to do it for all objects this PFM is attached to.
        # Otherwise, you get non-determinant behavior.
        self._export_ancillary_sceneobject(exporter, bo, so)

        # No need to continue if the PFM was already generated.
        if pfm.filename:
            return

        py_name = Path(self.filename).stem
        pfm.filename = py_name

        # Check to see if we should pack this file
        if exporter.output.want_py_text(self.text_id):
            exporter.report.msg("Including Python '{}' for package", self.filename)
            exporter.output.add_python_mod(self.filename, text_id=self.text_id)
            # PFMs can have their own SDL...
            sdl_text = bpy.data.texts.get("{}.sdl".format(py_name), None)
            if sdl_text is not None:
                exporter.report.msg("Including corresponding SDL '{}'", sdl_text.name)
                exporter.output.add_sdl(sdl_text.name, text_id=sdl_text)

        # Handle exporting the Python Parameters
        attrib_sockets = (i for i in self.inputs if i.is_linked)
        for socket in attrib_sockets:
            from_node = socket.links[0].from_node

            value = from_node.value if socket.is_simple_value else from_node.get_key(exporter, so)
            if isinstance(value, str) or not isinstance(value, Iterable):
                value = (value,)
            for i in value:
                param = plPythonParameter()
                param.id = socket.attribute_id
                param.valueType = _attrib2param[socket.attribute_type]
                param.value = i

                if not socket.is_simple_value:
                    self._export_key_attrib(exporter, bo, so, pfm, i, socket)
                pfm.addParameter(param)

    def _export_ancillary_sceneobject(self, exporter, bo, so: plSceneObject) -> None:
        # Danger: Special case evil ahoy...
        # If the key is an object that represents a lamp, we have to assume that the reason it's
        # being passed to Python is so it can be turned on/off at will. That means it's technically
        # an animated lamp.
        if not bool(bo.users_group):
            for light in exporter.mgr.find_interfaces(plLightInfo, so):
                exporter.report.msg(f"Marking RT light '{so.key.name}' as animated due to usage in a Python File node", so.key.name)
                light.setProperty(plLightInfo.kLPMovable, True)

    def _export_key_attrib(self, exporter, bo, so: plSceneObject, pfm: plPythonFileMod, key: plKey, socket) -> None:
        if key is None:
            exporter.report.warn("Attribute '{}' didn't return a key and therefore will be unavailable to Python",
                                 self.id_data.name, socket.links[0].name)
            return

        key_type = _attrib_key_types[socket.attribute_type]
        if isinstance(key_type, tuple):
            good_key = key.type in key_type
        else:
            good_key = key.type == key_type
        if not good_key:
            exporter.report.warn("'{}' Node '{}' returned an unexpected key type '{}'",
                                 self.id_data.name, socket.links[0].from_node.name,
                                 plFactory.ClassName(key.type))

        key_object = key.object
        if isinstance(key_object, plSceneObject):
            self._export_ancillary_sceneobject(exporter, bo, key_object)
        elif isinstance(key_object, plPythonFileMod):
            key_object.addReceiver(pfm.key)

    def _get_attrib_sockets(self, idx):
        for i in self.inputs:
            if i.attribute_id == idx:
                yield i

    def generate_valid_links_for(self, context, socket, is_output):
        if is_output:
            yield from PlasmaNodeBase.generate_valid_links_for(self, context, socket, True)
            return

        attrib_type = socket.attribute_type
        for i in bpy.types.Node.__subclasses__():
            node_attrib_types = getattr(i, "pl_attrib", None)
            if node_attrib_types is None or issubclass(i, PlasmaDeprecatedNode):
                continue

            if attrib_type in node_attrib_types:
                if issubclass(i, PlasmaAttribNodeBase):
                   yield { "node_idname": i.bl_idname,
                           "node_text": i.bl_label,
                           "socket_name": "pfm",
                           "socket_text": "Python File" }
                else:
                    for socket_name, socket_def in i.output_sockets.items():
                        if socket_def.get("hidden") is True:
                            continue
                        if socket_def.get("can_link") is False:
                            continue

                        valid_link_nodes = socket_def.get("valid_link_nodes")
                        valid_link_sockets = socket_def.get("valid_link_sockets")
                        if valid_link_nodes is not None and self.bl_idname not in valid_link_nodes:
                            continue
                        if valid_link_sockets is not None and "PlasmaPythonFileNodeSocket" not in valid_link_sockets:
                            continue

                        yield { "node_idname": i.bl_idname,
                                "node_text": i.bl_label,
                                "socket_name": socket_name,
                                "socket_text": socket_def["text"] }

    @classmethod
    def generate_valid_links_to(cls, context, socket, is_output):
        # This is only useful for nodes wanting to connect to our inputs (ptAttributes)
        if not is_output:
            return

        if isinstance(socket, PlasmaPythonAttribNodeSocket):
            pl_attrib = socket.node.pl_attrib
        else:
            pl_attrib = getattr(socket.node, "pl_attrib", set())
            if not pl_attrib:
                return

            # Fetch the output definition for the requested socket and make sure it can connect to us.
            socket_def = getattr(socket.node, "output_sockets", {}).get(socket.alias)
            if socket_def is None:
                return
            valid_link_sockets = socket_def.get("valid_link_sockets")
            valid_link_nodes = socket_def.get("valid_link_nodes")
            if valid_link_sockets is not None and "PlasmaPythonFileNodeSocket" not in valid_link_sockets:
                return
            if valid_link_nodes is not None and "PlasmaPythonFileNode" not in valid_link_nodes:
                return

        # Ok, apparently this thing can connect as a ptAttribute. The only problem with that is
        # that we have no freaking where... The sockets are spawned by Python files... So, we
        # need to look at all the Python files we know about...
        for text_id in bpy.data.texts:
            if not text_id.name.endswith(".py"):
                continue
            attribs = get_attributes_from_str(text_id.as_string())
            if not attribs:
                continue

            for _, attrib in attribs.items():
                if not attrib["type"] in pl_attrib:
                    continue

                # *gulp*
                yield { "node_idname": "PlasmaPythonFileNode",
                        "node_text": text_id.name,
                        "node_settings": { "filename": text_id.name },
                        "socket_name":  attrib["name"],
                        "socket_text": attrib["name"] }

    def harvest_actors(self):
        for i in self.inputs:
            if not i.is_linked or i.attribute_type not in {"ptAttribSceneobject", "ptAttribSceneobjectList"}:
                continue
            node = i.links[0].from_node
            if node.target_object is not None:
                yield node.target_object.name

    def _make_attrib_socket(self, attrib, is_init=False):
        new_pos = len(self.inputs)
        if not is_init:
            for i, socket in enumerate(self.inputs):
                if attrib.attribute_id < socket.attribute_id:
                    new_pos = i
                    break
        old_pos = len(self.inputs)
        socket = self.inputs.new("PlasmaPythonFileNodeSocket", attrib.attribute_name)
        socket.attribute_id = attrib.attribute_id
        if not is_init and new_pos != old_pos:
            self.inputs.move(old_pos, new_pos)

    @property
    def requires_actor(self):
        return True

    @contextmanager
    def NoUpdate(self):
        self.no_update = True
        try:
            yield self
        finally:
            self.no_update = False

    def update(self):
        if self.no_update:
            return
        with self.NoUpdate():
            # First, we really want to make sure our junk matches up. Yes, this does dupe what
            # happens in PlasmaAttribNodeBase, but we can link much more than those node types...
            toasty_sockets = []
            input_nodes = (i for i in self.inputs if i.is_linked and i.links)
            for i in input_nodes:
                link = i.links[0]
                allowed_attribs = getattr(link.from_node, "pl_attrib", set())
                if i.attribute_type not in allowed_attribs:
                    self.id_data.links.remove(link)
                    # Bad news, old chap... Even though we're doing this before we figure out
                    # how many socket we need, the changes won't be committed to the socket's links
                    # until later. damn. We'll have to track it manually
                    toasty_sockets.append(i)

            attribs = self.attribute_map
            empty = not self.inputs
            for idx in sorted(attribs):
                attrib = attribs[idx]

                # Delete any attribute sockets whose type changed
                for i in self._get_attrib_sockets(idx):
                    if i.attribute_type != attrib.attribute_type:
                        self.inputs.remove(i)

                # Fetch the list of sockets again because we may have nuked some
                inputs = list(self._get_attrib_sockets(idx))
                if not inputs:
                    self._make_attrib_socket(attrib, empty)
                elif attrib.attribute_type not in _single_user_attribs:
                    unconnected = [socket for socket in inputs if not socket.is_linked or socket in toasty_sockets]
                    if not unconnected:
                        self._make_attrib_socket(attrib, empty)
                    while len(unconnected) > 1:
                        self.inputs.remove(unconnected.pop())

            # Make sure the output sockets are present and accounted for.
            self._update_extant_sockets(self.output_sockets, self.outputs)
            self._update_init_sockets(self.output_sockets, self.outputs)

    @property
    def latest_version(self):
        return 2

    def upgrade(self):
        # In version 1 of this node, Python scripts were referenced by their filename in the
        # python package and by their path on the local machine. This created an undue dependency
        # on the artist's environment. In version 2, we will use Blender's text data blocks to back
        # Python scripts. It is still legal to export Python File nodes that are not backed by a script.
        if self.version == 1:
            text_id = bpy.data.texts.get(self.filename, None)
            if text_id is None:
                path = Path(self.filepath)
                try:
                    if path.exists():
                        text_id = bpy.data.texts.load(self.filepath)
                except OSError:
                    pass
            with self.NoUpdate():
                self.text_id = text_id
            self.property_unset("filepath")
            self.version = 2


class PlasmaPythonFileNodeSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
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
        self.draw_add_operator(context, layout, node)
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

    @property
    def attribute_arguments(self):
        return self.node.attribute_map[self.attribute_id].attribute_arguments


class PlasmaPythonAttribNodeSocket(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    def draw_content(self, context, layout, node, text):
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

    @classmethod
    def register(cls):
        pl_attrib = cls.pl_attrib
        if isinstance(pl_attrib, tuple):
            color = _attrib_colors.get(pl_attrib, None)
            if color is not None:
                for i in pl_attrib:
                    _attrib_colors[i] = color

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
    pl_label_attrib = "value"
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


class PlasmaAttribDropDownListNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribDropDownListNode"
    bl_label = "Drop Down List Attribute"

    pl_attrib = "ptAttribDropDownList"
    pl_label_attrib = "value"

    def _list_items(self, context):
        attrib = self.to_socket
        if attrib is not None:
            return [(option.value, option.value, "") for option in attrib.attribute_arguments.options]
        else:
            return []
    value = EnumProperty(items=_list_items)

    def draw_buttons(self, context, layout):
        layout.prop(self, "value", text=self.attribute_name)

    def update(self):
        super().update()
        attrib = self.to_socket
        if attrib is not None and not self.value:
            self.value = attrib.simple_value


class PlasmaAttribIntNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribIntNode"
    bl_label = "Numeric Attribute"

    def _get_int(self):
        return round(self.value_float)
    def _set_int(self, value):
        self.value_float = float(value)
    def _on_update_float(self, context):
        self.inited = True

    pl_attrib = ("ptAttribFloat", "ptAttribInt")
    pl_label_attrib = "value"
    value_int = IntProperty(get=_get_int, set=_set_int, options={"HIDDEN"})
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
            self._range_label(layout)
            layout.alert = self._out_of_range(self.value_float)
            layout.prop(self, "value_float", text=attrib.name)
        elif attrib.attribute_type == "ptAttribInt":
            self._range_label(layout)
            layout.alert = self._out_of_range(self.value_int)
            layout.prop(self, "value_int", text=attrib.name)
        else:
            raise RuntimeError()

    def update(self):
        super().update()
        attrib = self.to_socket
        if attrib is not None and not self.inited:
            self.value = attrib.simple_value
            self.inited = True

    def _get_value(self):
        attrib = self.to_socket
        if attrib is None or attrib.attribute_type == "ptAttribInt":
            return self.value_int
        else:
            return self.value_float
    def _set_value(self, value):
        self.value_float = value
    value = property(_get_value, _set_value)

    def _range_label(self, layout):
        attrib = self.to_socket
        layout.label(text="Range: [{}, {}]".format(attrib.attribute_arguments.range_values[0], attrib.attribute_arguments.range_values[1]))

    def _out_of_range(self, value):
        attrib = self.to_socket
        if attrib.attribute_arguments.range_values[0] == attrib.attribute_arguments.range_values[1]:
            # Ignore degenerate intervals
            return False
        if attrib.attribute_arguments.range_values[0] <= value <= attrib.attribute_arguments.range_values[1]:
            return False
        return True


class PlasmaAttribObjectNode(idprops.IDPropObjectMixin, PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribObjectNode"
    bl_label = "Object Attribute"

    pl_attrib = ("ptAttribSceneobject", "ptAttribSceneobjectList", "ptAttribAnimation",
                 "ptAttribSwimCurrent", "ptAttribWaveSet", "ptAttribGrassShader",
                 "ptAttribGUIDialog")

    target_object = PointerProperty(name="Object",
                                    description="Object containing the required data",
                                    type=bpy.types.Object)

    def init(self, context):
        super().init(context)
        # keep the code simple
        self.outputs[0].link_limit = 1

    def draw_buttons(self, context, layout):
        layout.prop(self, "target_object", text=self.attribute_name)

    def get_key(self, exporter, so):
        attrib_socket = self.to_socket
        if attrib_socket is None:
            self.raise_error("must be connected to a Python File node!")
        attrib = attrib_socket.attribute_type

        bo = self.target_object
        if bo is None:
            self.raise_error("Target object must be specified")
        ref_so_key = exporter.mgr.find_create_key(plSceneObject, bl=bo)
        ref_so = ref_so_key.object

        # Add your attribute type handling here...
        if attrib in {"ptAttribSceneobject", "ptAttribSceneobjectList"}:
            return ref_so_key
        elif attrib == "ptAttribAnimation":
            return exporter.animation.get_animation_key(bo, ref_so)
        elif attrib == "ptAttribSwimCurrent":
            swimregion = bo.plasma_modifiers.swimregion
            return swimregion.get_key(exporter, ref_so)
        elif attrib == "ptAttribWaveSet":
            waveset = bo.plasma_modifiers.water_basic
            if not waveset.enabled:
                self.raise_error("water modifier not enabled on '{}'".format(self.object_name))
            return exporter.mgr.find_create_key(plWaveSet7, so=ref_so, bl=bo)
        elif attrib == "ptAttribGrassShader":
            grass_shader = bo.plasma_modifiers.grass_shader
            if not grass_shader.enabled:
                self.raise_error("grass shader modifier not enabled on '{}'".format(self.object_name))
            if exporter.mgr.getVer() <= pvPots:
                return None
            return [exporter.mgr.find_create_key(plGrassShaderMod, so=ref_so, name=i.name)
                    for i in exporter.mesh.material.get_materials(bo)]
        elif attrib == "ptAttribGUIDialog":
            gui_dialog = bo.plasma_modifiers.gui_dialog
            if not gui_dialog.enabled:
                self.raise_error(f"GUI Dialog modifier not enabled on '{self.object_name}'")
            dialog_mod = exporter.mgr.find_create_object(pfGUIDialogMod, so=ref_so, bl=bo)
            dialog_mod.procReceiver = attrib_socket.node.get_key(exporter, so)
            return dialog_mod.key

    @classmethod
    def _idprop_mapping(cls):
        return {"target_object": "object_name"}


class PlasmaAttribStringNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribStringNode"
    bl_label = "String Attribute"

    pl_attrib = "ptAttribString"
    pl_label_attrib = "value"
    value = StringProperty()

    def draw_buttons(self, context, layout):
        layout.prop(self, "value", text=self.attribute_name)

    def update(self):
        super().update()
        attrib = self.to_socket
        if attrib is not None and not self.value:
            self.value = attrib.simple_value


class PlasmaAttribTextureNode(idprops.IDPropMixin, PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribTextureNode"
    bl_label = "Texture Attribute"
    bl_width_default = 175

    pl_attrib = ("ptAttribMaterial", "ptAttribMaterialList",
                 "ptAttribDynamicMap", "ptAttribMaterialAnimation")

    def _poll_texture(self, value: bpy.types.Texture) -> bool:
        # is this the type of dealio that we're looking for?
        attrib = self.to_socket
        if attrib is not None:
            attrib = attrib.attribute_type
            if attrib == "ptAttribDynamicMap" and self._is_dyntext(value):
                return True
            elif attrib == "ptAttribMaterialAnimation" and not self._is_dyntext:
                return True
            return False

        # We're not hooked up to a PFM node yet, so let anything slide.
        return True

    target_object = idprops.triprop_object(
        "target_object", "material", "texture",
        name="Object",
        description="Target object"
    )
    material = idprops.triprop_material(
        "target_object", "material", "texture",
        name="Material",
        description="Material the texture is attached to"
    )
    texture = idprops.triprop_texture(
        "target_object", "material", "texture",
        name="Texture",
        description="Texture to expose to Python",
        poll=_poll_texture
    )

    anim_name = enum_props.triprop_animation(
        "target_object", "material", "texture",
        name="Animation",
        description="Name of the animation to control",
        options=set()
    )

    def init(self, context):
        super().init(context)
        # keep the code simple
        self.outputs[0].link_limit = 1

    def draw_buttons(self, context, layout):
        if self.target_object is not None:
            iter_materials = lambda: (i.material for i in self.target_object.material_slots if i and i.material)
            if self.material is not None:
                if self.material not in iter_materials():
                    layout.label("The selected material is not linked to the target object.", icon="ERROR")
                    layout.alert = True
            if self.texture is not None:
                if not frozenset(self.texture.users_material) & frozenset(iter_materials()):
                    layout.label("The selected texture is not on a material linked to the target object.", icon="ERROR")
                    layout.alert = True
        layout.alert = not any((self.target_object, self.material, self.texture))
        layout.prop(self, "target_object")
        layout.prop(self, "material")
        layout.prop(self, "texture")
        wants_anim = bool(self.to_socket and self.to_socket.attribute_type == "ptAttribMaterialAnimation")
        col = layout.column()
        col.alert = False
        col.active = wants_anim
        col.prop(self, "anim_name")

    def get_key(self, exporter, so):
        if not any((self.target_object, self.material, self.texture)):
            self.raise_error("At least one of: target object, material, or texture must be specified.")

        attrib = self.to_socket
        if attrib is None:
            self.raise_error("must be connected to a Python File node!")
        attrib = attrib.attribute_type

        layer_generator = exporter.mesh.material.get_layers(self.target_object, self.material, self.texture)
        bottom_layers = (i.object.bottomOfStack for i in layer_generator)

        if attrib == "ptAttribDynamicMap":
            yield from filter(lambda x: x and isinstance(x.object, plDynamicTextMap),
                              (i.object.texture for i in layer_generator))
        elif attrib == "ptAttribMaterialAnimation":
            anim_generator = exporter.mesh.material.get_texture_animation_key(self.target_object, self.material, self.texture, self.anim_name)
            yield from filter(lambda x: not isinstance(x.object, (plAgeGlobalAnim, plLayerSDLAnimation)), anim_generator)
        elif attrib == "ptAttribMaterialList":
            yield from filter(lambda x: x and not isinstance(x.object, plLayerAnimationBase), bottom_layers)
        elif attrib == "ptAttribMaterial":
            # Only return the first key; warn about others.
            result_gen = filter(lambda x: x and not isinstance(x.object, plLayerAnimationBase), bottom_layers)
            result = next(result_gen, None)
            remainder = sum((1 for i in result))
            if remainder > 1:
                exporter.report.warn("'{}.{}': Expected a single layer, but mapped to {}. Make the settings more specific.",
                                     self.id_data.name, self.path_from_id(), remainder + 1)
            if result is not None:
                yield result
        else:
            raise RuntimeError(attrib)

    @classmethod
    def _idprop_mapping(cls):
        return {"material": "material_name",
                "texture": "texture_name"}

    def _idprop_sources(self):
        return {"material_name": bpy.data.materials,
                "texture_name": bpy.data.textures}

    def _is_dyntext(self, texture):
        return texture.type == "IMAGE" and texture.image is None


_attrib_colors = {
    "ptAttribActivator": (0.188, 0.086, 0.349, 1.0),
    "ptAttribActivatorList": (0.188, 0.086, 0.349, 1.0),
    "ptAttribBehavior": (0.348, 0.186, 0.349, 1.0),
    "ptAttribBoolean": (0.71, 0.706, 0.655, 1.0),
    "ptAttribExcludeRegion": (0.031, 0.110, 0.290, 1.0),
    "ptAttribDropDownList": (0.475, 0.459, 0.494, 1.0),
    "ptAttribNamedActivator": (0.188, 0.086, 0.349, 1.0),
    "ptAttribNamedResponder": (0.031, 0.110, 0.290, 1.0),
    "ptAttribResponder": (0.031, 0.110, 0.290, 1.0),
    "ptAttribResponderList": (0.031, 0.110, 0.290, 1.0),
    "ptAttribString": (0.675, 0.659, 0.494, 1.0),

    PlasmaAttribIntNode.pl_attrib: (0.443, 0.439, 0.392, 1.0),
    PlasmaAttribObjectNode.pl_attrib: (0.565, 0.267, 0.0, 1.0),
    PlasmaAttribTextureNode.pl_attrib: (0.035, 0.353, 0.0, 1.0),
}
