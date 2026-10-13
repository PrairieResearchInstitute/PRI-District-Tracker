"""Shared test setup: scripts/ on the import path, every temporary file on the drive,
and every backup the tests write in a throwaway folder.

Two rules meet here, and they point in different directions.

App standard v2 section B says the app writes nothing on C:, and Python's default
temp folder sits in the user profile there. The suite therefore keeps its scratch in
.tmp/ beside the app, on the drive, and points TMP, TEMP, TMPDIR and
tempfile.tempdir at it so a plain tempfile.mkdtemp() in any test lands there too.

The app's own rule says the tests must never write the data folder, because the
Studio tests would otherwise append probe entries to the real history.log (D-003).
So the suite sets $PRI_TMP_DIR to .tmp/ rather than letting app_config take
<dataFolder>/tmp, and keeps $PRI_BACKUP_DIR inside it.
"""
import os, sys, shutil, atexit, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

# Tests that exercise saving and restoring must write a real file inside the project,
# because the Studio only opens files it can resolve there. Two suites running at the
# same time (a local gate while CI runs, or two sessions) used fixed names and deleted
# each other's probes mid-test, which looked like five Studio failures and was not.
# One tag per process keeps them apart.
TAG = "p%d" % os.getpid()
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

if not os.environ.get("PRI_TEST_BACKUPS"):
    _tmp = os.path.join(ROOT, ".tmp", "tests-" + TAG)
    os.makedirs(_tmp, exist_ok=True)
    os.environ["PRI_TMP_DIR"] = _tmp
    import app_config
    app_config.use_drive_temp()
    os.environ["PRI_TEST_BACKUPS"] = _tmp
    os.environ["PRI_BACKUP_DIR"] = _tmp
    atexit.register(shutil.rmtree, _tmp, True)
else:
    # A child process the tests launched: the folder came down in the environment,
    # and tempfile caches its answer on first use, so name it again here.
    tempfile.tempdir = os.environ["PRI_TEST_BACKUPS"]

TMP = os.environ["PRI_TEST_BACKUPS"]


def free_drive():
    """A drive root, letter, colon and backslash, that is not mounted on this computer.

    Tests that must hand the code a lettered path build it from this, so no drive
    letter is written in the tests: the first free one, scanning Z down to C."""
    for c in range(ord("Z"), ord("C") - 1, -1):
        root = chr(c) + ":\\"
        if not os.path.exists(root):
            return root
    raise RuntimeError("every drive letter is mounted")
