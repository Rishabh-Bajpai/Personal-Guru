#!/bin/bash
# Ensure script runs from project root (scripts/installation -> project root)
cd "$(dirname "$0")/../.."
echo "🛑 Stopping all Personal Guru containers (including TTS)..."
docker compose --profile "*" down
echo "✅ All stopped."
