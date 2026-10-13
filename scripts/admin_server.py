"""PRI District Tracker - local back-office DATA CONSOLE.

This is NOT the public site. It binds to 127.0.0.1 only and is never linked from
index.html. Run it locally to ingest / edit records; every save is date-stamped and
carries a per-record show_until (blank = evergreen). Nothing is ever deleted - "Retire"
just sets show_until into the past so the record drops off the public site but stays in
the database. "Publish" regenerates index.html / handout.html / data.js.

    py scripts/admin_server.py       then open http://127.0.0.1:8770

Pure stdlib.
"""
import json, os, sys, subprocess, csv, io, re, datetime, webbrowser, urllib.parse, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import app_config
import pri_data as db
import studio

PORT = 8770

# Binding to 127.0.0.1 keeps other MACHINES out. It does not keep other WEB PAGES out:
# a page open in the same browser can POST here, and a "simple" request (text/plain)
# is sent cross-site with no CORS preflight to block it. Since this server writes the
# project's own code, that would be a way to take the machine over. So every call must
# carry a token that only our own page can read, and must come from our own origin.
CSRF_TOKEN = secrets.token_urlsafe(32)
ALLOWED_HOSTS = {"127.0.0.1:%d" % PORT, "localhost:%d" % PORT, "[::1]:%d" % PORT}
ALLOWED_ORIGINS = {"http://127.0.0.1:%d" % PORT, "http://localhost:%d" % PORT,
                   "http://[::1]:%d" % PORT}
SCRIPTS = os.path.dirname(os.path.abspath(__file__))

SURVEYS = ["INHS", "ISGS", "ISWS", "ISAS", "ISTC"]
TYPES = ["Program", "Project", "Facility", "Grant", "Publication", "News", "Community science"]
SCOPES = ["statewide", "sited", "regional", "external"]
STATUSES = ["Active", "Ongoing", "Completed", "Planned", "Published", "Pending"]

# Fields copied straight through from the form / CSV (string-valued).
STR_FIELDS = ["survey", "title", "type", "topic", "group", "summary", "description", "lead",
              "program", "funder", "partners", "status", "url", "image", "scope", "location",
              "county", "keywords", "notes", "theme", "start_year", "end_year", "latitude",
              "longitude"]
DISTRICTS = ["us_house", "il_senate", "il_house"]


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "item"


def unique_slug(title, taken):
    base = slug(title)[:40]
    s = base
    i = 2
    while s in taken:
        s = "%s-%d" % (base, i)
        i += 1
    return s


def norm_districts(v):
    """Accept a list, or a string like '13, 14' -> [13, 14] (ints; the front end matches on Number)."""
    if isinstance(v, list):
        items = v
    else:
        items = re.split(r"[,;\s]+", str(v or "").strip())
    out = []
    for x in items:
        x = str(x).strip()
        if x.isdigit():
            out.append(int(x))
    return out


def status_of(rec, today):
    su = str(rec.get("show_until") or "").strip()
    if not su:
        return "evergreen"
    if su < today:
        return "expired"
    soon = (datetime.date.fromisoformat(today) + datetime.timedelta(days=60)).isoformat()
    return "soon" if su <= soon else "fresh"


def build_record(form, existing, taken_ids):
    """Merge a form/CSV payload into a canonical runtime record. Assigns districts from
    lat/long for sited/regional records when none were given explicitly."""
    rec = dict(existing) if existing else {}
    for k in STR_FIELDS:
        if k in form:
            rec[k] = str(form.get(k) or "").strip()
    rec["featured"] = bool(form.get("featured"))
    rec["confirm"] = bool(form.get("confirm"))
    # lifecycle: carry the display-timer inputs through so stamp() can apply them
    if "show_until" in form:
        rec["show_until"] = str(form.get("show_until") or "").strip()
    if "_evergreen" in form:
        rec["_evergreen"] = form.get("_evergreen")

    scope = rec.get("scope", "")
    manual = {c: norm_districts(form.get(c)) for c in DISTRICTS}
    if scope in ("statewide", "external"):
        for c in DISTRICTS:
            manual[c] = []
    elif not any(manual.values()):
        lat, lon = rec.get("latitude", ""), rec.get("longitude", "")
        try:
            if lat != "" and lon != "":
                manual = db.assign_districts(float(lat), float(lon))
        except (ValueError, TypeError):
            pass
    rec.update(manual)

    if not rec.get("id"):
        rec["id"] = unique_slug(rec.get("title", "item"), taken_ids)
    return rec


def stamp(rec, existing, today):
    rec["ingested_at"] = (existing or {}).get("ingested_at") or today
    rec["updated_at"] = today
    ev = str(rec.get("_evergreen") or "").lower() in ("1", "true", "on", "yes")
    rec.pop("_evergreen", None)
    if ev:
        rec["show_until"] = ""
    else:
        # Parsed here, at the single point every save passes through, so a date that
        # cannot be read is refused with a message instead of silently deciding whether
        # the record is visible. Raises db.BadDateError.
        rec["show_until"] = db.normalize_date(rec.get("show_until"))
    return rec


