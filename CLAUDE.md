@AGENTS.md

# PRI District Tracker: drive layer

AGENTS.md above holds the domain rules (offline rendering, the toolkit header, nothing deleted, the clobber guard, the console token, the Studio guard rails, integer districts). Where it names the OneDrive folder as canonical, read the drive copy `App_to_Migrate\apps\pri-district-tracker` instead; the OneDrive original is a read-only archive.

## Commands

| Command | Healthy output |
|---|---|
| `py tools/check.py` (the gate) | `CHECK OK` |
| `py scripts/run_tests.py` | `OK` (145 tests) |
| `DT_TEST_DRIVER=pgsql` + PHP `tests/php/run-tests.php` | `79 passed, 0 failed` (test database on the drive cluster only; the gate runs it when pg.env exists) |
| `py scripts/estate_pg.py status` / `start` / `stop` | the estate PostgreSQL on the drive, 127.0.0.1 port 5433 (platform D-028, D-015) |
| `py scripts/find_php.py` | the portable PHP in `tools/php` with pgsql |
| `PRI_SKIP_REPS=1 py scripts/build_site.py` | exit 0; outputs match git unless the data changed |
| `py scripts/app_config.py --show` | `backups  ...\data\pri-district-tracker\backups` on the drive |
| `SETUP.bat` | creates config.local.json and sets dataFolder |

## Layout

- `scripts/`: the Python generator, Data Console, Studio, backups; standard library only, run with `py`.
- `scripts/app_config.py`: the portable loader; the only writer of `config.local.json` (git-ignored).
- `data/activities.json`: database of record, tracked in git, stays in the repository.
- `..\..\data\pri-district-tracker\backups`: what the app writes outside git (snapshots, Studio copies, history.log). Read-only for Claude.
- `php/`, `includes/`, `migrations/`, `tools/*.php`, `sql/`, `health.php`, `Dockerfile`, `compose.yaml`: hosted layer, not deployed. `includes/db.php` is the only data-access module; `DB_DRIVER` is `pgsql` (default, D-017) or `mysql` (until go-live); PostgreSQL credentials come from `<dataFolder>/pg.env` and point at the estate cluster on the drive (port 5433; a pg.env naming another port is refused). No API server: the layer connects to the cluster directly.
- `tools/php/`: git-ignored portable PHP (SETUP.bat copies it).
- `reference/`: git-ignored source documents (Information docx, district text files, captured PRI pages).
- `intent.md`, `plan.md`, `handoff.md`, `docs/decisions.md`: state on disk; history in `docs/handoffs/`.

## Hard rules

- Never edit the build outputs (index.html, handout.html, PRI-Tracker-Kit.html, data.js, data/geo.json, data/reps.json, sql/data.sql); edit `scripts/build_site.py` and rebuild.
- Never regenerate `assets/vendor` (make_vendor.py needs the internet); git tracks it from the initial commit although .gitignore lists it.
- Never create a `.env` with values; `.env.example` lists the names. Never open, print or copy `pg.env`; `includes/db.php` reads it.
- Never run `tools/migrate.php` or `tools/load-pg.php` with `--live`; the owner switches over with `py scripts/pg_switch_over.py --confirm-live`. Tests use `--test` / `DT_TEST_DRIVER=pgsql` only.
- Never edit an applied file in `migrations/`; add the next number as a `.pgsql.sql` and `.mysql.sql` twin.
- Tests must never write the data folder: `tests/_ctx.py` points `PRI_BACKUP_DIR` at a temp folder.

## Things Claude gets wrong here

- Pointing PostgreSQL at the computer: the database is the estate cluster on the drive (`<estate>\runtime\postgresql\17`, `<estate>\data\postgres\17`, port 5433). Never use a PostgreSQL installed on the computer, never run `estate-pg.js init` (the PRI Suite session does), never read `<estate>\data\postgres\superuser.env`.

- Treating `git status` M on the outputs as a change: the build writes CRLF; an empty `git diff` means no change.
- Trusting the pri-php-webapp skill on sign-in: no HTTP Basic exists; identity is the NetID from the campus proxy's headers and authority is the role from `user_roles` or the `AUTH_*` allowlists (`includes/auth.php`, D-018). `ADMIN_EMAILS` still grants admin.
- Thinking a back-office save may write every column: the form writes only `ACTIVITY_FORM_FIELDS`, carries `version` and a CSRF token (D-019). The Data Console stays the editor of record.

## Before saying done

Run `py tools/check.py`, quote `CHECK OK`, update the row in `plan.md` and rewrite `handoff.md` in the same turn.
