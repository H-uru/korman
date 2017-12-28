!macro StrAppendChar src_str src_idx dst_str
    Push      $R0
    StrCpy    $R0 ${src_str} 1 ${src_idx}
    StrCpy    ${dst_str} ${dst_str}$R0
    Pop       $R0
!macroend
!define StrAppendChar `!insertmacro StrAppendChar`

; Takes a Guid string and returns the mangled form found in Windows Installer registry values
; Input MUST contain dashes but no brackets enclosing the guid
!macro MangleGuidForRegistry src dst
    StrCpy               ${dst}  ""
    ${StrAppendChar}     ${src}  7 ${dst}
    ${StrAppendChar}     ${src}  6 ${dst}
    ${StrAppendChar}     ${src}  5 ${dst}
    ${StrAppendChar}     ${src}  4 ${dst}
    ${StrAppendChar}     ${src}  3 ${dst}
    ${StrAppendChar}     ${src}  2 ${dst}
    ${StrAppendChar}     ${src}  1 ${dst}
    ${StrAppendChar}     ${src}  0 ${dst}
    ; Dash
    ${StrAppendChar}     ${src} 12 ${dst}
    ${StrAppendChar}     ${src} 11 ${dst}
    ${StrAppendChar}     ${src} 10 ${dst}
    ${StrAppendChar}     ${src}  9 ${dst}
    ; Dash
    ${StrAppendChar}     ${src} 17 ${dst}
    ${StrAppendChar}     ${src} 16 ${dst}
    ${StrAppendChar}     ${src} 15 ${dst}
    ${StrAppendChar}     ${src} 14 ${dst}
    ; Dash
    ${StrAppendChar}     ${src} 20 ${dst}
    ${StrAppendChar}     ${src} 19 ${dst}
    ${StrAppendChar}     ${src} 22 ${dst}
    ${StrAppendChar}     ${src} 21 ${dst}
    ; Dash
    ${StrAppendChar}     ${src} 25 ${dst}
    ${StrAppendChar}     ${src} 24 ${dst}
    ${StrAppendChar}     ${src} 27 ${dst}
    ${StrAppendChar}     ${src} 26 ${dst}
    ${StrAppendChar}     ${src} 29 ${dst}
    ${StrAppendChar}     ${src} 28 ${dst}
    ${StrAppendChar}     ${src} 31 ${dst}
    ${StrAppendChar}     ${src} 30 ${dst}
    ${StrAppendChar}     ${src} 33 ${dst}
    ${StrAppendChar}     ${src} 32 ${dst}
    ${StrAppendChar}     ${src} 35 ${dst}
    ${StrAppendChar}     ${src} 34 ${dst}
!macroend
!define MangleGuidForRegistry `!insertmacro MangleGuidForRegistry`

!macro UnmangleGuidFromRegistry src dst
    StrCpy               ${dst}  ""
    ${StrAppendChar}     ${src}  7 ${dst}
    ${StrAppendChar}     ${src}  6 ${dst}
    ${StrAppendChar}     ${src}  5 ${dst}
    ${StrAppendChar}     ${src}  4 ${dst}
    ${StrAppendChar}     ${src}  3 ${dst}
    ${StrAppendChar}     ${src}  2 ${dst}
    ${StrAppendChar}     ${src}  1 ${dst}
    ${StrAppendChar}     ${src}  0 ${dst}
    ${StrAppendChar}     "-"     0 ${dst}
    ${StrAppendChar}     ${src} 11 ${dst}
    ${StrAppendChar}     ${src} 10 ${dst}
    ${StrAppendChar}     ${src}  9 ${dst}
    ${StrAppendChar}     ${src}  8 ${dst}
    ${StrAppendChar}     "-"     0 ${dst}
    ${StrAppendChar}     ${src} 15 ${dst}
    ${StrAppendChar}     ${src} 14 ${dst}
    ${StrAppendChar}     ${src} 13 ${dst}
    ${StrAppendChar}     ${src} 12 ${dst}
    ${StrAppendChar}     "-"     0 ${dst}
    ${StrAppendChar}     ${src} 17 ${dst}
    ${StrAppendChar}     ${src} 16 ${dst}
    ${StrAppendChar}     ${src} 19 ${dst}
    ${StrAppendChar}     ${src} 18 ${dst}
    ${StrAppendChar}     "-"     0 ${dst}
    ${StrAppendChar}     ${src} 21 ${dst}
    ${StrAppendChar}     ${src} 20 ${dst}
    ${StrAppendChar}     ${src} 23 ${dst}
    ${StrAppendChar}     ${src} 22 ${dst}
    ${StrAppendChar}     ${src} 25 ${dst}
    ${StrAppendChar}     ${src} 24 ${dst}
    ${StrAppendChar}     ${src} 27 ${dst}
    ${StrAppendChar}     ${src} 26 ${dst}
    ${StrAppendChar}     ${src} 29 ${dst}
    ${StrAppendChar}     ${src} 28 ${dst}
    ${StrAppendChar}     ${src} 31 ${dst}
    ${StrAppendChar}     ${src} 30 ${dst}
!macroend
!define UnmangleGuidFromRegistry `!insertmacro UnmangleGuidFromRegistry`
