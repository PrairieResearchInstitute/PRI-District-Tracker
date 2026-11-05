"""The one launcher rule (owner ruling 2026-11-03, D-056, D-057, D-058).

Every PHP web app starts from one <App>.exe built from the estate template, keeps
SETUP.bat as its only .bat, and lets one tools/serve.ps1 own the server. The
server's folder check must compare real identity, because the fixed estate alias and
the drive-letter path name one folder; a text comparison of spellings once refused
to start a sibling app. These tests fail when any of that slips back.
"""
import unittest, os, re
import _ctx

SERVE = os.path.join(_ctx.ROOT, "tools", "serve.ps1")
WRAPPER = os.path.join(_ctx.ROOT, "tools", "estate-pg.ps1")
INI = os.path.join(_ctx.ROOT, "launcher", "launcher.ini")
CONSOLE = os.path.join(_ctx.ROOT, "tools", "data-console.ps1")
ROUTER = os.path.join(_ctx.ROOT, "tools", "router.php")
DRIVE_LETTER = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")


def read(p):
    with open(p, encoding="utf-8-sig") as f:
        return f.read()


def code_lines(text):
    """PowerShell lines without their comments (the here-string C# is code too)."""
    return [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]


class TheRootHoldsOneLauncher(unittest.TestCase):
    def test_setup_bat_is_the_only_script_launcher(self):
        names = os.listdir(_ctx.ROOT)
        bats = sorted(n for n in names if n.lower().endswith(".bat") and n != "SETUP.bat")
        others = sorted(n for n in names if n.lower().endswith((".cmd", ".vbs")))
        self.assertEqual(bats + others, [],
                         "only SETUP.bat may sit at the root; the .exe starts the app: %s"
                         % (bats + others))

    def test_no_vbs_anywhere_in_the_app(self):
        found = []
        for dirpath, dirnames, filenames in os.walk(_ctx.ROOT):
            dirnames[:] = [d for d in dirnames if d not in {".git", "reference", ".tmp", "php"}]
            found += [os.path.join(dirpath, n) for n in filenames if n.lower().endswith(".vbs")]
        self.assertEqual(found, [], ".vbs is retired everywhere (platform D-042)")

    def test_the_exe_and_its_source_exist(self):
        self.assertTrue(os.path.isfile(os.path.join(_ctx.ROOT, "PRI District Tracker.exe")))
        self.assertTrue(os.path.isfile(INI))
        self.assertTrue(os.path.isfile(SERVE), "tools/serve.ps1 is missing")
        self.assertTrue(os.path.isfile(WRAPPER), "tools/estate-pg.ps1 is missing")
        self.assertTrue(os.path.isfile(CONSOLE), "tools/data-console.ps1 is missing")
        self.assertTrue(os.path.isfile(ROUTER), "tools/router.php is missing")

    def test_the_exe_runs_serve_ps1_with_a_quoted_path(self):
        ini = read(INI)
        self.assertIn('run=powershell -NoProfile -ExecutionPolicy Bypass -File '
                      '"{app}\\tools\\serve.ps1" start -Open', ini)
        self.assertIn("exe=PRI District Tracker.exe", ini)
        for need in (r"tools\\serve\.ps1", r"tools\\router\.php", r"tools\\php\\php\.exe",
                     r"config\.local\.json", r"index\.html"):
            self.assertRegex(ini, r"(?m)^require=" + need + r"\|", need)

    def test_the_exe_opens_the_main_page_not_the_backend(self):
        """Owner correction 2026-11-03 (D-059): the exe opens the PHP web site, whose
        main page is index.html; the Data Console is the backend and starts apart."""
        text = read(SERVE)
        self.assertIn("[string]$Server = 'site'", text)
        self.assertRegex(text, r"-S', \"127\.0\.0\.1:\$port\", '-t', \('\"' \+ \$root \+ '\"'\)")
        self.assertIn("-Server console", read(CONSOLE))
        self.assertNotIn("admin_server", read(INI).split("run=", 1)[1])

    def test_the_router_refuses_what_the_container_refuses(self):
        text = read(ROUTER)
        for folder in ("includes", "tools", "migrations", "sql", "templates"):
            self.assertIn("'%s'" % folder, text)
        with open(os.path.join(_ctx.ROOT, "Dockerfile"), encoding="utf-8") as f:
            self.assertIn("(includes|tools|migrations|sql|templates)", f.read())

    def test_no_drive_letter_in_the_launcher_files(self):
        for p in (SERVE, WRAPPER, INI, CONSOLE, ROUTER):
            self.assertIsNone(DRIVE_LETTER.search(read(p)), "%s names a drive letter" % p)


