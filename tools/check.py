"""PRI District Tracker self-check (the gate in .claude/gate.json).

    py tools/check.py

Prints one line per check, then CHECK OK or CHECK FAILED: n.

  1. the test suite (scripts/run_tests.py) passes; the tests keep their probe
     backups in a temp folder (tests/_ctx.py), never in the data folder
  2. the site builds offline (scripts/build_site.py with PRI_SKIP_REPS=1); the
     build rewrites the tracked outputs, so the check reports whether they now
     differ from git
  3. data/activities.json, the database of record, parses (read-only)
  4. the data folder: when the drive folder ..\\..\\data\\pri-district-tracker
     exists, config.local.json must exist and name it, and the backups the app
     writes must resolve there. The newest snapshot is verified and history.log
     counted, read-only. Nothing in the data folder is written.
  5. API keys live in their own git-ignored SQLite database in the data folder
     (scripts/keys.py), never in data/activities.json. The check confirms the name
     is git-ignored and counts the names held, never a value. Nothing is created.
  6. temporary files resolve to the drive (scripts/app_config.py tmp_dir), never to
     %TEMP% in the user profile. Nothing is created.
  7. the hosted PHP layer: every PHP file passes php -l, and tests/php/run-tests.php
     passes its unit checks (no database). PHP comes from scripts/find_php.py; with
     no PHP on the machine the check fails, because a skipped check proves nothing.
     Each app carries its own PHP copy in tools/php, made by SETUP.bat (owner Q-10,
     2026-10-12); PRI_PHP names another php.exe for one run.
  8. PostgreSQL: when <dataFolder>/pg.env exists, the PHP suite runs again with
     DT_TEST_DRIVER=pgsql against the _test database only (the module refuses any
     other name). The real database is never opened. The database is the estate
     cluster on the portable drive (127.0.0.1 port 5433, platform D-028):
     scripts/estate_pg.py starts it first when it is not running and stops it
     cleanly afterwards when this check started it. Without pg.env the check says
     so and passes, because the owner has not provisioned the drive cluster.
  9. the authorship credit (drez-ui-elements rule 27): the exact line is in the
     build constant, in every generated page (index.html, handout.html,
     PRI-Tracker-Kit.html), in the back-office partial, the hosted back office
     and the Data Console, and in the NOTICE at the repository root.

Pure stdlib.
"""
import json, os, subprocess, sys, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
APP_ID = "pri-district-tracker"
DRIVE_DATA = os.path.normpath(os.path.join(ROOT, "..", "..", "data", APP_ID))
OUTPUTS = ["index.html", "handout.html", "PRI-Tracker-Kit.html", "data.js",
           "data/geo.json", "data/reps.json"]

failed = 0


def ok(msg):
    print("  ok    " + msg)


def fail(msg):
    global failed
    failed += 1
    print("  FAIL  " + msg)


def run(args, env=None, timeout=600):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          env=env, timeout=timeout)


# 1. Tests.
try:
    r = run([sys.executable, os.path.join(SCRIPTS, "run_tests.py")])
    m = re.search(r"Ran (\d+) tests?", r.stderr + r.stdout)
    n = m.group(1) if m else "?"
    if r.returncode == 0:
        ok("test suite passes (%s tests)" % n)
    else:
        tail = [l for l in (r.stderr + r.stdout).splitlines() if l.startswith(("FAIL:", "ERROR:"))]
        fail("test suite failed (%s tests): %s" % (n, "; ".join(tail[:5]) or "exit %d" % r.returncode))
except subprocess.TimeoutExpired:
    fail("test suite did not finish in 600 s")

# 2. Offline build.
try:
    env = dict(os.environ, PRI_SKIP_REPS="1")
    r = run([sys.executable, os.path.join(SCRIPTS, "build_site.py")], env=env)
    if r.returncode != 0:
        fail("build_site.py exited %d: %s" % (r.returncode, (r.stderr or r.stdout).strip().splitlines()[-1:]))
    else:
        g = run(["git", "-c", "safe.directory=*", "diff", "--name-only", "--"] + OUTPUTS, timeout=120)
        changed = [l for l in g.stdout.splitlines() if l.strip()]
        if g.returncode != 0:
            ok("site builds offline (git could not compare the outputs: %s)" % g.stderr.strip()[:120])
        elif changed:
            ok("site builds offline; outputs differ from git: %s (commit them with the data change)" % ", ".join(changed))
        else:
            ok("site builds offline; outputs match git")
except subprocess.TimeoutExpired:
    fail("build_site.py did not finish in 600 s")

