"""The app must render with no internet connection. This is easy to break by accident
(one CDN <link> reinstated, or the toolkit script switched from an inline module to a
classic or linked one) and the breakage is invisible until someone is actually offline."""
import unittest, os, re

# CI sets this so a missing build is a FAILURE, not a silent skip.
REQUIRE_BUILT = bool(os.environ.get("PRI_REQUIRE_BUILT"))
import _ctx  # noqa: F401

OUTPUTS = ["index.html", "handout.html", "PRI-Tracker-Kit.html"]

# Check the VALUE of each resource reference, not a substring of the file. Inline
# data: URIs legitimately contain the SVG XML namespace URL (and quote characters),
# so naive substring matching invents failures that are not there.
RESOURCE_TAG = re.compile(r"<(?:script|link|img)\b[^>]*>", re.I)
ATTR = re.compile(r"\b(?:src|href)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
CSS_URL = re.compile(r"url\(\s*([^)]*)\)", re.I)
REMOTE = ("http://", "https://", "//")


def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v.strip()


def external_refs(html):
    """Every URL the browser would fetch at render time. Hyperlinks (<a href>) are
    excluded: they are only followed if a user clicks, which is fine offline."""
    out = []
    for tag in RESOURCE_TAG.findall(html):
        for raw in ATTR.findall(tag):
            v = _unquote(raw)
            if v.lower().startswith(REMOTE):
                out.append(v[:80])
    for raw in CSS_URL.findall(html):
        v = _unquote(raw)
        if v.lower().startswith(REMOTE):
            out.append(v[:80])
    return out


def built(name):
    return os.path.join(_ctx.ROOT, name)


class DetectorItself(unittest.TestCase):
    """A test that cannot fail is worse than no test. Prove the detector fires."""

    def test_flags_real_external_references(self):
        for html in [
            '<link rel="stylesheet" href="https://cdn.toolkit.illinois.edu/3/toolkit.css">',
            '<script type="module" src="https://cdn.toolkit.illinois.edu/3/toolkit.js"></script>',
            '<img src="https://www.prairie.illinois.edu/wp-content/x.svg">',
            '<link rel="preconnect" href="https://fonts.googleapis.com">',
            '<style>a{background:url(https://cdn.brand.illinois.edu/i.png)}</style>',
        ]:
            self.assertTrue(external_refs(html), "should have been flagged: %s" % html[:60])

    def test_ignores_inline_and_hyperlinks(self):
        for html in [
            "<style>.x{background:url(\"data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%3E%3C/svg%3E\")}</style>",
            '<a href="https://www.prairie.illinois.edu/about/">About</a>',
            '<script type="module">customElements.define("x", X)</script>',
            '<img src="data:image/png;base64,iVBORw0KGgo=">',
        ]:
            self.assertEqual(external_refs(html), [], "false positive on: %s" % html[:60])


class NoNetworkAtRenderTime(unittest.TestCase):
    def test_outputs_fetch_nothing(self):
        checked = 0
        for name in OUTPUTS:
            p = built(name)
            if not os.path.exists(p):
                continue
            checked += 1
            with open(p, encoding="utf-8") as f:
                refs = external_refs(f.read())
            self.assertEqual(refs, [], "%s fetches at render time: %s" % (name, refs[:3]))
        if not checked:
            msg = "nothing built - run scripts/build_site.py"
            self.fail(msg) if REQUIRE_BUILT else self.skipTest(msg)

    def test_toolkit_script_is_an_inline_module(self):
        """A linked module is CORS-blocked on file://, and a classic <script> never
        registers the toolkit's web components - the banner silently degrades."""
        p = built("PRI-Tracker-Kit.html")
        if not os.path.exists(p):
            (self.fail if REQUIRE_BUILT else self.skipTest)("Kit not built")
        with open(p, encoding="utf-8") as f:
            html = f.read()
        self.assertIn('<script type="module">', html,
                      "the toolkit bundle must be inlined as a module")
        self.assertNotIn('<script type="module" src=', html,
                         "a linked module breaks when opened as a file://")

    def test_kit_is_self_contained(self):
        """The Kit is handed out as ONE file; it must not depend on siblings."""
        p = built("PRI-Tracker-Kit.html")
        if not os.path.exists(p):
            (self.fail if REQUIRE_BUILT else self.skipTest)("Kit not built")
        with open(p, encoding="utf-8") as f:
            html = f.read()
        for sibling in ['src="data.js"', 'href="assets/vendor/', 'src="assets/vendor/']:
            self.assertNotIn(sibling, html, "Kit references a sibling file: %s" % sibling)


class VendorBundle(unittest.TestCase):
    def test_bundle_has_no_external_hosts(self):
        vendor = os.path.join(_ctx.ROOT, "assets", "vendor")
        files = [os.path.join(vendor, n) for n in ("toolkit.local.css", "toolkit.local.js")]
        if not all(os.path.exists(f) for f in files):
            (self.fail if REQUIRE_BUILT else self.skipTest)("vendor bundle not built - run scripts/make_vendor.py")
        for f in files:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
            for host in ("cdn.toolkit.illinois.edu", "cdn.brand.illinois.edu",
                         "fonts.googleapis.com", "fonts.gstatic.com",
                         "onetrust.techservices.illinois.edu"):
                self.assertNotIn(host, text, "%s still points at %s" % (os.path.basename(f), host))


if __name__ == "__main__":
    unittest.main()
