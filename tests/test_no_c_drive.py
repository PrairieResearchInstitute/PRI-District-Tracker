"""Nothing on the computer: every file the app writes lands on the drive.

App standard v2 section B. Python's default temp folder sits in the user profile on
C:, so a plain tempfile.mkdtemp() anywhere in this app or its suite would break the
rule silently. These tests fail if that happens again.
"""
import unittest, os, re, glob, tempfile, shutil
import _ctx  # noqa: F401
import app_config

# Words that answer with a path on C:. A script naming one has left the drive.
OFF_DRIVE_CALLS = ("expanduser", "gettempdir")
OFF_DRIVE_VARS = ("appdata", "localappdata", "programdata", "userprofile")


def _drive(p):
    return os.path.splitdrive(os.path.abspath(p))[0].lower()


class TheSuiteKeepsItsScratchOnTheDrive(unittest.TestCase):
    def test_pythons_temp_folder_is_on_the_drive(self):
        self.assertEqual(_drive(tempfile.gettempdir()), _drive(_ctx.ROOT),
                         "the temp folder is on a different drive from the app")

    def test_the_temp_folder_is_the_projects_own(self):
        self.assertTrue(os.path.abspath(tempfile.gettempdir()).startswith(
            os.path.join(os.path.abspath(_ctx.ROOT), ".tmp")),
            "the suite is not using .tmp/ beside the app: %s" % tempfile.gettempdir())

    def test_a_plain_mkdtemp_lands_there_too(self):
        """The five suites that call tempfile.mkdtemp() directly need no change."""
        d = tempfile.mkdtemp(prefix="pri-drive-check-")
        try:
            self.assertEqual(_drive(d), _drive(_ctx.ROOT))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_the_suite_does_not_write_the_data_folder(self):
        """Section B sends temp to the drive; D-003 keeps the suite out of the data
        folder. .tmp/ beside the app satisfies both."""
        folder = app_config.data_folder()
        if folder is None:
            self.skipTest("no dataFolder configured on this machine")
        for p in (tempfile.gettempdir(), app_config.backups_dir()):
            self.assertFalse(os.path.abspath(p).startswith(os.path.abspath(folder)),
                             "the suite writes inside the data folder: %s" % p)


class TheAppResolvesTempToTheDrive(unittest.TestCase):
    """Each test here may move the process temp folder, so the whole environment it
    depends on goes back afterwards; a later test calling mkdtemp must still work."""

    NAMES = ("PRI_TMP_DIR", "TMP", "TEMP", "TMPDIR")

    def setUp(self):
        self._env = {n: os.environ.get(n) for n in self.NAMES}
        self._tempdir = tempfile.tempdir
        self.probe = os.path.join(_ctx.ROOT, ".tmp", "probe-" + _ctx.TAG)

    def tearDown(self):
        for name, value in self._env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        tempfile.tempdir = self._tempdir
        shutil.rmtree(self.probe, ignore_errors=True)

    def test_with_a_data_folder_temp_sits_inside_it(self):
        os.environ.pop("PRI_TMP_DIR", None)
        folder = app_config.data_folder()
        if folder is None:
            self.skipTest("no dataFolder configured on this machine")
        self.assertEqual(os.path.normcase(app_config.tmp_dir()),
                         os.path.normcase(os.path.join(folder, "tmp")))

    def test_reporting_the_path_creates_nothing(self):
        os.environ["PRI_TMP_DIR"] = self.probe
        self.assertFalse(os.path.isdir(self.probe))
        self.assertEqual(app_config.tmp_dir(), self.probe)
        self.assertFalse(os.path.isdir(self.probe),
                         "tmp_dir() created a folder without being asked")

    def test_the_environment_override_wins(self):
        os.environ["PRI_TMP_DIR"] = self.probe
        self.assertEqual(app_config.tmp_dir(), self.probe)

    def test_use_drive_temp_sets_every_name_python_and_children_read(self):
        os.environ["PRI_TMP_DIR"] = self.probe
        path = app_config.use_drive_temp()
        self.assertEqual(path, self.probe)
        for name in ("TMP", "TEMP", "TMPDIR"):
            self.assertEqual(os.environ[name], path, "%s was not pointed at the drive" % name)
        self.assertEqual(tempfile.tempdir, path)
        self.assertTrue(os.path.isdir(path), "use_drive_temp() did not create the folder")


class NoCodeReachesIntoTheUserProfile(unittest.TestCase):
    def _scripts(self):
        return sorted(glob.glob(os.path.join(_ctx.SCRIPTS, "*.py")))

    def test_no_script_asks_the_computer_for_a_temp_or_home_folder(self):
        for path in self._scripts():
            with open(path, encoding="utf-8") as f:
                text = f.read().lower()
            for word in OFF_DRIVE_CALLS:
                self.assertNotIn(word, text,
                                 "%s calls %s, which answers with a path on C:"
                                 % (os.path.basename(path), word))

    def test_no_script_names_a_user_profile_variable(self):
        for path in self._scripts():
            with open(path, encoding="utf-8") as f:
                text = f.read().lower()
            for word in OFF_DRIVE_VARS:
                self.assertNotIn(word, text, "%s names %s" % (os.path.basename(path), word))

    def test_no_script_hardcodes_a_windows_user_path(self):
        for path in self._scripts():
            with open(path, encoding="utf-8") as f:
                text = f.read()
            # Any drive letter, then Users: the pattern, so no letter is written here.
            self.assertIsNone(re.search(r"[A-Za-z]:[\\/]+Users[\\/]", text, re.I),
                              "%s hardcodes a user folder" % os.path.basename(path))

    def test_the_data_console_points_itself_at_the_drive(self):
        with open(os.path.join(_ctx.SCRIPTS, "admin_server.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("use_drive_temp()", text,
                      "the console no longer sends its temporary files to the drive")


if __name__ == "__main__":
    unittest.main()
