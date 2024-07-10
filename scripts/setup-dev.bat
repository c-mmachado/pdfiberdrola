@echo off
setLocal enableDelayedExpansion

:: Resolves the root directory of the script folder to be used for virtual environment setup and dependency installation
set root=%~dp0
set root=!root:~0,-1!
set venv=!root!\..\.venv

:: Checking for Python installation in the system
:: If Python is not found, the script will exit with an error message
echo Checking for Python...
for /F "tokens=*" %%g IN ('python --version') do (set version=%%g)
if not errorlevel 0 (
    echo Python is not installed. Please install Python 3.12.3 or later.
    echo You can download Python from https://www.python.org/downloads/
    echo Make sure to add Python to the system PATH during installation.
    echo Once Python is installed, run this script again.
    exit /b 1
)
echo !version! found.

:: Getting the Python installation directory from the Python executable
for /F "tokens=*" %%g IN ('python -c "import os, sys; print(os.path.dirname(sys.executable)); exit()"') do (set install_dir=%%g)
echo Python installation found at: '!install_dir!'

:: Checking for virtual environment folder in the parent directory of the script folder
:: If the folder is not found, the script will create a new virtual environment
:: If the folder is found, the script will ask the user if they want to recreate the virtual environment
echo Checking for virtual environment...
if not exist !venv! (
    echo Virtual environment not found.
) else (
    echo Virtual environment found.
    echo Would you like to recreate the virtual environment?
    echo [1] Yes
    echo [2] No
    echo.
    set /p choice=Enter your choice: 
    if !choice! == 1 (
        echo Recreating virtual environment...
        rmdir /s /q !venv!
    )
)

if not exist !venv! (
    :: Creating a new virtual environment in the parent directory of the script folder
    echo Creating virtual environment...
    python -m venv !venv!
    if not errorlevel 0 (
        echo Failed to create virtual environment.
        exit /b 1
    )
)

:: Activating the virtual environment and installing dependencies from requirements.txt
echo Activating virtual environment...
call !root!\..\.venv\Scripts\activate.bat
if not errorlevel 0 (
    echo Failed to activate virtual environment.
    exit /b 1
)

:: Installing dependencies from requirements.txt using pip in the virtual environment
echo Installing dependencies...
python -m pip install -r !root!\..\requirements.txt
if not errorlevel 0 (
    echo Failed to install dependencies.
    exit /b 1
)
echo Dependencies installed.

echo Virtual environment setup complete.
echo.

endLocal disableDelayedExpansion
exit /b 0