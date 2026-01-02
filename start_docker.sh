#!/bin/bash

echo "🐳 Interactive Docker Launcher"
echo ""

PROFILES=""

# Check env or ask
echo "Do you want to run local Coqui TTS? (Large download ~5GB) [y/N]"
read run_tts
if [[ "$run_tts" =~ ^[Yy]$ ]]; then
    PROFILES="$PROFILES --profile tts"
    echo "✅ Enabled 'tts' profile."
fi

echo "Do you want to run in detached mode (background)? [Y/n]"
read run_detached
if [[ "$run_detached" =~ ^[Nn]$ ]]; then
    DETACHED=""
    echo "Running in foreground..."
else
    DETACHED="-d"
    echo "Running in background (detached)..."
fi

echo ""
echo "Starting Docker Compose with profiles: $PROFILES"
docker compose $PROFILES up --build $DETACHED