def upsert(form):
    obj = db.load_db()
    acts = obj["activities"]
    today = db.today_iso()
    rid = str(form.get("id") or "").strip()
    idx = next((i for i, a in enumerate(acts) if a.get("id") == rid), -1) if rid else -1
    existing = acts[idx] if idx >= 0 else None
    taken = {a.get("id") for a in acts}
    rec = build_record(form, existing, taken)
    stamp(rec, existing, today)
    if idx >= 0:
        acts[idx] = rec
    else:
        acts.append(rec)
    db.save_db(obj)
    return {"ok": True, "record": rec, "new": idx < 0}


def retire(rid):
    obj = db.load_db()
    today = db.today_iso()
    yest = (datetime.date.fromisoformat(today) - datetime.timedelta(days=1)).isoformat()
    for a in obj["activities"]:
        if a.get("id") == rid:
            a["show_until"] = yest
            a["updated_at"] = today
            db.save_db(obj)
            return {"ok": True, "id": rid, "show_until": yest}
    return {"ok": False, "error": "id not found"}


def import_csv(text):
    obj = db.load_db()
    acts = obj["activities"]
    today = db.today_iso()
    reader = csv.DictReader(io.StringIO(text))
    added = updated = 0
    errors = []
    for n, row in enumerate(reader, start=2):
        clean = {}
        for k, v in row.items():
            if k is None:            # columns beyond the header land under restkey=None
                continue
            if isinstance(v, list):  # ragged row: join the overflow back together
                v = " ".join(x for x in v if x)
            clean[k.strip()] = (v or "").strip()
        row = clean
        if not row.get("title") or (row.get("notes", "").upper().startswith("EXAMPLE")):
            continue
        form = dict(row)
        form["id"] = row.get("activity_id") or row.get("id") or ""
        # Intake-template column names -> the field names the front end actually reads, so
        # nothing a collator fills in is silently dropped (location_text/county -> location,
        # program/topic -> group, which the pop-up shows as "Program area").
        if not form.get("location"):
            form["location"] = row.get("location_text") or row.get("county") or ""
        if not form.get("group"):
            form["group"] = row.get("program") or row.get("topic") or ""
        if not (form.get("show_until") or "").strip():
            form["_evergreen"] = "1" if row.get("type") in db.EVERGREEN_TYPES else ""
            if not form.get("_evergreen"):
                form["show_until"] = db.suggest_show_until(row.get("type"), today)
        form["featured"] = str(row.get("featured", "")).lower() in ("yes", "true", "1")
        form["confirm"] = str(row.get("confirm", "")).lower() in ("yes", "true", "1")
        rid = form["id"].strip()
        idx = next((i for i, a in enumerate(acts) if a.get("id") == rid), -1) if rid else -1
        if idx < 0 and not rid:
            # No activity_id in the sheet (the normal case for staff). Match on the
            # natural key instead, so re-submitting a corrected CSV UPDATES the record
            # rather than creating a near-duplicate beside it.
            t = (row.get("title") or "").strip().lower()
            sv = ((row.get("survey") or "").strip() or "INHS").lower()
            idx = next((i for i, a in enumerate(acts)
                        if (a.get("title") or "").strip().lower() == t
                        and ((a.get("survey") or "INHS").strip() or "INHS").lower() == sv), -1)
        existing = acts[idx] if idx >= 0 else None
        try:
            rec = build_record(form, existing, {a.get("id") for a in acts})
            stamp(rec, existing, today)
            if idx >= 0:
                acts[idx] = rec; updated += 1
            else:
                acts.append(rec); added += 1
        except Exception as e:
            errors.append("row %d: %s" % (n, e))
    db.save_db(obj)
    return {"ok": True, "added": added, "updated": updated, "errors": errors}


def publish():
    env = dict(os.environ, PRI_SKIP_REPS="1")
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "build_site.py")],
                       capture_output=True, text=True, env=env, timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    return {"ok": p.returncode == 0, "log": out.strip().splitlines()[-12:]}


def records_payload():
    obj = db.load_db()
    today = db.today_iso()
    recs = []
    for a in obj["activities"]:
        r = dict(a)
        r["_status"] = status_of(a, today)
        r["_shown"] = db.fresh(a, today)
        recs.append(r)
    recs.sort(key=lambda r: (r.get("updated_at") or "", r.get("survey") or ""), reverse=True)
    counts = {s: 0 for s in ["evergreen", "fresh", "soon", "expired"]}
    for r in recs:
        counts[r["_status"]] += 1
    warnings = []
    for c in db.conflict_copies():
        warnings.append("Sync conflict file found next to the database: %s - two machines "
                        "edited at once. Merge it by hand, then delete it."
                        % os.path.basename(c))
    return {"today": today, "total": len(recs), "shown": sum(1 for r in recs if r["_shown"]),
            "counts": counts, "records": recs, "warnings": warnings}


