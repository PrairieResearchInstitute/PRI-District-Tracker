"""The activities columns live in five places, and a column missing from one of them is
silent: the export writes a column the table lacks and the import fails on the host, or
the loader drops a field nobody notices. These checks hold the five together without a
database:

  migrations/*.pgsql.sql     PostgreSQL schema (tools/migrate.php)
  migrations/*.mysql.sql     MySQL schema
  sql/schema.sql             MySQL in one file, for a phpMyAdmin import
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

    def test_mysql_migrations_hold_every_column(self):
        self.assertEqual(sorted(engine_columns("mysql")), sorted(self.canon + ["version"]))

    def test_one_file_mysql_schema_matches_the_migrations(self):
        with open(os.path.join(ROOT, "sql", "schema.sql"), encoding="utf-8") as f:
            self.assertEqual(sorted(create_columns(f.read())), sorted(engine_columns("mysql")))

    def test_the_export_writes_the_same_columns_in_the_same_order(self):
        self.assertEqual([c for c, _k in pri_sql.COLUMNS], self.canon)

    def test_every_field_of_the_live_records_has_a_column(self):
        """A field with no column is dropped on the way to the host. Read-only."""
        with open(os.path.join(ROOT, "data", "activities.json"), encoding="utf-8") as f:
            acts = json.load(f)["activities"]
        fields = {k for a in acts for k in a}
        self.assertEqual(sorted(fields - set(self.canon)), [])

    def test_every_migration_has_its_twin(self):
        names = {}
        for path in glob.glob(os.path.join(MIG, "*.sql")):
            m = re.match(r"^(\d{4}_[a-z0-9_]+?)(?:\.(mysql|pgsql))?\.sql$", os.path.basename(path))
            self.assertIsNotNone(m, "badly named migration %s" % path)
            names.setdefault(m.group(1), set()).add(m.group(2) or "both")
        for name, engines in names.items():
            self.assertTrue(engines in ({"both"}, {"mysql", "pgsql"}), "%s has %s" % (name, sorted(engines)))


class PostgresDialect(unittest.TestCase):
    REC = {"id": "o-brien", "title": "O'Brien \\ a back\\slash", "summary": "line one\nline two",
           "survey": "", "us_house": [13], "featured": True, "confirm": False,
           "ingested_at": "2026-07-01", "show_until": "", "historic": True, "region": "Chicago metro"}

    def setUp(self):
        self.pg = pri_sql.statements([self.REC], "pgsql")[0]
        self.my = pri_sql.statements([self.REC], "mysql")[0]

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

    def test_mysql_output_keeps_its_own_form(self):
        self.assertIn("ON DUPLICATE KEY UPDATE", self.my)
        self.assertIn("`group`", self.my)
        self.assertIn("`lead`", self.my)          # LEAD is reserved from MySQL 8.0.2
        self.assertIn("'O\\'Brien \\\\ a back\\\\slash'", self.my)

    def test_unknown_dialect_is_refused(self):
        with self.assertRaises(ValueError):
            pri_sql.statements([self.REC], "oracle")


if __name__ == "__main__":
    unittest.main()
