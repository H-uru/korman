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

from contextlib import ExitStack
import itertools
import math
from pathlib import Path
from typing import *

from PyHSPlasma import *

from ...addon_prefs import game_versions
from ...exporter import ExportError, utils
from .base import PlasmaModifierProperties, PlasmaModifierLogicWiz
from ... import helpers, idprops

if TYPE_CHECKING:
    from ...exporter import Exporter
    from .game_gui import PlasmaGameGuiDialogModifier


journal_pfms = {
    pvPots : {
        # Supplied by the OfflineKI script:
        # https://gitlab.com/diafero/offline-ki/blob/master/offlineki/xSimpleJournal.py
        "filename": "xSimpleJournal.py",
        "attribs": (
            { 'id':  1, 'type': "ptAttribActivator", "name": "bookClickable" },
            { 'id':  2, 'type': "ptAttribString",    "name": "journalFileName" },
            { 'id':  3, 'type': "ptAttribBoolean",   "name": "isNotebook" },
            { 'id':  4, 'type': "ptAttribFloat",     "name": "BookWidth" },
            { 'id':  5, 'type': "ptAttribFloat",     "name": "BookHeight" },
        )
    },
    pvMoul : {
        "filename": "xJournalBookGUIPopup.py",
        "attribs": (
            { 'id':  1, 'type': "ptAttribActivator", 'name': "actClickableBook" },
            { 'id': 10, 'type': "ptAttribBoolean",   'name': "StartOpen" },
            { 'id': 11, 'type': "ptAttribFloat",     'name': "BookWidth" },
            { 'id': 12, 'type': "ptAttribFloat",     'name': "BookHeight" },
            { 'id': 13, 'type': "ptAttribString",    'name': "LocPath" },
            { 'id': 14, 'type': "ptAttribString",    'name': "GUIType" },
        )
    },
}

# Do not change the numeric IDs. They allow the list to be rearranged.
_languages = [("Dutch", "Nederlands", "Dutch", 0),
              ("English", "English", "", 1),
              ("Finnish", "Suomi", "Finnish", 2),
              ("French", "Français", "French", 3),
              ("German", "Deutsch", "German", 4),
              ("Hungarian", "Magyar", "Hungarian", 5),
              ("Italian", "Italiano ", "Italian", 6),
              # Blender 2.79b can't render 日本語 by default
              ("Japanese", "Nihongo", "Japanese", 7),
              ("Norwegian", "Norsk", "Norwegian", 8),
              ("Polish", "Polski", "Polish", 9),
              ("Romanian", "Română", "Romanian", 10),
              ("Russian", "Pyccĸий", "Russian", 11),
              ("Spanish", "Español", "Spanish", 12),
              ("Swedish", "Svenska", "Swedish", 13)]
languages = sorted(_languages, key=lambda x: x[1])
_DEFAULT_LANGUAGE_NAME = "English"
_DEFAULT_LANGUAGE_ID = 1


class ImageLibraryItem(bpy.types.PropertyGroup):
    image = bpy.props.PointerProperty(name="Image Item",
                                      description="Image stored for export.",
                                      type=bpy.types.Image,
                                      options=set())
    enabled = bpy.props.BoolProperty(name="Enabled",
                                     description="Specifies whether this image will be stored during export.",
                                     default=True,
                                     options=set())


class PlasmaImageLibraryModifier(PlasmaModifierProperties):
    pl_id = "imagelibmod"

    bl_category = "GUI"
    bl_label = "Image Library"
    bl_description = "A collection of images to be stored for later use"
    bl_icon = "RENDERLAYERS"

    images = CollectionProperty(name="Images", type=ImageLibraryItem, options=set())
    active_image_index = IntProperty(options={"HIDDEN"})

    def export(self, exporter, bo, so):
        if self.images:
            ilmod = exporter.mgr.find_create_object(plImageLibMod, so=so, name=self.key_name)

            for item in self.images:
                if item.image and item.enabled:
                    exporter.mesh.material.export_prepared_image(owner=ilmod, image=item.image, allowed_formats={"JPG", "PNG"}, extension="hsm")


class PlasmaJournalTranslation(bpy.types.PropertyGroup):
    def _poll_nonpytext(self, value):
        return not value.name.endswith(".py")

    language = EnumProperty(name="Language",
                            description="Language of this translation",
                            items=languages,
                            default=_DEFAULT_LANGUAGE_NAME,
                            options=set())
    text_id = PointerProperty(name="Contents",
                              description="Text data block containing the text for this language",
                              type=bpy.types.Text,
                              poll=_poll_nonpytext,
                              options=set())