class ServePs1ComparesIdentityNotSpelling(unittest.TestCase):
    def setUp(self):
        self.text = read(SERVE)
        self.code = code_lines(self.text)

    def test_identity_is_volume_serial_and_file_index(self):
        self.assertIn("GetFileInformationByHandle", self.text)
        self.assertRegex(self.text, r"\[DtFolderId\]::Of\(\$p\) -eq \$rootId")

    def test_no_path_is_compared_as_text(self):
        """A path (root, a health answer, a command line) is compared only through
        Test-SameFolder; any -eq, -like, -match or .Equals on a path value fails."""
        bad = re.compile(r"(\$root|\.root|\$script|Groups\[1\])\S*\s+-(i|c)?(eq|ne|like|notlike)\b"
                         r"|-(i|c)?(eq|ne|like|notlike)\s+\$root\b"
                         r"|\$root\S*\.(Equals|StartsWith|Contains)\(")
        hits = [l.strip() for l in self.code if bad.search(l)]
        self.assertEqual(hits, [], "serve.ps1 compares a path as text: %s" % hits)

    def test_binds_and_opens_127_0_0_1_never_localhost(self):
        self.assertFalse([l for l in self.code if "localhost" in l.lower()],
                         "serve.ps1 uses localhost in code")
        self.assertIn("http://127.0.0.1:$port/", self.text)

    def test_one_copy_and_quoted_start(self):
        self.assertIn("System.Threading.Mutex", self.text)
        self.assertIn("""('"' + $root + '"')""", self.text)
        self.assertIn("""('"' + $router + '"')""", self.text)
        self.assertIn("""('"' + (Join-Path $root 'scripts\\admin_server.py') + '"')""", self.text)

    def test_stop_matches_only_this_apps_kind_of_process(self):
        self.assertIn("-Filter \"Name='php.exe'\"", self.text)
        self.assertRegex(self.text, r"\$_\.Name -in @\('py\.exe'")

    def test_postgres_is_awaited_alone(self):
        """Start-Process -Wait waits for postgres.exe too, a descendant, and never
        returned; the wrapper process alone is awaited."""
        line = [l for l in self.code if "estate-pg" in l.lower() or "$wrapper" in l]
        self.assertFalse([l for l in self.code if "Start-Process" in l and "-Wait" in l
                          and "powershell" in l.lower()], "a -Wait on the PostgreSQL wrapper")
        self.assertIn("$p.WaitForExit(", self.text)
        self.assertTrue(line)

    def test_refuses_an_administrator_window(self):
        for p in (SERVE, WRAPPER):
            self.assertIn("BuiltInRole]::Administrator", read(p), p)


class PostgresOnlyThroughTheEstateScript(unittest.TestCase):
    def test_no_pg_ctl_in_the_app(self):
        for rel in ("scripts/estate_pg.py", "tools/estate-pg.ps1", "tools/serve.ps1",
                    "scripts/pg_switch_over.py", "tools/check.py"):
            code = [l for l in read(os.path.join(_ctx.ROOT, rel)).splitlines()
                    if not l.strip().startswith(("#", "//"))]
            calls = [l for l in code if re.search(r"pg_ctl(\.exe)?['\"]|_exe\(p, \"pg_", l)]
            self.assertEqual(calls, [], "%s runs PostgreSQL's programs itself" % rel)

    def test_the_wrapper_runs_estate_pg_js(self):
        text = read(WRAPPER)
        self.assertIn("runtime\\postgresql\\estate-pg.js", text)
        self.assertNotRegex(text, r"(?m)^[^#]*\binit\b.*\$node")

    def test_the_python_helper_calls_the_wrapper(self):
        self.assertIn('"tools", "estate-pg.ps1"', read(os.path.join(_ctx.SCRIPTS, "estate_pg.py")))


if __name__ == "__main__":
    unittest.main()
