#!/bin/bash
# K305 Newsense vs Ouster dashboard - macOS start file. Double-click it in Finder.
# First start: creates a private Python environment in this folder (.venv) and installs the requirements (needs internet, ~2-5 min).
cd "$(dirname "$0")" || exit 1
clear
echo "=== K305 Newsense vs Ouster dashboard ==="
pause_exit() { echo; read -r -p "Press Enter to close this window." _; exit "${1:-1}"; }

# 1. find Python 3.11+ (python.org and Homebrew locations first; /usr/bin/python3 on macOS is too old)
PY=""
for c in /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
         /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 \
         /usr/local/bin/python3.12 /usr/local/bin/python3.11 python3.12 python3.11 python3.13 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ] && [ ! -x .venv/bin/python ]; then
  echo
  echo "Python 3.11 or newer is not installed."
  echo "Please install Python 3.12 from https://www.python.org/downloads/ (macOS installer), then double-click this file again."
  open "https://www.python.org/downloads/macos/" 2>/dev/null
  pause_exit 1
fi

# 2. private environment in .venv (created once)
if [ ! -x .venv/bin/python ]; then
  echo "First start: creating the Python environment (once) ..."
  "$PY" -m venv .venv || { echo "Could not create the environment."; pause_exit 1; }
fi
if ! cmp -s requirements.txt .venv/requirements.installed; then
  echo "Installing the required packages (once, needs internet, a few minutes) ..."
  .venv/bin/python -m pip install --disable-pip-version-check -q --upgrade pip
  if .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt; then
    cp requirements.txt .venv/requirements.installed
  else
    echo "Installing the packages failed. Check the internet connection and try again."; pause_exit 1
  fi
fi

# 3. start (opens the browser automatically)
.venv/bin/python run_dashboard.py "$@" || pause_exit 1
