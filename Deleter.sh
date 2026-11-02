#!/usr/bin/env bash
# Starts Deleter on Arch Linux. Other distros work once Python and Tk are installed.
# Packages go to .venv because Arch refuses system-wide pip installs (PEP 668).
set -euo pipefail
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

# Keep a terminal opened by a double-click visible, so a failure can be read.
trap 'code=$?; if [ "$code" -ne 0 ] && [ -t 0 ]; then read -rp "Failed, press Enter to close. " _; fi; exit "$code"' EXIT

if ! command -v python >/dev/null 2>&1 || ! python -c "import tkinter" >/dev/null 2>&1; then
    if ! command -v pacman >/dev/null 2>&1; then
        echo "Python with Tk is required, see README.md for your distro." >&2
        exit 1
    fi
    echo "Installing Python and Tk with pacman (asks for your sudo password)..."
    sudo pacman -S --needed python tk
fi

# Also fails after a Python upgrade, because .venv is tied to the old version.
if ! .venv/bin/python -c "import requests, customtkinter" >/dev/null 2>&1; then
    echo "First start: installing required packages..."
    python -m venv --clear .venv
    .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt
fi

# Menu entry that starts the app without opening a terminal at all.
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$apps"
cat >"$apps/deleter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Deleter
Comment=Remove your own Discord messages and reactions
Exec="$PWD/Deleter.sh"
Path=$PWD
Terminal=false
Categories=Utility;
StartupWMClass=Deleter
EOF

# New session: the app keeps running after the terminal is closed.
setsid -f .venv/bin/python deleter.py >/dev/null 2>&1 </dev/null
