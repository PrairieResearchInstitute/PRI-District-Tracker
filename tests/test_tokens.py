"""One token block, five surfaces (UI Elements deviation PDT-32).

The colours, radii and sizes used to live in three hand-copied blocks plus literals in
two more files, and they had drifted into eleven muted greys, seven hairlines, two
navies and two link blues. scripts/ui_tokens.py is the source now. Python can hand the
block to the three generated pages and to the Data Console at run time; PHP cannot
import it, so php/admin_ingest.php carries a copy and this file holds the two together,
the way tests/test_freshness.py holds the display timer's two copies together.
"""
import unittest, os, re
import _ctx  # noqa: F401
import ui_tokens
import pri_data

PUBLIC = ["index.html", "handout.html", "PRI-Tracker-Kit.html"]


def _read(rel):
    with open(os.path.join(_ctx.ROOT, rel), encoding="utf-8") as f:
        return f.read()


class TheBlockIsOneThing(unittest.TestCase):
    def test_the_scope_and_fonts_are_the_only_differences(self):
        a = ui_tokens.tokens_css("#pdt")
        b = ui_tokens.tokens_css(":root")
        self.assertEqual(a.replace("#pdt{", ":root{", 1), b)

    def test_every_token_the_spec_names_is_defined(self):
        block = ui_tokens.tokens_css()
        for name in ("--blue", "--blue-deep", "--orange", "--orange-hover", "--il-altgeld",
                     "--link", "--ink", "--storm", "--storm-dark", "--line", "--field",
                     "--soft", "--page", "--backdrop", "--font-body", "--font-head",
                     "--font-mono", "--radius-xs", "--radius-sm", "--radius-md",
                     "--radius-lg", "--radius-dialog", "--radius-pill",
                     "--ok-bg", "--warn-bg", "--err-bg", "--focus"):
            self.assertIn(name + ":", block, "%s is missing from the token block" % name)

    def test_every_surface_carries_the_campus_faces(self):
        """Q-19 (owner, 2026-10-17): the campus pairing everywhere, back offices too."""
        back = ui_tokens.tokens_css(":root", ui_tokens.FONT_BODY_SYSTEM, ui_tokens.FONT_HEAD_SYSTEM)
        self.assertIn("Source Sans 3", back)
        self.assertIn("Montserrat", back)
        self.assertNotIn("Segoe UI", back, "a back office still names the system stack (PDT-03)")

    def test_the_back_office_loads_the_faces_rather_than_naming_them(self):
        """Naming a face the page never loads is the PDT-03 defect itself."""
        import ui_fonts
        faces = ui_fonts.font_faces()
        self.assertIn("@font-face", faces)
        self.assertIn("Source Sans 3", faces)
        self.assertIn("Montserrat", faces)
        self.assertIn("/*FONTS*/", _read("scripts/admin_ui.html"),
                      "the console has no place for the faces")
        self.assertIn("assets/fonts.css", _read("php/admin_ingest.php"),
                      "the hosted back office does not link the faces")


class EverySurfaceCarriesIt(unittest.TestCase):
    def test_the_generated_pages_carry_the_block(self):
        for name in PUBLIC:
            self.assertIn("--storm-dark:", _read(name), "%s has no token block" % name)

    def test_the_console_has_the_placeholder_the_server_fills(self):
        self.assertIn("/*TOKENS*/", _read("scripts/admin_ui.html"))

    def test_the_php_copy_matches_this_module_exactly(self):
        """A copy that can drift is the defect PDT-32 names, so it may not drift."""
        want = ui_tokens.tokens_css(":root", ui_tokens.FONT_BODY_SYSTEM, ui_tokens.FONT_HEAD_SYSTEM)
        self.assertIn(want.rstrip(chr(10)), _read("includes/ui.php"),
                      "includes/ui.php no longer matches scripts/ui_tokens.py")

    def test_the_php_pages_take_the_block_from_that_one_copy(self):
        """The host page used to carry its own; it reads the partial's now (PDT-14)."""
        host = _read("php/admin_ingest.php")
        self.assertIn("DT_TOKENS", host)
        self.assertNotIn("--storm-dark:#4A4C4B", host, "the host carries a second token block")


class OneStatusList(unittest.TestCase):
    """Q-16: the Status list is fixed everywhere, so there is one list."""

    def test_the_php_copy_matches_pri_data(self):
        php = _read("includes/ui.php")
        want = "const DT_STATUSES = ['" + "', '".join(pri_data.STATUSES) + "'];"
        self.assertIn(want, php, "includes/ui.php no longer matches pri_data.STATUSES")

    def test_the_kit_bakes_the_same_list_in(self):
        kit = _read("PRI-Tracker-Kit.html")
        for s in pri_data.STATUSES:
            self.assertIn("<option>%s</option>" % s, kit, "the Kit is missing status %s" % s)
        self.assertNotIn('id="kadd_status" placeholder', kit, "the Kit still takes free text")


class OneProductName(unittest.TestCase):
    """Q-17: one name, with a suffix per page."""

    def test_each_page_names_the_product_the_same_way(self):
        for name, title in (("index.html", "<title>PRI District Tracker</title>"),
                            ("handout.html", "<title>PRI District Tracker: District Profile</title>"),
                            ("PRI-Tracker-Kit.html", "<title>PRI District Tracker: Working Group Kit</title>")):
            self.assertIn(title, _read(name), "%s does not carry its page title" % name)

    def test_the_old_names_are_gone(self):
        for name in ("index.html", "handout.html", "PRI-Tracker-Kit.html"):
            page = _read(name)
            self.assertNotIn("PRI Project District Tracker", page)
            self.assertNotIn("PRI District handout", page)


class NothingReferencesATokenThatDoesNotExist(unittest.TestCase):
    """A misspelled var() fails silently and the colour simply vanishes."""

    def test_every_token_used_in_a_built_page_is_defined_in_it(self):
        for name in PUBLIC:
            page = _read(name)
            used = set(re.findall(r"var\(--([a-z0-9-]+)\)", page))
            defined = set(re.findall(r"--([a-z0-9-]+)\s*:", page))
            # The toolkit's own --ilw-* and --il-* variables come from the vendored bundle.
            missing = sorted(u for u in used - defined
                             if not u.startswith(("ilw", "il-", "-ilw")))
            self.assertEqual(missing, [], "%s uses undefined tokens: %s" % (name, missing))


if __name__ == "__main__":
    unittest.main()
