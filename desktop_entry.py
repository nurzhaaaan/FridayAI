"""Use python -I desktop_entry.py so old vendored dependencies cannot shadow installed wheels."""

from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    sys.path.append(str(Path(__file__).resolve().parent))
from desktop.app import main

if __name__ == "__main__":
    raise SystemExit(main())
