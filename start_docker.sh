#!/bin/bash

echo "🐳 Interactive Docker Launcher"
echo ""

PROFILES=""

# Check env or ask
echo "Do you want to run a local LLM via Docker (Ollama)? [y/N]"
read run_llm
if [[ "$run_llm" =~ ^[Yy]$ ]]; then
    PROFILES="$PROFILES --profile llm"
    echo "✅ Enabled 'llm' profile."
fi

# TTS?
# Assuming there might be a TTS service definition I didn't add yet, but for now I'll check generic logic.
# The user repo has `coqui_tts` dir. I should strictly add it to docker-compose if I want to support it properly.
# But for now, let's stick to what's defined.

echo ""
echo "Starting Docker Compose with profiles: $PROFILES"
docker compose $PROFILES up --build