class TranslationMixin:
    def export_localization(self, exporter):
        translations = [i for i in self.translations if i.text_id is not None]
        if not translations:
            exporter.report.error(f"'{self.id_data.name}': '{self.bl_label}' No content translations available. The localization will not be exported.")
            return
        for i in translations:
            exporter.locman.add_string(self.localization_set, self.key_name, i.language, i.text_id)

    def _get_translation(self):
        # Ensure there is always a default (read: English) translation available.
        default_idx, default = next(((idx, translation) for idx, translation in enumerate(self.translations)
                                    if translation.language == _DEFAULT_LANGUAGE_NAME), (None, None))
        if default is None:
            default_idx = len(self.translations)
            default = self.translations.add()
            default.language = _DEFAULT_LANGUAGE_NAME
        if self.active_translation_index < len(self.translations):
            language = self.translations[self.active_translation_index].language
        else:
            self.active_translation_index = default_idx
            language = default.language

        # Due to the fact that we are using IDs to keep the data from becoming insane on new
        # additions, we must return the integer id...
        return next((idx for key, _, _, idx in languages if key == language))

    def _set_translation(self, value):
        # We were given an int here, must change to a string
        language_name = next((key for key, _, _, i in languages if i == value))
        idx = next((idx for idx, translation in enumerate(self.translations)
                   if translation.language == language_name), None)
        if idx is None:
            self.active_translation_index = len(self.translations)
            translation = self.translations.add()
            translation.language = language_name
        else:
            self.active_translation_index = idx

    @property
    def localization_set(self):
        raise RuntimeError("TranslationMixin subclass needs a localization set getter!")

    @property
    def translations(self):
        raise RuntimeError("TranslationMixin subclass needs a translation getter!")


