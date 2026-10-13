"""Portable settings for the PRI District Tracker (drive-ready loader).

The app reads one optional file, config.local.json, beside the project root. It is
git-ignored and starts as a copy of config.template.json (SETUP.bat makes it). The
only setting today is dataFolder: the folder, relative to the project root, that
holds what the app writes outside git (backups\\: verified snapshots of
data/activities.json, the Studio's edit copies and history.log). On the drive it reads
..\\..\\data\\pri-district-tracker.

With no config.local.json, or an empty dataFolder, every path stays where it was:
backups\\ beside the project. data/activities.json, the database of record, stays in
the repository either way.

Resolution order for the backups folder:
  1. $PRI_BACKUP_DIR, when set (the older override; the tests point it at a temp dir)
  2. <dataFolder>\\backups, when config.local.json names a dataFolder
  3. <project>\\backups

The keys database (app standard v2 section A) resolves the same way: $PRI_KEYS_DB,
then <dataFolder>/keys.db, then <project>/keys.db. It is git-ignored, separate from
data/activities.json so a key never travels with an export or a port, and only
scripts/keys.py opens it.

Pure stdlib.

    py scripts/app_config.py --show                     # what the app resolves
    py scripts/app_config.py --init                     # create config.local.json from the template
    py scripts/app_config.py --set-data-folder <rel>    # save dataFolder (relative path only)
"""
import json, os, re, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, "config.local.json")
TEMPLATE = os.path.join(ROOT, "config.template.json")

_ABSOLUTE = re.compile(r"^([A-Za-z]:|[\\/])")


def _read(path):
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("%s does not hold a JSON object" % os.path.basename(path))
    return obj


def source():
    """'portable' when config.local.json exists, else 'default'."""
    return "portable" if os.path.isfile(LOCAL) else "default"


def load():
    """The settings in config.local.json, or an empty dict when it does not exist."""
    return _read(LOCAL) if os.path.isfile(LOCAL) else {}


def _check_relative(value):
    if _ABSOLUTE.match(value):
        raise ValueError("dataFolder must be relative to the app folder (no drive letter): %r" % value)


def data_folder():
    """The resolved data folder, or None when no dataFolder is set."""
    value = (load().get("dataFolder") or "").strip()
    if not value:
        return None
    _check_relative(value)
    # The file is written on Windows (..\..\data\...) but the server runs
    # Linux, where a backslash is an ordinary character: treat both as separators.
    value = value.replace("\\", "/")
    return os.path.normpath(os.path.join(ROOT, *value.split("/")))


def backups_dir():
    """Where backups\\ lives: $PRI_BACKUP_DIR, then <dataFolder>\\backups, then the project."""
    env = os.environ.get("PRI_BACKUP_DIR")
    if env:
        return env
    base = data_folder()
    return os.path.join(base if base else ROOT, "backups")


def keys_db():
    """Where the git-ignored keys database lives (app standard v2 section A).

    Resolution order, the same shape as backups_dir():
      1. $PRI_KEYS_DB, when set (the tests point it at a temp file)
      2. <dataFolder>/keys.db, when config.local.json names a dataFolder
      3. <project>/keys.db

    Separate from data/activities.json on purpose: a key in the main database would
    travel with every export, change log and port to PostgreSQL. scripts/keys.py is
    the only module that opens this file.
    """
    env = os.environ.get("PRI_KEYS_DB")
    if env:
        return env
    base = data_folder()
    return os.path.join(base if base else ROOT, "keys.db")


def tmp_dir(create=False):
    """Where temporary files go (app standard v2 section B: nothing on C:).

    Python would otherwise use %TEMP%, which sits in the user profile on C:. The app
    keeps its scratch on the drive beside its data:

      1. $PRI_TMP_DIR, when set (the tests point it at .tmp/ beside the app, because
         the suite must never write the data folder)
      2. <dataFolder>/tmp, when config.local.json names a dataFolder
      3. <project>/.tmp

    Nothing is created unless `create` is true, so reporting the path costs nothing.
    """
    env = os.environ.get("PRI_TMP_DIR")
    if env:
        path = env
    else:
        base = data_folder()
        path = os.path.join(base, "tmp") if base else os.path.join(ROOT, ".tmp")
    if create and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path


def use_drive_temp():
    """Point this process at the drive for every temporary file, and return the folder.

    Sets TMPDIR, TEMP and TMP for anything the process launches, and tempfile.tempdir
    for Python itself, because tempfile caches the folder after its first use.
    """
    path = tmp_dir(create=True)
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = path
    tempfile.tempdir = path
    return path


def save(changes):
    """The only writer of config.local.json: merge `changes` into it and write atomically."""
    if "dataFolder" in changes and changes["dataFolder"]:
        _check_relative(changes["dataFolder"])
    current = load() if os.path.isfile(LOCAL) else (_read(TEMPLATE) if os.path.isfile(TEMPLATE) else {})
    current.update(changes)
    tmp = LOCAL + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(current, f, indent=2)
        f.write("\n")
    os.replace(tmp, LOCAL)
    return current


def main(argv):
    arg = argv[1] if len(argv) > 1 else "--show"
    if arg == "--init":
        if os.path.isfile(LOCAL):
            print("config.local.json already exists; left as it is.")
        else:
            save({})
            print("Created config.local.json from config.template.json.")
        return 0
    if arg == "--set-data-folder":
        if len(argv) < 3:
            print("Usage: py scripts/app_config.py --set-data-folder <relative path>")
            return 2
        save({"dataFolder": argv[2]})
        print("dataFolder set to %s -> %s" % (argv[2], data_folder()))
        return 0
    if arg == "--show":
        print("source      %s" % source())
        print("dataFolder  %s" % (data_folder() or "(none: backups stay beside the app)"))
        print("backups     %s" % backups_dir())
        print("keys        %s%s" % (keys_db(), "" if os.path.isfile(keys_db()) else "  (not created yet)"))
        print("temp        %s%s" % (tmp_dir(), "" if os.path.isdir(tmp_dir()) else "  (created on first use)"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