# 9. The authorship credit (drez-ui-elements rule 27). Runs after the build, so the
# generated pages it reads are the ones this run produced.
CREDIT = "Developed by M. J. Dreslik, with Claude Opus 5"
CREDIT_FILES = ["scripts/build_site.py", "index.html", "handout.html", "PRI-Tracker-Kit.html",
                "includes/ui.php", "scripts/admin_ui.html", "NOTICE"]
missing = []
for rel in CREDIT_FILES:
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    if CREDIT not in text:
        missing.append(rel)
if "dt_back_office_foot()" not in open(os.path.join(ROOT, "php", "admin_ingest.php"), encoding="utf-8").read():
    missing.append("php/admin_ingest.php (no dt_back_office_foot())")
if missing:
    fail("the credit line \"%s\" is missing from: %s" % (CREDIT, ", ".join(missing)))
else:
    ok("the credit line is in every footer and in NOTICE (%d files and php/admin_ingest.php)" % len(CREDIT_FILES))

# 3. Database of record.
try:
    with open(os.path.join(ROOT, "data", "activities.json"), encoding="utf-8") as f:
        acts = json.load(f)["activities"]
    ok("data/activities.json parses (%d activities, read-only)" % len(acts))
except Exception as e:
    fail("data/activities.json does not load: %s" % e)

# 4. Data folder.
try:
    import app_config
    local = os.path.isfile(app_config.LOCAL)
    if not local:
        if os.path.isdir(DRIVE_DATA):
            fail("config.local.json is missing while the drive data exists (%s); run SETUP.bat" % DRIVE_DATA)
        else:
            ok("no config.local.json and no drive data folder; backups stay beside the app")
    else:
        folder = app_config.data_folder()
        if folder is None:
            if os.path.isdir(DRIVE_DATA):
                fail("config.local.json names no dataFolder while the drive data exists (%s)" % DRIVE_DATA)
            else:
                ok("config.local.json loads; no dataFolder, so backups stay beside the app")
        elif not os.path.isdir(folder):
            fail("config.local.json names a data folder that does not exist: %s" % folder)
        else:
            ok("config.local.json loads; dataFolder %s -> %s" % (app_config.load()["dataFolder"], folder))
            backups = app_config.backups_dir()
            if os.environ.get("PRI_BACKUP_DIR"):
                ok("PRI_BACKUP_DIR overrides the backups folder: %s" % backups)
            elif os.path.normcase(backups) != os.path.normcase(os.path.join(folder, "backups")):
                fail("backups resolve to %s, not the data folder" % backups)
            if not os.path.isdir(backups):
                ok("no backups folder yet at %s (first run)" % backups)
            else:
                import backup_data
                snaps = sorted(n for n in os.listdir(backups)
                               if n.startswith(backup_data.PREFIX) and n.endswith(".json"))
                if snaps:
                    count = backup_data.verify(os.path.join(backups, snaps[-1]))
                    ok("backups resolve to %s; newest snapshot %s verifies (%d activities, read-only)"
                       % (backups, snaps[-1], count))
                else:
                    ok("backups resolve to %s; no snapshot yet" % backups)
                hist = os.path.join(backups, "studio", "history.log")
                if os.path.isfile(hist):
                    with open(hist, encoding="utf-8") as f:
                        lines = sum(1 for l in f if l.strip())
                    ok("Studio history.log read from %s (%d entries, read-only)" % (hist, lines))
except Exception as e:
    fail("data folder check failed: %s" % e)

# 5. API keys: their own git-ignored database, never the main one (app standard v2 A).
try:
    import keys as app_keys
    kp = app_keys.path()
    kname = os.path.basename(kp)
    g = run(["git", "-c", "safe.directory=*", "check-ignore", "-q", kname], timeout=120)
    if g.returncode != 0:
        fail("the keys database name %s is not git-ignored" % kname)
    elif not os.path.isfile(kp):
        ok("keys database would be %s; none created yet, and the tracker needs no key" % kp)
    else:
        ok("keys database %s holds %d name(s), git-ignored, values never printed"
           % (kp, len(app_keys.names())))
except Exception as e:
    fail("keys check failed: %s" % e)

# 6. Temporary files: on the drive, never in the user profile (app standard v2 B).
try:
    import app_config as _ac
    tp = _ac.tmp_dir()
    if os.path.splitdrive(os.path.abspath(tp))[0].lower() != os.path.splitdrive(os.path.abspath(ROOT))[0].lower():
        fail("temporary files would go to %s, a different drive from the app" % tp)
    elif os.path.isdir(tp):
        ok("temp files -> %s (on the drive, nothing on C:)" % tp)
    else:
        ok("temp files would be %s; created on first use, nothing on C:" % tp)
