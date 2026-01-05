@echo off
setlocal
chcp 65001 >nul 2>nul

echo [INFO] Starting Personal Guru Setup...

:: Check Conda
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Conda is not installed. Please install Miniconda or Anaconda first.
    pause
    exit /b 1
)

:: Initialize conda for batch scripts
call conda activate base
if %errorlevel% neq 0 (
    echo [ERROR] Failed to initialize conda. Make sure conda init has been run.
    pause
    exit /b 1
)

:: Check FFmpeg
where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] FFmpeg is not installed. It is required for audio processing.
    set /p install_ffmpeg="Do you want to install it now using winget? [y/N]: "
    if /i "%install_ffmpeg%"=="y" (
        echo [INFO] Attempting to install FFmpeg via winget...
        winget install ffmpeg
        if %errorlevel% neq 0 (
            echo [ERROR] Failed to install FFmpeg via winget. Please install manually from https://ffmpeg.org/download.html
        ) else (
            echo [SUCCESS] FFmpeg installed successfully.
        )
    ) else (
        echo [WARNING] Skipping FFmpeg installation. Audio features may not work.
    )
) else (
    echo [INFO] FFmpeg is already installed.
)

:: Interactive Prompts




echo.
set /p install_tts="Install Speech Services (TTS/STT) dependencies? (Large download) [y/N]: "

:: Check if environment already exists
call conda info --envs | findstr /B /C:"Personal-Guru " >nul 2>nul
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
call conda info --envs | findstr /B /C:"Personal-Guru " >nul 2>nul
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
echo [INFO] Installing Dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies may have failed to install.
)

:: Optional TTS
:: Docker TTS Setup
if /i "%install_tts%"=="y" (
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
)

:: Install GTK3 for WeasyPrint (required for PDF generation on Windows)
echo.
echo [INFO] Installing GTK3 runtime for WeasyPrint (PDF generation)...
call conda install -n Personal-Guru -c conda-forge gtk3 -y
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
echo The setup for environment 'Personal-Guru' is complete.
echo To run the application:
echo   python run.py
echo.
echo If you open a new terminal, first run:
echo   conda activate Personal-Guru
echo.endlocal
