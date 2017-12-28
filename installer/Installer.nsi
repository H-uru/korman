;;;;;;;;;;;;
; Includes ;
;;;;;;;;;;;;
!include MUI2.nsh
!include WinVer.nsh
!include x64.nsh
!include RegGuid.nsh

;;;;;;;;;;;;;;;;;;;;;;
; Installer Settings ;
;;;;;;;;;;;;;;;;;;;;;;
BrandingText            "Korman"
CRCCheck                on
OutFile                 "korman.exe"
RequestExecutionLevel   admin

;;;;;;;;;;;;;;;;;;;;
; Meta Information ;
;;;;;;;;;;;;;;;;;;;;
Name                "Korman"
VIAddVersionKey     "CompanyName"       "Guild of Writers"
VIAddVersionKey     "FileDescription"   "Blender Plugin for Plasma Age Creation"
VIAddVersionKey     "FileVersion"       "0"
VIAddVersionKey     "LegalCopyright"    "Guild of Writers"
VIAddVersionKey     "ProductName"       "Korman"
VIProductVersion    "0.0.0.0"

;;;;;;;;;;;;;;;;;;;;;
; MUI Configuration ;
;;;;;;;;;;;;;;;;;;;;;
!define MUI_ABORTWARNING
!define MUI_ICON                        "Icon.ico"
!define MUI_FINISHPAGE_RUN              "$INSTDIR\..\blender.exe"

; Custom Images :D
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP          "Header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP    "WelcomeFinish.bmp"

;;;;;;;;;;;;;
; Variables ;
;;;;;;;;;;;;;
!define BlenderUpgradeCode "B767E4FD-7DE7-4094-B051-3AE62E13A17A"
!define UninstallRegKey "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
!define UpgradeRegKey "SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UpgradeCodes"

Var BlenderDir
Var BlenderDirScanned
Var BlenderVer

;;;;;;;;;;;;;;;;;
; Install Types ;
;;;;;;;;;;;;;;;;;
InstType           "Korman (32-bits)"
InstType           "Korman (64-bits)"
InstType           /NOCUSTOM

;;;;;;;;;;;;;
; Functions ;
;;;;;;;;;;;;;

; Inform the user if their OS is unsupported.
Function .onInit
    ${IfNot} ${AtLeastWinVista}
        MessageBox MB_YESNO|MB_ICONEXCLAMATION \
           "Windows Vista or above is required to run Korman$\r$\n\
            You may install the client but will be unable to run it on this OS.$\r$\n$\r$\n\
            Do you still wish to install?" \
            /SD IDYES IDNO do_quit
    ${EndIf}
    Goto done
    do_quit:
        Quit
    done:
FunctionEnd

; Checks the install dir...
Function .onVerifyInstDir
    ; Test for valid Blender
    IfFileExists "$INSTDIR\..\blender.exe" 0 fail
    IfFileExists "$INSTDIR\..\${PYTHON_DLL}" 0 fail

    ; Try to guess if we're x64--it doesn't have BlendThumb.dll
    IfFileExists "$INSTDIR\..\BlendThumb64.dll" 0 done
    IfFileExists "$INSTDIR\..\BlendThumb.dll" blender_x86 blender_x64

    fail:
    Abort

    blender_x86:
    SetCurInstType 0
    Goto   done
    blender_x64:
    SetCurInstType 1
    Goto   done

    done:
FunctionEnd

