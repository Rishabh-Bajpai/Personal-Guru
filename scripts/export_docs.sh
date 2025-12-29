#!/bin/bash

# Usage: ./scripts/export_docs.sh <REPO_URL> <TARGET_DIR>
# Example: ./scripts/export_docs.sh git@github.com:username/repo-b.git /tmp/repo-b

REPO_URL=$1
TARGET_DIR=$2

if [ -z "$REPO_URL" ] || [ -z "$TARGET_DIR" ]; then
    echo "Usage: $0 <REPO_URL> <TARGET_DIR>"
    exit 1
fi

# 1. Generate Docs
./scripts/generate_docs.sh

# 2. Clone/Update Repo B
if [ -d "$TARGET_DIR" ]; then
    echo "Updating existing repo at $TARGET_DIR..."
    cd "$TARGET_DIR"
    git pull
else
    echo "Cloning repo to $TARGET_DIR..."
    git clone "$REPO_URL" "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

# 3. Copy Docs
# Assuming Repo B has a 'docs' folder where we want to put the reference
DEST_PATH="$TARGET_DIR/docs/reference"
mkdir -p "$DEST_PATH"
cp -r ../../../docs/reference/* "$DEST_PATH"

# 4. Commit and Push
if [ -n "$(git status --porcelain)" ]; then
    echo "Changes detected. Committing and pushing..."
    git add .
    git commit -m "Update API documentation from Personal-Guru"
    git push
else
    echo "No changes detected."
fi
