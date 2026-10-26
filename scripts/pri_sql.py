"""Export the local database of record (data/activities.json) to an SQL import file
whose columns line up 1:1 with the hosted schema (migrations/). Idempotent on the
host: re-importing refreshes rather than duplicates.

One dialect, PostgreSQL. The owner retired MySQL on 2026-10-20 (Q-11): the app has
run on PostgreSQL since D-016 and nothing is to be kept selectable.

    py scripts/pri_sql.py    -> sql/data.sql   PostgreSQL
    --source <file>  read another copy of activities.json;  --out <file>  write elsewhere

INSERT ... ON CONFLICT (id) DO UPDATE SET c = EXCLUDED.c. "group" is quoted because
it is reserved; quotes are doubled and backslashes stay literal; booleans are
TRUE/FALSE. A blank show_until is NULL, which is what evergreen means.

The canonical record keys are identical across JSON, the local admin and SQL, so
nothing has to be renamed as data moves from the local tool to the hosted database.
The verified way to fill PostgreSQL is tools/load-pg.php, which compares every row
after loading; the file here is the same data for psql, and the PHP test suite
checks that the two paths produce identical rows. Pure stdlib.
"""
import json, os, sys
import pri_data as db

SQL_DIR = os.path.join(db.PROJ, "sql")
RESERVED = {"group"}        # reserved in PostgreSQL, so it is quoted

# (json_key == sql column, kind).  kind: str | text | bool | num | date | dt | json
COLUMNS = [
    ("id", "str"), ("survey", "str"), ("title", "str"),
    ("type", "str"), ("topic", "str"), ("group", "str"),
    ("summary", "text"), ("description", "text"),
    ("lead", "str"), ("program", "str"), ("funder", "str"),
    ("partners", "str"), ("status", "str"),
    ("start_year", "str"), ("end_year", "str"),
    ("url", "str"), ("image", "str"), ("scope", "str"),
    ("latitude", "num"), ("longitude", "num"),
    ("county", "str"), ("location", "str"),
    ("us_house", "json"), ("il_senate", "json"),
    ("il_house", "json"), ("featured", "bool"),
    ("confirm", "bool"), ("keywords", "str"),
    ("notes", "text"), ("theme", "str"),
    ("ingested_at", "dt"), ("updated_at", "dt"),
    ("show_until", "date"),
    ("region", "str"), ("historic", "bool"),
]

def _ident(col):
    return '"%s"' % col if col in RESERVED else col


def _q(s):
    return "'" + str(s).replace("'", "''") + "'"


def _cell(rec, key, kind):
    v = rec.get(key, None)
    if kind in ("str", "text"):
        return _q(v or "")
    if kind == "bool":
        return "TRUE" if v else "FALSE"
    if kind == "num":
        s = str(v).strip() if v not in (None, "") else ""
        return s if s else "NULL"
    if kind == "date":
        s = str(v or "").strip()
        return _q(s) if s else "NULL"   # blank show_until = evergreen = NULL (never expires)
    if kind == "dt":
        s = str(v or "").strip()
        if not s:
            return "NULL"
        return _q(s + " 00:00:00" if len(s) == 10 else s)
    if kind == "json":
        return _q(json.dumps(v if isinstance(v, list) else []))
    return "NULL"


def statements(acts):
    """One upsert per record."""
    cols = [_ident(c) for c, _k in COLUMNS]
    sets = ["%s=EXCLUDED.%s" % (c, c) for c in cols if c != "id"] + ["version=activities.version+1"]
    tail = "ON CONFLICT (id) DO UPDATE SET " + ", ".join(sets)
    out = []
    for a in acts:
        if not (a.get("survey") or "").strip():
            a = {**a, "survey": "INHS"}   # match the front end's surveyOf default; keep the DB clean
        vals = ", ".join(_cell(a, k, kind) for (k, kind) in COLUMNS)
        out.append("INSERT INTO activities (%s) VALUES (%s)" % (", ".join(cols), vals)
                   + chr(10) + "  " + tail + ";")
    return out


def write_data_sql(path=None, source=None):
    """Write the import file; `source` is another copy of activities.json (read-only)."""
    if path is None:
        os.makedirs(SQL_DIR, exist_ok=True)
        path = os.path.join(SQL_DIR, "data.sql")
    acts = db.load_db(source)["activities"]
    lines = ["-- Generated from data/activities.json by scripts/pri_sql.py (PostgreSQL)",
             "-- Import AFTER the schema (migrations/).  Re-running refreshes existing rows (upsert).",
             "SET client_encoding = 'UTF8';", ""]
    lines += statements(acts)
    with open(path, "w", encoding="utf-8") as f:
        f.write(chr(10).join(lines) + chr(10))
    return path, len(acts)


def _arg(name, default=None):
    if name not in sys.argv:
        return default
    i = sys.argv.index(name)
    return sys.argv[i + 1] if i + 1 < len(sys.argv) else ""


if __name__ == "__main__":
    p, n = write_data_sql(path=_arg("--out"), source=_arg("--source"))
    print("Wrote %s (%d activities)" % (p, n))
