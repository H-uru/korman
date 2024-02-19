Korman
======

An open source, GPLv3 Blender addon for creating ages for Cyan Worlds' proprietary Plasma engine
and its open source variant, CyanWorlds.com Engine. For more information, visit https://guildofwriters.org

Dependencies
------------
- [Blender](http://blender3d.org) - 3D modeling software
- [libHSPlasma](https://github.com/H-uru/libhsplasma) - Universal Plasma library used for manipulating data

Building
--------
Korman is written primarily in Python and therefore requires little in the way of compiling. However, Korman
depends on the libHSPlasma Python bindings called "PyHSPlasma". Therefore, you will need to compile libHSPlasma
with python bindings for the platform of your choice. A helper script has been provided to compile PyHSPlasma
and all dependency libraries for you on Windows. To build Korman for rapid development, run
`./build.ps1 -Dev -BlenderDir "<path to blender 2.79>"`

Installing
----------
Copy the `korman` directory into Blender's `addons` directory. You must enable the addon in Blender's User
Preferences window. Korman is listed as a **System** addon. Switch the render engine to Korman and enjoy!

Zen of Korman
-------------
- Korman should be intuitive and discoverable.
- Mapping Korman features to Plasma features 1:1 is not desirable.
- Hide annoying details and make age building fun!
- Any Python traceback seen by the user is a bug.
- Korman is written in Python, not C. The code should reflect that fact.
- Avoid "it's better to ask for forgiveness" `try... except` blocks.
- Spaces over tabs.
- Break lines around 100 columns (it's OK if your log message exceeds that however).
