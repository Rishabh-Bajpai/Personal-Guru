@echo off
setlocal
echo 🚀 Starting Personal Guru Setup...

:: Check Conda
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Conda is not installed. Please install Miniconda or Anaconda first.
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

:: Create Environment
call conda create -n Personal-Guru python=3.11 -y

:: Install Dependencies
echo 📦 Installing Dependencies from %req_file%...
call conda run -n Personal-Guru pip install -r %req_file%

:: Database Setup
echo.
set /p start_db="Start Database via Docker now? [Y/n]: "
if /i "%start_db%"=="n" goto :skip_db

echo 🐳 Starting Database...
docker compose up -d db

echo ⏳ Waiting for Database to be ready...
timeout /t 5 /nobreak

echo 🗄️  Initializing/Updating Database Tables...
call conda run -n Personal-Guru python scripts/update_database.py

:skip_db

echo.
echo ✅ Setup Complete!
echo.
echo To run the application:
echo   conda activate Personal-Guru
echo   python run.py
echo.
pause
endlocal
