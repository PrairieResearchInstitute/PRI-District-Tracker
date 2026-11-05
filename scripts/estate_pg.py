"""The estate's PostgreSQL on the portable drive, for the gate and the switch-over.

PostgreSQL, program and data, travels on the drive (platform D-028): the runtime in
<estate>/runtime/postgresql/17, one cluster for every app in
<estate>/data/postgres/17, listening on 127.0.0.1 port 5433. <estate> is the folder
holding the .estate-live marker, found by walking up from this app; no drive letter
is written anywhere. The tracker connects to that cluster directly (no API server).

The estate's own script, <estate>/runtime/postgresql/estate-pg.js, is the only thing
that starts or stops the cluster (owner ruling 2026-11-03). This module calls the
app's one wrapper, tools/estate-pg.ps1, which finds Node and that script, refuses an
administrator window with a plain message, and passes the action on. Nothing here
runs pg_ctl, creates the cluster or reads a credential file.

    py scripts/estate_pg.py status
    py scripts/estate_pg.py start
    py scripts/estate_pg.py stop [--force]
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
PORT = 5433
MARKER = ".estate-live"
WRAPPER = os.path.join(ROOT, "tools", "estate-pg.ps1")


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
    pg = os.path.join(estate, "runtime", "postgresql")
    return {
        "estate": estate,
        "script": os.path.join(pg, "estate-pg.js"),
        "bin": os.path.join(pg, "17", "bin"),
        "data": os.path.join(estate, "data", "postgres", "17"),
    }


def _wrapper(*args, capture=True):
    """Run tools/estate-pg.ps1; returns (exit code, combined output).

    capture=False sends the output to NUL. A start that really starts the server
    must run that way: Windows hands the caller's inheritable handles down through
    powershell, node and cmd to postgres.exe, so a captured pipe stays open for as
    long as PostgreSQL runs and the caller waits until its timeout (measured
    2026-11-03: 180 s, then the gate failed with the cluster running).
    """
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", WRAPPER] + list(args)
    out = {} if capture else {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    try:
        r = subprocess.run(cmd, capture_output=capture, text=True, timeout=180, cwd=ROOT,
                           stdin=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **out)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip() if capture else ""


def _last_json(out, prefix):
    for line in reversed(out.splitlines()):
        if line.startswith(prefix + ": "):
            try:
                return json.loads(line.split(": ", 1)[1])
            except ValueError:
                break
    return {"output": out[-600:]}


def status():
    code, out = _wrapper("status")
    if code == 0 and "{" in out:
        try:
            return json.loads(out[out.index("{"):out.rindex("}") + 1])
        except ValueError:
            pass
    return {"running": False, "host": HOST, "port": PORT, "error": out[-600:]}


def start():
    """Start the drive cluster unless it runs. Returns {running, started}."""
    before = status()
    if before.get("running"):
        return {"running": True, "started": False}
    if "error" in before:                      # no Node, no marker: the wrapper said why
        raise RuntimeError(before["error"])
    code, _ = _wrapper("start", capture=False)  # no pipe for postgres.exe to inherit
    after = status()
    if code != 0 or not after.get("running"):
        raise RuntimeError("the drive cluster did not start (tools/estate-pg.ps1 start exited %d). "
                           "Run it in a normal window to read why: powershell -NoProfile "
                           "-ExecutionPolicy Bypass -File tools/estate-pg.ps1 start" % code)
    return {"running": True, "started": True}


def stop(force=False):
    """Stop the drive cluster cleanly unless another client is connected (estate-pg.js decides)."""
    code, out = _wrapper("stop", "-Force") if force else _wrapper("stop")
    if code != 0:
        raise RuntimeError(out[-600:] or "tools/estate-pg.ps1 stop exited %d" % code)
    return _last_json(out, "stop")


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
