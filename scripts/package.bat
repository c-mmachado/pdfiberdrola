@echo off
setLocal enableDelayedExpansion

:: Resolves the root directory of the script folder
set root=%~dp0
set root=!root:~0,-1!

:: Required 3rd party tools
set VARSALL_BAT="C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvarsall.bat"
set 7Z_EXE="C:\Programs\7-Zip\7z.exe"
set NSIS_EXE="C:\Programs\NSIS\x64\3.10\makensis.exe"

:: Resolves the project directories and properties
set VENV_DIR=!root!\..\.venv

set PROJECT_ROOT=!root!\..
set PROJECT_RESOURCES_DIR=!PROJECT_ROOT!\resources
set PROJECT_DIST_DIR=!PROJECT_ROOT!\dist
set PROJECT_CONFIG_DIR=!PROJECT_ROOT!\config
set PROJECT_RESOURCES_UI_DIR=!PROJECT_RESOURCES_DIR!\gui
set PROJECT_TEMPLATES_DIR=!PROJECT_RESOURCES_DIR!\templates

set PROJECT_NAME=Inspetrio
set PROJECT_MAIN=!PROJECT_ROOT!\main.py
set PROJECT_ICON=!PROJECT_RESOURCES_UI_DIR!\iberdrola.ico

:: Resolves the Nuitka output directories
set NUITKA_OUT_DIR=!PROJECT_DIST_DIR!\Nuitka\Inspetrio
set NUITKA_DIST_DIR=!NUITKA_OUT_DIR!\main.dist
set NUITKA_RESOURCES_DIR=!NUITKA_DIST_DIR!\resources\gui
set NUITKA_CONFIG_DIR=!NUITKA_DIST_DIR!\config
set NUITKA_TEMPLATES_DIR=!NUITKA_DIST_DIR!\templates
set NUITKA_LOGS_DIR=!NUITKA_DIST_DIR!\logs
set NUITKA_EXE_NAME=Inspetrio.exe 

:: Resolves the NSIS directory
set NSIS_DIR=!PROJECT_RESOURCES_DIR!\installer
set NSIS_SCRIPT=!NSIS_DIR!\nsis-setup.nsi
set NSIS_DIST_DIR=!PROJECT_DIST_DIR!\Installer\NSIS

:: Resolves the 7zExec directory
set 7ZEXEC_DIR=!PROJECT_RESOURCES_DIR!\installer
set 7ZEXEC_DIST_DIR=!PROJECT_DIST_DIR!\installer

:: Reads the .env file and sets the environment variables
echo Reading '!PROJECT_CONFIG_DIR!\.env' file and setting the environment variables
for /F "delims== tokens=1,* eol=#" %%i in (!PROJECT_CONFIG_DIR!\.env) do (
    set %%i=%%~j
)
echo Environment variables set successfully

:: Compiles the application using Nuitka and generate the application executable
if not exist !NUITKA_DIST_DIR!\!NUITKA_EXE_NAME! (
    !VENV_DIR!/Scripts/python -m nuitka --standalone --remove-output --output-dir=!NUITKA_OUT_DIR! --output-filename=!NUITKA_EXE_NAME! --windows-icon-from-ico=!PROJECT_ICON! --product-name=!PROJECT_NAME! --product-version=!APP_VERSION! --enable-plugin=pyside6 --windows-console-mode=disable --mingw64 !PROJECT_MAIN! && (
        echo Nuitka compilation successful
    ) || (
        echo Error: Nuitka compilation failed && goto eof
    )
)

if not exist !NUITKA_RESOURCES_DIR! (
    robocopy !PROJECT_RESOURCES_UI_DIR! !NUITKA_RESOURCES_DIR!
    del !NUITKA_RESOURCES_DIR!\main_window.ui
    del !NUITKA_RESOURCES_DIR!\memento.json
)
if not exist !NUITKA_CONFIG_DIR! (
    robocopy !PROJECT_CONFIG_DIR! !NUITKA_CONFIG_DIR! /E
)
if not exist !NUITKA_TEMPLATES_DIR! (
    robocopy !PROJECT_TEMPLATES_DIR! !NUITKA_TEMPLATES_DIR! /E
)
mkdir !NUITKA_LOGS_DIR! || (
    if not exist !NUITKA_LOGS_DIR! (
        echo Error: Logs folder creation failed && goto eof
    )
)

:: Updates the version related files
!VENV_DIR!/Scripts/python !PROJECT_ROOT!\scripts\version_sync.py && (
    echo Version synchronization successful
) || (
    echo Error: NSIS script version update failed && goto eof
)

:: Compiles NSIS script and generates the installer
!NSIS_EXE! !NSIS_SCRIPT! || (
    echo Error: NSIS script compilation and installer generation failed && goto eof
)

:: Updates the 7zSD.sfx manifest file to remove UAC prompt if needed by user
echo Update 7zSD.sfx manifest file to remove UAC prompt? (Requires VS2022 or later installed)
echo [1] Yes
echo [2] No [Default]
echo.
set /p choice=Enter your choice: || set choice=2
if !choice! == 1 (
    echo Updating 7zSD.sfx manifest file to remove UAC prompt on 7zip self-extracting archive
    call !VARSALL_BAT! x86 && (
        mt.exe -manifest !7ZEXEC_DIR!\manifest.xml -outputresource:"!7ZEXEC_DIR!\7zSD.sfx;#1" || (
            echo Error: 7zSD.sfx manifest file update failed && goto eof
        )
    ) || (
        echo Error: 7zSD.sfx manifest file update environment initialization failed && goto eof
    )
    
    echo 7zSD.sfx manifest file updated successfully
)

:: Generates the final executable archive
:: https://stackoverflow.com/questions/27904532/how-do-i-make-a-self-extract-and-running-installer
:: https://stackoverflow.com/questions/17923346/7zip-self-extracting-archive-sfx-without-administrator-privileges
!7Z_EXE! a -t7z !7ZEXEC_DIST_DIR!\Installer.7z !NSIS_DIST_DIR!\Installer.exe || (
    echo Error: 7z compression for Installer.exe failed && goto eof
)
copy /b !7ZEXEC_DIR!\7zSD.sfx + !7ZEXEC_DIR!\config.txt + !7ZEXEC_DIST_DIR!\Installer.7z !7ZEXEC_DIST_DIR!\InspetrioSetup.exe

:eof
endLocal disableDelayedExpansion
exit /b 0