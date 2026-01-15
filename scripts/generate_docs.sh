#!/bin/bash
set -euo pipefail

# Ensure pydoc-markdown is installed
if ! command -v pydoc-markdown &> /dev/null; then
    echo "pydoc-markdown could not be found. Installing..."
    pip install pydoc-markdown
fi

# Generate documentation
echo "Generating documentation..."
# Ensure we are in project root
cd "$(dirname "$0")/.."

if ! pydoc-markdown docs/pydoc-markdown.yml; then
    echo "Error: Failed to generate documentation with pydoc-markdown." >&2
    exit 1
fi
echo "Documentation generated in docs/reference"
