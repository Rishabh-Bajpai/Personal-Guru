@echo off
chcp 65001 >nul 2>nul
echo 🛑 Stopping all Personal Guru containers (including TTS)...
docker compose -f docker-compose.windows.yml --profile "*" down
echo ✅ All stopped.
