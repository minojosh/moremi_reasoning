#!/bin/bash

# Unified entry script for reasoning pipelines
# This script provides a simple wrapper around the Python entry point

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/run_reasoning_pipeline.py"

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python script not found at $PYTHON_SCRIPT"
    exit 1
fi

# Use minoenv for WSL environment (as per your instructions)
if [ -n "$WSL_DISTRO_NAME" ]; then
    # We're in WSL, use minoenv
    if command -v conda >/dev/null 2>&1; then
        # Activate minoenv if conda is available
        eval "$(conda shell.bash hook)"
        conda activate minoenv 2>/dev/null || echo "Warning: Could not activate minoenv"
    fi
fi

# Execute the Python script with all arguments
python3 "$PYTHON_SCRIPT" "$@"
