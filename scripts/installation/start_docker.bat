@echo off
setlocal
chcp 65001 >nul 2>nul

:: Navigate to project root (scripts/installation -> project root)
pushd "%~dp0\..\.."

echo 🐳 Interactive Docker Launcher
echo.

set PROFILES=

:: Check TTS
set /p run_tts="Do you want to run local Speaches/Kokoro (TTS/STT)? (Large download ~5GB) [y/N]: "
if /i "%run_tts%"=="y" (
    set PROFILES=%PROFILES% --profile tts
    echo [INFO] Enabled 'tts' profile.

    echo.
    echo [INFO] Starting TTS Server (Speaches/Kokoro) to check/download model...
    docker compose -f docker-compose.windows.yml %PROFILES% up -d speaches

    echo [INFO] Waiting for TTS Server to start (15s)...
    timeout /t 15 /nobreak

    echo [INFO] Downloading Kokoro-82M model...
    docker compose -f docker-compose.windows.yml exec speaches uv tool run speaches-cli model download speaches-ai/Kokoro-82M-v1.0-ONNX
    echo [INFO] Downloading Faster Whisper Medium model (STT)...
    docker compose -f docker-compose.windows.yml exec speaches uv tool run speaches-cli model download Systran/faster-whisper-medium.en
    echo [SUCCESS] TTS Model Ready.
)

echo.
echo Starting Docker Compose with profiles: %PROFILES%
docker compose -f docker-compose.windows.yml %PROFILES% up --build

endlocal
