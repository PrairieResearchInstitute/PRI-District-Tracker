"""Rules from AGENTS.md that are easy to break by accident and invisible until the
project is opened somewhere else.

A hardcoded absolute path works perfectly on the machine it was written on and fails
silently everywhere else - which is exactly how the project ended up building into a
stale Desktop copy while the real one lived in OneDrive.
"""
import unittest, os, re, subprocess
import _ctx

SOURCE_DIRS = ["scripts", "php", "sql", "tests", "includes", "tools", "migrations"]
SOURCE_EXT = {".py", ".php", ".sql", ".yml", ".yaml"}

# A user-specific absolute path: a drive letter followed by \Users or /Users.
HARDCODED = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]", re.I)

# Scripts that locate the project for themselves must do it from their own file.
DERIVES = re.compile(r"os\.path\.dirname\(\s*os\.path\.dirname\(\s*os\.path\.abspath\(__file__\)")


def source_files():
    here = os.path.basename(__file__)   # this file holds example paths on purpose
    for d in SOURCE_DIRS:
        root = os.path.join(_ctx.ROOT, d)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [x for x in dirnames if x not in {"__pycache__", "backups"}
                           and not (d == "tools" and x == "php")]   # the portable PHP copy
            for fn in filenames:
                if fn == here:
                    continue
                if os.path.splitext(fn)[1].lower() in SOURCE_EXT:
                    yield os.path.join(dirpath, fn)


class NoHardcodedPaths(unittest.TestCase):
    def test_no_user_specific_absolute_paths(self):
        offenders = []
        for p in source_files():
            with open(p, encoding="utf-8", errors="replace") as f:
                for n, line in enumerate(f, 1):
                    if HARDCODED.search(line):
                        offenders.append("%s:%d" % (os.path.relpath(p, _ctx.ROOT), n))
        self.assertEqual(offenders, [],
                         "hardcoded absolute path(s); derive from __file__ instead: %s" % offenders)

    def test_the_detector_would_actually_catch_one(self):
        """A rule that cannot fail is not a rule."""
        # The drive is computed (tests/_ctx.py free_drive), so no letter is written here.
        drive = _ctx.free_drive()
        self.assertTrue(HARDCODED.search('PROJ = r"' + drive + r'Users\someone\Desktop\App"'))
        self.assertTrue(HARDCODED.search('p = "' + drive[:2] + '/Users/someone/Desktop/App"'))
        self.assertIsNone(HARDCODED.search('PROJ = os.path.abspath(__file__)'))


class ScriptsLocateThemselves(unittest.TestCase):
    """Every script that needs the project root derives it, so the project can be
    moved or copied without editing code."""

    def test_project_root_is_derived_not_declared(self):
        for name in ["build_site.py", "make_templates.py", "make_inset.py",
                     "pri_data.py", "studio.py", "backup_data.py"]:
            p = os.path.join(_ctx.ROOT, "scripts", name)
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as f:
                src = f.read()
            if "PROJ" in src or "ROOT" in src:
                self.assertTrue(DERIVES.search(src),
                                "%s does not derive its project root from __file__" % name)


if __name__ == "__main__":
    unittest.main()


# App standard v2 section C1: the repository root holds only what runs, builds or
# tests the app, plus the files the standard names. Everything else is reference
# material and belongs in the git-ignored reference/ folder. Adding a document here
# instead of to the list is the mistake this guards against.
ROOT_FILES = {
    # Named by C1
    "AGENTS.md", "CLAUDE.md", "README.md", "intent.md", "plan.md", "handoff.md",
    "SETUP.bat", "Data Console.bat",
    # The owner's delivery rule: a README for people ships as .docx
    "README.docx",
    # Build, container and configuration
    "Dockerfile", "compose.yaml", ".dockerignore", ".gitignore", ".gitattributes",
    ".env.example", "config.template.json", "config.local.json",
    # Read by the build, the audit or the host
    "data-sources.yaml", "hardcoded-allow.json", "health.php",
    # The credit line the gate checks for (D-031)
    "NOTICE",
    # drez-php-core's sync manifest: which library version includes/core.php came from
    "drez-php-core.sync.json",
    # The deliverables themselves
    "index.html", "handout.html", "PRI-Tracker-Kit.html", "data.js",
}

# Written by SETUP.bat on each machine, git-ignored, so absent from a fresh clone.
PER_MACHINE = {"config.local.json"}


class TheRootHoldsOnlyWorkingFiles(unittest.TestCase):
    def _tracked_root(self):
        r = subprocess.run(["git", "-c", "safe.directory=*", "ls-files"],
                           cwd=_ctx.ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return {p.strip() for p in r.stdout.splitlines() if p.strip() and "/" not in p}

    def test_no_document_is_tracked_at_the_root(self):
        strays = sorted(self._tracked_root() - ROOT_FILES)
        self.assertEqual(strays, [],
                         "these sit at the root but do not run, build or test the app; "
                         "move them to reference/ or add them to ROOT_FILES with a reason: %s"
                         % strays)

    def test_every_named_working_file_still_exists(self):
        """Keeps the list honest: a renamed or deleted file must be renamed here too."""
        missing = sorted(n for n in ROOT_FILES - PER_MACHINE
                         if not os.path.isfile(os.path.join(_ctx.ROOT, n)))
        self.assertEqual(missing, [], "ROOT_FILES names files that are gone: %s" % missing)

    def test_the_design_preview_is_reference_material(self):
        """make_inset.py renders one district inset for the eye only, so its output
        lives in reference/ rather than at the root."""
        with open(os.path.join(_ctx.SCRIPTS, "make_inset.py"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn('"reference", "preview.html"', text,
                      "make_inset.py writes its preview back to the repository root")