def export_sql():
    """Wired up in the SQL/PHP scaffold phase."""
    try:
        import pri_sql
        path, rows = pri_sql.write_data_sql()
        return {"ok": True, "path": path, "rows": rows}
    except Exception as e:
        return {"ok": False, "error": "%s (SQL scaffold not present yet)" % e}


# ------------------------------------------------------------------ HTTP layer
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p.startswith("/api/"):
            ok, why = self._authorized()
            if not ok:
                return self._json({"ok": False, "error": why}, 403)
        if p == "/":
            with open(os.path.join(SCRIPTS, "admin_ui.html"), encoding="utf-8") as f:
                page = f.read()
            # Only a same-origin page can read this; another site is blocked from
            # reading our HTML, so it can never learn the token.
            page = page.replace("</head>",
                                '<meta name="pri-csrf" content="%s"></head>' % CSRF_TOKEN, 1)
            return self._html(page)
        if p == "/api/records":
            return self._json(records_payload())
        if p == "/api/meta":
            return self._json({"surveys": SURVEYS, "types": TYPES, "scopes": SCOPES,
                               "statuses": STATUSES})
        if p == "/api/export_sql":
            return self._json(export_sql())
        if p.startswith("/api/studio/"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            rel = (q.get("path") or [""])[0]
            if p == "/api/studio/tree":
                return self._json({"ok": True, "root": studio.ROOT, "files": studio.tree()})
            if p == "/api/studio/file":
                ok, payload = studio.read(rel)
                return self._json({"ok": ok, "path": rel,
                                   "code" if ok else "error": payload,
                                   "backups": studio.backups(rel) if ok else []},
                                  200 if ok else 404)
            if p == "/api/studio/backups":
                return self._json({"ok": True, "backups": studio.backups(rel)})
            if p == "/api/studio/log":
                return self._json({"ok": True, "entries": studio.history()})
        return self._json({"error": "not found"}, 404)

    def _authorized(self):
        """Every /api/ call must prove it came from our own page in this browser.

        Three independent checks: the Host we were asked for (defeats DNS rebinding),
        the Origin if the browser sent one (defeats a plain cross-site POST), and a
        per-run token that only our page can read (defeats everything else, because a
        cross-origin request cannot set a custom header without a preflight we refuse).
        """
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in ALLOWED_HOSTS:
            return False, "Unexpected Host header."
        origin = (self.headers.get("Origin") or "").strip()
        if origin and origin not in ALLOWED_ORIGINS:
            return False, "Cross-site request refused."
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token") or "", CSRF_TOKEN):
            return False, "Missing or stale session token - reload the console."
        return True, ""

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode("utf-8") if n else ""

    def do_POST(self):
        p = self.path.split("?")[0]
        ok, why = self._authorized()
        if not ok:
            self._body()          # drain so the connection stays usable
            return self._json({"ok": False, "error": why}, 403)
        raw = self._body()
        try:
            if p == "/api/upsert":
                return self._json(upsert(json.loads(raw)))
            if p == "/api/retire":
                return self._json(retire(json.loads(raw).get("id", "")))
            if p == "/api/import_csv":
                return self._json(import_csv(raw))
            if p == "/api/build":
                return self._json(publish())
            if p == "/api/studio/save":
                d = json.loads(raw)
                ok, msg = studio.save(d.get("path", ""), d.get("code", ""))
                return self._json({"ok": ok, "message": msg,
                                   "backups": studio.backups(d.get("path", ""))},
                                  200 if ok else 400)
            if p == "/api/studio/restore":
                d = json.loads(raw)
                ok, msg = studio.restore(d.get("path", ""), d.get("name", ""))
                return self._json({"ok": ok, "message": msg,
                                   "backups": studio.backups(d.get("path", ""))},
                                  200 if ok else 400)
        except db.BadDateError as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        except db.ConcurrentEditError as e:
            # 409 Conflict: someone else saved while this page was open.
            return self._json({"ok": False, "conflict": True, "error": str(e),
                               "hint": "Reload the console (F5) and re-apply your change."}, 409)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)
        return self._json({"error": "not found"}, 404)


def main():
    # App standard v2 section B: nothing on C:. Point this process at the drive
    # before anything here writes a temporary file.
    tmp = app_config.use_drive_temp()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d" % PORT
    print("PRI Data Console (back-office, localhost only) ->", url)
    print("Ctrl+C to stop. This is NOT the public site.")
    print("temp files ->", tmp)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
