"""API keys: one separate, git-ignored database, and no key anywhere else.

App standard v2 section A. The tracker needs no key today, so these tests exist to
keep the place closed: a key must never land in data/activities.json (the main
database, tracked in git and bound for PostgreSQL), never in a tracked file, and
never in a printed line. Every key here is fake and lives in a temp folder.
"""
import unittest, os, tempfile, shutil, subprocess, sys, json
import _ctx  # noqa: F401
import app_config
import keys

FAKE = "fake-value-zzz-not-a-real-key-0123456789"


class Location(unittest.TestCase):
    def test_the_database_sits_in_the_drive_data_folder(self):
        folder = app_config.data_folder()
        if folder is None:
            self.skipTest("no dataFolder configured on this machine")
        env = os.environ.pop("PRI_KEYS_DB", None)
        try:
            p = app_config.keys_db()
        finally:
            if env is not None:
                os.environ["PRI_KEYS_DB"] = env
        self.assertEqual(os.path.dirname(os.path.normcase(p)), os.path.normcase(folder))
        self.assertFalse(os.path.normcase(p).startswith(os.path.normcase(app_config.ROOT) + os.sep),
                         "the keys database must not sit inside the repository")

    def test_the_environment_override_wins(self):
        os.environ["PRI_KEYS_DB"] = os.path.join(tempfile.gettempdir(), "override.db")
        try:
            self.assertTrue(app_config.keys_db().endswith("override.db"))
        finally:
            os.environ.pop("PRI_KEYS_DB", None)

    def test_the_main_database_holds_no_key(self):
        """A key inside activities.json would travel with every export and the port."""
        with open(os.path.join(_ctx.ROOT, "data", "activities.json"), encoding="utf-8") as f:
            db = json.load(f)
        blob = json.dumps(db).lower()
        for word in ("api_key", "apikey", "api-key", "secret", "token", "bearer"):
            self.assertNotIn(word, blob, "data/activities.json looks like it carries a credential")
        self.assertNotIn("keys", db, "the main database must not carry a keys table")


class Storage(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pri-keys-test-")
        os.environ["PRI_KEYS_DB"] = os.path.join(self.dir, "keys.db")

    def tearDown(self):
        os.environ.pop("PRI_KEYS_DB", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_read_does_not_create_the_database(self):
        self.assertIsNone(keys.get("OPEN_STATES"))
        self.assertFalse(os.path.exists(keys.path()), "a read created the keys database")

    def test_a_fake_key_round_trips(self):
        keys.put("OPEN_STATES", FAKE)
        self.assertEqual(keys.get("OPEN_STATES"), FAKE)

    def test_storing_again_replaces_rather_than_duplicates(self):
        keys.put("OPEN_STATES", FAKE)
        keys.put("OPEN_STATES", FAKE + "-2")
        self.assertEqual(keys.get("OPEN_STATES"), FAKE + "-2")
        self.assertEqual(len(keys.names()), 1)

    def test_an_empty_value_is_refused(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError):
                keys.put("OPEN_STATES", bad)

    def test_names_reports_names_and_dates_only(self):
        keys.put("OPEN_STATES", FAKE)
        rows = keys.names()
        self.assertEqual([r["name"] for r in rows], ["OPEN_STATES"])
        self.assertNotIn(FAKE, json.dumps(rows), "names() leaked a value")

    def test_delete_removes_one(self):
        keys.put("OPEN_STATES", FAKE)
        self.assertTrue(keys.delete("OPEN_STATES"))
        self.assertIsNone(keys.get("OPEN_STATES"))


class LegacyImport(unittest.TestCase):
    """Section A3: keys still load. An old plain-text store fills missing names once
    and stays in place until the owner confirms every key works."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pri-keys-old-")
        os.environ["PRI_KEYS_DB"] = os.path.join(self.dir, "keys.db")
        self.old = os.path.join(self.dir, keys.LEGACY_NAMES[0])
        with open(self.old, "w", encoding="utf-8") as f:
            f.write("# an old store\nOPEN_STATES=%s\nGEOCODER = \"%s-geo\"\n" % (FAKE, FAKE))
        self._real = app_config.data_folder
        app_config.data_folder = lambda: self.dir

    def tearDown(self):
        app_config.data_folder = self._real
        os.environ.pop("PRI_KEYS_DB", None)
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_missing_names_are_filled_and_the_file_stays(self):
        added = keys.import_legacy()
        self.assertEqual(sorted(added), ["GEOCODER", "OPEN_STATES"])
        self.assertEqual(keys.get("OPEN_STATES"), FAKE)
        self.assertEqual(keys.get("GEOCODER"), FAKE + "-geo")
        self.assertTrue(os.path.isfile(self.old), "the old store was moved or deleted")

    def test_a_name_already_held_is_not_overwritten(self):
        keys.put("OPEN_STATES", "kept")
        added = keys.import_legacy()
        self.assertEqual(added, ["GEOCODER"])
        self.assertEqual(keys.get("OPEN_STATES"), "kept")

    def test_running_it_twice_changes_nothing(self):
        keys.import_legacy()
        self.assertEqual(keys.import_legacy(), [])


class NeverCommitted(unittest.TestCase):
    def _ignored(self, name):
        r = subprocess.run(["git", "-c", "safe.directory=*", "check-ignore", "-q", name],
                           cwd=_ctx.ROOT, capture_output=True, text=True)
        return r.returncode == 0

    def test_the_keys_database_is_git_ignored(self):
        self.assertTrue(self._ignored("keys.db"), "keys.db is not git-ignored")

    def test_an_old_plain_text_store_is_git_ignored(self):
        for name in keys.LEGACY_NAMES:
            self.assertTrue(self._ignored(name), "%s is not git-ignored" % name)

    def test_no_key_store_is_tracked(self):
        r = subprocess.run(["git", "-c", "safe.directory=*", "ls-files"],
                           cwd=_ctx.ROOT, capture_output=True, text=True)
        tracked = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        for p in tracked:
            base = os.path.basename(p).lower()
            self.assertNotEqual(base, "keys.db", "a keys database is tracked: %s" % p)
            self.assertNotIn(base, [n.lower() for n in keys.LEGACY_NAMES],
                             "an old key store is tracked: %s" % p)


class TheCommandLineNeverPrintsAValue(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pri-keys-cli-")
        self.env = dict(os.environ, PRI_KEYS_DB=os.path.join(self.dir, "keys.db"))
        import keys as k
        os.environ["PRI_KEYS_DB"] = self.env["PRI_KEYS_DB"]
        k.put("OPEN_STATES", FAKE)
        os.environ.pop("PRI_KEYS_DB", None)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_list_shows_the_name_and_hides_the_value(self):
        r = subprocess.run([sys.executable, os.path.join(_ctx.SCRIPTS, "keys.py"), "--list"],
                           cwd=_ctx.ROOT, capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OPEN_STATES", r.stdout)
        self.assertNotIn(FAKE, r.stdout + r.stderr, "the command line printed a key value")


if __name__ == "__main__":
    unittest.main()