class PlasmaJournalBookModifier(PlasmaModifierProperties, PlasmaModifierLogicWiz, TranslationMixin):
    pl_id = "journalbookmod"

    bl_category = "GUI"
    bl_label = "Journal"
    bl_description = "Journal Book"
    bl_icon = "WORDWRAP_ON"

    versions = EnumProperty(name="Export Targets",
                            description="Plasma versions for which this journal exports",
                            items=game_versions,
                            options={"ENUM_FLAG"},
                            default={"pvMoul"})
    start_state = EnumProperty(name="Start",
                               description="State of journal when activated",
                               items=[("OPEN", "Open", "Journal will start opened to first page"),
                                      ("CLOSED", "Closed", "Journal will start closed showing cover")],
                               default="CLOSED")
    book_type = EnumProperty(name="Book Type",
                             description="GUI type to be used for the journal",
                             items=[("bkBook", "Book", "A journal written on worn, yellowed paper"),
                                    ("bkNotebook", "Notebook", "A journal written on white, lined paper")],
                             default="bkBook")
    book_scale_w = IntProperty(name="Book Width Scale",
                               description="Width scale",
                               default=100, min=0, max=100,
                               subtype="PERCENTAGE")
    book_scale_h = IntProperty(name="Book Height Scale",
                               description="Height scale",
                               default=100, min=0, max=100,
                               subtype="PERCENTAGE")
    clickable_region = PointerProperty(name="Region",
                                       description="Region inside which the avatar must stand to be able to open the journal (optional)",
                                       type=bpy.types.Object,
                                       poll=idprops.poll_mesh_objects)

    journal_translations = CollectionProperty(name="Journal Translations",
                                              type=PlasmaJournalTranslation,
                                              options=set())
    active_translation_index = IntProperty(options={"HIDDEN"})
    active_translation = EnumProperty(name="Language",
                                      description="Language of this translation",
                                      items=languages,
                                      get=TranslationMixin._get_translation,
                                      set=TranslationMixin._set_translation,
                                      options=set())

    def pre_export(self, exporter, bo):
        our_versions = (globals()[j] for j in self.versions)
        version = exporter.mgr.getVer()
        if version not in our_versions:
            # We aren't needed here
            exporter.report.port("Object '{}' has a JournalMod not enabled for export to the selected engine.  Skipping.",
                                 bo.name, version)
            return

        # Generate the clickable region if it was not provided
        yield utils.pre_export_optional_cube_region(
            self, "clickable_region",
            f"{bo.name}_Journal_ClkRgn", 6.0, bo
        )

        # Generate the logic nodes
        yield self.convert_logic(bo, age_name=exporter.age_name, version=version)

    def logicwiz(self, bo, tree, age_name, version):
        # Assign journal script based on target version
        journal_pfm = journal_pfms[version]
        journalnode = self._create_python_file_node(tree, journal_pfm["filename"], journal_pfm["attribs"])
        if version <= pvPots:
            self._create_pots_nodes(bo, tree.nodes, journalnode, age_name)
        else:
            self._create_moul_nodes(bo, tree.nodes, journalnode, age_name)

    def _create_pots_nodes(self, clickable_object, nodes, journalnode, age_name):
        clickable_region = nodes.new("PlasmaClickableRegionNode")
        clickable_region.region_object = self.clickable_region

        facing_object = nodes.new("PlasmaFacingTargetNode")
        facing_object.directional = False
        facing_object.tolerance = math.degrees(-1)

        clickable = nodes.new("PlasmaClickableNode")
        clickable.link_input(clickable_region, "satisfies", "region")
        clickable.link_input(facing_object, "satisfies", "facing")
        clickable.link_output(journalnode, "satisfies", "bookClickable")
        clickable.clickable_object = clickable_object

        srcfile = nodes.new("PlasmaAttribStringNode")
        srcfile.link_output(journalnode, "pfm", "journalFileName")
        srcfile.value = self.key_name

        guitype = nodes.new("PlasmaAttribBoolNode")
        guitype.link_output(journalnode, "pfm", "isNotebook")
        guitype.value = self.book_type == "bkNotebook"

        width = nodes.new("PlasmaAttribIntNode")
        width.link_output(journalnode, "pfm", "BookWidth")
        width.value_float = self.book_scale_w / 100.0

        height = nodes.new("PlasmaAttribIntNode")
        height.link_output(journalnode, "pfm", "BookHeight")
        height.value_float = self.book_scale_h / 100.0

    def _create_moul_nodes(self, clickable_object, nodes, journalnode, age_name):
        clickable_region = nodes.new("PlasmaClickableRegionNode")
        clickable_region.region_object = self.clickable_region

        facing_object = nodes.new("PlasmaFacingTargetNode")
        facing_object.directional = False
        facing_object.tolerance = math.degrees(-1)

        clickable = nodes.new("PlasmaClickableNode")
        clickable.link_input(clickable_region, "satisfies", "region")
        clickable.link_input(facing_object, "satisfies", "facing")
        clickable.link_output(journalnode, "satisfies", "actClickableBook")
        clickable.clickable_object = clickable_object

        start_open = nodes.new("PlasmaAttribBoolNode")
        start_open.link_output(journalnode, "pfm", "StartOpen")
        start_open.value = self.start_state == "OPEN"

        width = nodes.new("PlasmaAttribIntNode")
        width.link_output(journalnode, "pfm", "BookWidth")
        width.value_float = self.book_scale_w / 100.0

        height = nodes.new("PlasmaAttribIntNode")
        height.link_output(journalnode, "pfm", "BookHeight")
        height.value_float = self.book_scale_h / 100.0

        locpath = nodes.new("PlasmaAttribStringNode")
        locpath.link_output(journalnode, "pfm", "LocPath")
        locpath.value = "{}.{}.{}".format(age_name, self.localization_set, self.key_name)

        guitype = nodes.new("PlasmaAttribStringNode")
        guitype.link_output(journalnode, "pfm", "GUIType")
        guitype.value = self.book_type

    @property
    def localization_set(self):
        return "Journals"

    @property
    def requires_actor(self):
        # We are too late in the export to be harvested automatically, so let's be explicit
        return True

    @property
    def translations(self):
        # Backwards compatibility thunk.
        return self.journal_translations


