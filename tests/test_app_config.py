"""The portable loader: with no config.local.json the app keeps backups beside itself;
with a dataFolder it writes them there; a drive letter is refused (the drive may take
any letter)."""
import unittest, tempfile, shutil, os, json
import _ctx
import app_config


class Loader(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._local, self._template = app_config.LOCAL, app_config.TEMPLATE
        app_config.LOCAL = os.path.join(self.dir, "config.local.json")
        app_config.TEMPLATE = os.path.join(_ctx.ROOT, "config.template.json")
        self._env = os.environ.pop("PRI_BACKUP_DIR", None)

    def tearDown(self):
        app_config.LOCAL, app_config.TEMPLATE = self._local, self._template
        if self._env is not None:
            os.environ["PRI_BACKUP_DIR"] = self._env
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_no_local_file_keeps_backups_beside_the_app(self):
        self.assertEqual(app_config.source(), "default")
        self.assertIsNone(app_config.data_folder())
        self.assertEqual(app_config.backups_dir(), os.path.join(app_config.ROOT, "backups"))

    def test_init_copies_the_template_with_an_empty_data_folder(self):
        app_config.save({})
        with open(app_config.LOCAL, encoding="utf-8") as f:
            self.assertEqual(json.load(f).get("dataFolder"), "")
        self.assertIsNone(app_config.data_folder())

    def test_data_folder_routes_backups_there(self):
        app_config.save({"dataFolder": r"..\..\data\pri-district-tracker"})
        want = os.path.normpath(os.path.join(app_config.ROOT, "..", "..", "data", "pri-district-tracker"))
        self.assertEqual(app_config.data_folder(), want)
        self.assertEqual(app_config.backups_dir(), os.path.join(want, "backups"))

    def test_env_override_wins(self):
        app_config.save({"dataFolder": r"..\elsewhere"})
        os.environ["PRI_BACKUP_DIR"] = self.dir
        try:
            self.assertEqual(app_config.backups_dir(), self.dir)
        finally:
            del os.environ["PRI_BACKUP_DIR"]

    def test_drive_letter_is_refused(self):
        with self.assertRaises(ValueError):
            app_config.save({"dataFolder": _ctx.free_drive() + r"data\x"})


class StudioLeavesItAlone(unittest.TestCase):
    """Only app_config.save() writes config.local.json; the Studio neither lists nor opens it."""

    def test_studio_refuses_config_local(self):
        import studio
        self.assertIsNone(studio.resolve("config.local.json"))
        self.assertNotIn("config.local.json", [f["path"] for f in studio.tree()])

    def test_studio_skips_the_reference_folder(self):
        import studio
        self.assertFalse(any(f["path"].startswith("reference/") for f in studio.tree()))


if __name__ == "__main__":
    unittest.main()
