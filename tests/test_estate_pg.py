"""The drive's PostgreSQL: found from the marker, port 5433, never the computer's.

Platform D-028. scripts/estate_pg.py starts and stops the estate cluster on the
portable drive. These tests build fake estates in a temp folder; none starts,
stops or connects to a database.
"""
import unittest, os, tempfile, shutil
import _ctx  # noqa: F401
import estate_pg


class FakeEstate(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="pri-estate-")
        self.app = os.path.join(self.root, "apps", "pri-district-tracker")
        os.makedirs(self.app)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def mark(self):
        open(os.path.join(self.root, estate_pg.MARKER), "w").close()


class TheEstateIsFoundByItsMarker(FakeEstate):
    def test_walks_up_to_the_marker(self):
        self.mark()
        self.assertEqual(estate_pg.estate_dir(self.app), self.root)

    def test_the_nearest_marker_wins(self):
        # The fake tree sits in .tmp/ inside the app, so the real marker is above it;
        # a tree with its own marker must win, and the walk must stop there.
        self.mark()
        os.makedirs(os.path.join(self.app, "x"))
        self.assertEqual(estate_pg.estate_dir(os.path.join(self.app, "x")), self.root)

    def test_layout_is_the_drive_runtime_and_cluster(self):
        p = estate_pg.paths(self.root)
        self.assertEqual(p["bin"], os.path.join(self.root, "runtime", "postgresql", "17", "bin"))
        self.assertEqual(p["data"], os.path.join(self.root, "data", "postgres", "17"))
        self.assertEqual(p["script"], os.path.join(self.root, "runtime", "postgresql", "estate-pg.js"))
        for v in p.values():
            self.assertTrue(os.path.abspath(v).startswith(self.root), v)


class TheClusterIsTheDrives(unittest.TestCase):
    def test_port_and_host(self):
        self.assertEqual(estate_pg.PORT, 5433)
        self.assertEqual(estate_pg.HOST, "127.0.0.1")

    def test_the_php_module_defaults_to_the_same_port(self):
        with open(os.path.join(_ctx.ROOT, "includes", "db.php"), encoding="utf-8") as f:
            self.assertIn("const PG_DRIVE_PORT = '%d';" % estate_pg.PORT, f.read())


class NodeIsPreferredFromTheDrive(FakeEstate):
    def test_a_node_under_runtime_wins(self):
        self.mark()
        d = os.path.join(self.root, "runtime", "node")
        os.makedirs(d)
        node = os.path.join(d, "node.exe")
        open(node, "w").close()
        self.assertEqual(estate_pg.find_node(estate_pg.paths(self.root)), node)

    def test_an_uninitialised_cluster_is_never_created(self):
        self.mark()
        p = estate_pg.paths(self.root)
        self.assertFalse(estate_pg.initialized(p))
        self.assertFalse(os.path.exists(p["data"]))


if __name__ == "__main__":
    unittest.main()
