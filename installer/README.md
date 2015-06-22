## Korman NSIS Installer

In order to facillitate usage by non-technical users, Korman has a NSIS installer. Currently, the
installer only supports 32-bit Blenders because of PhysX limitations when exporting to MOUL. 64-bit
installers should not be produced until the PhysX dependency is removed.

## Building the Installer
You are responsible for supplying the following items in the Files directory:
- libHSPlasma libraries (**HSPlasma.dll** and **PyHSPlasma.pyd**)
- Visual C++ Redistributable package (**vcredist_x86.exe**)
- **NxCooking.dll** *(if applicable)*

Given that PyHSPlasma can only be used with ABI-compatible Python releases (generally minor version
levels), it is recommended that you define the name of the Python DLL (**PYTHON_DLL**) you expect for
Blender to have. This can be done using the GUI by editing the symbol definitions under ***Tools >
Settings***, or by using the command line switch ***-DPYTHON_DLL=yourPythonDll***. Failure to do so
will not prevent the installer from working; however, it may lead to GOTCHAs where users are attempting
to install Korman for Blender versions that are not actually compatible with your PyHSPlasma.
