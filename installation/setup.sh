#!/bin/bash
set -e

# Ensure script runs from project root
cd "$(dirname "$0")/.."

echo "🚀 Starting Personal Guru Setup..."

# --- Function Definitions ---

check_conda() {
    if ! command -v conda &> /dev/null; then
        echo "❌ Conda is not installed. Please install Miniconda or Anaconda first."
        exit 1
    fi
}

check_env_exists() {
    if conda env list | grep -q "Personal-Guru"; then
        return 0
    else
        return 1
    fi
}

# --- Main Script ---

check_ffmpeg() {
    if ! command -v ffmpeg &> /dev/null; then
        echo "⚠️  FFmpeg is not installed. It is required for audio processing."
        read -p "Do you want to install it now? [y/N]: " install_ffmpeg
        if [[ "$install_ffmpeg" =~ ^[Yy]$ ]]; then
            if [[ "$OSTYPE" == "linux-gnu"* ]]; then
                if command -v apt &> /dev/null; then
                    echo "📦 Installing FFmpeg via apt..."
                    sudo apt update && sudo apt install -y ffmpeg
                elif command -v dnf &> /dev/null; then
                    echo "📦 Installing FFmpeg via dnf..."
                    sudo dnf install -y ffmpeg
                elif command -v pacman &> /dev/null; then
                    echo "📦 Installing FFmpeg via pacman..."
                    sudo pacman -S ffmpeg
                else
                    echo "❌ Could not detect package manager. Please install FFmpeg manually."
                fi
            elif [[ "$OSTYPE" == "darwin"* ]]; then
                 if command -v brew &> /dev/null; then
                    echo "📦 Installing FFmpeg via Homebrew..."
                    brew install ffmpeg
                 else
                    echo "❌ Homebrew not found. Please install FFmpeg manually."
                 fi
            else
                echo "❌ OS not supported for auto-install. Please install FFmpeg manually."
            fi
        else
            echo "⚠️  Skipping FFmpeg installation. Audio features may not work."
        fi
    else
        echo "✅ FFmpeg is already installed."
    fi
}

# --- Main Script ---

check_conda
check_ffmpeg

# Interactive Prompts

env_opts="python=3.11"



echo ""
read -p "Install Speech Services (TTS/STT) dependencies? (Large download) [y/N]: " install_tts

# Environment Creation
if check_env_exists; then
    echo "✅ Conda environment 'Personal-Guru' already exists."
else
    echo "📦 Creating Conda environment..."
    conda create -n Personal-Guru $env_opts -y
fi

# Install Dependencies
echo "📦 Installing Dependencies from requirements.txt..."
ENV_PYTHON=$(conda run -n Personal-Guru which python)

# Core Install
$ENV_PYTHON -m pip install -r requirements.txt

# Optional TTS
# Docker TTS Setup
if [[ "$install_tts" =~ ^[Yy]$ ]]; then
    if command -v docker &> /dev/null; then
        echo "🎤 Starting TTS Server (Speaches/Kokoro)..."
        docker compose up -d speaches

        echo "⏳ Waiting for TTS Server to start (15s)..."
        sleep 15

        echo "⬇️  Downloading Kokoro-82M model..."
        docker compose exec speaches uv tool run speaches-cli model download speaches-ai/Kokoro-82M-v1.0-ONNX

        echo "⬇️  Downloading Faster Whisper Medium model (STT)..."
        docker compose exec speaches uv tool run speaches-cli model download Systran/faster-whisper-medium.en

        echo "✅ TTS Setup Complete."
    else
        echo "❌ Docker not found. Cannot set up TTS server."
    fi
fi

# Database Setup
echo ""
read -p "Start Database via Docker now? [Y/n]: " start_db
if [[ "$start_db" =~ ^[Nn]$ ]]; then
    echo "Using existing DB or manual setup..."
else
    if command -v docker &> /dev/null; then
        echo "🐳 Starting Database..."
        docker compose up -d db

        echo "⏳ Waiting for Database to be ready..."
        sleep 5

        echo "🗄️  Initializing/Updating Database Tables..."
        $ENV_PYTHON scripts/update_database.py
    else
        echo "❌ Docker not found. Skipping DB start."
    fi
fi

echo ""
echo "✅ Setup Complete!"
echo "To run the application:"
echo "  conda activate Personal-Guru"
echo "  python run.py"
