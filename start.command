#!/bin/bash
# The default workflow is now a native Mac window, not a browser.
set -euo pipefail
cd "$(dirname "$0")"
exec bash desktop.command
