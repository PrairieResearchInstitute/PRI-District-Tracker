"""Shared data layer for the PRI District Tracker.

One source of truth for:
  * where the local "database of record" lives (data/activities.json),
  * loading / saving it (preserving the one-record-per-line style so it stays diff-able),
  * the freshness rule (a record shows only while its show_until is blank or still in the future),
  * point-in-polygon district assignment from a lat/long,
  * the ingest upsert that date-stamps every record.

The front-end build (build_site.py), the migration, the local admin server, and the SQL
export all import from here so the rules never drift apart. Pure stdlib.
"""
import json, os, datetime, hashlib

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJ, "data")
DB_PATH = os.path.join(DATA, "activities.json")

# Runtime record fields the front end actually reads, plus the lifecycle stamps.
DATE_FIELDS = ["ingested_at", "updated_at", "show_until"]

# Types that, by convention, get a blank (evergreen) show_until suggested in the admin.
# The user chose per-record control, so this only seeds the default; it is always editable.
EVERGREEN_TYPES = {"Program", "Facility"}
DEFAULT_WINDOW_DAYS = 548  # ~18 months, suggested for dated items (News/Publication/Project/Grant)


def today_iso():
    return datetime.date.today().isoformat()


class BadDateError(ValueError):
    """A display-timer date that could not be understood."""


def normalize_date(value):
    """Return an ISO (YYYY-MM-DD) date, or raise BadDateError naming what was wrong.

    Dates arrive from a date picker (always ISO) but also from staff spreadsheets,
    where "12/31/2099" is natural to type. Storing that unchecked used to be silently
    destructive: the old comparison was done on the raw STRINGS, so "12/31/2099" sorted
    before today and hid the record for ever, while "soon" sorted after it and showed
    for ever. Neither raised anything. So parse here, at the boundary, and refuse what
    cannot be read.
    """
    v = str(value or "").strip()
    if not v:
        return ""                      # blank is legitimate: evergreen
    try:                               # the canonical form
        return datetime.date.fromisoformat(v).isoformat()
    except ValueError:
        pass
    for fmt, shape in (("%Y/%m/%d", "YYYY/MM/DD"), ("%m/%d/%Y", "MM/DD/YYYY"),
                       ("%m-%d-%Y", "MM-DD-YYYY")):
        try:
            return datetime.datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            continue
    raise BadDateError(
        "%r is not a date I can read. Use YYYY-MM-DD (for example %s), or leave it "
        "blank to show until the record is retired." % (v, today_iso()))


def fresh(rec, today=None):
    """A record is shown iff show_until is blank (evergreen) or on/after today.

    Compares real dates, not strings. A value that cannot be parsed is treated as
    evergreen: ingest refuses bad dates, so if one is somehow present, showing real
    work is the safer failure than hiding it with no trace.
    """
    today = today or today_iso()
    su = str(rec.get("show_until") or "").strip()
    if not su:
        return True
    try:
        return datetime.date.fromisoformat(su) >= datetime.date.fromisoformat(today)
    except ValueError:
        return True


class ConcurrentEditError(RuntimeError):
    """The database changed on disk between load_db() and save_db().

    The database of record is a single JSON file, and on a synced share (OneDrive)
    two people can hold it open at once. Without this check the second save would
    silently overwrite the first person's work. See docs/architecture.md.
    """


# path -> content fingerprint observed at the last load_db(), so save_db() can tell
# whether anyone else wrote the file in the meantime.
_SEEN = {}


def fingerprint(path=None):
    """Cheap identity of the file's current contents: "size:sha1-16".

    Content-based rather than mtime-based, because sync clients touch timestamps
    without changing anything. Returns None when the file does not exist yet.
    """
    path = path or DB_PATH
    try:
        st = os.stat(path)
    except OSError:
        return None
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "%d:%s" % (st.st_size, h.hexdigest()[:16])