linking_pfms = {
    pvPots : {
        # Supplied by the OfflineKI script:
        # https://gitlab.com/diafero/offline-ki/blob/master/offlineki/xSimpleLinkingBook.py
        "filename": "xSimpleLinkingBook.py",
        "attribs": (
            { 'id':  1, 'type': "ptAttribActivator", "name": "bookClickable" },
            { 'id':  2, 'type': "ptAttribString",    "name": "destinationAge" },
            { 'id':  3, 'type': "ptAttribString",    "name": "spawnPoint" },
            { 'id':  4, 'type': "ptAttribString",    "name": "linkPanel" },
            { 'id':  5, 'type': "ptAttribString",    "name": "bookCover" },
            { 'id':  6, 'type': "ptAttribString",    "name": "stampTexture" },
            { 'id':  7, 'type': "ptAttribFloat",     "name": "stampX" },
            { 'id':  8, 'type': "ptAttribFloat",     "name": "stampY" },
            { 'id':  9, 'type': "ptAttribFloat",     "name": "bookWidth" },
            { 'id': 10, 'type': "ptAttribFloat",     "name": "BookHeight" },
            { 'id': 11, 'type': "ptAttribBehavior",  "name": "msbSeekBeforeUI" },
            { 'id': 12, 'type': "ptAttribResponder", "name": "respOneShot" },
        )
    },
    pvMoul : {
        "filename": "xLinkingBookGUIPopup.py",
        "attribs": (
            { 'id':  1, 'type': "ptAttribActivator", 'name': "actClickableBook" },
            { 'id':  2, 'type': "ptAttribBehavior",  'name': "SeekBehavior" },
            { 'id':  3, 'type': "ptAttribResponder", 'name': "respLinkResponder" },
            { 'id':  4, 'type': "ptAttribString",    'name': "TargetAge" },
            { 'id':  5, 'type': "ptAttribActivator", 'name': "actBookshelf" },
            { 'id':  6, 'type': "ptAttribActivator", 'name': "shareRegion" },
            { 'id':  7, 'type': "ptAttribBehavior",  'name': "shareBookSeek" },
            { 'id': 10, 'type': "ptAttribBoolean",   'name': "IsDRCStamped" },
            { 'id': 11, 'type': "ptAttribBoolean",   'name': "ForceThirdPerson" },
        )
    },
}


