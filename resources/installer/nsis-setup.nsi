!define APPNAME "Inspetrio"
!define COMPANYNAME "Iberdrola"
!define DESCRIPTION "Inspetrio"

# These three must be integers
!define VERSIONMAJOR 0
!define VERSIONMINOR 0
!define VERSIONBUILD 1
!define VERSIONPATCH alpha

# These will be displayed by the "Click here for support information" link in "Add/Remove Programs"
# It is possible to use "mailto:" links in here to open the email client
# !define HELPURL "http://..." # "Support Information" link
# !define UPDATEURL "http://..." # "Product Updates" link
# !define ABOUTURL "http://..." # "Publisher" link

# This is the size (in kB) of all the files copied into "Program Files"
# !define INSTALLSIZE 7233

# Require user rights on NT6+ (When UAC is turned on). Allowed: none|user|highest|admin
RequestExecutionLevel user

# The default installation directory. Eg. "$PROGRAMFILES\${COMPANYNAME}\${APPNAME}"
InstallDir "$PROFILE\${COMPANYNAME}\${APPNAME}" ; 
 
# The application's license file in either .rtf or .txt format. If it is a .txt, it must be in the DOS text format (\r\n)
# LicenseData "license.rtf"

# This will be in the installer/uninstaller's title bar
Name "${COMPANYNAME} - ${APPNAME}"

# The installer executable icon
Icon "../../../resources/iberdrola.ico"

# The output file created by this script
outFile "Installer.exe"

!include LogicLib.nsh
!include "MUI2.nsh"

# Installer pages
Page directory
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\Inspetrio.exe"
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ModifyRunCheckbox
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "Spanish"

Section "Inspetrio" SID_MAYBE
; File "Inspetrio.exe"
SectionEnd

Function ModifyRunCheckbox
	SendMessage $mui.FinishPage.Text ${WM_SETTEXT} 0 "STR:$(MUI_FINISHPAGE_TEXT)$\n$\nSe ha creado uno acceso directo en el desktop"

	${IfNot} ${SectionIsSelected} ${SID_MAYBE} 
		SendMessage $mui.FinishPage.Run ${BM_SETCHECK} ${BST_UNCHECKED} 0
		EnableWindow $mui.FinishPage.Run 0 
	${EndIf}
FunctionEnd
 
#!macro VerifyUserIsAdmin
#UserInfo::GetAccountType
#pop $0
#${If} $0 != "admin" ;Require admin rights on NT4+
#        messageBox mb_iconstop "Administrator rights required!"
#        setErrorLevel 740 ;ERROR_ELEVATION_REQUIRED
#        quit
#${EndIf}
#!macroend

function .onInit
	setShellVarContext current
	# !insertmacro VerifyUserIsAdmin
functionEnd
 
section "install"
	# Files for the install directory - to build the installer, these should be in the same directory as the install script (this file)
	setOutPath $INSTDIR
	
	# Files added here should be removed by the uninstaller (see section "uninstall")
	file /r ..\..\Nuitka\Inspetrio\main.dist\*.*
 
	# Uninstaller - See function un.onInit and section "uninstall" for configuration
	writeUninstaller "$INSTDIR\uninstall.exe"
 
	# Start Menu
	createDirectory "$SMPROGRAMS\${COMPANYNAME}"
	createShortCut "$SMPROGRAMS\${COMPANYNAME}\${APPNAME}.lnk" "$INSTDIR\Inspetrio.exe" "" "$INSTDIR\resources\iberdrola.ico"
	
	# Desktop Shortcut
	createShortcut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPNAME}.exe"
 
	# Registry information for add/remove programs
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayName" "${COMPANYNAME} - ${APPNAME} - ${DESCRIPTION}"
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "InstallLocation" "$\"$INSTDIR$\""
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayIcon" "$\"$INSTDIR\logo.ico$\""
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "Publisher" "$\"${COMPANYNAME}$\""
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "HelpLink" "$\"${HELPURL}$\""
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "URLUpdateInfo" "$\"${UPDATEURL}$\""
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "URLInfoAbout" "$\"${ABOUTURL}$\""
	# WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "DisplayVersion" "$\"${VERSIONMAJOR}.${VERSIONMINOR}.${VERSIONBUILD}$\""
	# WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
	# WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "VersionMinor" ${VERSIONMINOR}
	
	# There is no option for modifying or repairing the install
	# WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoModify" 1
	# WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "NoRepair" 1
	
	# Set the INSTALLSIZE constant (!defined at the top of this script) so Add/Remove Programs can accurately report the size
	# WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}" "EstimatedSize" ${INSTALLSIZE}
sectionEnd
 
# Uninstaller
function un.onInit
	SetShellVarContext current
 
	#Verify the uninstaller - last chance to back out
	MessageBox MB_OKCANCEL "Permanantly remove ${APPNAME}?" IDOK next
		Abort
	next:
	# !insertmacro VerifyUserIsAdmin
functionEnd
 
section "uninstall"
	SetShellVarContext current

	# Remove Start Menu launcher
	Delete "$SMPROGRAMS\${COMPANYNAME}\${APPNAME}.lnk"
	
	# Remove Desktop shortcut
	Delete "$DESKTOP\${APPNAME}.lnk"
	
	# Try to remove the Start Menu folder - this will only happen if it is empty
	RMDir "$SMPROGRAMS\${COMPANYNAME}"
	 
	# Try to remove the install directory
	RMDir /r $INSTDIR
 
	# Always delete uninstaller as the last action
	Delete $INSTDIR\uninstall.exe
 
	# Remove uninstaller information from the registry
	# DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMPANYNAME} ${APPNAME}"
sectionEnd