def conflict_copies(path=None):
    """Sync-client conflict files sitting beside the database (e.g. OneDrive's
    "... conflicted copy ..."). Their presence means two machines both wrote."""
    path = path or DB_PATH
    folder = os.path.dirname(path) or "."
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for n in names:
        low = n.lower()
        if low == os.path.basename(path).lower() or not low.startswith(stem):
            continue
        if "conflict" in low or "copy" in low:
            found.append(os.path.join(folder, n))
    return found


def load_db(path=None):
    path = path or DB_PATH
    with open(path, encoding="utf-8") as f:
        obj = json.load(f)
    _SEEN[os.path.abspath(path)] = fingerprint(path)
    return obj


def save_db(obj, path=None, check=True):
    """Write the DB back with meta keys first and one activity per line, so the file
    stays human-readable and reviewable instead of a single giant line.

    Refuses to write if the file changed since this process loaded it (pass
    check=False only for deliberate whole-file rewrites such as a migration).
    """
    path = path or DB_PATH
    key = os.path.abspath(path)
    if check and key in _SEEN:
        current = fingerprint(path)
        if current is not None and current != _SEEN[key]:
            raise ConcurrentEditError(
                "%s changed on disk since it was loaded - someone else (or another "
                "sync'd machine) saved in the meantime. Reload before saving so their "
                "work is not overwritten." % os.path.basename(path))
    acts = obj.get("activities", [])
    meta_keys = [k for k in obj if k != "activities"]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("{\n")
        for k in meta_keys:
            f.write("  " + json.dumps(k) + ": " + json.dumps(obj[k], ensure_ascii=False) + ",\n")
        f.write('  "activities": [\n')
        for i, a in enumerate(acts):
            comma = "," if i < len(acts) - 1 else ""
            f.write("    " + json.dumps(a, ensure_ascii=False, sort_keys=False) + comma + "\n")
        f.write("  ]\n}\n")
    os.replace(tmp, path)
    _SEEN[key] = fingerprint(path)


def suggest_show_until(rec_type, ingested=None):
    """Suggested default only. Programs/Facilities -> blank (evergreen); everything else
    -> ingest date + DEFAULT_WINDOW_DAYS. The admin can always override or clear it."""
    if rec_type in EVERGREEN_TYPES:
        return ""
    base = datetime.date.fromisoformat(ingested or today_iso())
    return (base + datetime.timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()


# ---------------------------------------------------------------- geometry (PIP)
def _rings(geom):
    """Flatten a GeoJSON Polygon / MultiPolygon into a list of coordinate rings."""
    out = []
    t = geom.get("type")
    if t == "Polygon":
        out.extend(geom["coordinates"])
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            out.extend(poly)
    return out


def _point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


_GEO_CACHE = {}


def _load_geo(path):
    if path not in _GEO_CACHE:
        with open(path, encoding="utf-8") as f:
            _GEO_CACHE[path] = json.load(f)
    return _GEO_CACHE[path]


CHAMBER_FILES = {
    "us_house": "il_congress_current.geojson",
    "il_senate": "il_senate.geojson",
    "il_house": "il_house.geojson",
}


def district_for(lat, lon, chamber):
    """Return the district number (as a string) containing (lat,lon) for a chamber, or None.
    Ray-casting even-odd rule; first ring is the outer boundary of each feature."""
    path = os.path.join(DATA, CHAMBER_FILES[chamber])
    if not os.path.exists(path):
        return None
    gj = _load_geo(path)
    for ft in gj["features"]:
        bn = str(ft["properties"].get("BASENAME", "")).strip()
        if not bn.isdigit():
            continue
        rings = _rings(ft["geometry"])
        if rings and _point_in_ring(lon, lat, rings[0]):
            return int(bn)  # front end matches on Number(district)
    return None


def assign_districts(lat, lon):
    """All three chambers for a point. Returns dict of chamber -> [district] (or [])."""
    out = {}
    for ch in CHAMBER_FILES:
        d = district_for(lat, lon, ch)
        out[ch] = [d] if d else []
    return out
