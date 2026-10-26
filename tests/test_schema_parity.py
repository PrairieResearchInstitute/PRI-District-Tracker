"""The activities columns live in five places, and a column missing from one of them is
silent: the export writes a column the table lacks and the import fails on the host, or
the loader drops a field nobody notices. These checks hold the five together without a
database:

  migrations/*.pgsql.sql     PostgreSQL schema (tools/migrate.php)
  includes/activities.php    activity_columns(), what the PHP layer writes
  scripts/pri_sql.py         COLUMNS, what the export writes

and check the PostgreSQL export's dialect. The PHP suite (tests/php/run-tests.php with
DT_TEST_DRIVER=pgsql) runs the same schema and export on a real PostgreSQL server.
"""
import glob, json, os, re, unittest
import _ctx  # noqa: F401
import pri_sql

ROOT = _ctx.ROOT
MIG = os.path.join(ROOT, "migrations")
TABLE_COLS = re.compile(r"CREATE TABLE(?: IF NOT EXISTS)? activities \((.*?)\n\)", re.S)
ADD_COL = re.compile(r"ALTER TABLE activities ADD COLUMN [`\"]?(\w+)", re.I)


def _strip(sql):
    return re.sub(r"--[^\n]*", "", sql)


def create_columns(sql):
    m = TABLE_COLS.search(_strip(sql))
    if not m:
        return []
    cols = []
    for line in m.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line or re.match(r"(KEY|PRIMARY|UNIQUE|INDEX|CONSTRAINT)\b", line, re.I):
            continue
        cols.append(line.split()[0].strip('`"'))
    return cols


def engine_columns(engine):
    cols = []
    for path in sorted(glob.glob(os.path.join(MIG, "[0-9][0-9][0-9][0-9]_*.%s.sql" % engine))):
        with open(path, encoding="utf-8") as f:
            sql = _strip(f.read())
        cols += create_columns(sql) + ADD_COL.findall(sql)
    return cols


def php_columns():
    with open(os.path.join(ROOT, "includes", "activities.php"), encoding="utf-8") as f:
        src = f.read()
    m = re.search(r"function activity_columns\(\): array \{\s*return \[(.*?)\];", src, re.S)
    return re.findall(r"'(\w+)'", m.group(1)) if m else []


class FiveListsAgree(unittest.TestCase):
    def setUp(self):
        self.canon = php_columns()
        self.assertTrue(self.canon, "activity_columns() not found in includes/activities.php")

    def test_pgsql_migrations_hold_every_column(self):
        self.assertEqual(sorted(engine_columns("pgsql")), sorted(self.canon + ["version"]))

    def test_the_export_writes_the_same_columns_in_the_same_order(self):
        self.assertEqual([c for c, _k in pri_sql.COLUMNS], self.canon)

    def test_every_field_of_the_live_records_has_a_column(self):
        """A field with no column is dropped on the way to the host. Read-only."""
        with open(os.path.join(ROOT, "data", "activities.json"), encoding="utf-8") as f:
            acts = json.load(f)["activities"]
        fields = {k for a in acts for k in a}
        self.assertEqual(sorted(fields - set(self.canon)), [])

    def test_no_migration_carries_a_mysql_twin(self):
        """Q-11, 2026-10-20: one engine. A .mysql.sql twin is a file nothing applies."""
        for path in glob.glob(os.path.join(MIG, "*.sql")):
            base = os.path.basename(path)
            m = re.match(r"^(\d{4}_[a-z0-9_]+?)(?:\.(pgsql))?\.sql$", base)
            self.assertIsNotNone(m, "badly named or non-PostgreSQL migration %s" % base)


class PostgresDialect(unittest.TestCase):
    REC = {"id": "o-brien", "title": "O'Brien \\ a back\\slash", "summary": "line one\nline two",
           "survey": "", "us_house": [13], "featured": True, "confirm": False,
           "ingested_at": "2026-07-01", "show_until": "", "historic": True, "region": "Chicago metro"}

    def setUp(self):
        self.pg = pri_sql.statements([self.REC])[0]

    def test_upsert_is_on_conflict(self):
        self.assertIn("ON CONFLICT (id) DO UPDATE SET", self.pg)
        self.assertIn("title=EXCLUDED.title", self.pg)
        self.assertNotIn("ON DUPLICATE KEY", self.pg)

    def test_group_is_double_quoted_and_nothing_back_quoted(self):
        self.assertIn('"group"', self.pg)
        self.assertNotIn("`", self.pg)

    def test_quotes_double_and_backslashes_stay_literal(self):
        self.assertIn("'O''Brien \\ a back\\slash'", self.pg)
        self.assertIn("'line one\nline two'", self.pg)

    def test_booleans_are_true_false(self):
        self.assertIn("TRUE, FALSE", self.pg)      # featured, confirm
        self.assertNotIn(", 1, 0,", self.pg)

    def test_blank_timer_is_null_and_stamp_is_midnight(self):
        self.assertIn("'2026-07-01 00:00:00'", self.pg)
        self.assertRegex(self.pg, r"'2026-07-01 00:00:00', NULL, NULL, 'Chicago metro', TRUE\)")

    def test_the_export_carries_no_mysql_form(self):
        """Q-11, 2026-10-20: one engine, so no back-quotes and no VALUES() upsert."""
        self.assertNotIn("`", self.pg)
        self.assertNotIn("ON DUPLICATE KEY", self.pg)
        self.assertNotIn("utf8mb4", self.pg)


if __name__ == "__main__":
    unittest.main()
