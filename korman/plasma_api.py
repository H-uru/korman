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

python_files = {
    "xAgeSDLBoolShowHide.py": (
        { "id": 1, "type": "ptAttribString",  "name": "sdlName" },
        { "id": 2, "type": "ptAttribBoolean", "name": "showOnTrue" },
        # --- CWE Only Below ---
        { "id": 3, "type": "ptAttribBoolean", "name": "defaultValue" },
        { "id": 4, "type": "ptAttribBoolean", "name": "evalOnFirstUpdate "},
    ),

    "xAgeSDLIntShowHide.py": (
        { "id": 1, "type": "ptAttribString",  "name": "stringVarName" },
        { "id": 2, "type": "ptAttribString",  "name": "stringShowStates" },
        # --- CWE Only Below ---
        { "id": 3, "type": "ptAttribInt",     "name": "intDefault" },
        { "id": 4, "type": "ptAttribBoolean", "name": "boolFirstUpdate "},
    ),

    # Provided by all variants of Uru and Myst V
    "xDialogToggle.py": (
        { "id":  1, "type": "ptAttribActivator", "name": "Activate" },
        { "id":  4, "type": "ptAttribString",    "name": "Vignette" },
    ),

    # Provided by CWE or OfflineKI
    "xDynTextLoc.py": (
        { "id": 1,  "type": "ptAttribDynamicMap",   "name": "dynTextMap", },
        { "id": 2,  "type": "ptAttribString",       "name": "locPath" },
        { "id": 3,  "type": "ptAttribString",       "name": "fontFace" },
        { "id": 4,  "type": "ptAttribInt",          "name": "fontSize" },
        { "id": 5,  "type": "ptAttribFloat",        "name": "fontColorR" },
        { "id": 6,  "type": "ptAttribFloat",        "name": "fontColorG" },
        { "id": 7,  "type": "ptAttribFloat",        "name": "fontColorB" },
        { "id": 8,  "type": "ptAttribFloat",        "name": "fontColorA" },
        { "id": 9,  "type": "ptAttribInt",          "name": "marginTop" },
        { "id": 10, "type": "ptAttribInt",          "name": "marginLeft" },
        { "id": 11, "type": "ptAttribInt",          "name": "marginBottom" },
        { "id": 12, "type": "ptAttribInt",          "name": "marginRight" },
        { "id": 13, "type": "ptAttribInt",          "name": "lineSpacing" },
        # Yes, it"s really a ptAttribDropDownList, but those are only for use in
        # artist generated node trees.
        { "id": 14, "type": "ptAttribString",       "name": "justify" },
        { "id": 15, "type": "ptAttribFloat",        "name": "clearColorR" },
        { "id": 16, "type": "ptAttribFloat",        "name": "clearColorG" },
        { "id": 17, "type": "ptAttribFloat",        "name": "clearColorB" },
        { "id": 18, "type": "ptAttribFloat",        "name": "clearColorA" },
        { "id": 19, "type": "ptAttribBoolean",      "name": "blockRGB" },
    ),

    # Provided by CWE and OfflineKI
    "xEntryCam.py": (
        { "id":  1, "type": "ptAttribActivator",   "name": "actRegionSensor" },
        { "id":  2, "type": "ptAttribSceneobject", "name": "camera" },
        { "id":  3, "type": "ptAttribBoolean",     "name": "undoFirstPerson" },
    ),

    # Provided by CWE
    "xJournalBookGUIPopup.py": (
        { "id":  1, "type": "ptAttribActivator", "name": "actClickableBook" },
        { "id": 10, "type": "ptAttribBoolean",   "name": "StartOpen" },
        { "id": 11, "type": "ptAttribFloat",     "name": "BookWidth" },
        { "id": 12, "type": "ptAttribFloat",     "name": "BookHeight" },
        { "id": 13, "type": "ptAttribString",    "name": "LocPath" },
        { "id": 14, "type": "ptAttribString",    "name": "GUIType" },
    ),

    # Provided by all variants of Uru and Myst V
    "xLinkingBookGUIPopup.py": (
        { "id":  1, "type": "ptAttribActivator", "name": "actClickableBook" },
        { "id":  2, "type": "ptAttribBehavior",  "name": "SeekBehavior" },
        { "id":  3, "type": "ptAttribResponder", "name": "respLinkResponder" },
        { "id":  4, "type": "ptAttribString",    "name": "TargetAge" },
        { "id":  5, "type": "ptAttribActivator", "name": "actBookshelf" },
        { "id":  6, "type": "ptAttribActivator", "name": "shareRegion" },
        { "id":  7, "type": "ptAttribBehavior",  "name": "shareBookSeek" },
        { "id": 10, "type": "ptAttribBoolean",   "name": "IsDRCStamped" },
        { "id": 11, "type": "ptAttribBoolean",   "name": "ForceThirdPerson" },
    ),

    # Supplied by the OfflineKI script:
    # https://gitlab.com/diafero/offline-ki/blob/master/offlineki/xSimpleJournal.py
    "xSimpleJournal.py": (
        { "id":  1, "type": "ptAttribActivator", "name": "bookClickable" },
        { "id":  2, "type": "ptAttribString",    "name": "journalFileName" },
        { "id":  3, "type": "ptAttribBoolean",   "name": "isNotebook" },
        { "id":  4, "type": "ptAttribFloat",     "name": "BookWidth" },
        { "id":  5, "type": "ptAttribFloat",     "name": "BookHeight" },
    ),

    # Supplied by the OfflineKI script:
    # https://gitlab.com/diafero/offline-ki/blob/master/offlineki/xSimpleLinkingBook.py
    "xSimpleLinkingBook.py": (
        { "id":  1, "type": "ptAttribActivator", "name": "bookClickable" },
        { "id":  2, "type": "ptAttribString",    "name": "destinationAge" },
        { "id":  3, "type": "ptAttribString",    "name": "spawnPoint" },
        { "id":  4, "type": "ptAttribString",    "name": "linkPanel" },
        { "id":  5, "type": "ptAttribString",    "name": "bookCover" },
        { "id":  6, "type": "ptAttribString",    "name": "stampTexture" },
        { "id":  7, "type": "ptAttribFloat",     "name": "stampX" },
        { "id":  8, "type": "ptAttribFloat",     "name": "stampY" },
        { "id":  9, "type": "ptAttribFloat",     "name": "bookWidth" },
        { "id": 10, "type": "ptAttribFloat",     "name": "BookHeight" },
        { "id": 11, "type": "ptAttribBehavior",  "name": "msbSeekBeforeUI" },
        { "id": 12, "type": "ptAttribResponder", "name": "respOneShot" },
    ),

    # Provided by CWE or OfflineKI
    "xSitCam.py": (
        { "id":  1, "type": "ptAttribActivator", "name": "sitAct" },
        { "id":  2, "type": "ptAttribSceneobject", "name": "sitCam" },
    ),

    # Provided by all variants of Uru and Myst V
    "xTelescope.py": (
        { "id":  1, "type": "ptAttribActivator", "name": "Activate" },
        { "id":  2, "type": "ptAttribSceneobject", "name": "Camera" },
        { "id":  3, "type": "ptAttribBehavior", "name": "Behavior" },
        { "id":  4, "type": "ptAttribString", "name": "Vignette" },
    )
}
