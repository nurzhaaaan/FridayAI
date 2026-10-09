#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname -s)" != "Darwin" ]; then echo "Friday.app жинау Mac-та орындалады."; exit 1; fi
if [ ! -x .venv-desktop/bin/python ]; then echo "Алдымен bash desktop.command іске қосыңыз, содан кейін GUI-ді жабыңыз."; exit 1; fi
.venv-desktop/bin/python -m pip install 'pyinstaller>=6.11,<7'
.venv-desktop/bin/python -I desktop/build_macos.py
