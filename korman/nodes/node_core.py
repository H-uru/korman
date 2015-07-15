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

import abc
import bpy
from PyHSPlasma import plMessage, plNotifyMsg

from ..exporter import ExportError

class PlasmaNodeBase:
    def generate_notify_msg(self, exporter, so, socket_id, idname=None):
        notify = plNotifyMsg()
        notify.BCastFlags = (plMessage.kNetPropagate | plMessage.kLocalPropagate)
        for i in self.find_outputs(socket_id, idname):
            key = i.get_key(exporter, so)
            if key is None:
                exporter.report.warn(" '{}' Node '{}' doesn't expose a key. It won't be triggered by '{}'!".format(i.bl_idname, i.name, self.name), indent=3)
            elif isinstance(key, tuple):
                for i in key:
                    notify.addReceiver(key)
            else:
                notify.addReceiver(key)
        return notify

    def get_key(self, exporter, so):
        return None

    def export(self, exporter, bo, so):
        pass

    def find_input(self, key, idname=None):
        for i in self.inputs:
            if i.identifier == key:
                if i.links:
                    node = i.links[0].from_node
                    if idname is not None and idname != node.bl_idname:
                        return None
                    return node
                else:
                    return None
        raise KeyError(key)

    def find_input_socket(self, key):
        for i in self.inputs:
            if i.identifier == key:
                return i
        raise KeyError(key)

    def find_input_sockets(self, key, idname=None):
        for i in self.inputs:
            if i.identifier == key:
                if idname is None:
                    yield i
                elif i.links:
                    node = i.links[0].from_node
                    if idname == node.bl_idname:
                        yield i

    def find_output(self, key, idname=None):
        for i in self.outputs:
            if i.identifier == key:
                if i.links:
                    node = i.links[0].to_node
                    if idname is not None and idname != node.bl_idname:
                        return None
                    return node
                else:
                    return None
        raise KeyError(key)

    def find_outputs(self, key, idname=None):
        for i in self.outputs:
            if i.identifier == key:
                for j in i.links:
                    node = j.to_node
                    if idname is not None and idname != node.bl_idname:
                        continue
                    yield node

    def find_output_socket(self, key):
        for i in self.outputs:
            if i.identifier == key:
                return i
        raise KeyError(key)

    def harvest_actors(self):
        return set()

    @property
    def key_name(self):
        return "{}_{}".format(self.id_data.name, self.name)

    def link_input(self, node, out_key, in_key):
        """Links a given Node's output socket to a given input socket on this Node"""
        if isinstance(in_key, str):
            in_socket = self.find_input_socket(in_key)
        else:
            in_socket = in_key
        if isinstance(out_key, str):
            out_socket = node.find_output_socket(out_key)
        else:
            out_socket = out_key
        link = self.id_data.links.new(in_socket, out_socket)

    def link_output(self, node, out_key, in_key):
        """Links a given Node's input socket to a given output socket on this Node"""
        if isinstance(in_key, str):
            in_socket = node.find_input_socket(in_key)
        else:
            in_socket = in_key
        if isinstance(out_key, str):
            out_socket = self.find_output_socket(out_key)
        else:
            out_socket = out_key
        link = self.id_data.links.new(in_socket, out_socket)

    @property
    def node_path(self):
        """Returns an absolute path to this Node. Needed because repr() uses an elipsis..."""
        return "{}.{}".format(repr(self.id_data), self.path_from_id())

    @classmethod
    def poll(cls, context):
        return (context.bl_idname == "PlasmaNodeTree")

    def raise_error(self, message):
        final = "Plasma Node Tree '{}' Node '{}': {}".format(self.id_data.name, self.name, message)
        raise ExportError(final)

    @property
    def requires_actor(self):
        return False


class PlasmaNodeVariableInput(PlasmaNodeBase):
    def ensure_sockets(self, idname, name, identifier=None):
        """Ensures there is one (and only one) empty input socket"""
        empty = [i for i in self.inputs if i.bl_idname == idname and not i.links]
        if not empty:
            if identifier is None:
                self.inputs.new(idname, name)
            else:
                self.inputs.new(idname, name, identifier)
        while len(empty) > 1:
            self.inputs.remove(empty.pop())


class PlasmaNodeSocketBase:
    def draw(self, context, layout, node, text):
        layout.label(text)

    def draw_color(self, context, node):
        # It's so tempting to just do RGB sometimes... Let's be nice.
        if len(self.bl_color) == 3:
            return tuple(self.bl_color[0], self.bl_color[1], self.bl_color[2], 1.0)
        return self.bl_color


class PlasmaNodeTree(bpy.types.NodeTree):
    bl_idname = "PlasmaNodeTree"
    bl_label = "Plasma"
    bl_icon = "NODETREE"

    def export(self, exporter, bo, so):
        # just pass it off to each node
        for node in self.nodes:
            node.export(exporter, bo, so)

    def harvest_actors(self):
        actors = set()
        for node in self.nodes:
            actors.update(node.harvest_actors())
        return actors

    @classmethod
    def poll(cls, context):
        return (context.scene.render.engine == "PLASMA_GAME")
