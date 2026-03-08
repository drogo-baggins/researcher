#!/usr/bin/env bash
# sandbox-init.sh — Bootstrap Linux venv in ~/.researcher/venv
# This script is executed by opencode sandbox on container start.
# The venv is persisted via the ~/.researcher volume mount.
set -euo pipefail

VENV_DIR="/root/.researcher/venv"
PROJECT_DIR="/workspace"

# If venv already exists and has the right Python, just ensure editable install is current
if [ -f "$VENV_DIR/bin/python" ]; then
    echo "[sandbox-init] venv found at $VENV_DIR — updating editable install..."
    "$VENV_DIR/bin/pip" install --quiet -e "$PROJECT_DIR"
    "$VENV_DIR/bin/pip" install --quiet -r "$PROJECT_DIR/requirements-dev.txt"
    echo "[sandbox-init] venv ready."
    exit 0
fi

echo "[sandbox-init] Creating venv at $VENV_DIR ..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -e "$PROJECT_DIR" --quiet
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements-dev.txt" --quiet
echo "[sandbox-init] venv created and packages installed."
