"""The Studio edits the application's own code, so its guard rails are the point.

Borrowed from PRI Facilities Request: confined, checked, reversible, recorded.
Each of those four is tested here, because a failure in any one of them turns a
convenience into a way to break the site with no way back.
"""
import unittest, os, glob
import _ctx  # noqa: F401
import studio

PROBE = "docs/_studio_test_probe_%s.md" % _ctx.TAG
PROBE_PY = "docs/_studio_test_probe_%s.py" % _ctx.TAG


class Confined(unittest.TestCase):
    def test_path_traversal_is_refused(self):
        for bad in ["../../../Windows/System32/drivers/etc/hosts",
                    "..\\..\\secrets.txt",
                    "scripts/../../outside.py",
                    "/etc/passwd"]:
            self.assertIsNone(studio.resolve(bad), "escaped the project: %s" % bad)

    def test_null_byte_is_refused(self):
        self.assertIsNone(studio.resolve("scripts/pri_data.py\0.txt"))

    def test_empty_path_is_refused(self):
        self.assertIsNone(studio.resolve(""))

    def test_only_allowlisted_extensions_open(self):
        self.assertIsNone(studio.resolve("data/il_house.geojson"))
        self.assertIsNotNone(studio.resolve("scripts/pri_data.py"))

    def test_build_outputs_are_not_editable(self):
        """They are overwritten by the next build, so editing them is a trap."""
        for gen in ["index.html", "data.js", "sql/data.sql", "sql/data.pgsql.sql", "includes/core.php"]:
            self.assertIsNone(studio.resolve(gen), "%s should not be editable" % gen)

    def test_migrations_and_portable_php_are_not_editable(self):
        """An applied migration must never change, and tools/php is a binary copy."""
        self.assertIsNone(studio.resolve("migrations/0001_baseline.pgsql.sql"))
        self.assertIsNone(studio.resolve("tools/php/php.ini"))
        self.assertIsNotNone(studio.resolve("includes/db.php"))

    def test_tree_hides_generated_and_vendor(self):
        paths = {f["path"] for f in studio.tree()}
        for hidden in ["index.html", "data.js", "data/geo.json"]:
            self.assertNotIn(hidden, paths)
        self.assertFalse([p for p in paths if p.startswith("assets/vendor/")])
        self.assertIn("scripts/build_site.py", paths)


class Checked(unittest.TestCase):
    def test_broken_python_is_refused(self):
        ok, msg = studio.check("x.py", "def broken(:\n  pass")
        self.assertFalse(ok)
        self.assertIn("syntax error", msg.lower())

    def test_valid_python_passes(self):
        ok, _ = studio.check("x.py", "def fine():\n    return 1\n")
        self.assertTrue(ok)

    def test_broken_json_is_refused(self):
        ok, _ = studio.check("x.json", '{"a": 1,}')
        self.assertFalse(ok)

    def test_valid_json_passes(self):
        ok, _ = studio.check("x.json", '{"a": 1}')
        self.assertTrue(ok)

    def test_php_without_opening_tag_is_refused(self):
        ok, _ = studio.check("x.php", "echo 'hi';")
        self.assertFalse(ok)

    def test_php_with_unbalanced_braces_is_refused(self):
        ok, msg = studio.check("x.php", "<?php function a() { echo 1;")
        self.assertFalse(ok)
        self.assertIn("unbalanced", msg.lower())

    def test_php_check_admits_it_is_not_a_full_parse(self):
        ok, msg = studio.check("x.php", "<?php echo 1;")
        self.assertTrue(ok)
        self.assertIn("not fully parsed", msg.lower())


