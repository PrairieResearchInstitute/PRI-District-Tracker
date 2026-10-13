"""The database of record is a single JSON file on a synced share, so two people can
hold it open at once. Without this guard the second save silently overwrites the
first person's work. See docs/architecture.md -> Known risks."""
import unittest, tempfile, shutil, os, sys, json, subprocess
import _ctx  # noqa: F401
import pri_data as db


class ConcurrentEdits(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "activities.json")
        shutil.copy(db.DB_PATH, self.db)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _external_write(self, title):
        """Simulate another process/machine writing the file."""
        subprocess.run([sys.executable, "-c",
            "import sys,json;p=sys.argv[1];"
            "o=json.load(open(p,encoding='utf-8'));o['activities'][0]['title']=sys.argv[2];"
            "json.dump(o,open(p,'w',encoding='utf-8'))", self.db, title], check=True)

    def test_second_writer_is_blocked(self):
        obj = db.load_db(self.db)
        self._external_write("B was here")
        obj["activities"][0]["title"] = "A was here"
        with self.assertRaises(db.ConcurrentEditError):
            db.save_db(obj, self.db)

    def test_blocked_save_does_not_destroy_the_other_edit(self):
        obj = db.load_db(self.db)
        self._external_write("B was here")
        obj["activities"][0]["title"] = "A was here"
        try:
            db.save_db(obj, self.db)
        except db.ConcurrentEditError:
            pass
        with open(self.db, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["activities"][0]["title"], "B was here")

    def test_normal_single_writer_flow_is_unaffected(self):
        obj = db.load_db(self.db)
        obj["activities"][0]["title"] = "normal edit"
        db.save_db(obj, self.db)
        with open(self.db, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["activities"][0]["title"], "normal edit")

    def test_check_false_is_a_deliberate_override(self):
        obj = db.load_db(self.db)
        self._external_write("B was here")
        db.save_db(obj, self.db, check=False)      # e.g. a migration
        self.assertTrue(os.path.exists(self.db))

    def test_fingerprint_tracks_content_not_timestamp(self):
        fp1 = db.fingerprint(self.db)
        os.utime(self.db, None)                    # touch: mtime moves, content does not
        self.assertEqual(fp1, db.fingerprint(self.db))
        self._external_write("changed")
        self.assertNotEqual(fp1, db.fingerprint(self.db))

    def test_sync_conflict_copies_are_detected(self):
        self.assertEqual(db.conflict_copies(self.db), [])
        planted = os.path.join(self.dir, "activities-SOMEUSER's conflicted copy.json")
        shutil.copy(self.db, planted)
        found = db.conflict_copies(self.db)
        self.assertEqual(len(found), 1)
        self.assertIn("conflicted copy", found[0])


if __name__ == "__main__":
    unittest.main()
