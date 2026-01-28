#!/bin/bash
set -e

# Resolve project root (3 levels up from scripts/installation/linux)
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
cd "$PROJECT_ROOT"

# Create build build_env
# Always start with a clean build environment to avoid python version mismatches
if [ -d "build_env_release" ]; then
    echo "Removing existing virtual environment..."
    rm -rf build_env_release
fi

echo "Creating virtual environment..."
python3 -m venv build_env_release

source build_env_release/bin/activate


echo "Installing dependencies..."
pip install ".[local]"
pip install pyinstaller

echo "Building Linux binary..."
pyinstaller --noconfirm --log-level=WARN \
    --name PersonalGuru \
    --onedir \
    --clean \
    --paths . \
    --collect-all weasyprint \
    --add-data "app/core/templates:app/core/templates" \
    --add-data "app/static:app/static" \
    --add-data "app/modes:app/modes" \
    --add-data "app/common:app/common" \
    --add-data "migrations:migrations" \
    scripts/installation/linux/main.py

echo "Build complete. Binary is in dist/PersonalGuru"
