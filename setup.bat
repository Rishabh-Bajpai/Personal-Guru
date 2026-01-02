@echo off
chcp 65001 >nul 2>nul

echo [INFO] Starting Personal Guru Setup...

:: Check Conda
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Conda is not installed. Please install Miniconda or Anaconda first.
    exit /b 1
)

:: Initialize conda for batch scripts
call conda activate base
if %errorlevel% neq 0 (
    echo [ERROR] Failed to initialize conda. Make sure conda init has been run.
    exit /b 1
)

:: Interactive Prompts
echo.
echo Select Installation Type:
echo 1) Developer (Tests, Linting, Tools)
echo 2) User (Standard Usage)
echo 3) Production (Server Optimization)
set /p install_type="Enter number [1-3] (Default 1): "

if "%install_type%"=="2" (
    set req_file=requirements/base.txt
) else if "%install_type%"=="3" (
    set req_file=requirements/prod.txt
) else (
    set req_file=requirements/dev.txt
)

echo.
set /p install_tts="Install TTS dependencies? (Large download) [y/N]: "

:: Check if environment already exists
call conda info --envs | findstr /C:"Personal-Guru" >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Environment 'Personal-Guru' already exists. Skipping creation.
) else (
    :: Create Environment
    echo [INFO] Creating conda environment 'Personal-Guru' with Python 3.11...
    call conda create -n Personal-Guru python=3.11 -y
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Failed to create conda environment.
        echo         This may be due to Conda Terms of Service not being accepted.
        echo.
        echo Please run the following commands to accept the TOS:
        echo     conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
        echo     conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
        echo     conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2
        echo.
        echo Then re-run this setup script.
        pause
        exit /b 1
    )
)

:: Verify environment was created
call conda info --envs | findstr /C:"Personal-Guru" >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Environment 'Personal-Guru' does not exist. Setup cannot continue.
    pause
    exit /b 1
)

:: Activate the environment
echo [INFO] Activating Personal-Guru environment...
call conda activate Personal-Guru
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate Personal-Guru environment.
    pause
    exit /b 1
)

:: Install Dependencies
echo [INFO] Installing Dependencies from %req_file%...
pip install -r %req_file%
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies may have failed to install.
)

:: Install GTK3 for WeasyPrint (required for PDF generation on Windows)
echo.
echo [INFO] Installing GTK3 runtime for WeasyPrint (PDF generation)...
call conda install -c conda-forge gtk3 -y
if %errorlevel% neq 0 (
    echo [WARNING] GTK3 installation via conda failed.
    echo          WeasyPrint PDF generation may not work.
    echo          You can manually install GTK3 from: https://github.com/nickvdw/msys2-runtime-win/releases
)

:: Database Setup
echo.
set /p start_db="Start Database via Docker now? [Y/n]: "
if /i "%start_db%"=="n" goto :skip_db

echo [INFO] Starting Database...
docker compose up -d db

echo [INFO] Waiting for Database to be ready...
timeout /t 5 /nobreak

echo [INFO] Initializing/Updating Database Tables...
python scripts/update_database.py

:skip_db

echo.
echo [SUCCESS] Setup Complete!
echo.
echo The environment 'Personal-Guru' is now active.
echo To run the application:
echo   python run.py
echo.
echo If you open a new terminal, first run:
echo   conda activate Personal-Guru
echo.
pause
