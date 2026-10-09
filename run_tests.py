"""Run with python -I run_tests.py after installing desktop dependencies."""

from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
sys.path.append(str(root))
if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    )
    raise SystemExit(not result.wasSuccessful())
