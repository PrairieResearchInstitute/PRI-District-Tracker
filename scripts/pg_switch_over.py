"""Switch-over to PostgreSQL: build the real database and load it from data/activities.json.

The owner runs this once, from the live app folder, when he moves the tracker onto
PostgreSQL. It runs nothing the test suite has not already run on the _test database:

    py scripts/pg_switch_over.py --status          # look only: migrations pending, rows held
    py scripts/pg_switch_over.py --confirm-live    # migrate, load, verify

Steps, stopping at the first failure:
  0. start the estate PostgreSQL on the portable drive (127.0.0.1 port 5433, platform
     D-028) through scripts/estate_pg.py unless it runs; stop it cleanly at the end
     when this run started it. On a server (DB_NAME set) the drive is not touched.
  1. refuse while the Data Console answers on 127.0.0.1:8770, because a save in the
     middle of the load would leave the database one edit behind the file
  2. tools/migrate.php --live --confirm-live       (schema from migrations/)
  3. tools/load-pg.php --source data/activities.json --live --confirm-live
     (original ids and stamps, then every field of every row and a checksum compared;
     it refuses a table that already holds rows)

Credentials: includes/db.php reads <dataFolder>/pg.env, or DB_* from the environment
on a server. Nothing is printed but names and counts. data/activities.json is opened
read-only and stays the file the Data Console and the build use until the owner
decides otherwise.
"""
import os, socket, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import find_php  # noqa: E402

CONSOLE = ("127.0.0.1", 8770)


def console_running():
    s = socket.socket()
    s.settimeout(0.5)
    try:
        return s.connect_ex(CONSOLE) == 0
    finally:
        s.close()


def run(php, args):
    env = dict(os.environ, DB_DRIVER="pgsql")
    env.pop("DT_DB_TARGET", None)
    r = subprocess.run(php + args, cwd=ROOT, env=env)
    return r.returncode


def main(argv):
    status = "--status" in argv
    if not status and "--confirm-live" not in argv:
        print(__doc__)
        return 2
    php = find_php.command()
    if not php:
        print("PHP not found ($PRI_PHP, tools/php/php.exe, PATH). Nothing was done.")
        return 2
    if os.environ.get("DB_NAME"):
        return switch(php, status)   # a server: DB_* in the environment, no drive cluster
    import estate_pg
    try:
        started = estate_pg.start().get("started")
    except Exception as e:
        print("The estate PostgreSQL on the drive did not start: %s. Nothing was done." % e)
        return 2
    try:
        return switch(php, status)
    finally:
        if started:
            print("Drive cluster stop: %s" % estate_pg.stop().get("reason"))


def switch(php, status):
    migrate = [os.path.join(ROOT, "tools", "migrate.php")]
    if status:
        return run(php, migrate + ["--status"])
    if console_running():
        print("The Data Console is running on 127.0.0.1:8770. Close it, then run this again. Nothing was done.")
        return 2
    code = run(php, migrate + ["--live", "--confirm-live"])
    if code != 0:
        print("Migrations failed (exit %d); the load was not started." % code)
        return code
    source = os.path.join(ROOT, "data", "activities.json")
    code = run(php, [os.path.join(ROOT, "tools", "load-pg.php"), "--source", source, "--live", "--confirm-live"])
    print("Switch-over %s." % ("complete: the PostgreSQL copy is VERIFIED" if code == 0 else "FAILED (exit %d)" % code))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
