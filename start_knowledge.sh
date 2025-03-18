#!/bin/bash
# start_knowledge.sh

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

PROJECT_DIR="/server/knowledge"
VENV_ACTIVATE="$HOME/.pyenv/versions/venv_knowledge/bin/activate"
APP_SCRIPT="$PROJECT_DIR/knowledge.py"

if [ ! -f "$VENV_ACTIVATE" ]; then
    echo "Virtual environment activation script not found at $VENV_ACTIVATE"
    exit 1
fi

source "$VENV_ACTIVATE"
python3 -m streamlit run "$APP_SCRIPT" --server.port=8501 --server.address=0.0.0.0
