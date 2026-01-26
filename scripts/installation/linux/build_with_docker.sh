#!/bin/bash
set -e

# Resolve project root
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_ROOT="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"
cd "$PROJECT_ROOT"

# Name of the docker image
IMAGE_NAME="personal-guru-builder"

echo "Building Docker image for legacy compatibility (Ubuntu 22.04)..."
docker build -t "$IMAGE_NAME" -f scripts/installation/linux/Dockerfile .

echo "Running build inside Docker..."
# We mount the current directory to /app
# We use --device /dev/fuse and --cap-add SYS_ADMIN for FUSE/AppImage if needed,
# or we just rely on --appimage-extract which acts differently.
# But appimagetool usually needs FUSE to mount the runtime if not extracted.
# Adding --priviledged is blunt but works for FUSE in docker usually.
docker run --rm \
    -v "$(pwd):/app" \
    --device /dev/fuse \
    --cap-add SYS_ADMIN \
    --security-opt apparmor:unconfined \
    "$IMAGE_NAME"

echo "Build artifact should be in dist/"
