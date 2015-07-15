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
    "ptAttribActivator": plFactory.ClassIndex("plLogicModifier"),
    "ptAttribActivatorList": plFactory.ClassIndex("plLogicModifier"),
    "ptAttribNamedActivator": plFactory.ClassIndex("plLogicModifier"),
    "ptAttribResponder": plFactory.ClassIndex("plResponderModifier"),
    "ptAttribResponderList": plFactory.ClassIndex("plResponderModifier"),
    "ptAttribNamedResponder": plFactory.ClassIndex("plResponderModifier"),
    "ptAttribDynamicMap": plFactory.ClassIndex("plDynamicTextMap"),
    "ptAttribGUIDialog": plFactory.ClassIndex("pfGUIDialogMod"),
    "ptAttribExcludeRegion": plFactory.ClassIndex("plExcludeRegionMod"),
    "ptAttribAnimation": plFactory.ClassIndex("plAGMasterMod"),
    "ptAttribBehavior": plFactory.ClassIndex("plMultistageBehMod"),
    "ptAttribMaterial": plFactory.ClassIndex("plLayer"),
    "ptAttribMaterialList": plFactory.ClassIndex("plLayer"),
    "ptAttribGUIPopUpMenu": plFactory.ClassIndex("pfGUIPopUpMenu"),
    "ptAttribGUISkin": plFactory.ClassIndex("pfGUISkin"),
    "ptAttribWaveSet": plFactory.ClassIndex("plWaveSet7"),
    "ptAttribSwimCurrent": (plFactory.ClassIndex("plSwimCircularCurrentRegion"),
                            plFactory.ClassIndex("plSwimStraightCurrentRegion")),
    "ptAttribClusterList": plFactory.ClassIndex("plClusterGroup"),
    "ptAttribMaterialAnimation": plFactory.ClassIndex("plLayerAnimation"),
    "ptAttribGrassShader": plFactory.ClassIndex("plGrassShaderMod"),
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

    class _NoUpdate:
        def __init__(self, node):
            self._node = node
        def __enter__(self):
            self._node.no_update = True
        def __exit__(self, type, value, traceback):
            self._node.no_update = False

    def _update_pyfile(self, context):
        with self._NoUpdate(self) as _hack:
            self.attributes.clear()
            self.inputs.clear()
        bpy.ops.node.plasma_attributes_to_node(node_path=self.node_path, python_path=self.filepath)

    filename = StringProperty(name="File",
                              description="Python Filename")
    filepath = StringProperty(update=_update_pyfile,
                              options={"HIDDEN"})

    attributes = CollectionProperty(type=PlasmaAttribute, options={"HIDDEN"})
    no_update = BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})

    @property
    def attribute_map(self):
        return { i.attribute_id: i for i in self.attributes }

    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        if self.filename:
            row.prop(self, "filename")
            if os.path.isfile(self.filepath):
                operator = row.operator("node.plasma_attributes_to_node", icon="FILE_REFRESH", text="")
                operator.python_path = self.filepath
                operator.node_path = self.node_path

        op_text = "" if self.filename else "Select"
        operator = row.operator("file.plasma_file_picker", icon="SCRIPT", text=op_text)
        operator.filter_glob = "*.py"
        operator.data_path = self.node_path
        operator.filepath_property = "filepath"
        operator.filename_property = "filename"

    def get_key(self, exporter, so):
        return exporter.mgr.find_create_key(plPythonFileMod, name=self.key_name, so=so)

    def export(self, exporter, bo, so):
        pfm = self.get_key(exporter, so).object
        pfm.filename = os.path.splitext(self.filename)[0]
        attrib_sockets = (i for i in self.inputs if i.is_linked)
        for socket in attrib_sockets:
            attrib = socket.attribute_type
            from_node = socket.links[0].from_node

            value = from_node.value if socket.is_simple_value else from_node.get_key(exporter, so)
            if not isinstance(value, tuple):
                value = (value,)
            for i in value:
                param = plPythonParameter()
                param.id = socket.attribute_id
                param.valueType = _attrib2param[attrib]
                param.value = i

                # Key type sanity checking... Because I trust no user.
                if not socket.is_simple_value:
                    if i is None:
                        msg = "'{}' Node '{}' didn't return a key and therefore will be unavailable to Python".format(
                            self.id_data.name, from_node.name)
                        exporter.report.warn(msg, indent=3)
                    else:
                        key_type = _attrib_key_types[attrib]
                        if isinstance(key_type, tuple):
                            good_key = i.type in key_type
                        else:
                            good_key = i.type == key_type
                        if not good_key:
                            msg = "'{}' Node '{}' returned an unexpected key type '{}'".format(
                                self.id_data.name, from_node.name, plFactory.ClassName(i.type))
                            exporter.report.warn(msg, indent=3)
                pfm.addParameter(param)

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
        socket = self.inputs.new("PlasmaPythonFileNodeSocket", attrib.attribute_name)
        socket.attribute_id = attrib.attribute_id
        if not is_init and new_pos != old_pos:
            self.inputs.move(old_pos, new_pos)

    def update(self):
        if self.no_update:
            return
        with self._NoUpdate(self) as _no_recurse:
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

    @property
    def value(self):
        attrib = self.to_socket
        if attrib is None or attrib.attribute_type == "ptAttribInt":
            return self.value_int
        else:
            return self.value_float


class PlasmaAttribObjectNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribObjectNode"
    bl_label = "Object Attribute"

    pl_attrib = ("ptAttribSceneobject", "ptAttribSceneobjectList", "ptAttribAnimation")

    object_name = StringProperty(name="Object",
                                 description="Object containing the required data")

    def init(self, context):
        super().init(context)
        # keep the code simple
        self.outputs[0].link_limit = 1

    def draw_buttons(self, context, layout):
        layout.prop_search(self, "object_name", bpy.data, "objects", text=self.attribute_name)

    def get_key(self, exporter, so):
        attrib = self.to_socket
        if attrib is None:
            self.raise_error("must be connected to a Python File node!")
        attrib = attrib.attribute_type

        bo = bpy.data.objects.get(self.object_name, None)
        if bo is None:
            self.raise_error("invalid object specified: '{}'".format(self.object_name))
        ref_so_key = exporter.mgr.find_create_key(plSceneObject, bl=bo)
        ref_so = ref_so_key.object

        # Add your attribute type handling here...
        if attrib in {"ptAttribSceneobject", "ptAttribSceneobjectList"}:
            return ref_so_key
        elif attrib == "ptAttribAnimation":
            anim = bo.plasma_modifiers.animation
            agmod = exporter.mgr.find_create_key(plAGModifier, so=ref_so, name=anim.display_name)
            agmaster = exporter.mgr.find_create_key(plAGMasterModifier, so=ref_so, name=anim.display_name)
            return agmaster


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


class PlasmaAttribTextureNode(PlasmaAttribNodeBase, bpy.types.Node):
    bl_category = "PYTHON"
    bl_idname = "PlasmaAttribTextureNode"
    bl_label = "Texture Attribute"
    bl_width_default = 175

    pl_attrib = ("ptAttribMaterial", "ptAttribMaterialList",
                 "ptAttribDynamicMap", "ptAttribMaterialAnimation")
    material_name = StringProperty(name="Material")
    texture_name = StringProperty(name="Texture")

    def init(self, context):
        super().init(context)
        # keep the code simple
        self.outputs[0].link_limit = 1

    def draw_buttons(self, context, layout):
        layout.prop_search(self, "material_name", bpy.data, "materials")
        material = bpy.data.materials.get(self.material_name, None)
        if material is not None:
            layout.prop_search(self, "texture_name", material, "texture_slots")

    def get_key(self, exporter, so):
        material = bpy.data.materials.get(self.material_name, None)
        if material is None:
            self.raise_error("invalid Material '{}'".format(self.material_name))
        tex_slot = material.texture_slots.get(self.texture_name, None)
        if tex_slot is None:
            self.raise_error("invalid Texture '{}'".format(self.texture_name))
        attrib = self.attribute_type

        # Helpers
        texture = tex_slot.texture
        is_animated = ((material.animation_data is not None and material.animation_data.action is not None)
                       or (texture.animation_data is not None and texture.animation_data.action is not None))
        is_dyntext = texture.type == "IMAGE" and texture.image is None

        # Your attribute stuff here...
        if attrib == "ptAttribDynamicMap":
            if not is_dyntext:
                self.raise_error("Texture '{}' is not a Dynamic Text Map".format(self.texture_name))
            name = "{}_{}_DynText".format(self.material_name, self.texture_name)
            return exporter.mgr.find_create_key(plDynamicTextMap, name=name, so=so)
        elif is_animated:
            name = "{}_{}_LayerAnim".format(self.material_name, self.texture_name)
            return exporter.mgr.find_create_key(plLayerAnimation, name=name, so=so)
        else:
            name = "{}_{}".format(self.material_name, self.texture_name)
            return exporter.mgr.find_create_key(plLayer, name=name, so=so)


_attrib_colors = {
    "ptAttribActivator": (0.031, 0.110, 0.290, 1.0),
    "ptAttribActivatorList": (0.451, 0.0, 0.263, 1.0),
    "ptAttribBoolean": (0.71, 0.706, 0.655, 1.0),
    "ptAttribResponder": (0.031, 0.110, 0.290, 1.0),
    "ptAttribResponderList": (0.031, 0.110, 0.290, 1.0),
    "ptAttribString": (0.675, 0.659, 0.494, 1.0),

    PlasmaAttribNumericNode.pl_attrib: (0.443, 0.439, 0.392, 1.0),
    PlasmaAttribObjectNode.pl_attrib: (0.565, 0.267, 0.0, 1.0),
    PlasmaAttribTextureNode.pl_attrib: (0.035, 0.353, 0.0, 1.0),
}