except Exception as e:
    fail("temp folder check failed: %s" % e)

# 7. The hosted PHP layer: lint and unit checks.
def php_source(binary):
    """Where the PHP came from, in words (owner Q-10: each app carries its own copy)."""
    own = os.path.normcase(os.path.join(ROOT, "tools", "php"))
    if os.path.normcase(os.path.dirname(os.path.abspath(binary))) == own:
        return "tools/php, the app's own copy (Q-10)"
    if os.environ.get("PRI_PHP", "").strip():
        return "PRI_PHP; run SETUP.bat to give the app its own copy (Q-10)"
    return "the PATH; run SETUP.bat to give the app its own copy (Q-10)"


php_cmd = None
try:
    import find_php
    php_cmd = find_php.command()
    if not php_cmd:
        fail("PHP not found ($PRI_PHP, tools/php/php.exe, PATH); the hosted layer is unchecked. "
             "Each app carries its own PHP copy (owner Q-10): run SETUP.bat once to copy it into "
             "tools/php, or set PRI_PHP to a php.exe with pdo_pgsql")
    else:
        files = []
        for d in ("includes", "php", "tools", os.path.join("tests", "php")):
            folder = os.path.join(ROOT, d)
            if os.path.isdir(folder):
                files += [os.path.join(folder, n) for n in sorted(os.listdir(folder)) if n.endswith(".php")]
        files.append(os.path.join(ROOT, "health.php"))
        bad = []
        for f in files:
            r = run(php_cmd + ["-l", f], timeout=120)
            if r.returncode != 0:
                bad.append(os.path.relpath(f, ROOT))
        r = run(php_cmd + [os.path.join(ROOT, "tests", "php", "run-tests.php")],
                env={k: v for k, v in os.environ.items() if k not in ("DT_TEST_DRIVER", "DB_DRIVER", "DT_DB_TARGET")})
        m = re.search(r"(\d+) passed, (\d+) failed", r.stdout)
        if bad:
            fail("php -l rejects: %s" % ", ".join(bad))
        elif r.returncode != 0 or not m:
            tail = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
            fail("PHP unit checks failed: %s" % ("; ".join(tail[:5]) or (r.stderr or r.stdout).strip()[-200:]))
        else:
            ok("PHP layer: %d files lint clean; unit checks %s passed (no database); PHP from %s"
               % (len(files), m.group(1), php_source(php_cmd[0])))
except subprocess.TimeoutExpired:
    fail("PHP checks did not finish")
except Exception as e:
    fail("PHP check failed: %s" % e)

# 8. PostgreSQL, on the _test database only.
try:
    import app_config as _ac8
    folder = _ac8.data_folder()
    pg_env = os.path.join(folder, "pg.env") if folder else None
    if not pg_env or not os.path.isfile(pg_env):
        ok("PostgreSQL suite not run: no pg.env in the data folder (the owner provisions the drive cluster)")
    elif not php_cmd:
        fail("pg.env exists but PHP was not found, so the PostgreSQL suite cannot run")
    else:
        import estate_pg
        started = estate_pg.start().get("started")   # raises when the drive cluster cannot start
        try:
            env = dict(os.environ, DT_TEST_DRIVER="pgsql", DT_PYTHON=sys.executable)
            env.pop("DB_NAME", None)   # credentials come from pg.env, test database only
            r = run(php_cmd + [os.path.join(ROOT, "tests", "php", "run-tests.php")], env=env)
        finally:
            if started:
                stopped = estate_pg.stop()
                ok("drive cluster started for this check; stop: %s" % stopped.get("reason", stopped))
        m = re.search(r"(\d+) passed, (\d+) failed", r.stdout)
        if r.returncode == 0 and m:
            ok("PostgreSQL suite on the _test database: %s passed (migrations, upsert, timer, loader, pages)" % m.group(1))
        else:
            tail = [l for l in r.stdout.splitlines() if l.startswith("FAIL")]
            fail("PostgreSQL suite failed: %s" % ("; ".join(tail[:5]) or (r.stderr or r.stdout).strip()[-200:]))
except subprocess.TimeoutExpired:
    fail("PostgreSQL suite did not finish in 600 s")
except Exception as e:
    fail("PostgreSQL check failed: %s" % e)

print("\nCHECK FAILED: %d" % failed if failed else "\nCHECK OK")
sys.exit(1 if failed else 0)
