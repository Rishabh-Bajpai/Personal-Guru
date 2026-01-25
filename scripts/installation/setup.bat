@echo off
setlocal
chcp 65001 >nul 2>nul

REM Navigate to project root
pushd "%~dp0\..\.."

echo [INFO] Starting Personal Guru Setup...

REM Check Conda
where conda >nul 2>nul
if %errorlevel% neq 0 goto :no_conda

REM Initialize conda for batch scripts
call conda activate base
if %errorlevel% neq 0 goto :conda_init_fail

REM Check FFmpeg
where ffmpeg >nul 2>nul
if %errorlevel% equ 0 goto :ffmpeg_ok

echo.
echo [WARNING] FFmpeg is not installed. It is required for audio processing.
set /p install_ffmpeg="Do you want to install it now using winget? [y/N]: "
if /i not "%install_ffmpeg%"=="y" goto :ffmpeg_skip
echo [INFO] Attempting to install FFmpeg via winget...
winget install ffmpeg
if %errorlevel% neq 0 echo [ERROR] Failed to install FFmpeg via winget. Please install manually from https://ffmpeg.org/download.html
if %errorlevel% equ 0 echo [SUCCESS] FFmpeg installed successfully.
goto :ffmpeg_done

:ffmpeg_skip
echo [WARNING] Skipping FFmpeg installation. Audio features may not work.
goto :ffmpeg_done

:ffmpeg_ok
echo [INFO] FFmpeg is already installed.

:ffmpeg_done

REM Interactive Prompts
echo.
echo Select Installation Mode:
echo 1. Standard Mode (Docker Required - Best Quality/Features)
echo 2. Local Lite Mode (No Docker - Easiest Setup)

:ask_mode
set /p mode_choice="Enter choice [1/2]: "
if "%mode_choice%"=="1" goto :mode_selected
if "%mode_choice%"=="2" goto :mode_selected

echo [ERROR] Invalid choice. Please enter 1 or 2.
goto :ask_mode

:mode_selected

if "%mode_choice%"=="2" (
    echo [INFO] Local Mode selected. Using SQLite and Local Audio.
    set local_mode=y
    set install_tts=n
    set start_db=n

    if not exist .env (
        copy .env.example .env
        echo [INFO] Created .env from example.
    )
    echo. >> .env
    echo # Local Mode Overrides >> .env
    echo TTS_PROVIDER=native >> .env
    echo STT_PROVIDER=native >> .env
    echo [INFO] Updated .env for Local Mode (Default: Kokoro + Faster Whisper).
) else (
    echo [INFO] Standard Mode selected.
    set local_mode=n
    echo.
    set /p install_tts="Install Speech Services (TTS/STT) dependencies? (Large download) [y/N]: "
)

REM Check if environment already exists
call conda info --envs | findstr /B /C:"Personal-Guru " >nul 2>nul
if %errorlevel% equ 0 goto :env_exists

REM Create Environment
echo [INFO] Creating conda environment 'Personal-Guru' with Python 3.11...
call conda create -n Personal-Guru python=3.11 -y
if %errorlevel% neq 0 goto :env_create_fail
goto :env_verify

:env_exists
echo [INFO] Environment 'Personal-Guru' already exists. Skipping creation.

:env_verify
REM Verify environment was created
call conda info --envs | findstr /B /C:"Personal-Guru " >nul 2>nul
if %errorlevel% neq 0 goto :env_not_found

REM Activate the environment
echo [INFO] Activating Personal-Guru environment...
call conda activate Personal-Guru
if %errorlevel% neq 0 goto :env_activate_fail

REM Install Dependencies
echo [INFO] Installing Dependencies from pyproject.toml...
if /i "%local_mode%"=="y" (
    call pip install -e .[local]
) else (
    call pip install -e .
)
if %errorlevel% neq 0 echo [WARNING] Some dependencies may have failed to install.

REM Optional TTS
if /i not "%install_tts%"=="y" goto :skip_tts
echo.
echo [WARNING] High-quality TTS is best run via Docker (see deployment guide).
echo          Local installation of TTS on Windows is experimental.
echo [INFO] Starting TTS Server (Speaches/Kokoro)...
docker compose up -d speaches
echo [INFO] Waiting for TTS Server to start (15s)...
timeout /t 15 /nobreak
echo [INFO] Downloading Kokoro-82M model...
docker compose exec speaches uv tool run speaches-cli model download speaches-ai/Kokoro-82M-v1.0-ONNX
echo [INFO] Downloading Faster Whisper Medium model (STT)...
docker compose exec speaches uv tool run speaches-cli model download Systran/faster-whisper-medium.en
echo [SUCCESS] TTS Setup Complete.
:skip_tts

REM Install GTK3 for WeasyPrint (required for PDF generation on Windows)
echo.
echo [INFO] Installing GTK3 runtime for WeasyPrint (PDF generation)...
call conda install -n Personal-Guru -c conda-forge gtk3 -y
if %errorlevel% neq 0 echo [WARNING] GTK3 installation via conda failed. WeasyPrint PDF generation may not work.

REM Database Setup
echo.
if /i "%local_mode%"=="y" (
    echo [INFO] Using Local SQLite Database.
    echo [INFO] Initializing SQLite Database...
    python scripts\update_database.py
    set start_db=n
) else (
    set /p start_db="Start Database via Docker now? [Y/n]: "
)
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
echo The setup for environment 'Personal-Guru' is complete.
echo To run the application:
echo   python run.py
echo.
echo If you open a new terminal, first run:
echo   conda activate Personal-Guru
echo.
goto :end

:no_conda
echo [ERROR] Conda is not installed. Please install Miniconda or Anaconda first.
pause
exit /b 1

:conda_init_fail
echo [ERROR] Failed to initialize conda. Make sure conda init has been run.
pause
exit /b 1

:env_create_fail
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

:env_not_found
echo [ERROR] Environment 'Personal-Guru' does not exist. Setup cannot continue.
pause
exit /b 1

:env_activate_fail
echo [ERROR] Failed to activate Personal-Guru environment.
pause
exit /b 1

:end
endlocal