; Tries to find the Blender directory in the registry.
Function FindBlenderDir
    ; To prevent overwriting user data, we will only do this once
    StrCmp $BlenderDirScanned "" 0 done
    StrCpy $BlenderDirScanned "true"

    StrCpy $1 ""
    find_product_code:
    ; Blender's CPack-generated MSI package has spewed mess into hidden registry keys.
    ; We know what the upgrade guid is, so we will use that to find the install directory
    ; and the Blender version.
    ${MangleGuidForRegistry} ${BlenderUpgradeCode} $0
    EnumRegValue $0 HKLM "${UpgradeRegKey}\$0" 0

    ; If we are on a 64-bit system, we might not have found the product code guid in the 32-bit registry
    ; ergo, we will need to change over to that registry
    ${If} ${RunningX64}
        IfErrors 0 find_uninstall_info
        StrCmp $1 "" 0 done
        StrCpy $1 "DEADBEEF"

        ClearErrors
        SetRegView 64
        Goto find_product_code
    ${Else}
        Goto done
    ${EndIf}

    find_uninstall_info:
    ; Read the Blender directory and the versions from the uninstall record
    ${UnmangleGuidFromRegistry} $0 $1
    StrCpy $0 "${UninstallRegKey}\{$1}"
    ReadRegStr $BlenderDir HKLM $0 "InstallLocation"
    IfErrors done
    ReadRegDWORD $1 HKLM $0 "VersionMajor"
    ReadRegDWORD $2 HKLM $0 "VersionMinor"
    StrCpy $BlenderVer "$1.$2"

    ; Test our detected schtuff for validity
    ; NOTE: Windows Installer puts a trailing slash on the end of directories!
    StrCpy $3 "$BlenderDir$BlenderVer"
    IfFileExists "$3\*.*" 0 done
    StrCpy $INSTDIR $3

    done:
    ClearErrors
    ${If} ${RunningX64}
        SetRegView 32
    ${EndIf}
FunctionEnd

;;;;;;;;;
; Pages ;
;;;;;;;;;
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE                   "GPLv3.txt"
!define MUI_PAGE_CUSTOMFUNCTION_PRE             FindBlenderDir
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;;;;;;;;;;;;;
; Languages ;
;;;;;;;;;;;;;
!insertmacro MUI_LANGUAGE "English"

;;;;;;;;;;;;
; Sections ;
;;;;;;;;;;;;
Section "Visual C++ Runtime"
    SectionIn     1 2 RO

    SetOutPath    "$TEMP\Korman"
    File          "Files\x86\vcredist_x86.exe"
    ExecWait      "$TEMP\Korman\vcredist_x86.exe /q /norestart"
    ${If} ${RunningX64}
        File      "Files\x64\vcredist_x64.exe"
        ExecWait  "$TEMP\Korman\vcredist_x64.exe /q /norestart"
    ${EndIf}
    RMdir         "$TEMP\Korman"
SectionEnd

SectionGroup /e "Korman"
    Section "Python Addon"
        SectionIn     1 2 RO

        SetOutPath    "$INSTDIR\scripts\addons"
        File          /r /x "__pycache__" /x "*.pyc" /x "*.komodo*" /x ".vs" "..\korman"
    SectionEnd

    Section "x86 Libraries"
        SectionIn     1 RO

        SetOutPath    "$INSTDIR\python\lib\site-packages"
        File          "Files\x86\HSPlasma.dll"
        File          "Files\x86\PyHSPlasma.pyd"
        File          "Files\x86\_korlib.pyd"
    SectionEnd

    Section "x64 Libraries"
        SectionIn     2 RO

        SetOutPath    "$INSTDIR\python\lib\site-packages"
        File          "Files\x64\HSPlasma.dll"
        File          "Files\x64\PyHSPlasma.pyd"
        File          "Files\x64\_korlib.pyd"
    SectionEnd
SectionGroupEnd

Section #TheRemover
    WriteRegStr HKLM "Software\Korman" "" $INSTDIR
    WriteUninstaller "$INSTDIR\korman_uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\korman_uninstall.exe"
    RMDir /r "$INSTDIR\scripts\addons\korman"
    Delete "$INSTDIR\python\lib\site-packages\HSPlasma.dll"
    Delete "$INSTDIR\python\lib\site-packages\PyHSPlasma.pyd"
    ; Leaving the NxCooking reference in for posterity
    Delete "$INSTDIR\python\lib\site-packages\NxCooking.dll"
    Delete "$INSTDIR\python\lib\site-packages\_korlib.pyd"
    DeleteRegKey /ifempty HKLM "Software\Korman"
SectionEnd
