"""Back up the PRI District Tracker's owned data.

`data/activities.json` is the database of record: every activity plus its lifecycle
stamps, and it exists nowhere else (see data-sources.yaml -> owned). PRI requires
owned data to be backed up and the backups to be tested
(.claude/skills/pri-database, pri-data-sources).

Each run writes a timestamped, verified snapshot and prunes old ones:
  * everything from the last KEEP_DAYS days is kept
  * older than that, only the first snapshot of each month is kept

Snapshots go to $PRI_BACKUP_DIR if set, else to <dataFolder>/backups when
config.local.json names a dataFolder (scripts/app_config.py), else to ./backups.
Point either at a location that is NOT the synced project folder for real
off-site safety.

Pure stdlib.

    py scripts/backup_data.py            # take a snapshot, then prune
    py scripts/backup_data.py --list     # show what exists
    py scripts/backup_data.py --verify   # re-read the newest snapshot and check it
"""
import json, os, sys, shutil, datetime

import app_config

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "data", "activities.json")
DEST = app_config.backups_dir()
KEEP_DAYS = 30
PREFIX = "activities-"


def _snapshots():
    if not os.path.isdir(DEST):
        return []
    out = []
    for n in sorted(os.listdir(DEST)):
        if n.startswith(PREFIX) and n.endswith(".json"):
            out.append(os.path.join(DEST, n))
    return out


def _stamp_of(path):
    """'activities-2026-09-24T1530.json' -> date(2026, 9, 24); None if unparseable."""
    base = os.path.basename(path)[len(PREFIX):-len(".json")]
    try:
        return datetime.datetime.strptime(base[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def verify(path):
    """A backup nobody can read is not a backup. Parse it and count the records."""
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    acts = obj.get("activities")
    if not isinstance(acts, list) or not acts:
        raise ValueError("no activities array in %s" % os.path.basename(path))
    missing = [a.get("id", "?") for a in acts if "ingested_at" not in a]
    if missing:
        raise ValueError("%d record(s) missing lifecycle stamps, e.g. %s"
                         % (len(missing), missing[0]))
    return len(acts)


def prune():
    today = datetime.date.today()
    kept_months = set()
    removed = []
    for p in sorted(_snapshots(), reverse=True):      # newest first
        d = _stamp_of(p)
        if d is None:
            continue
        if (today - d).days <= KEEP_DAYS:
            continue                                   # inside the daily window
        key = (d.year, d.month)
        if key in kept_months:
            os.remove(p)
            removed.append(os.path.basename(p))
        else:
            kept_months.add(key)                       # monthly keeper (oldest of month wins)
    return removed


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "--list":
        snaps = _snapshots()
        if not snaps:
            print("No snapshots in", DEST)
            return 0
        print("%d snapshot(s) in %s" % (len(snaps), DEST))
        for p in snaps:
            print("  %-34s %7d bytes" % (os.path.basename(p), os.path.getsize(p)))
        return 0

    if arg == "--verify":
        snaps = _snapshots()
        if not snaps:
            print("FAIL: no snapshots to verify in", DEST)
            return 1
        newest = snaps[-1]
        n = verify(newest)
        print("OK: %s restores cleanly (%d activities)" % (os.path.basename(newest), n))
        return 0

    if not os.path.exists(SRC):
        print("FAIL: source not found:", SRC)
        return 1
    os.makedirs(DEST, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H%M")
    out = os.path.join(DEST, "%s%s.json" % (PREFIX, stamp))
    shutil.copy2(SRC, out)

    try:
        n = verify(out)
    except Exception as e:
        os.remove(out)
        print("FAIL: snapshot did not verify, discarded ->", e)
        return 1

    with open(SRC, encoding="utf-8") as f:
        src_n = len(json.load(f)["activities"])
    if n != src_n:
        os.remove(out)
        print("FAIL: snapshot has %d activities but source has %d; discarded" % (n, src_n))
        return 1

    removed = prune()
    try:
        shown = os.path.relpath(out, PROJ)
    except ValueError:                                 # another drive: relpath cannot span it
        shown = out
    print("Backed up %d activities -> %s" % (n, shown))
    print("Verified OK. %d snapshot(s) retained%s."
          % (len(_snapshots()), (", %d pruned" % len(removed)) if removed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
