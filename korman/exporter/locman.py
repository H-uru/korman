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

from PyHSPlasma import *
import weakref
from xml.sax.saxutils import escape as xml_escape

_SP_LANGUAGES = {"English", "French", "German", "Italian", "Spanish"}

class LocalizationConverter:
    def __init__(self, exporter):
        self._exporter = weakref.ref(exporter)
        self._journals = {}
        self._strings = {}

    def add_journal(self, name, language, text_id, indent=0):
        if text_id.is_modified:
            self._report.warn("Journal '{}' translation for '{}' is modified on the disk but not reloaded in Blender.",
                              name, language, indent=indent)
        journal = self._journals.setdefault(name, {})
        journal[language] = text_id.as_string()

    def add_string(self, set_name, element_name, language, value):
        trans_set = self._strings.setdefault(set_name, {})
        trans_element = trans_set.setdefault(element_name, {})
        trans_element[language] = value

    def _generate_journal_texts(self):
        age_name = self._exporter().age_name
        output = self._exporter().output

        def write_journal_file(language, file_name, contents):
            try:
                with output.generate_dat_file(dirname="ageresources", filename=file_name) as stream:
                    stream.write(contents.encode("windows-1252"))
            except UnicodeEncodeError:
                self._report.error("Translation '{}': Contents contains characters that cannot be used in this version of Plasma",
                                   language, indent=2)
                return False
            else:
                return True

        for journal_name, translations in self._journals.items():
            self._report.msg("Copying Journal '{}'", journal_name, indent=1)
            for language_name, value in translations.items():
                if language_name not in _SP_LANGUAGES:
                    self._report.warn("Translation '{}' will not be used because it is not supported in this version of Plasma.",
                                      language_name, indent=2)
                    continue
                suffix = "_{}".format(language_name.lower()) if language_name != "English" else ""
                file_name = "{}--{}{}.txt".format(age_name, journal_name, suffix)
                write_journal_file(language_name, file_name, value)

            # Ensure that default (read: "English") journal is available
            if "English" not in translations:
                language_name, value = next(((language_name, value) for language_name, value in translations.items()
                                            if language_name in _SP_LANGUAGES), (None, None))
                if language_name is not None:
                    file_name = "{}--{}.txt".format(age_name, journal_name)
                    # If you manage to screw up this badly... Well, I am very sorry.
                    if write_journal_file(language_name, file_name, value):
                        self._report.warn("No 'English' translation available, so '{}' will be used as the default",
                                          language_name, indent=2)
                else:
                    self._report.port("No 'English' nor any other suitable default translation available", indent=2)

    def _generate_loc_file(self):
        # Only generate this junk if needed
        if not self._strings and not self._journals:
            return

        def write_line(value, *args, **kwargs):
            # tabs suck, then you die...
            whitespace = "    " * kwargs.pop("indent", 0)
            if args or kwargs:
                value = value.format(*args, **kwargs)
            line = "".join((whitespace, value, "\n"))
            stream.write(line.encode("utf-16_le"))

        age_name = self._exporter().age_name
        enc = plEncryptedStream.kEncAes if self._version == pvEoa else None
        file_name = "{}.loc".format(age_name)
        with self._exporter().output.generate_dat_file(file_name, enc=enc) as stream:
            # UTF-16 little endian byte order mark
            stream.write(b"\xFF\xFE")

            write_line("<?xml version=\"1.0\" encoding=\"utf-16\"?>")
            write_line("<localizations>")
            write_line("<age name=\"{}\">", age_name, indent=1)

            # Arbitrary strings defined by something like a GUI or a node tree
            for set_name, elements in self._strings.items():
                write_line("<set name=\"{}\">", set_name, indent=2)
                for element_name, translations in elements.items():
                    write_line("<element name=\"{}\">", element_name, indent=3)
                    for language_name, value in translations.items():
                        write_line("<translation language=\"{language}\">{translation}</translation>",
                                   language=language_name, translation=xml_escape(value), indent=4)
                    write_line("</element>", indent=3)
                write_line("</set>", indent=2)

            # Journals
            if self._journals:
                write_line("<set name=\"Journals\">", indent=2)
                for journal_name, translations in self._journals.items():
                    write_line("<element name=\"{}\">", journal_name, indent=3)
                    for language_name, value in translations.items():
                        write_line("<translation language=\"{language}\">{translation}</translation>",
                                   language=language_name, translation=xml_escape(value), indent=4)
                    write_line("</element>", indent=3)
                write_line("</set>", indent=2)

            # Verbose XML junk...
            # <Deledrius> You call it verbose.  I call it unambiguously complete.
            write_line("</age>", indent=1)
            write_line("</localizations>")

    def save(self):
        if self._version > pvPots:
            self._generate_loc_file()
        else:
            self._generate_journal_texts()

    @property
    def _report(self):
        return self._exporter().report

    @property
    def _version(self):
        return self._exporter().mgr.getVer()
