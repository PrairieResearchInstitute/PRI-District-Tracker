"""Guards on the Data Console, which can write the project's own code.

Binding to 127.0.0.1 keeps other MACHINES out. It does not keep other WEB PAGES out: a
page open in the same browser can POST to localhost, and a "simple" request
(Content-Type: text/plain) is sent cross-site with no CORS preflight to stop it. Before
these guards existed, a hostile page could overwrite any script in this project - and
the Studio writes code the next build runs. Both holes below were real and were
demonstrated against the running server before being fixed.
"""
import unittest, os, glob
import _ctx  # noqa: F401
import studio
import admin_server as adm

GOOD_HOST = "127.0.0.1:%d" % adm.PORT
GOOD_ORIGIN = "http://127.0.0.1:%d" % adm.PORT


class FakeRequest:
    """Just enough of a handler for _authorized(), which only reads headers."""

    def __init__(self, **headers):
        self.headers = {k.replace("_", "-"): v for k, v in headers.items()}


def authorize(**headers):
    return adm.Handler._authorized(FakeRequest(**headers))


class RequestGuard(unittest.TestCase):
    def test_our_own_page_is_allowed(self):
        ok, why = authorize(Host=GOOD_HOST, Origin=GOOD_ORIGIN,
                            **{"X-CSRF-Token": adm.CSRF_TOKEN})
        self.assertTrue(ok, why)

    def test_allowed_without_an_origin_header(self):
        """Same-origin GETs do not always carry Origin; the token still proves it."""
        ok, why = authorize(Host=GOOD_HOST, **{"X-CSRF-Token": adm.CSRF_TOKEN})
        self.assertTrue(ok, why)

    def test_cross_site_origin_is_refused(self):
        ok, why = authorize(Host=GOOD_HOST, Origin="https://evil.example.com",
                            **{"X-CSRF-Token": adm.CSRF_TOKEN})
        self.assertFalse(ok)
        self.assertIn("cross-site", why.lower())

    def test_missing_token_is_refused(self):
        ok, why = authorize(Host=GOOD_HOST, Origin=GOOD_ORIGIN)
        self.assertFalse(ok)

    def test_wrong_token_is_refused(self):
        ok, _ = authorize(Host=GOOD_HOST, **{"X-CSRF-Token": "not-the-token"})
        self.assertFalse(ok)

    def test_unexpected_host_is_refused(self):
        """Defeats DNS rebinding, where a hostile name resolves to 127.0.0.1."""
        ok, why = authorize(Host="evil.example.com",
                            **{"X-CSRF-Token": adm.CSRF_TOKEN})
        self.assertFalse(ok)
        self.assertIn("host", why.lower())

    def test_localhost_spellings_are_accepted(self):
        for h in ("localhost:%d" % adm.PORT, "127.0.0.1:%d" % adm.PORT):
            ok, why = authorize(Host=h, **{"X-CSRF-Token": adm.CSRF_TOKEN})
            self.assertTrue(ok, "%s rejected: %s" % (h, why))

    def test_token_is_not_guessable(self):
        self.assertGreaterEqual(len(adm.CSRF_TOKEN), 32)


class ConsolePageCarriesTheToken(unittest.TestCase):
    def test_ui_sends_the_header(self):
        p = os.path.join(_ctx.ROOT, "scripts", "admin_ui.html")
        with open(p, encoding="utf-8") as f:
            ui = f.read()
        self.assertIn("X-CSRF-Token", ui, "the console would lock itself out")
        self.assertIn('meta[name="pri-csrf"]', ui, "the console never reads the token")

    def test_server_injects_the_meta_tag(self):
        p = os.path.join(_ctx.ROOT, "scripts", "admin_server.py")
        with open(p, encoding="utf-8") as f:
            src = f.read()
        self.assertIn('name="pri-csrf"', src)


class RestoreBelongsToItsFile(unittest.TestCase):
    """A backup name ends with the path it came from. Without checking that, a copy of
    one file could be written over a different file and quietly destroy it."""

    A = "docs/_sec_probe_a_%s.md" % _ctx.TAG
    B = "docs/_sec_probe_b_%s.md" % _ctx.TAG

    def setUp(self):
        for rel, text in ((self.A, "A original\n"), (self.B, "B original\n")):
            with open(os.path.join(studio.ROOT, rel), "w", encoding="utf-8") as f:
                f.write(text)
        studio.save(self.B, "B second version\n")      # creates a backup of B

    def tearDown(self):
        for rel in (self.A, self.B):
            p = os.path.join(studio.ROOT, rel)
            if os.path.exists(p):
                os.remove(p)
        for b in glob.glob(os.path.join(studio.backup_dir(), "*_sec_probe_*%s*" % _ctx.TAG)):
            os.remove(b)

    def test_a_backup_of_another_file_is_refused(self):
        name = studio.backups(self.B)[0]["name"]
        ok, msg = studio.restore(self.A, name)
        self.assertFalse(ok)
        self.assertIn("different file", msg.lower())
        with open(os.path.join(studio.ROOT, self.A), encoding="utf-8") as f:
            self.assertEqual(f.read(), "A original\n", "the wrong file was overwritten")

    def test_its_own_backup_still_restores(self):
        name = studio.backups(self.B)[0]["name"]
        ok, msg = studio.restore(self.B, name)
        self.assertTrue(ok, msg)
        with open(os.path.join(studio.ROOT, self.B), encoding="utf-8") as f:
            self.assertEqual(f.read(), "B original\n")

    def test_a_path_instead_of_a_name_is_refused(self):
        ok, _ = studio.restore(self.A, "../../../evil")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
