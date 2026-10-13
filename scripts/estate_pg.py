"""Start and stop the estate's PostgreSQL on the portable drive (platform D-028).

PostgreSQL, program and data, travels on the drive: the runtime in
<estate>/runtime/postgresql/17, one cluster for every app in
<estate>/data/postgres/17, listening on 127.0.0.1 port 5433. <estate> is the folder
holding the .estate-live marker, found by walking up from this app; no drive letter
is written anywhere. The tracker connects to that cluster directly (no API server).

The shared script <estate>/runtime/postgresql/estate-pg.js owns the cluster. This
helper uses it whenever a node.exe exists, first under <estate>/runtime, then on
the PATH. The tracker itself needs only Python and its portable PHP, so on a
computer with no Node the helper mirrors estate-pg.js with the runtime's own tools:

  start  pg_isready -h 127.0.0.1 -p 5433 -t 3; when nothing answers,
         pg_ctl start -D <data> -l <estate>/data/postgres/log/postgresql.log
                -w -t 60 -o "-p 5433"
  stop   when another client is still connected, leave the cluster running;
         otherwise pg_ctl stop -D <data> -m fast -w -t 60 (a fast, clean shutdown)

estate-pg.js counts other connections as the superuser, whose password only that
script reads. Without Node the count runs as the tracker's own role through
tools/pg-connections.php (credentials from <dataFolder>/pg.env, test database),
and it counts every session it cannot see into as a connection. When the count
cannot run, the cluster is left running: an unstopped cluster is safe, a stop that
cuts off another app is not.

The helper never creates the cluster (`node estate-pg.js init` is the PRI Suite's
job) and never reads a credential file.

    py scripts/estate_pg.py status
    py scripts/estate_pg.py start
    py scripts/estate_pg.py stop
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
PORT = 5433
MARKER = ".estate-live"


def estate_dir(start=ROOT):
    """The folder holding .estate-live above the app, or None off the drive."""
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, MARKER)):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


def paths(estate=None):
    estate = estate or estate_dir()
    if estate is None:
        return None
    home = os.path.join(estate, "data", "postgres")
    pg = os.path.join(estate, "runtime", "postgresql")
    return {
        "estate": estate,
        "script": os.path.join(pg, "estate-pg.js"),
        "bin": os.path.join(pg, "17", "bin"),
        "data": os.path.join(home, "17"),
        "log": os.path.join(home, "log", "postgresql.log"),
    }


def find_node(p):
    """A node.exe under <estate>/runtime (three levels deep at most), else on the PATH."""
    runtime = os.path.join(p["estate"], "runtime")
    base = runtime.count(os.sep)
    for dirpath, dirnames, filenames in os.walk(runtime):
        if dirpath.count(os.sep) - base >= 3:
            dirnames[:] = []
        if os.path.basename(dirpath).lower() == "postgresql":
            dirnames[:] = []           # the PostgreSQL runtime holds no Node
        for n in filenames:
            if n.lower() in ("node.exe", "node"):
                return os.path.join(dirpath, n)
    return shutil.which("node")


def _exe(p, name):
    return os.path.join(p["bin"], name + (".exe" if os.name == "nt" else ""))


def _run(args, timeout=120):
    env = dict(os.environ, PGTZ="UTC")
    try:
        r = subprocess.run(args, capture_output=True, text=True, env=env, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, r.stdout or "", r.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


def initialized(p):
    return os.path.isfile(os.path.join(p["data"], "PG_VERSION"))


def running(p):
    return _run([_exe(p, "pg_isready"), "-h", HOST, "-p", str(PORT), "-t", "3"])[0] == 0


def status():
    p = paths()
    if p is None:
        return {"estate": None, "initialized": False, "running": False, "host": HOST, "port": PORT}
    init = initialized(p)
    node = find_node(p)
    return {"estate": p["estate"], "initialized": init, "running": init and running(p),
            "host": HOST, "port": PORT, "data": p["data"], "bin": p["bin"],
            "via": "estate-pg.js (node)" if node else "pg_ctl (no node found)"}


def _via_node(p, node, *args):
    code, out, err = _run([node, p["script"]] + list(args), timeout=180)
    if code != 0:
        raise RuntimeError((err or out).strip()[-600:] or "estate-pg.js %s exited %d" % (" ".join(args), code))
    line = out.strip().splitlines()[-1] if out.strip() else ""
    try:
        return json.loads(line.split(": ", 1)[1])
    except (IndexError, ValueError):
        return {"output": line}


def start():
    """Start the drive cluster unless it runs. Returns {running, started}."""
    p = paths()
    if p is None:
        raise RuntimeError("No %s marker above %s, so the drive's PostgreSQL cannot be found." % (MARKER, ROOT))
    if not initialized(p):
        raise RuntimeError("The estate PostgreSQL cluster does not exist yet (%s). "
                           "The PRI Suite session creates it with: node estate-pg.js init" % p["data"])
    node = find_node(p)
    if node and os.path.isfile(p["script"]):
        return _via_node(p, node, "start")
    if running(p):
        return {"running": True, "started": False}
    os.makedirs(os.path.dirname(p["log"]), exist_ok=True)
    code, out, err = _run([_exe(p, "pg_ctl"), "start", "-D", p["data"], "-l", p["log"],
                           "-w", "-t", "60", "-o", "-p %d" % PORT])
    if code != 0 or not running(p):
        raise RuntimeError("PostgreSQL on the drive did not start: %s (log: %s)"
                           % ((err or out).strip()[:600], p["log"]))
    return {"running": True, "started": True}


def other_connections():
    """Client sessions other than the counting one, seen as the tracker's own role."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import find_php
    php = find_php.command()
    if not php:
        raise RuntimeError("no PHP to count connections with")
    env = {k: v for k, v in os.environ.items() if k not in ("DB_NAME",)}
    env.update(DB_DRIVER="pgsql", DT_DB_TARGET="test")
    r = subprocess.run(php + [os.path.join(ROOT, "tools", "pg-connections.php")], cwd=ROOT,
                       capture_output=True, text=True, env=env, timeout=60)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out.isdigit():
        raise RuntimeError("could not count connections: %s" % ((r.stderr or out).strip()[:300]))
    return int(out)


