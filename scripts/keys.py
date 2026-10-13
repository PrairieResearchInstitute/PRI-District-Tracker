"""The one door to this application's API keys.

App standard v2 section A: every app keeps its keys in its OWN separate, git-ignored
SQLite database in the drive data folder, so a key never reaches the main database,
a change log, an export, PostgreSQL or another app that reads that database.

    <dataFolder>/keys.db      api_keys(name, value, updated_at)

The tracker needs no key today. fetch_reps.py reads the Open States PUBLIC bulk
roster, which takes none, and district assignment runs locally as point-in-polygon
against the tracked geojson rather than through a geocoding service. The door exists
so that the day a key is needed there is exactly one place for it, and the tests can
hold that place closed.

Rules this module keeps, from section A5:
  - no function prints, logs or returns a key except get(), which the caller asked for.
  - names() and the command line report names and dates, never values.
  - a read never creates the database, so a missing key stays a missing key.
  - --set reads the value from a prompt, never from argv, so it misses shell history.

Pure stdlib (sqlite3 ships with Python).

    py scripts/keys.py --path            where the database lives
    py scripts/keys.py --list            the names held, never the values
    py scripts/keys.py --set NAME        prompt for a value and store it
    py scripts/keys.py --delete NAME     remove one
    py scripts/keys.py --import          fill missing names from an old api-keys.txt
"""
import os, sqlite3, datetime, getpass, sys

import app_config

TABLE = "api_keys"
SCHEMA = ("CREATE TABLE IF NOT EXISTS %s ("
          "name TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)" % TABLE)

# Old stores a one-time import reads, in order. The tracker has never had one; the
# standard asks for the path anyway so a key cannot be stranded.
LEGACY_NAMES = ("api-keys.txt", "api_keys.txt")


def path():
    """The resolved keys database. Never inside the repository when a dataFolder is set."""
    return app_config.keys_db()


def _open(create):
    p = path()
    if not create and not os.path.isfile(p):
        return None
    folder = os.path.dirname(p)
    if create and folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute(SCHEMA)
    return con


def get(name, default=None):
    """One key, or `default`. A read never creates the database."""
    con = _open(create=False)
    if con is None:
        return default
    try:
        row = con.execute("SELECT value FROM %s WHERE name = ?" % TABLE, (name,)).fetchone()
    finally:
        con.close()
    return row[0] if row else default


def put(name, value):
    """Store or replace one key. Returns the name, never the value."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("a key needs a name")
    if not str(value or "").strip():
        raise ValueError("refusing to store an empty value for %s" % name)
    con = _open(create=True)
    try:
        con.execute("INSERT INTO %s (name, value, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(name) DO UPDATE SET value = excluded.value, "
                    "updated_at = excluded.updated_at" % TABLE,
                    (name, value, datetime.datetime.now().isoformat(timespec="seconds")))
        con.commit()
    finally:
        con.close()
    return name


def names():
    """Every name held, with the date it changed. No values, by design."""
    con = _open(create=False)
    if con is None:
        return []
    try:
        rows = con.execute("SELECT name, updated_at FROM %s ORDER BY name" % TABLE).fetchall()
    finally:
        con.close()
    return [{"name": r[0], "updated_at": r[1]} for r in rows]


def delete(name):
    con = _open(create=False)
    if con is None:
        return False
    try:
        cur = con.execute("DELETE FROM %s WHERE name = ?" % TABLE, (name,))
        con.commit()
        return cur.rowcount > 0
    finally:
        con.close()


def legacy_files():
    """Old key files the import would read, if any exist. Paths only."""
    folders = [app_config.data_folder(), app_config.ROOT]
    out = []
    for folder in folders:
        if not folder:
            continue
        for nm in LEGACY_NAMES:
            p = os.path.join(folder, nm)
            if os.path.isfile(p) and p not in out:
                out.append(p)
    return out


def import_legacy():
    """Fill MISSING names from an old api-keys.txt, leaving the file where it is.

    Section A3: keys still load, and the old store stays until the owner confirms
    every key works. A name already in the database wins, so running this twice
    changes nothing.
    """
    held = {r["name"] for r in names()}
    added = []
    for p in legacy_files():
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                name, value = name.strip(), value.strip().strip('"').strip("'")
                if not name or not value or name in held:
                    continue
                put(name, value)
                held.add(name)
                added.append(name)
    return added


def main(argv):
    arg = argv[1] if len(argv) > 1 else "--list"
    if arg == "--path":
        print(path())
        return 0
    if arg == "--list":
        rows = names()
        print("keys database  %s" % path())
        print("holds          %d key(s)%s" % (len(rows), ":" if rows else ""))
        for r in rows:
            print("  %-28s set %s" % (r["name"], r["updated_at"]))
        old = legacy_files()
        if old:
            print("old store(s) found; run --import to fill missing names:")
            for p in old:
                print("  %s" % p)
        return 0
    if arg == "--set":
        if len(argv) < 3:
            print("Usage: py scripts/keys.py --set NAME")
            return 2
        value = getpass.getpass("Value for %s (not shown, not saved to history): " % argv[2])
        if not value.strip():
            print("Nothing entered, so nothing was stored.")
            return 2
        print("Stored %s in %s." % (put(argv[2], value), path()))
        return 0
    if arg == "--delete":
        if len(argv) < 3:
            print("Usage: py scripts/keys.py --delete NAME")
            return 2
        print("Removed %s." % argv[2] if delete(argv[2]) else "No key named %s." % argv[2])
        return 0
    if arg == "--import":
        added = import_legacy()
        print("Imported %d name(s)%s" % (len(added), (": " + ", ".join(added)) if added else "; nothing was missing"))
        print("The old file stays in place until every key is confirmed working.")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
