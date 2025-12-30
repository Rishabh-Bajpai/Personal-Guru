#!/bin/bash
set -euo pipefail

# Usage: ./scripts/export_docs.sh <REPO_URL> <TARGET_DIR>
# Example: ./scripts/export_docs.sh git@github.com:username/repo-b.git /tmp/repo-b

REPO_URL=$1
TARGET_DIR=$2

# Save original directory to return to later
ORIGINAL_DIR=$(pwd)

if [ -z "$REPO_URL" ] || [ -z "$TARGET_DIR" ]; then
    echo "Usage: $0 <REPO_URL> <TARGET_DIR>"
    exit 1
fi

# 1. Generate Docs
./scripts/generate_docs.sh
if [ $? -ne 0 ]; then
    echo "Error: Documentation generation script failed. Aborting."
    exit 1
fi

DOCS_DIR="${ORIGINAL_DIR}/docs/reference"
if [ ! -d "$DOCS_DIR" ]; then
    echo "Error: Docs directory '$DOCS_DIR' not found after generation. Aborting."
    exit 1
fi

# Ensure docs directory is not empty
if ! find "$DOCS_DIR" -mindepth 1 -maxdepth 1 | read -r _; then
    echo "Error: Docs directory '$DOCS_DIR' is empty after generation. Aborting."
    exit 1
fi
# 2. Clone/Update Repo B
if [ -d "$TARGET_DIR" ]; then
    echo "Updating existing repo at $TARGET_DIR..."
    cd "$TARGET_DIR" || { echo "Error: Failed to change to directory $TARGET_DIR"; exit 1; }
    if ! git pull; then
        echo "Error: git pull failed. Please resolve any conflicts or issues manually."
        exit 1
    fi
else
    echo "Cloning repo to $TARGET_DIR..."
    if ! git clone "$REPO_URL" "$TARGET_DIR"; then
        echo "Error: git clone failed. Check the repository URL and your credentials."
        exit 1
    fi
    cd "$TARGET_DIR" || { echo "Error: Failed to change to directory $TARGET_DIR"; exit 1; }
fi

# 3. Copy Docs
# Assuming Repo B has a 'docs' folder where we want to put the reference
DEST_PATH="$TARGET_DIR/docs/reference"
mkdir -p "$DEST_PATH"
cp -r "$DOCS_DIR"/* "$DEST_PATH"

# 4. Commit and Push
if [ -n "$(git status --porcelain)" ]; then
    echo "Changes detected. Committing and pushing..."
    git add . || { echo "Error: git add failed."; exit 1; }
    if ! git commit -m "Update API documentation from Personal-Guru"; then
        echo "Error: git commit failed."
        exit 1
    fi
    if ! git push; then
        echo "Error: git push failed. Please check your credentials and network connection."
        exit 1
    fi
else
    echo "No changes detected."
fi

# Return to original directory
cd "$ORIGINAL_DIR" || exit 1
