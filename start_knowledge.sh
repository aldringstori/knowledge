#!/bin/bash

# Define the project directory
PROJECT_DIR="/srv/knowledge"

# Define the path to the virtual environment activation script
VENV_ACTIVATE="$PROJECT_DIR/venv_knowledge/bin/activate"

# Define the path to the Streamlit application
APP_SCRIPT="$PROJECT_DIR/knowledge.py"

# Check if the virtual environment activation script exists
if [ ! -f "$VENV_ACTIVATE" ]; then
    echo "Virtual environment activation script not found at $VENV_ACTIVATE"
    exit 1
fi

# Activate the virtual environment
source "$VENV_ACTIVATE"

# Run the Streamlit application
streamlit run "$APP_SCRIPT"
