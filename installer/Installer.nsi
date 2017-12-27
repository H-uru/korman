;;;;;;;;;;;;
; Includes ;
;;;;;;;;;;;;
!include MUI2.nsh
!include WinVer.nsh
!include x64.nsh
!include StrFunc.nsh

; Enable StrStr
${StrStr}

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
Var BlenderDir
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
    StrCmp     $BlenderDir "" 0 done

    ; Try to grab the Blender directory from the default registry...
    ReadRegStr  $BlenderDir HKLM "Software\BlenderFoundation" "Install_Dir"
    ReadRegStr  $BlenderVer HKLM "Software\BlenderFoundation" "ShortVersion"

    ; Bad news, old chap, certain x86 Blender versions will write their registry keys to the
    ; x64 registry. Dang! It looks like we will have to try to hack around that. But only if
    ; we got nothing...
    ${If} ${RunningX64}
        StrCmp  $BlenderDir "" try_again winning

        try_again:
        SetRegView  64
        ReadRegStr  $BlenderDir HKLM "Software\BlenderFoundation" "Install_Dir"
        ReadRegStr  $BlenderVer HKLM "Software\BlenderFoundation" "ShortVersion"
        SetRegView  32

        StrCmp  $BlenderDir "" total_phailure

        ; Before we suggest this, let's make sure it's not Program Files (x64) version unleashed(TM)
        StrCpy  $0 "$PROGRAMFILES64\" ; Otherwise, it would match ALL Program Files directories...
        ${StrStr}  $1 $BlenderDir $0
        StrCmp  $1 "" winning total_phailure
    ${EndIf}

    winning:
    StrCpy  $INSTDIR "$BlenderDir\$BlenderVer"
    Goto done

    total_phailure:
    StrCpy  $INSTDIR ""
    Goto done

    done:
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
