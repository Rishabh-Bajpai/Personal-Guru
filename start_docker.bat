@echo off
setlocal
echo 🐳 Interactive Docker Launcher
echo.

set PROFILES=

:: Check TTS
set /p run_tts="Do you want to run local Coqui TTS? (Large download ~5GB) [y/N]: "
if /i "%run_tts%"=="y" (
    set PROFILES=%PROFILES% --profile tts
    echo ✅ Enabled 'tts' profile.
)

echo.
echo Starting Docker Compose with profiles: %PROFILES%
docker compose -f docker-compose.windows.yml %PROFILES% up --build

endlocal
