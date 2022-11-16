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
from PyHSPlasma import *

from collections import defaultdict
from contextlib import contextmanager
import itertools
from pathlib import Path
import re
from typing import NamedTuple, Union
from xml.sax.saxutils import escape as xml_escape
import weakref

from .explosions import NonfatalExportError
from .. import korlib
from . import logger

_SP_LANGUAGES = {"English", "French", "German", "Italian", "Spanish"}

# Detects if there are any Plasma esHTML tags in the translated data. If so, we store
# as CDATA instead of XML encoding the entry.
_ESHTML_REGEX = re.compile("<.+>")

# Converts smart characters to the not-so-smart variety to fix common problems related to
# limitations in the Plasma font system.
class _DumbCharacter(NamedTuple):
    desc: str
    needle: Union[re.Pattern, str]
    sub: str = ""


_DUMB_CHARACTERS = [
    _DumbCharacter(
        "smart single quote (probably copypasta'd from Microsoft Word)",
        re.compile("[\u2018\u2019\u201A\u201B]"), "'"
    ),
    _DumbCharacter(
        "smart double quote (probably copypasta'd from Microsoft Word)",
        re.compile("[\u201C\u201D\u201E\u201F\u2E42]"), '"'
    ),
]


class LocalizationConverter:
    def __init__(self, exporter=None, **kwargs):
        if exporter is not None:
            self._exporter = weakref.ref(exporter)
            self._age_name = exporter.age_name
            self._report = exporter.report
            self._version = exporter.mgr.getVer()
        else:
            self._exporter = None
            self._age_name = kwargs.get("age_name")
            self._path = kwargs.get("path")
            self._version = kwargs.get("version")
        self._strings = defaultdict(lambda: defaultdict(dict))

    def add_string(self, set_name, element_name, language, value, indent=0):
        self._report.msg("Accepted '{}' translation for '{}'.", element_name, language, indent=indent)
        if isinstance(value, bpy.types.Text):
            if value.is_modified:
                self._report.warn("'{}' translation for '{}' is modified on the disk but not reloaded in Blender.",
                                element_name, language, indent=indent)
            value = value.as_string()

        for dc in _DUMB_CHARACTERS:
            old_value = value
            if isinstance(dc.needle, str):
                value = value.replace(dc.needle, dc.sub)
            else:
                value = dc.needle.sub(dc.sub, value)
            if value != old_value:
                self._report.warn(
                    "'{}' translation for '{}' has an illegal {}, which was replaced with: {}",
                    element_name, language, dc.desc, dc.sub, indent=indent
                )

        self._strings[set_name][element_name][language] = value

    @contextmanager
    def _generate_file(self, filename, **kwargs):
        if self._exporter is not None:
            with self._exporter().output.generate_dat_file(filename, **kwargs) as handle:
                yield handle
        else:
            dirname = kwargs.get("dirname", "dat")
            filepath = str(Path(self._path) / dirname / filename)
            handle = open(filepath, "wb")
            try:
                yield handle
            except:
                raise
            finally:
                handle.close()

    def _generate_text_files(self):
        age_name = self._age_name

        def write_text_file(language, file_name, contents):
            with self._generate_file(dirname="ageresources", filename=file_name) as stream:
                try:
                    stream.write(contents.encode("windows-1252"))
                except UnicodeEncodeError:
                    self._report.warn("Translation '{}': Contents contains characters that cannot be used in this version of Plasma. They will appear as a '?' in game.",
                                    language, indent=2)

                    # Yes, there are illegal characters... As a stopgap, we will export the file with
                    # replacement characters ("?") just so it'll work dammit.
                    stream.write(contents.encode("windows-1252", "replace"))
                return True

        locs = itertools.chain(self._strings["Journals"].items(), self._strings["DynaTexts"].items())
        for journal_name, translations in locs:
            self._report.msg("Copying localization '{}'", journal_name, indent=1)
            for language_name, value in translations.items():
                if language_name not in _SP_LANGUAGES:
                    self._report.warn("Translation '{}' will not be used because it is not supported in this version of Plasma.",
                                      language_name, indent=2)
                    continue
                suffix = "_{}".format(language_name.lower()) if language_name != "English" else ""
                file_name = "{}--{}{}.txt".format(age_name, journal_name, suffix)
                write_text_file(language_name, file_name, value)

            # Ensure that default (read: "English") journal is available
            if "English" not in translations:
                language_name, value = next(((language_name, value) for language_name, value in translations.items()
                                            if language_name in _SP_LANGUAGES), (None, None))
                if language_name is not None:
                    file_name = "{}--{}.txt".format(age_name, journal_name)
                    # If you manage to screw up this badly... Well, I am very sorry.
                    if write_text_file(language_name, file_name, value):
                        self._report.warn("No 'English' translation available, so '{}' will be used as the default",
                                          language_name, indent=2)
                else:
                    self._report.port("No 'English' nor any other suitable default translation available", indent=2)

    def _generate_loc_files(self):
        if not self._strings:
            return

        method = bpy.context.scene.world.plasma_age.localization_method
        if method == "single_file":
            self._generate_loc_file("{}.loc".format(self._age_name), self._strings)
        elif method in {"database", "database_back_compat"}:
            # Where the strings are set -> element -> language: str, we want language -> set -> element: str
            # This is so we can mimic pfLocalizationEditor's <agename>English.loc pathing.
            database = defaultdict(lambda: defaultdict(dict))
            for set_name, elements in self._strings.items():
                for element_name, translations in elements.items():
                    for language_name, value in translations.items():
                        database[language_name][set_name][element_name] = value

            for language_name, sets in database.items():
                self._generate_loc_file("{}{}.loc".format(self._age_name, language_name), sets, language_name)

            # Generate an empty localization file to defeat any old ones from Korman 0.11 (and lower)
            if method == "database_back_compat":
                self._generate_loc_file("{}.loc".format(self._age_name), {})
        else:
            raise RuntimeError("Unexpected localization method {}".format(method))

    def _generate_loc_file(self, filename, sets, language_name=None):
        def write_line(value, *args, **kwargs):
            # tabs suck, then you die...
            whitespace = "    " * kwargs.pop("indent", 0)
            if args or kwargs:
                value = value.format(*args, **kwargs)
            line = "".join((whitespace, value, "\n"))
            stream.write(line.encode("utf-8"))

        def iter_element(element):
            if language_name is None:
                yield from sorted(element.items())
            else:
                yield language_name, element

        enc = plEncryptedStream.kEncAes if self._version == pvEoa else None
        with self._generate_file(filename, enc=enc) as stream:
            write_line("<?xml version=\"1.0\" encoding=\"utf-8\"?>")
            write_line("<localizations>")
            write_line("<age name=\"{}\">", self._age_name, indent=1)

            for set_name, elements in sorted(sets.items()):
                write_line("<set name=\"{}\">", set_name, indent=2)
                for element_name, value in sorted(elements.items()):
                    write_line("<element name=\"{}\">", element_name, indent=3)
                    for translation_language, translation_value in iter_element(value):
                        if _ESHTML_REGEX.search(translation_value):
                            encoded_value = "<![CDATA[{}]]>".format(translation_value)
                        else:
                            encoded_value = xml_escape(translation_value)
                        write_line("<translation language=\"{language}\">{translation}</translation>",
                                   language=translation_language, translation=encoded_value, indent=4)
                    write_line("</element>", indent=3)
                write_line("</set>", indent=2)

            # Verbose XML junk...
            # <Deledrius> You call it verbose.  I call it unambiguously complete.
            write_line("</age>", indent=1)
            write_line("</localizations>")

    def run(self):
        age_props = bpy.context.scene.world.plasma_age
        loc_path = str(Path(self._path) / "dat" / "{}.loc".format(self._age_name))
        log = logger.ExportVerboseLogger if age_props.verbose else logger.ExportProgressLogger
        with korlib.ConsoleToggler(age_props.show_console), log(loc_path) as self._report:
            self._report.progress_add_step("Harvesting Translations")
            self._report.progress_add_step("Generating Localization")
            self._report.progress_start("Exporting Localization Data")

            self._run_harvest_journals()
            self._run_generate()

            # DONE
            self._report.progress_end()
            self._report.raise_errors()

    def _run_harvest_journals(self):
        from ..properties.modifiers import TranslationMixin

        objects = bpy.context.scene.objects
        self._report.progress_advance()
        self._report.progress_range = len(objects)
        inc_progress = self._report.progress_increment

        for i in objects:
            for mod_type in filter(None, (getattr(j, "pl_id", None) for j in TranslationMixin.__subclasses__())):
                modifier = getattr(i.plasma_modifiers, mod_type)
                if modifier.enabled:
                    translations = [j for j in modifier.translations if j.text_id is not None]
                    if not translations:
                        self._report.error("'{}': No content translations available. The localization will not be exported.",
                                        i.name, indent=2)
                    for j in translations:
                        self.add_string(modifier.localization_set, modifier.key_name, j.language, j.text_id, indent=1)
            inc_progress()

    def _run_generate(self):
        self._report.progress_advance()
        self.save()

    def save(self):
        if self._version > pvPots:
            self._generate_loc_files()
        else:
            self._generate_text_files()
