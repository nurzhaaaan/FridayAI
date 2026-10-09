"""Use python -I desktop_entry.py so old vendored dependencies cannot shadow installed wheels."""

from pathlib import Path
import sys
import os
import tempfile

if not getattr(sys, "frozen", False):
    sys.path.append(str(Path(__file__).resolve().parent))
# The checkout includes a legacy dylib. Never let dyld resolve it from cwd.
# Keep imports rooted above while resolving native libraries outside the checkout.
_library_directory = tempfile.TemporaryDirectory(prefix="friday-native-")
os.chdir(_library_directory.name)
from desktop.app import main

if __name__ == "__main__":
    raise SystemExit(main())