class PlasmaLinkingBookModifier(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "linkingbookmod"

    bl_category = "GUI"
    bl_label = "Linking Book"
    bl_description = "Linking Book"
    bl_icon = "FILE_IMAGE"

    versions = EnumProperty(name="Export Targets",
                            description="Plasma versions for which this journal exports",
                            items=game_versions,
                            options={"ENUM_FLAG"},
                            default={"pvMoul"})

    # Link Info
    link_type = EnumProperty(name="Linking Type",
                             description="The type of Link this Linking Book will use",
                             items=[
                                 ("kBasicLink", "Public Link", "Links to a public instance of the specified Age"),
                                 ("kOriginalBook", "Private Link", "Links to a new or existing private instance of the specified Age"),
                                 ("kSubAgeBook", "Closed Loop Link", "Links between instances of the specifed Age and the current one"),],
                             options=set(),
                             default="kOriginalBook")
    age_name = StringProperty(name="Age Name",
                              description="Filename of the Age to link to (e.g. Garrison)",)
    age_instance = StringProperty(name="Age Instance",
                                  description="Friendly name of the Age to link to (e.g. Gahreesen)",)
    age_uuid = StringProperty(name="Age GUID",
                              description="GUID for a specific instance (used with public Ages)",)
    age_parent = StringProperty(name="Parent Age",
                                description="Name of the Child Age's parent Age",)

    spawn_title = StringProperty(name="Spawn Title",
                                 description="Title of the Spawn Point",
                                 default="Default")
    spawn_point = StringProperty(name="Spawn Point",
                                 description="Name of the Spawn Point to arrive at after the link",
                                 default="LinkInPointDefault")
    anim_type = EnumProperty(name="Link Animation",
                             description="Type of Linking Animation to use",
                             items=[("LinkOut", "Standing", "The avatar steps up to the book and places their hand on the panel"),
                                    ("FishBookLinkOut", "Kneeling", "The avatar kneels in front of the book and places their hand on the panel"),],
                             default="LinkOut",
                             options=set())
    link_destination = StringProperty(name="Linking Panel Name",
                                      description="Optional: Name of Linking Panel to use for this link-in point if it differs from the Age Name",)

    # Interactables
    seek_point = PointerProperty(name="Seek Point",
                                 description="The point the avatar will seek to before opening the Linking Book GUI",
                                 type=bpy.types.Object,
                                 poll=idprops.poll_empty_objects)
    clickable_region = PointerProperty(name="Clickable Region",
                                       description="The region in which the avatar must be standing before they can click on the Linking Book",
                                       type=bpy.types.Object,
                                       poll=idprops.poll_mesh_objects)
    clickable = PointerProperty(name="Clickable",
                                description="The object the avatar will click on to activate the Linking Book GUI",
                                type=bpy.types.Object,
                                poll=idprops.poll_mesh_objects)
    shareable = BoolProperty(name="Shareable",
                             description="Enable the Book to be Shareable (MOUL private instance only)",
                             default=True,
                             options=set())
    share_region = PointerProperty(name="Share Region",
                                   description="Sets the share region in which the receiving avatar must stand",
                                   type=bpy.types.Object,
                                   poll=idprops.poll_mesh_objects)

    # -- Path of the Shell options --
    # Popup Appearance
    book_cover_image = PointerProperty(name="Book Cover",
                                       description="Image to use for the Linking Book's cover (Optional: book starts open if left blank)",
                                       type=bpy.types.Image,
                                       options=set())
    link_panel_image = PointerProperty(name="Linking Panel",
                                       description="Image to use for the Linking Panel",
                                       type=bpy.types.Image,
                                       options=set())
    stamp_image = PointerProperty(name="Stamp Image",
                                  description="Image to use for the stamp on the page opposite the book's linking panel, if any",
                                  type=bpy.types.Image,
                                  options=set())
    stamp_x = IntProperty(name="Stamp Position X",
                          description="X position of Stamp",
                          default=140,
                          subtype="UNSIGNED")
    stamp_y = IntProperty(name="Stamp Position Y",
                          description="Y position of Stamp",
                          default=255,
                          subtype="UNSIGNED")

    def _check_version(self, *args) -> bool:
        our_versions = frozenset((globals()[j] for j in self.versions))
        return frozenset(args) & our_versions

    def pre_export(self, exporter, bo):
        if not self._check_version(exporter.mgr.getVer()):
            # We aren't needed here
            exporter.report.port(f"Object '{self.id_data.name}' has a LinkingBookMod not enabled for export to the selected engine.  Skipping.")
            return

        # Auto-generate a six-foot cube region around the clickable if none was provided.
        yield utils.pre_export_optional_cube_region(
            self, "clickable_region",
            f"{self.key_name}_LinkingBook_ClkRgn", 6.0,
            self.clickable
        )

        # Auto-generate a ten-foot cube region around the clickable if none was provided.
        if self.shareable:
            yield utils.pre_export_optional_cube_region(
                self, "share_region",
                f"{self.key_name}_LinkingBook_ShareRgn", 10.0,
                self.clickable
            )

        yield self.convert_logic(bo, age_name=exporter.age_name, version=exporter.mgr.getVer())

    def export(self, exporter, bo, so):
        if self._check_version(pvPrime, pvPots):
            # Create ImageLibraryMod in which to store the Cover, Linking Panel, and Stamp images
            ilmod = exporter.mgr.find_create_object(plImageLibMod, so=so, name=self.key_name)

            user_images = (i for i in (self.book_cover_image, self.link_panel_image, self.stamp_image)
                           if i is not None)
            for image in user_images:
                exporter.mesh.material.export_prepared_image(owner=ilmod, image=image,
                                                             allowed_formats={"JPG", "PNG"}, extension="hsm")

    def harvest_actors(self):
        if self.seek_point is not None:
            yield self.seek_point.name

    def logicwiz(self, bo, tree, age_name, version):
        # Assign linking book script based on target version
        linking_pfm = linking_pfms[version]
        linkingnode = self._create_python_file_node(tree, linking_pfm["filename"], linking_pfm["attribs"])
        if version <= pvPots:
            self._create_pots_nodes(bo, tree.nodes, linkingnode, age_name)
        else:
            self._create_moul_nodes(bo, tree.nodes, linkingnode, age_name)

    def _create_pots_nodes(self, clickable_object, nodes, linkingnode, age_name):
        # Clickable
        clickable_region = nodes.new("PlasmaClickableRegionNode")
        clickable_region.region_object = self.clickable_region

        clickable = nodes.new("PlasmaClickableNode")
        clickable.clickable_object = self.clickable
        clickable.find_input_socket("facing").allow_simple = False
        clickable.link_input(clickable_region, "satisfies", "region")
        clickable.link_output(linkingnode, "satisfies", "bookClickable")

        # Destination Age Name
        age_name = nodes.new("PlasmaAttribStringNode")
        age_name.value = self.age_name
        age_name.link_output(linkingnode, "pfm", "destinationAge")

        # Spawn Point Name
        spawn_point = nodes.new("PlasmaAttribStringNode")
        spawn_point.value = self.spawn_point
        spawn_point.link_output(linkingnode, "pfm", "spawnPoint")

        # Book Cover Image
        if self.book_cover_image:
            book_cover_name = nodes.new("PlasmaAttribStringNode")
            book_cover_name.value = str(Path(self.book_cover_image.name).with_suffix(".hsm"))
            book_cover_name.link_output(linkingnode, "pfm", "bookCover")

        # Linking Panel Image
        if self.link_panel_image:
            linking_panel_name = nodes.new("PlasmaAttribStringNode")
            linking_panel_name.value = str(Path(self.link_panel_image.name).with_suffix(".hsm"))
            linking_panel_name.link_output(linkingnode, "pfm", "linkPanel")

        # Stamp Image
        if self.stamp_image:
            stamp_texture_name = nodes.new("PlasmaAttribStringNode")
            stamp_texture_name.value = str(Path(self.stamp_image.name).with_suffix(".hsm"))
            stamp_texture_name.link_output(linkingnode, "pfm", "stampTexture")

            # Stamp X Position
            stamp_x = nodes.new("PlasmaAttribIntNode")
            stamp_x.value = self.stamp_x
            stamp_x.link_output(linkingnode, "pfm", "stampX")

            # Stamp Y Position
            stamp_y = nodes.new("PlasmaAttribIntNode")
            stamp_y.value = self.stamp_y
            stamp_y.link_output(linkingnode, "pfm", "stampY")

        # MSB
        seek = nodes.new("PlasmaSeekTargetNode")
        seek.target = self.seek_point

        anim_stage = nodes.new("PlasmaAnimStageNode")
        anim_stage.anim_name = "LinkOut"
        anim_settings = nodes.new("PlasmaAnimStageSettingsNode")
        anim_settings.forward = "kPlayAuto"
        anim_settings.stage_advance = "kAdvanceAuto"
        anim_stage.link_input(anim_settings, "stage", "stage_settings")

        msb = nodes.new("PlasmaMultiStageBehaviorNode")
        msb.link_input(seek, "seekers", "seek_target")
        msb.link_input(anim_stage, "stage", "stage_refs")
        msb.link_output(linkingnode, "hosts", "msbSeekBeforeUI")

        # Responder
        one_shot = nodes.new("PlasmaOneShotMsgNode")
        one_shot.animation = self.anim_type
        one_shot.marker = "touch"
        one_shot.pos_object = self.seek_point

        responder_state = nodes.new("PlasmaResponderStateNode")
        responder_state.link_output(one_shot, "msgs", "sender")

        responder = nodes.new("PlasmaResponderNode")
        responder.link_output(responder_state, "state_refs", "resp")
        responder.link_output(linkingnode, "keyref", "respOneShot")

    def _create_moul_nodes(self, clickable_object, nodes, linkingnode, age_name):
        # Clickable
        clickable_region = nodes.new("PlasmaClickableRegionNode")
        clickable_region.region_object = self.clickable_region

        clickable = nodes.new("PlasmaClickableNode")
        clickable.clickable_object = self.clickable
        clickable.find_input_socket("facing").allow_simple = False
        clickable.link_input(clickable_region, "satisfies", "region")
        clickable.link_output(linkingnode, "satisfies", "actClickableBook")

        # MSB
        seek = nodes.new("PlasmaSeekTargetNode")
        seek.target = self.seek_point

        anim_stage = nodes.new("PlasmaAnimStageNode")
        anim_stage.anim_name = "LinkOut"
        anim_settings = nodes.new("PlasmaAnimStageSettingsNode")
        anim_settings.forward = "kPlayAuto"
        anim_settings.stage_advance = "kAdvanceAuto"
        anim_stage.link_input(anim_settings, "stage", "stage_settings")

        msb = nodes.new("PlasmaMultiStageBehaviorNode")
        msb.link_input(seek, "seekers", "seek_target")
        msb.link_input(anim_stage, "stage", "stage_refs")
        msb.link_output(linkingnode, "hosts", "SeekBehavior")

        # Responder
        link_message = nodes.new("PlasmaLinkToAgeMsg")
        link_message.rules = self.link_type
        link_message.parent_filename = self.age_parent
        link_message.age_filename = self.age_name
        link_message.age_instance = self.age_instance
        link_message.age_uuid = self.age_uuid
        link_message.spawn_title = self.spawn_title
        link_message.spawn_point = self.spawn_point

        one_shot = nodes.new("PlasmaOneShotMsgNode")
        one_shot.animation = self.anim_type
        one_shot.marker = "touch"
        one_shot.pos_object = self.seek_point
        one_shot.link_output(link_message, "msgs", "sender")

        responder_state = nodes.new("PlasmaResponderStateNode")
        responder_state.link_output(one_shot, "msgs", "sender")

        responder = nodes.new("PlasmaResponderNode")
        responder.link_output(responder_state, "state_refs", "resp")
        responder.link_output(linkingnode, "keyref", "respLinkResponder")

        # Linking Panel Name
        linking_panel_name = nodes.new("PlasmaAttribStringNode")
        linking_panel_name.value = self.link_destination if self.link_destination else self.age_name
        linking_panel_name.link_output(linkingnode, "pfm", "TargetAge")

        # Share MSB
        if self.shareable:
            # Region
            share_msb_region = nodes.new("PlasmaVolumeSensorNode")
            share_msb_region.region_object = self.share_region
            for i in share_msb_region.inputs:
                i.allow = True
            share_msb_region.link_output(linkingnode, "satisfies", "shareRegion")
            # MSB Behavior
            share_seek = nodes.new("PlasmaSeekTargetNode")
            share_seek.target = self.seek_point

            share_anim_stage = nodes.new("PlasmaAnimStageNode")
            share_anim_stage.anim_name = "LinkOut"
            share_anim_settings = nodes.new("PlasmaAnimStageSettingsNode")
            share_anim_settings.forward = "kPlayAuto"
            share_anim_settings.stage_advance = "kAdvanceAuto"
            share_anim_stage.link_input(share_anim_settings, "stage", "stage_settings")

            share = nodes.new("PlasmaMultiStageBehaviorNode")
            share.link_input(share_seek, "seekers", "seek_target")
            share.link_input(share_anim_stage, "stage", "stage_refs")
            share.link_output(linkingnode, "hosts", "shareBookSeek")

    def sanity_check(self):
        if self.clickable is None:
            raise ExportError("{}: Linking Book modifier requires a clickable!", self.id_data.name)
        if self.seek_point is None:
            raise ExportError("{}: Linking Book modifier requires a seek point!", self.id_data.name)


dialog_toggle = {
    "filename": "xDialogToggle.py",
    "attribs": (
        { 'id':  1, 'type': "ptAttribActivator", 'name': "Activate" },
        { 'id':  4, 'type': "ptAttribString",    'name': "Vignette" },
    )
}

class PlasmaNotePopupModifier(PlasmaModifierProperties, PlasmaModifierLogicWiz):
    pl_id = "note_popup"

    bl_category = "GUI"
    bl_label = "Ex: Note Popup"
    bl_description = "XXX"
    bl_icon = "MATPLANE"

    def _get_gui_pages(self, context):
        scene = context.scene if context is not None else bpy.context.scene
        return [
            (i.name, i.name, i.name)
            for i in scene.world.plasma_age.pages
            if i.page_type == "gui"
        ]

    clickable: bpy.types.Object = PointerProperty(
        name="Clickable",
        description="The object the player will click on to activate the GUI",
        type=bpy.types.Object,
        poll=idprops.poll_mesh_objects
    )
    clickable_region: bpy.types.Object = PointerProperty(
        name="Clickable Region",
        description="The region in which the avatar must be standing before they can click on the note",
        type=bpy.types.Object,
        poll=idprops.poll_mesh_objects
    )
    gui_page: str = EnumProperty(
        name="GUI Page",
        description="Page containing all of the objects to display",
        items=_get_gui_pages,
        options=set()
    )
    gui_camera: bpy.types.Object = PointerProperty(
        name="GUI Camera",
        description="",
        poll=idprops.poll_camera_objects,
        type=bpy.types.Object,
        options=set()
    )

    @property
    def clickable_object(self) -> Optional[bpy.types.Object]:
        if self.clickable is not None:
            return self.clickable
        if self.id_data.type == "MESH":
            return self.id_data

    def sanity_check(self):
        page_type = helpers.get_page_type(self.id_data.plasma_object.page)
        if page_type != "room":
            raise ExportError(f"Note Popup modifiers should be in a 'room' page, not a '{page_type}' page!")

    def pre_export(self, exporter: Exporter, bo: bpy.types.Object):
        guidialog_object = utils.create_empty_object(f"{self.gui_page}_NoteDialog")
        guidialog_object.plasma_object.enabled = True
        guidialog_object.plasma_object.page = self.gui_page
        yield guidialog_object

        guidialog_mod: PlasmaGameGuiDialogModifier = guidialog_object.plasma_modifiers.gui_dialog
        guidialog_mod.enabled = True
        guidialog_mod.is_modal = True
        if self.gui_camera:
            guidialog_mod.camera_object = self.gui_camera
        else:
            # Abuse the GUI Dialog's lookat caLculation to make us a camera that looks at everything
            # the artist has placed into the GUI page. We want to do this NOW because we will very
            # soon be adding more objects into the GUI page.
            camera_object = yield utils.create_camera_object(f"{self.key_name}_GUICamera")
            camera_object.data.angle = math.radians(45.0)
            camera_object.data.lens_unit = "FOV"

            visible_objects = [
                i for i in exporter.get_objects(self.gui_page)
                if i.type == "MESH" and i.data.materials
            ]
            camera_object.matrix_world = exporter.gui.calc_camera_matrix(
                bpy.context.scene,
                visible_objects,
                camera_object.data.angle
            )
            clipping = exporter.gui.calc_clipping(
                camera_object.matrix_world,
                bpy.context.scene,
                visible_objects,
                camera_object.data.angle
            )
            camera_object.data.clip_start = clipping.hither
            camera_object.data.clip_end = clipping.yonder
            guidialog_mod.camera_object = camera_object

        # Begin creating the object for the clickoff plane. We want to yield it immediately
        # to the exporter in case something goes wrong during the export, allowing the stale
        # object to be cleaned up.
        click_plane_object = utils.BMeshObject(f"{self.key_name}_Exit")
        click_plane_object.matrix_world = guidialog_mod.camera_object.matrix_world
        click_plane_object.plasma_object.enabled = True
        click_plane_object.plasma_object.page = self.gui_page
        yield click_plane_object

        # We have a camera on guidialog_mod.camera_object. We will now use it to generate the
        # points for the click-off plane button.
        # TODO: Allow this to be configurable to 4:3, 16:9, or 21:9?
        with ExitStack() as stack:
            stack.enter_context(exporter.gui.generate_camera_render_settings(bpy.context.scene))
            toggle = stack.enter_context(helpers.GoodNeighbor())

            # Temporarily adjust the clipping plane out to the farthest point we can find to ensure
            # that the click-off button ecompasses everything. This is a bit heavy-handed, but if
            # you want more refined control, you won't be using this helper.
            clipping = max((guidialog_mod.camera_object.data.clip_start, guidialog_mod.camera_object.data.clip_end))
            toggle.track(guidialog_mod.camera_object.data, "clip_start", clipping - 0.1)
            view_frame = guidialog_mod.camera_object.data.view_frame(bpy.context.scene)

        click_plane_object.data.materials.append(exporter.gui.transparent_material)
        with click_plane_object as click_plane_mesh:
            verts = [click_plane_mesh.verts.new(i) for i in view_frame]
            face = click_plane_mesh.faces.new(verts)
            # TODO: Ensure the face is pointing toward the camera!
            # I feel like we should be fine by assuming that Blender returns the viewframe
            # verts in the correct order, but this is Blender... So test that assumption carefully.
            # TODO: Apparently not!
            face.normal_flip()

        # We've now created the mesh object - handle the GUI Button stuff
        click_plane_object.plasma_modifiers.gui_button.enabled = True

        # NOTE: We will be using xDialogToggle.py, so we use a special tag ID instead of the
        # close dialog procedure.
        click_plane_object.plasma_modifiers.gui_control.tag_id = 99

        # Auto-generate a six-foot cube region around the clickable if none was provided.
        yield utils.pre_export_optional_cube_region(
            self, "clickable_region",
            f"{self.key_name}_DialogToggle_ClkRgn", 6.0,
            self.clickable_object
        )

        # Everything is ready now - create an xDialogToggle.py in the room page to display the GUI.
        yield self.convert_logic(bo)

    def export(self, exporter: Exporter, bo: bpy.types.Object, so: plSceneObject):
        # You're not hallucinating... Everything is done in the pre-export phase.
        pass

    def logicwiz(self, bo, tree):
        nodes = tree.nodes

        # xDialogToggle.py PythonFile Node
        dialog_node = self._create_python_file_node(
            tree,
            dialog_toggle["filename"],
            dialog_toggle["attribs"]
        )
        self._create_python_attribute(dialog_node, "Vignette", value=self.gui_page)

        # Clickable
        clickable_region = nodes.new("PlasmaClickableRegionNode")
        clickable_region.region_object = self.clickable_region

        clickable = nodes.new("PlasmaClickableNode")
        clickable.find_input_socket("facing").allow_simple = False
        clickable.clickable_object = self.clickable_object
        clickable.link_input(clickable_region, "satisfies", "region")
        clickable.link_output(dialog_node, "satisfies", "Activate")
