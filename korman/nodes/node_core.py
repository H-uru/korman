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
from bpy.props import *
from PyHSPlasma import *
import time

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

    def get_key_name(self, single, suffix=None, bl=None, so=None):
        assert bl or so
        if single:
            name = bl.name if bl is not None else so.key.name
            if suffix:
                return "{}_{}_{}_{}".format(name, self.id_data.name, self.name, suffix)
            else:
                return "{}_{}_{}".format(name, self.id_data.name, self.name)
        else:
            if suffix:
                return "{}_{}_{}".format(self.id_data.name, self.name, suffix)
            else:
                return "{}_{}".format(self.id_data.name, self.name)

    def draw_label(self):
        if hasattr(self, "pl_label_attr") and self.hide:
            return str(getattr(self, self.pl_label_attrib, self.bl_label))
        return self.bl_label

    def export(self, exporter, bo, so):
        pass

    @property
    def export_once(self):
        """This node can only be exported once because it is a targeted plSingleModifier"""
        return False

    def _find_create_object(self, pClass, exporter, **kwargs):
        """Finds or creates an hsKeyedObject specific to this node."""
        assert "name" not in kwargs
        kwargs["name"] = self.get_key_name(issubclass(pClass, (plObjInterface, plSingleModifier)),
                                           kwargs.pop("suffix", ""), kwargs.get("bl"),
                                           kwargs.get("so"))
        return exporter.mgr.find_create_object(pClass, **kwargs)

    def _find_create_key(self, pClass, exporter, **kwargs):
        """Finds or creates a plKey specific to this node."""
        assert "name" not in kwargs
        kwargs["name"] = self.get_key_name(issubclass(pClass, (plObjInterface, plSingleModifier)),
                                           kwargs.pop("suffix", ""), kwargs.get("bl"),
                                           kwargs.get("so"))
        return exporter.mgr.find_create_key(pClass, **kwargs)

    def find_input(self, key, idname=None):
        for i in self.inputs:
            if i.alias == key:
                if i.links:
                    node = i.links[0].from_node
                    if idname is not None and idname != node.bl_idname:
                        return None
                    return node
                else:
                    return None
        raise KeyError(key)

    def find_inputs(self, key, idname=None):
        for i in self.inputs:
            if i.alias == key:
                if i.links:
                    node = i.links[0].from_node
                    if idname is None or idname == node.bl_idname:
                        yield node

    def find_input_socket(self, key, spawn_empty=False):
        # In the case that this socket will be used to make new input linkage,
        # we might want to allow the spawning of a new input socket... :)
        # This will only be done if the node's socket definitions allow it.
        options = self._socket_defs[0].get(key, {})
        spawn_empty = spawn_empty and options.get("spawn_empty", False)

        for i in self.inputs:
            if i.alias == key:
                if spawn_empty and i.is_linked:
                    continue
                return i
        if spawn_empty:
            return self._spawn_socket(key, options, self.inputs)
        else:
            raise KeyError(key)

    def find_input_sockets(self, key, idname=None):
        for i in self.inputs:
            if i.alias == key:
                if idname is None:
                    yield i
                elif i.links:
                    node = i.links[0].from_node
                    if idname == node.bl_idname:
                        yield i

    def find_output(self, key, idname=None):
        for i in self.outputs:
            if i.alias == key:
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
            if i.alias == key:
                for j in i.links:
                    node = j.to_node
                    if idname is not None and idname != node.bl_idname:
                        continue
                    yield node

    def find_output_socket(self, key, spawn_empty=False):
        # In the case that this socket will be used to make new output linkage,
        # we might want to allow the spawning of a new output socket... :)
        # This will only be done if the node's socket definitions allow it.
        options = self._socket_defs[1].get(key, {})
        spawn_empty = spawn_empty and options.get("spawn_empty", False)

        for i in self.outputs:
            if i.alias == key:
                if spawn_empty and i.is_linked:
                    continue
                return i
        if spawn_empty:
            return self._spawn_socket(key, options, self.outputs)
        raise KeyError(key)

    def find_output_sockets(self, key, idname=None):
        for i in self.outputs:
            if i.alias == key:
                if idname is None:
                    yield i
                elif i.links:
                    node = i.links[0].from_node
                    if idname == node.bl_idname:
                        yield i

    def generate_valid_links_for(self, context, socket, is_output):
        """Generates valid node sockets that can be linked to a specific socket on this node."""
        from .node_deprecated import PlasmaDeprecatedNode

        for dest_node_cls in bpy.types.Node.__subclasses__():
            if not issubclass(dest_node_cls, PlasmaNodeBase) or issubclass(dest_node_cls, PlasmaDeprecatedNode):
                continue

            # Korman standard node socket definitions
            socket_defs = getattr(dest_node_cls, "input_sockets", {}) if is_output else \
                          getattr(dest_node_cls, "output_sockets", {})
            for socket_name, socket_def in socket_defs.items():
                if socket_def.get("can_link") is False:
                    continue
                if socket_def.get("hidden") is True:
                    continue
                
                valid_source_nodes = socket_def.get("valid_link_nodes")
                valid_source_sockets = socket_def.get("valid_link_sockets")
                if valid_source_nodes is not None and self.bl_idname not in valid_source_nodes:
                    continue
                if valid_source_sockets is not None and socket.bl_idname not in valid_source_sockets:
                    continue
                if valid_source_sockets is None and valid_source_nodes is None:
                    if socket.bl_idname != socket_def["type"]:
                        continue

                # Can we even add the node?
                poll_add = getattr(dest_node_cls, "poll_add", None)
                if poll_add is not None and not poll_add(context):
                    continue

                yield { "node_idname": dest_node_cls.bl_idname,
                        "node_text": dest_node_cls.bl_label,
                        "socket_name": socket_name,
                        "socket_text": socket_def["text"] }

            # Some node types (eg Python) may auto-generate their own sockets, so we ask them now.
            for i in dest_node_cls.generate_valid_links_to(context, socket, is_output):
                yield i

    @classmethod
    def generate_valid_links_to(cls, context, socket, is_output):
        """Generates valid sockets on this node type that can be linked to a specific node's socket."""
        return []

    def harvest_actors(self):
        return set()

    def link_input(self, node, out_key, in_key):
        """Links a given Node's output socket to a given input socket on this Node"""
        if isinstance(in_key, str):
            in_socket = self.find_input_socket(in_key, spawn_empty=True)
        else:
            in_socket = in_key
        if isinstance(out_key, str):
            out_socket = node.find_output_socket(out_key, spawn_empty=True)
        else:
            out_socket = out_key
        link = self.id_data.links.new(in_socket, out_socket)

    def link_output(self, node, out_key, in_key):
        """Links a given Node's input socket to a given output socket on this Node"""
        if isinstance(in_key, str):
            in_socket = node.find_input_socket(in_key, spawn_empty=True)
        else:
            in_socket = in_key
        if isinstance(out_key, str):
            out_socket = self.find_output_socket(out_key, spawn_empty=True)
        else:
            out_socket = out_key
        link = self.id_data.links.new(in_socket, out_socket)

    @property
    def node_path(self):
        """Returns an absolute path to this Node. Needed because repr() uses an elipsis..."""
        return "{}.{}".format(repr(self.id_data), self.path_from_id())

    def previously_exported(self, exporter):
        return self.name in exporter.exported_nodes[self.id_data.name]

    @classmethod
    def poll(cls, context):
        return (context.bl_idname == "PlasmaNodeTree")

    def raise_error(self, message):
        final = "Plasma Node Tree '{}' Node '{}': {}".format(self.id_data.name, self.name, message)
        raise ExportError(final)

    @property
    def requires_actor(self):
        return False

    @property
    def _socket_defs(self):
        return (getattr(self.__class__, "input_sockets", {}),
                getattr(self.__class__, "output_sockets", {}))

    def _spawn_socket(self, key, options, sockets):
        socket = sockets.new(options["type"], options["text"], key)
        link_limit = options.get("link_limit", None)
        if link_limit is not None:
            socket.link_limit = link_limit
        socket.hide = options.get("hidden", False)
        socket.hide_value = options.get("hidden", False)
        return socket

    def _tattle(self, socket, link, reason):
        direction = "->" if socket.is_output else "<-"
        print("Removing {} {} {} {}".format(link.from_node.name, direction, link.to_node.name, reason))

    def unlink_outputs(self, alias, reason=None):
        links = self.id_data.links
        from_socket = next((i for i in self.outputs if i.alias == alias))
        i = 0
        while i < len(from_socket.links):
            link = from_socket.links[i]
            self._tattle(from_socket, link, reason if reason else "socket unlinked")
            links.remove(link)

    def update(self):
        """Ensures that sockets are linked appropriately and there are enough inputs"""
        input_defs, output_defs = self._socket_defs
        for defs, sockets in ((input_defs, self.inputs), (output_defs, self.outputs)):
            self._update_extant_sockets(defs, sockets)
            self._update_init_sockets(defs, sockets)

    def _update_init_sockets(self, defs, sockets):
        # Create any missing sockets and spawn any required empties.
        for alias, options in defs.items():
            working_sockets = [(i, socket) for i, socket in enumerate(sockets) if socket.alias == alias]
            if not working_sockets:
                self._spawn_socket(alias, options, sockets)
            elif options.get("spawn_empty", False):
                last_socket_id = next(reversed(working_sockets))[0]
                for working_id, working_socket in working_sockets:
                    if working_id == last_socket_id and working_socket.is_linked:
                        new_socket_id = len(sockets)
                        new_socket = self._spawn_socket(alias, options, sockets)
                        desired_id = last_socket_id + 1
                        if new_socket_id != desired_id:
                            sockets.move(new_socket_id, desired_id)
                    elif working_id < last_socket_id and not working_socket.is_linked:
                        # Indices do not update until after the update() function finishes, so
                        # no need to decrement last_socket_id
                        sockets.remove(working_socket)

    def _update_extant_sockets(self, defs, sockets):
        # Manually enumerate the sockets that are present for their presence and for the
        # validity of their links. Can't use a for because we will overrun and crash Blender.
        i = 0
        while i < len(sockets):
            socket = sockets[i]
            node = socket.node

            options = defs.get(socket.alias, None)
            if options is None or socket.bl_idname != options["type"]:
                sockets.remove(socket)
                continue

            # Make sure the socket info is up to date
            socket.name = options["text"]
            link_limit = options.get("link_limit", None)
            if link_limit is not None:
                socket.link_limit = link_limit
            socket.hide = options.get("hidden", False)
            socket.hide_value = options.get("hidden", False)

            # Make sure the link is good
            allowed_sockets = options.get("valid_link_sockets", None)
            allowed_nodes = options.get("valid_link_nodes", None)

            # The socket may decide it doesn't want anyone linked to it.
            can_link_attr = options.get("can_link", None)
            if can_link_attr is not None:
                can_link = getattr(node, can_link_attr)
                socket.enabled = can_link
                if not can_link:
                    for link in socket.links:
                        try:
                            self._tattle(socket, link, "(socket refused link)")
                            self.id_data.links.remove(link)
                        except RuntimeError:
                            # was already removed by someone else
                            pass

            # Helpful default... If neither are set, require the link to be to the same socket type
            if allowed_nodes is None and allowed_sockets is None:
                allowed_sockets = frozenset((options["type"],))
            if allowed_sockets or allowed_nodes:
                for link in socket.links:
                    if allowed_nodes:
                        to_from_node = link.to_node if socket.is_output else link.from_node
                        if to_from_node.bl_idname not in allowed_nodes:
                            try:
                                self._tattle(socket, link, "(bad node)")
                                self.id_data.links.remove(link)
                            except RuntimeError:
                                # was already removed by someone else
                                pass
                            continue
                    if allowed_sockets:
                        to_from_socket = link.to_socket if socket.is_output else link.from_socket
                        if to_from_socket is None or to_from_socket.bl_idname not in allowed_sockets:
                            try:
                                self._tattle(socket, link, "(bad socket)")
                                self.id_data.links.remove(link)
                            except RuntimeError:
                                # was already removed by someone else
                                pass
                            continue

            i += 1

    def _whine(self, msg, *args):
        if args:
            msg = msg.format(*args)
        print("'{}' Node '{}': Whinging about {}".format(self.bl_idname, self.name, msg))


