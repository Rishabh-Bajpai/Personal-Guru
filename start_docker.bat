@echo off
setlocal
echo 🐳 Interactive Docker Launcher
echo.

set PROFILES=

:: Check LLM
set /p run_llm="Do you want to run a local LLM via Docker (Ollama)? [y/N]: "
if /i "%run_llm%"=="y" (
    set PROFILES=%PROFILES% --profile llm
    echo ✅ Enabled 'llm' profile.
)

echo.
echo Starting Docker Compose with profiles: %PROFILES%
docker compose %PROFILES% up --build

endlocal
