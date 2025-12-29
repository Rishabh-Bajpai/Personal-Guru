#!/bin/bash

# Ensure pydoc-markdown is installed
if ! command -v pydoc-markdown &> /dev/null; then
    echo "pydoc-markdown could not be found. Installing..."
    pip install pydoc-markdown
fi

# Generate documentation
echo "Generating documentation..."
pydoc-markdown
echo "Documentation generated in docs/reference"
