@AGENTS.md

# PRI District Tracker: drive layer

AGENTS.md above holds the domain rules (offline rendering, the toolkit header, nothing deleted, the clobber guard, the console token, the Studio guard rails, integer districts). Where it names the OneDrive folder as canonical, read the drive copy `App_to_Migrate\apps\pri-district-tracker` instead; the OneDrive original is a read-only archive.

## Commands

| Command | Healthy output |
|---|---|
| `py tools/check.py` (the gate) | `CHECK OK` |
| `py scripts/run_tests.py` | `OK` (171 tests) |
| `DT_TEST_DRIVER=pgsql` + PHP `tests/php/run-tests.php` | `130 passed, 0 failed` (test database on the drive cluster only; the gate runs it when pg.env exists) |
| `PRI District Tracker.exe` (double-click) | opens the MAIN PAGE: the PHP web site (`index.html`) through `tools\serve.ps1 start -Open` (D-059) |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tools\serve.ps1 start` / `stop` / `status` | the main page, the PHP web site: starts the drive PostgreSQL through `tools\estate-pg.ps1`, then `php -S 127.0.0.1:<8780-8789>` with the app folder as document root and `tools\router.php`; `site: running  http://127.0.0.1:8780/  pid ...` or `site: stopped`; `-Open` opens the browser, `-Console` runs it in the window; `stop` ends this folder's php and asks estate-pg.js to stop the cluster |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tools\data-console.ps1 start` / `stop` / `status` | the BACKEND, the Data Console (`scripts/admin_server.py`, editor of record and Studio): `console: running  http://127.0.0.1:8770/ ...`; ports 8770 to 8779; same rules as serve.ps1 (it calls `serve.ps1 -Server console`) |
| `powershell -NoProfile -ExecutionPolicy Bypass -File tools\estate-pg.ps1 start` / `stop` / `status` | the one wrapper around the estate's `estate-pg.js` for the drive cluster, 127.0.0.1 port 5433; `py scripts/estate_pg.py status` calls it for the gate and the switch-over |
| `node <estate>\Skills\drez-containerize\scripts\make-launcher.js .` | `OK   .: Built PRI District Tracker.exe` (rebuild after changing `launcher\launcher.ini`) |
| `py scripts/find_php.py` | the portable PHP in `tools/php` with pgsql |
| `PRI_SKIP_REPS=1 py scripts/build_site.py` | exit 0; outputs match git unless the data changed |
| `py scripts/app_config.py --show` | `backups  ...\data\pri-district-tracker\backups` on the drive |
| `SETUP.bat` | creates config.local.json and sets dataFolder |

## Layout

- `scripts/`: the Python generator, Data Console, Studio, backups; standard library only, run with `py`.
- `scripts/app_config.py`: the portable loader; the only writer of `config.local.json` (git-ignored).
- `data/activities.json`: database of record; stays in the app folder on disk but is git-ignored, because only empty databases go to a repository (D-021). `py scripts/backup_data.py` snapshots it; git does not hold it.
- `..\..\data\pri-district-tracker\backups`: what the app writes outside git (snapshots, Studio copies, history.log). Read-only for Claude.
- `php/`, `includes/`, `migrations/`, `tools/*.php`, `sql/`, `health.php`, `Dockerfile`, `compose.yaml`: hosted layer, not deployed. `includes/db.php` is the only data-access module; `DB_DRIVER` is `pgsql`, the only engine (D-031); PostgreSQL credentials come from `<dataFolder>/pg.env` and point at the estate cluster on the drive (port 5433; a pg.env naming another port is refused). No API server: the layer connects to the cluster directly.
- `tools/php/`: git-ignored portable PHP (SETUP.bat copies it).
- `PRI District Tracker.exe`, `launcher/`: the one launcher, built from the drez-containerize template with `launcher/launcher.ini`; `SETUP.bat` is the only `.bat` at the root, and no `.cmd` or `.vbs` exists (owner ruling 2026-11-03). The main page is the PHP web site (index.html at the document root, the app folder); the backend is the Data Console. `tools/serve.ps1` logs to `data/server.log`, PHP to `data/php*.log`, the console to `data/console*.log` (all git-ignored).
- `reference/`: git-ignored source documents (Information docx, district text files, captured PRI pages).
- `intent.md`, `plan.md`, `handoff.md`: state on disk; history in `docs/handoffs/`. Decisions live in `reference/context/DECISIONS.md` (through decisions.py); `docs/decisions.md` is a one-line pointer.

## Hard rules

- Never edit the build outputs (index.html, handout.html, PRI-Tracker-Kit.html, data.js, data/geo.json, data/reps.json, sql/data.sql); edit `scripts/build_site.py` and rebuild.
- Never regenerate `assets/vendor` (make_vendor.py needs the internet); git tracks it from the initial commit although .gitignore lists it.
- Never create a `.env` with values; `.env.example` lists the names. Never open, print or copy `pg.env`; `includes/db.php` reads it.
- Never run `tools/migrate.php` or `tools/load-pg.php` with `--live`; the owner switches over with `py scripts/pg_switch_over.py --confirm-live`. Tests use `--test` / `DT_TEST_DRIVER=pgsql` only.
- Never edit an applied file in `migrations/`; add the next number as a `.pgsql.sql` file. PostgreSQL is the only engine (Q-11, 2026-10-20).
- Tests must never write the data folder: `tests/_ctx.py` points `PRI_BACKUP_DIR` at a temp folder.
- Run the gate and the tests from the drive-letter spelling of this folder, never through the fixed `<SystemDrive>\Estate\App_to_Migrate` alias: both spellings name one folder (D-056), and checks that compare paths as text fail falsely through the alias.
- Start and stop PostgreSQL only through `tools\estate-pg.ps1` (which calls the estate's `estate-pg.js`), from a normal window, never "Run as administrator": PostgreSQL refuses an elevated account. Never run `pg_ctl` from this app.
- Start the main page only through `tools\serve.ps1` (or the `.exe`) and the Data Console only through `tools\data-console.ps1`. Both decide whether a port and a process belong to this folder by file identity, never by comparing path spellings; keep it that way. Each `stop` ends only this folder's processes.
- Never wait on the PostgreSQL wrapper with `Start-Process -Wait` or capture the output of a start that starts the server: postgres.exe is a descendant and inherits handles, so the caller never returns (D-057, measured 2026-11-03).
- Before any UI work, read `docs/design.md` (the UI Elements spec, skill drez-ui-elements) and reuse the component it names; styles live in the `build_site.py` constants it lists.

## Things Claude gets wrong here

- Pointing PostgreSQL at the computer: the database is the estate cluster on the drive (`<estate>\runtime\postgresql\17`, `<estate>\data\postgres\17`, port 5433). Never use a PostgreSQL installed on the computer, never run `estate-pg.js init` (the PRI Suite session does), never read `<estate>\data\postgres\superuser.env`.

- Treating `git status` M on the outputs as a change: the build writes CRLF; an empty `git diff` means no change.
- Trusting the pri-php-webapp skill on sign-in: no HTTP Basic exists; identity is the NetID from the campus proxy's headers and authority is the role from `user_roles` or the `AUTH_*` allowlists (`includes/auth.php`, D-018). `ADMIN_EMAILS` still grants admin.
- Thinking a back-office save may write every column: the form writes only `ACTIVITY_FORM_FIELDS`, carries `version` and a CSRF token (D-019). The Data Console stays the editor of record.

## Before saying done

Run `py tools/check.py`, quote `CHECK OK`, update the row in `plan.md` and rewrite `handoff.md` in the same turn.
