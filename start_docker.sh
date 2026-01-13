#!/bin/bash

echo "🐳 Interactive Docker Launcher"
echo ""

PROFILES=""

# Check env or ask
echo "Do you want to run local Speaches/Kokoro (TTS/STT)? (Large download ~5GB) [y/N]"
read run_tts
if [[ "$run_tts" =~ ^[Yy]$ ]]; then
    PROFILES="$PROFILES --profile tts"
    echo "✅ Enabled 'tts' profile."

    # Start just the TTS service first to download model
    echo "🎤 Starting Speaches (TTS) container to check/download model..."
    docker compose $PROFILES up -d speaches

    echo "⏳ Waiting for TTS Server to start (15s)..."
    sleep 15

    echo "⬇️  Downloading Kokoro-82M model..."
    docker compose exec speaches uv tool run speaches-cli model download speaches-ai/Kokoro-82M-v1.0-ONNX
    echo "⬇️  Downloading Faster Whisper Medium model (STT)..."
    docker compose exec speaches uv tool run speaches-cli model download Systran/faster-whisper-medium.en
    echo "✅ TTS Model Ready."
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
