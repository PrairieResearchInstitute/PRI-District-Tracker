"""Owned data must be backed up, and the backups must be tested - an unreadable
backup is not a backup (.claude/skills/pri-database)."""
import unittest, tempfile, shutil, os, json, datetime, subprocess, sys
import _ctx  # noqa: F401
import pri_data as db

SCRIPT = os.path.join(_ctx.ROOT, "scripts", "backup_data.py")


class BackupScript(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.env = dict(os.environ, PRI_BACKUP_DIR=self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _run(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True, env=self.env)

    def test_snapshot_is_written_and_verified(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Verified OK", r.stdout)
        snaps = [n for n in os.listdir(self.dir) if n.endswith(".json")]
        self.assertEqual(len(snaps), 1)

    def test_snapshot_contents_match_the_source(self):
        self._run()
        snap = os.path.join(self.dir, os.listdir(self.dir)[0])
        with open(snap, encoding="utf-8") as f:
            backed = json.load(f)["activities"]
        self.assertEqual(len(backed), len(db.load_db()["activities"]))

    def test_verify_reports_success(self):
        self._run()
        r = self._run("--verify")
        self.assertEqual(r.returncode, 0)
        self.assertIn("restores cleanly", r.stdout)

    def test_verify_fails_with_no_snapshots(self):
        r = self._run("--verify")
        self.assertEqual(r.returncode, 1)

    def test_corrupt_backup_is_caught(self):
        import backup_data
        bad = os.path.join(self.dir, "activities-2026-01-01T0000.json")
        with open(bad, "w", encoding="utf-8") as f:
            json.dump({"activities": []}, f)
        with self.assertRaises(ValueError):
            backup_data.verify(bad)

    def test_record_missing_stamps_is_caught(self):
        import backup_data
        bad = os.path.join(self.dir, "activities-2026-01-02T0000.json")
        with open(bad, "w", encoding="utf-8") as f:
            json.dump({"activities": [{"id": "x", "title": "no stamps"}]}, f)
        with self.assertRaises(ValueError):
            backup_data.verify(bad)


class Retention(unittest.TestCase):
    """Daily snapshots inside the window; one keeper per month beyond it."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        import backup_data
        self.bd = backup_data
        self._dest = backup_data.DEST
        backup_data.DEST = self.dir

    def tearDown(self):
        self.bd.DEST = self._dest
        shutil.rmtree(self.dir, ignore_errors=True)

    def _plant(self, d):
        p = os.path.join(self.dir, "activities-%sT1200.json" % d.isoformat())
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"activities": [{"id": "a", "ingested_at": "2026-01-01"}]}, f)
        return p

    def test_recent_snapshots_are_all_kept(self):
        today = datetime.date.today()
        for i in range(5):
            self._plant(today - datetime.timedelta(days=i))
        self.bd.prune()
        self.assertEqual(len(os.listdir(self.dir)), 5)

    def test_old_month_collapses_to_one_keeper(self):
        old = datetime.date.today() - datetime.timedelta(days=200)
        base = old.replace(day=1)
        for i in range(5):
            self._plant(base + datetime.timedelta(days=i))
        removed = self.bd.prune()
        left = os.listdir(self.dir)
        self.assertEqual(len(left), 1, "expected one monthly keeper, got %s" % left)
        self.assertEqual(len(removed), 4)

    def test_pruning_keeps_recent_and_trims_old_together(self):
        today = datetime.date.today()
        for i in range(3):
            self._plant(today - datetime.timedelta(days=i))
        old = today - datetime.timedelta(days=200)
        for i in range(4):
            self._plant(old.replace(day=1) + datetime.timedelta(days=i))
        self.bd.prune()
        self.assertEqual(len(os.listdir(self.dir)), 4)   # 3 recent + 1 monthly keeper


if __name__ == "__main__":
    unittest.main()
