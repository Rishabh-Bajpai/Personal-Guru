#!/bin/bash
set -e

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

check_conda

# Interactive Prompts
echo ""
echo "Select Installation Type:"
echo "1) Developer (Tests, Linting, Tools)"
echo "2) User (Standard Usage)"
echo "3) Production (Server Optimization)"
read -p "Enter number [1-3]: " install_type

case $install_type in
    1) req_file="requirements/dev.txt"; env_opts="python=3.11";;
    3) req_file="requirements/prod.txt"; env_opts="python=3.11";;
    *) req_file="requirements/base.txt"; env_opts="python=3.11";;
esac

echo ""
read -p "Install TTS (Text-to-Speech) dependencies? (Large download) [y/N]: " install_tts

# Environment Creation
if check_env_exists; then
    echo "✅ Conda environment 'Personal-Guru' already exists."
else
    echo "📦 Creating Conda environment..."
    conda create -n Personal-Guru $env_opts -y
fi

# Install Dependencies
echo "📦 Installing Dependencies from $req_file..."
ENV_PYTHON=$(conda run -n Personal-Guru which python)

# Core Install
$ENV_PYTHON -m pip install -r $req_file

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