def stop(force=False):
    """Stop the drive cluster cleanly unless another client is connected. Returns {stopped, reason}."""
    p = paths()
    if p is None or not initialized(p):
        return {"stopped": False, "reason": "not running"}
    node = find_node(p)
    if node and os.path.isfile(p["script"]):
        return _via_node(p, node, "stop", "--force") if force else _via_node(p, node, "stop")
    if not running(p):
        return {"stopped": False, "reason": "not running"}
    if not force:
        try:
            n = other_connections()
        except Exception as e:
            return {"stopped": False, "reason": "left running, %s" % e}
        if n > 0:
            return {"stopped": False, "reason": "%d other connection(s) still open" % n}
    code, out, err = _run([_exe(p, "pg_ctl"), "stop", "-D", p["data"], "-m", "fast", "-w", "-t", "60"])
    if code != 0:
        raise RuntimeError("pg_ctl stop failed: %s" % (err or out).strip()[:600])
    return {"stopped": True, "reason": "clean shutdown"}


def main(argv):
    cmd = argv[0] if argv else "status"
    try:
        if cmd == "status":
            print(json.dumps(status(), indent=2))
        elif cmd == "start":
            print("start: " + json.dumps(start()))
        elif cmd == "stop":
            print("stop: " + json.dumps(stop(force="--force" in argv)))
        else:
            print("Usage: py scripts/estate_pg.py status | start | stop [--force]")
            return 2
    except Exception as e:
        print("ERROR " + str(e))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