class ReversibleAndRecorded(unittest.TestCase):
    def setUp(self):
        self.full = os.path.join(studio.ROOT, PROBE)
        with open(self.full, "w", encoding="utf-8") as f:
            f.write("original\n")

    def tearDown(self):
        for p in (self.full, os.path.join(studio.ROOT, PROBE_PY)):
            if os.path.exists(p):
                os.remove(p)
        for b in glob.glob(os.path.join(studio.backup_dir(), "*_studio_test_probe_%s*" % _ctx.TAG)):
            os.remove(b)

    def test_save_keeps_the_previous_copy(self):
        ok, msg = studio.save(PROBE, "changed\n")
        self.assertTrue(ok, msg)
        with open(self.full, encoding="utf-8") as f:
            self.assertEqual(f.read(), "changed\n")
        self.assertGreaterEqual(len(studio.backups(PROBE)), 1)

    def test_restore_puts_the_old_content_back(self):
        studio.save(PROBE, "changed\n")
        name = studio.backups(PROBE)[0]["name"]
        ok, msg = studio.restore(PROBE, name)
        self.assertTrue(ok, msg)
        with open(self.full, encoding="utf-8") as f:
            self.assertEqual(f.read(), "original\n")

    def test_restore_rejects_a_path_not_a_name(self):
        ok, msg = studio.restore(PROBE, "../../../evil")
        self.assertFalse(ok)

    def test_refused_save_leaves_the_file_untouched(self):
        py_full = os.path.join(studio.ROOT, PROBE_PY)
        with open(py_full, "w", encoding="utf-8") as f:
            f.write("good = 1\n")
        ok, msg = studio.save(PROBE_PY, "def broken(:\n")
        self.assertFalse(ok)
        with open(py_full, encoding="utf-8") as f:
            self.assertEqual(f.read(), "good = 1\n", "a refused save still wrote")

    def test_no_change_is_not_a_write(self):
        ok, msg = studio.save(PROBE, "original\n")
        self.assertTrue(ok)
        self.assertIn("no change", msg.lower())

    def test_every_action_is_recorded(self):
        studio.save(PROBE, "recorded change\n")
        recent = studio.history(20)
        self.assertTrue(any(e["file"] == PROBE and e["action"] == "saved" for e in recent),
                        "the save was not written to the audit log")
        self.assertTrue(all("who" in e and "at" in e for e in recent))

    def test_crlf_from_a_textarea_is_normalised(self):
        studio.save(PROBE, "a\r\nb\r\n")
        with open(self.full, encoding="utf-8", newline="") as f:
            self.assertNotIn("\r", f.read(), "CRLF would rewrite every line of the file")


class OfferedEqualsOpenable(unittest.TestCase):
    """Whatever the tree declines to list, resolve() must decline to open.

    The two were allowed to disagree: files under a skipped folder, and files above the
    size limit, stayed hidden from the editor while remaining writable by typing the
    path. Backups are the copies a restore reads back, so a silent write there destroys
    the recovery route rather than a working file.
    """

    @staticmethod
    def _disagreements():
        """One pass: list the files where the tree and resolve() disagree."""
        offered = {f["path"] for f in studio.tree()}
        hidden_but_open, offered_but_closed = set(), set()
        for dirpath, _dirnames, filenames in os.walk(studio.ROOT):
            for fn in filenames:
                rel = os.path.relpath(os.path.join(dirpath, fn), studio.ROOT).replace(os.sep, "/")
                openable = bool(studio.resolve(rel))
                if rel not in offered and openable:
                    hidden_but_open.add(rel)
                elif rel in offered and not openable:
                    offered_but_closed.add(rel)
        return hidden_but_open, offered_but_closed

    def test_the_offered_set_equals_the_openable_set(self):
        # A pass reads the folder twice, once inside tree() and once in the walk, so a
        # file written by another suite running at the same time can appear between the
        # two and look like a disagreement. A real one survives a second pass; a file
        # that was merely passing through does not.
        hidden, closed = self._disagreements()
        if hidden or closed:
            hidden2, closed2 = self._disagreements()
            hidden, closed = hidden & hidden2, closed & closed2
        self.assertEqual(sorted(hidden), [],
                         "hidden from the tree yet writable: %s" % sorted(hidden)[:5])
        self.assertEqual(sorted(closed), [],
                         "listed by the tree yet not openable: %s" % sorted(closed)[:5])

    def test_a_file_in_a_skipped_folder_cannot_be_opened(self):
        folder = os.path.join(studio.ROOT, "reference")
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, "_studio_skip_probe_%s.md" % _ctx.TAG)
        original = "reference material, not code\n"
        with open(probe, "w", encoding="utf-8") as f:
            f.write(original)
        try:
            rel = "reference/_studio_skip_probe_%s.md" % _ctx.TAG
            self.assertNotIn(rel, {f["path"] for f in studio.tree()})
            self.assertIsNone(studio.resolve(rel), "a skipped folder is still writable")
            ok, _msg = studio.save(rel, "overwritten\n")
            self.assertFalse(ok)
            with open(probe, encoding="utf-8") as f:
                self.assertEqual(f.read(), original)
        finally:
            os.remove(probe)


if __name__ == "__main__":
    unittest.main()
