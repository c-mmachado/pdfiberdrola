@echo off
setLocal enableDelayedExpansion

:: Resolves the root directory of the script folder
set root=%~dp0
set root=!root:~0,-1!
set venv=!root!\..\.venv

call !venv!/Scripts/pyside6-uic.exe -o !root!\..\app\gui\main_window.py !root!\..\resources\gui\main_window.ui

endLocal disableDelayedExpansion
exit /b 0