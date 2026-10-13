"""Run the whole test suite. Pure stdlib; no test runner to install.

    py scripts/run_tests.py
"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")

if __name__ == "__main__":
    sys.path.insert(0, TESTS)
    suite = unittest.defaultTestLoader.discover(TESTS, top_level_dir=TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