class PlasmaTreeOutputNodeBase(PlasmaNodeBase):
    """Represents the final output of a node tree"""
    @classmethod
    def poll_add(cls, context):
        # There can only be one of these nodes per tree, so we will only allow this to be
        # added if no other output nodes are found.
        return not any((isinstance(node, cls) for node in context.space_data.node_tree.nodes))


class PlasmaNodeSocketBase:
    @property
    def alias(self):
        """Blender appends .000 stuff if it's a dupe. We don't care about dupe identifiers..."""
        ident = self.identifier
        if ident.find('.') == -1:
            return ident
        return ident.rsplit('.', 1)[0]

    def draw(self, context, layout, node, text):
        if not self.is_output:
            self.draw_add_operator(context, layout, node)
        self.draw_content(context, layout, node, text)
        if self.is_output:
            self.draw_add_operator(context, layout, node)

    def draw_add_operator(self, context, layout, node):
        row = layout.row()
        row.enabled = self.has_possible_links
        row.operator_context = "INVOKE_DEFAULT"
        add_op = row.operator("node.plasma_create_link_node", text="", icon="ZOOMIN")
        add_op.node_name = node.name
        add_op.sock_ident = self.identifier
        add_op.is_output = self.is_output

    def draw_color(self, context, node):
        # It's so tempting to just do RGB sometimes... Let's be nice.
        if len(self.bl_color) == 3:
            return tuple(self.bl_color[0], self.bl_color[1], self.bl_color[2], 1.0)
        return self.bl_color

    def draw_content(self, context, layout, node, text):
        layout.label(text)

    def _has_possible_links(self):
        tval = time.monotonic()
        if (tval - self.possible_links_update_time) > 2:
            # Danger: hax!
            # We don't want to unleash errbody at exactly the same time. The good news is that
            # ***CURRENTLY*** the only way for the result to change is for a new PY file to be
            # loaded. So, only check in that case.
            hval = str(hash((i for i in bpy.data.texts)))
            if hval != self.possible_links_texts_hash:
                self.has_possible_links_value = any(self.node.generate_valid_links_for(bpy.context,
                                                                                       self,
                                                                                       self.is_output))
                self.possible_links_texts_hash = hval
            self.possible_links_update_time = tval
        return self.has_possible_links_value

    @property
    def is_used(self):
        return bool(self.links)

    @classmethod
    def register(cls):
        cls.has_possible_links = BoolProperty(options={"HIDDEN", "SKIP_SAVE"},
                                              get=cls._has_possible_links)
        cls.has_possible_links_value = BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
        cls.possible_links_update_time = FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
        cls.possible_links_texts_hash = StringProperty(options={"HIDDEN", "SKIP_SAVE"})


