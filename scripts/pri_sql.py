"""Export the local database of record (data/activities.json) to an SQL import file
whose columns line up 1:1 with the hosted schema (migrations/, sql/schema.sql).
Idempotent on the host: re-importing refreshes rather than duplicates.

Two dialects, because the hosted layer runs on either engine (includes/db.php DB_DRIVER):

    py scripts/pri_sql.py                    -> sql/data.sql        MySQL, the default
    py scripts/pri_sql.py --dialect pgsql    -> sql/data.pgsql.sql  PostgreSQL
    --source <file>  read another copy of activities.json;  --out <file>  write elsewhere

  MySQL       INSERT ... ON DUPLICATE KEY UPDATE c=VALUES(c); `group` and `lead`
              back-quoted (LEAD is reserved from MySQL 8.0.2); backslash escapes
  PostgreSQL  INSERT ... ON CONFLICT (id) DO UPDATE SET c=EXCLUDED.c; "group"
              double-quoted; quotes doubled, backslashes literal; TRUE/FALSE

The canonical record keys are identical across JSON, the local admin and SQL, so
nothing has to be renamed as data moves from the local tool to the hosted database.
The verified way to fill PostgreSQL is tools/load-pg.php, which compares every row
after loading; the PostgreSQL file here is the same data for psql, and the PHP test
suite checks that the two paths produce identical rows. Pure stdlib.
"""
import json, os, sys
import pri_data as db

SQL_DIR = os.path.join(db.PROJ, "sql")
DIALECTS = ("mysql", "pgsql")
RESERVED = {"mysql": {"group", "lead"}, "pgsql": {"group"}}

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


def _ident(col, dialect):
    if col not in RESERVED[dialect]:
        return col
    return "`%s`" % col if dialect == "mysql" else '"%s"' % col


def _q(s, dialect="mysql"):
    s = str(s)
    if dialect == "pgsql":
        return "'" + s.replace("'", "''") + "'"
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _cell(rec, key, kind, dialect="mysql"):
    v = rec.get(key, None)
    if kind in ("str", "text"):
        return _q(v or "", dialect)
    if kind == "bool":
        if dialect == "pgsql":
            return "TRUE" if v else "FALSE"
        return "1" if v else "0"
    if kind == "num":
        s = str(v).strip() if v not in (None, "") else ""
        return s if s else "NULL"
    if kind == "date":
        s = str(v or "").strip()
        return _q(s, dialect) if s else "NULL"   # blank show_until = evergreen = NULL (never expires)
    if kind == "dt":
        s = str(v or "").strip()
        if not s:
            return "NULL"
        return _q(s + " 00:00:00" if len(s) == 10 else s, dialect)
    if kind == "json":
        return _q(json.dumps(v if isinstance(v, list) else []), dialect)
    return "NULL"


def statements(acts, dialect="mysql"):
    """One upsert per record, in the given dialect."""
    if dialect not in DIALECTS:
        raise ValueError("dialect must be one of %s" % ", ".join(DIALECTS))
    cols = [_ident(c, dialect) for c, _k in COLUMNS]
    if dialect == "pgsql":
        sets = ["%s=EXCLUDED.%s" % (c, c) for c in cols if c != "id"] + ["version=activities.version+1"]
        tail = "ON CONFLICT (id) DO UPDATE SET " + ", ".join(sets)
    else:
        sets = ["%s=VALUES(%s)" % (c, c) for c in cols if c != "id"] + ["version=version+1"]
        tail = "ON DUPLICATE KEY UPDATE " + ", ".join(sets)
    out = []
    for a in acts:
        if not (a.get("survey") or "").strip():
            a = {**a, "survey": "INHS"}   # match the front end's surveyOf default; keep the DB clean
        vals = ", ".join(_cell(a, k, kind, dialect) for (k, kind) in COLUMNS)
        out.append("INSERT INTO activities (%s) VALUES (%s)\n  %s;" % (", ".join(cols), vals, tail))
    return out


def write_data_sql(path=None, dialect="mysql", source=None):
    """Write the import file; `source` is another copy of activities.json (read-only)."""
    name = "data.sql" if dialect == "mysql" else "data.%s.sql" % dialect
    if path is None:
        os.makedirs(SQL_DIR, exist_ok=True)
        path = os.path.join(SQL_DIR, name)
    acts = db.load_db(source)["activities"]
    lines = ["-- Generated from data/activities.json by scripts/pri_sql.py (%s)" % dialect,
             "-- Import AFTER the schema (migrations/).  Re-running refreshes existing rows (upsert)."]
    lines += ["SET NAMES utf8mb4;", ""] if dialect == "mysql" else ["SET client_encoding = 'UTF8';", ""]
    lines += statements(acts, dialect)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path, len(acts)


def _arg(name, default=None):
    if name not in sys.argv:
        return default
    i = sys.argv.index(name)
    return sys.argv[i + 1] if i + 1 < len(sys.argv) else ""


if __name__ == "__main__":
    dialect = _arg("--dialect", "mysql")
    if dialect not in DIALECTS:
        print("Usage: py scripts/pri_sql.py [--dialect mysql|pgsql] [--source <activities.json>] [--out <file.sql>]")
        sys.exit(2)
    p, n = write_data_sql(path=_arg("--out"), dialect=dialect, source=_arg("--source"))
    print("Wrote %s (%d activities)" % (p, n))
