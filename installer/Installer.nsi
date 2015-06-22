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
    IfFileExists "$INSTDIR\..\blender.exe" verify_python
    Abort

    verify_python:
    IfFileExists "$INSTDIR\..\${PYTHON_DLL}" done
    Abort

    done:
FunctionEnd

; Tries to find the Blender directory in the registry.
Function FindBlenderDir
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
Section "Runtimes"
    SetOutPath    "$TEMP\Korman"
    File          "Files\vcredist_x86.exe"
    ExecWait      "$TEMP\Korman\vcredist_x86.exe /q /norestart"
    RMdir         "$TEMP\Korman"
SectionEnd

Section "Files"
    ; The entire Korman
    SetOutPath    "$INSTDIR\scripts\addons"
    File          /r /x "__pycache__" /x "*.pyc" /x "*.komodo*" "..\korman"

    ; Libraries
    SetOutPath    "$INSTDIR\python\lib\site-packages"
    File          "Files\HSPlasma.dll"
    File          "Files\PyHSPlasma.pyd"
    File          "Files\NxCooking.dll"

    WriteRegStr HKLM "Software\Korman" "" $INSTDIR
    WriteUninstaller "$INSTDIR\korman_uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\korman_uninstall.exe"
    RMDir /r "$INSTDIR\scripts\addons\korman"
    Delete "$INSTDIR\python\lib\site-packages\HSPlasma.dll"
    Delete "$INSTDIR\python\lib\site-packages\PyHSPlasma.pyd"
    Delete "$INSTDIR\python\lib\site-packages\NxCooking.dll"
    DeleteRegKey /ifempty HKLM "Software\Korman"
SectionEnd
