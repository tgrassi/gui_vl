;NSIS Modern User Interface
;Welcome/Finish Page Example Script
;Written by Joost Verburg

;--------------------------------
;Include Modern UI

  !include "MUI2.nsh"

;--------------------------------
;General

  ;Name and file
  !define /date DATE "%Y-%b-%d %H:%M:%S"
  Name "QtFit (build ${DATE})"
  OutFile "QtFit_0.3.2_x86.exe"

  ;Default installation folder
  InstallDir "$LOCALAPPDATA\QtFit"

  ;Get installation folder from registry if available
  InstallDirRegKey HKCU "Software\QtFit" ""

  ;Request application privileges for Windows Vista
  RequestExecutionLevel user

;--------------------------------
;Variables

  Var StartMenuFolder

;--------------------------------
;Interface Settings

  !define MUI_ABORTWARNING

;--------------------------------
;Pages

  !insertmacro MUI_PAGE_WELCOME
  !insertmacro MUI_PAGE_LICENSE "qtfit\LICENSE"
  !insertmacro MUI_PAGE_COMPONENTS
  !insertmacro MUI_PAGE_DIRECTORY
  
  ;Start Menu Folder Page Configuration
  !define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU" 
  !define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\QtFit" 
  !define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "QtFit"
  !insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder

  !insertmacro MUI_PAGE_INSTFILES

  ;Finish Page Configuration for desktop shortcuts (not to view the readme!)
  !define MUI_FINISHPAGE_SHOWREADME ""
  !define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
  !define MUI_FINISHPAGE_SHOWREADME_TEXT "Create Desktop Shortcut"
  !define MUI_FINISHPAGE_SHOWREADME_FUNCTION finishpageaction
  !insertmacro MUI_PAGE_FINISH

  !insertmacro MUI_UNPAGE_WELCOME
  !insertmacro MUI_UNPAGE_CONFIRM
  !insertmacro MUI_UNPAGE_INSTFILES
  !insertmacro MUI_UNPAGE_FINISH

;--------------------------------
;Languages

  !insertmacro MUI_LANGUAGE "English"
  !insertmacro MUI_LANGUAGE "German"
  !insertmacro MUI_LANGUAGE "Italian"

;--------------------------------
;Installer Sections

Section "QtFit" SecQtFit

  SetOutPath "$INSTDIR"

  ;ADD YOUR OWN FILES HERE...
  File /r "qtfit\*"

  ;Store installation folder
  WriteRegStr HKCU "Software\QtFit" "" $INSTDIR
  
  ;Create start menu shortcuts
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
    
    CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\QtFit.lnk" "$INSTDIR\qtfit.exe"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\ProFitter.lnk" "$INSTDIR\profitter.exe"
    CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  
  !insertmacro MUI_STARTMENU_WRITE_END

  ;Create uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

SectionEnd

;--------------------------------
;Descriptions

  ;Language strings
  LangString DESC_SecQtFit ${LANG_ENGLISH} "Includes all the items built from the pyinstaller-based dist."

  ;Assign language strings to sections
  !insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecQtFit} $(DESC_SecQtFit)
  !insertmacro MUI_FUNCTION_DESCRIPTION_END

;--------------------------------
;Desktop shortcuts

Function finishpageaction

  CreateShortcut "$desktop\QtFit.lnk" "$INSTDIR\qtfit.exe"
  CreateShortcut "$desktop\ProFitter.lnk" "$INSTDIR\profitter.exe"

FunctionEnd

;--------------------------------
;Uninstaller Section

Section "Uninstall"

  ;Remove uninstaller and directory
  Delete "$INSTDIR\Uninstaller.exe"
  RMDir /r "$INSTDIR"

  ;Remove shortcuts
  RMDir /r "$SMPROGRAMS\$StartMenuFolder"
  Delete "$desktop\QtFit.lnk"
  Delete "$desktop\ProFitter.lnk"

  ;Clean up registry
  DeleteRegKey HKCU "Software\QtFit"

SectionEnd
