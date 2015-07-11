Korman
======

An open source, GPLv3 Blender addon for creating ages for Cyan Worlds' proprietary Plasma engine
and its open source variant, CyanWorlds.com Engine. For more information, visit https://guildofwriters.org

Dependencies
------------
- [Blender](http://blender3d.org) - 3d modelling problem
- [libHSPlasma](https://github.com/H-uru/libhsplasma) - Universal Plasma library used for manipulating data
- [PhysX 2.6 SDK](http://www.nvidia.com/object/physx_archives.html) - optional, required only for exporting
ages to the Myst Online: URU Live format with libHSPlasma.

Building
--------
Korman is written primarily in Python and therefore requires little in the way of compiling. However, Korman
depends on the libHSPlasma Python bindings called "PyHSPlasma". Therefore, you will need to compile libHSPlasma
with python bindings for the platform of your choice. You will need to be certain that you use the same version
of Python that ships with your Blender install. Once you have done this, copy the HSPlasma library and PyHSPlasma
python library into Blender's `python/lib/site-packages`.

See the installer directory for NSIS scripts. You can make a Windows installer by using `makensis
-DPYTHON_DLL=[pythonDllName] Installer.nsi`. Be sure to provide the Visual C++ redistributable and
libHSPlasma libraries. Prebuilt installers will be provided on the Guild of Writers website.

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
