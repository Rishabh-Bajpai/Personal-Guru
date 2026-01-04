#!/bin/bash
echo "🛑 Stopping all Personal Guru containers (including TTS)..."
docker compose --profile "*" down
echo "✅ All stopped."