class PlasmaNodeSocketInputGeneral(PlasmaNodeSocketBase, bpy.types.NodeSocket):
    """A general input socket that will steal the output's color"""
    def draw_color(self, context, node):
        if self.is_linked:
            return self.links[0].from_socket.draw_color(context, node)
        else:
            return (0.0, 0.0, 0.0, 0.0)


class PlasmaNodeTree(bpy.types.NodeTree):
    bl_idname = "PlasmaNodeTree"
    bl_label = "Plasma"
    bl_icon = "NODETREE"

    def export(self, exporter, bo, so):
        exported_nodes = exporter.exported_nodes.setdefault(self.name, set())
        for node in self.nodes:
            if not (node.export_once and node.previously_exported(exporter)):
                node.export(exporter, bo, so)
                exported_nodes.add(node.name)

    def find_output(self, idname):
        for node in self.nodes:
            if node.bl_idname == idname:
                return node
        return None

    def harvest_actors(self):
        actors = set()
        for node in self.nodes:
            harvest_method = getattr(node, "harvest_actors", None)
            if harvest_method is not None:
                actors.update(harvest_method())
            elif not isinstance(node, PlasmaNodeBase):
                raise ExportError("Plasma Node Tree '{}' Node '{}': is not a valid node for this tree".format(self.id_data.name, node.name))
        return actors

    @classmethod
    def poll(cls, context):
        return (context.scene.render.engine == "PLASMA_GAME")

    @property
    def requires_actor(self):
        return any((node.requires_actor for node in self.nodes))


# Welcome to HAXland!
# Blender 2.79 is great in that it allows us to have ID Datablock pointer properties everywhere.
# However, there is an error in the way user refcounts are handled in node trees. When a node is freed,
# it always decrements the user count. Good. But, the node tree decrements that same count again, resulting
# in a use-after-free (or double-free?) crash in Blender. I modelled and submitted a fix (see: Blender D4196)
# but a workaround is to just remove the nodes from all Plasma node trees before the data is unloaded. :)
@bpy.app.handlers.persistent
def _nuke_plasma_nodes(dummy):
    for i in bpy.data.node_groups:
        if isinstance(i, PlasmaNodeTree):
            i.nodes.clear()
bpy.app.handlers.load_pre.append(_nuke_plasma_nodes)
