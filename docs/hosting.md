# PRI District Tracker — data ingest, date-stamping & the display timer

Two ways to run the exact same data model. **Curate locally, publish anywhere.**

- **Local (today, no installs):** `scripts/admin_server.py` is a back-office **Data Console**
  that runs on your computer only. Ingest/edit records, date-stamp them, set each record's
  **display timer**, and click **Publish** to regenerate the static site.
- **Hosted (PHP on PostgreSQL, the Radiant target):** the `php/`,
  `includes/` and `migrations/` layer moves the same data into a database so the timer runs
  **live** on the server — no rebuild needed for records to expire. `DB_DRIVER` picks the
  engine (PostgreSQL only since Q-11); every query goes through `includes/db.php`.

Nothing is ever deleted. The full history stays in the database; the public site only ever
shows records whose **Show until** date is still in the future (or blank = never expires).

---

## The lifecycle model (both worlds, identical rules)

Every record carries three stamps:

| field | meaning |
|---|---|
| `ingested_at` | when the record was first loaded (set once) |
| `updated_at`  | last edit / re-ingest — **re-ingesting the same record refreshes it** |
| `show_until`  | the display timer. **Blank/NULL = evergreen** (shows until you retire it). A date = drops off the public site after that day. |

- **Fresh wins:** re-import a record and its `updated_at` moves to today; set a new `show_until`
  to extend it. Old copies never accumulate — import is an *upsert* keyed on the record id.
- **Retire = hide, not delete:** the *Retire* button sets `show_until` to yesterday. The record
  vanishes from the public site but stays in the database and can be revived by clearing the date.
- One rule, one place: `scripts/pri_data.py::fresh()` and `includes/db.php::FRESH_WHERE`
  (`show_until IS NULL OR show_until >= CURRENT_DATE`, standard SQL on both engines) say
  the same thing. On PostgreSQL the session calendar is `APP_TIMEZONE` (default
  America/Chicago), so "today" is the Illinois day whatever the server's own zone.

---

## Local workflow (use this now)

```
py scripts/admin_server.py         # opens http://127.0.0.1:8770 (back-office, localhost only)
```

- **+ New record** / **Edit** — full form; for *sited/regional* records, fill **latitude/longitude**
  and the US House / IL Senate / IL House districts are assigned automatically on save
  (point-in-polygon against the district maps in `data/`).
- **Import CSV…** — bulk-load the `templates/activities_template.csv` layout.
- **Display timer** — per record: tick *Never expires*, or pick a *Show until* date.
- **Retire** — hide a record without deleting it.
- **Publish to site** — regenerates `index.html`, `handout.html`, `data.js`, `data/geo.json`.

The database of record is `data/activities.json` (kept human-readable, one record per line).

---

## Moving to the host: PostgreSQL (the Radiant target)

Until Radiant exists the port runs against the estate's PostgreSQL 17 on the portable
drive (platform D-028): the program in `<estate>\runtime\postgresql\17`, one cluster for
every app in `<estate>\data\postgres\17`, listening on 127.0.0.1 port 5433, role
`district_tracker_app`, databases `district_tracker` and `district_tracker_test`. Nothing
is installed on the computer, and the tracker connects to the cluster directly (no API
server). Moving to Radiant later changes connection settings only.

Starting and stopping: `py tools/check.py` and `py scripts/pg_switch_over.py` start the
drive cluster when it is not running and stop it cleanly afterwards when they started it.
By hand: `py scripts/estate_pg.py start`, `stop` or `status`. The helper runs the shared
`<estate>\runtime\postgresql\estate-pg.js` when a node.exe exists (under
`<estate>\runtime`, then the PATH); otherwise it calls the runtime's `pg_ctl` with the same
data folder, port 5433 and a fast clean stop, and before stopping counts other connections
as the tracker's role (`tools/pg-connections.php`), leaving the cluster running when
another app is connected or the count cannot run (D-015).

PHP: any PHP 8.1+ with `pdo_pgsql`. On this computer `scripts/find_php.py` finds it
(`$PRI_PHP`, then `tools/php/php.exe`, then the PATH) and prints the command line; the
commands below write `php` for that command.

Credentials: on this computer none are typed. With `DB_NAME` unset, `includes/db.php`
reads `<dataFolder>/pg.env` (written by the owner for the drive cluster with
`PGPORT=5433`; dataFolder comes from `config.local.json`). `includes/db.php` refuses a
`pg.env` naming any other port. On a Radiant tier the environment file sets
`DB_DRIVER=pgsql`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

1. **Check on the test database** (never touches `district_tracker`):
   ```
   set DT_TEST_DRIVER=pgsql
   php tests/php/run-tests.php          # migrations, upsert, timer, loader, pages; ends "0 failed"
   ```
   `py tools/check.py` runs the same suite when `pg.env` exists.
2. **Switch-over, run by the owner once** (from the app folder, the Data Console closed so
   `data/activities.json` is not mid-save):
   ```
   py scripts/pg_switch_over.py --status          # look first: 3 migrations pending, nothing applied
   py scripts/pg_switch_over.py --confirm-live    # the switch-over itself
   ```
   It refuses while the Data Console is running, then runs
   `tools/migrate.php --live --confirm-live` and
   `tools/load-pg.php --source data/activities.json --live --confirm-live` with
   `DB_DRIVER=pgsql`, stopping at the first failure. The loader keeps every record's own id and stamps, then compares every field of every
   row and a checksum with the source; it must end with
   `VERIFIED: <n> rows of activities match the source ... source unchanged.`
   It refuses a table that already holds rows unless `--refresh` is given.
3. **Serve with** `DB_DRIVER=pgsql` (the container's environment file), and change
   `<script src="data.js">` to `<script src="php/data.php">` in the hosted `index.html`.
4. From then on the database is the record: see the open question on whether the local
   Data Console keeps writing `data/activities.json`.

## On Radiant: the move, step by step

Everything the move needs is a setting, so the move fills in values and changes no code.
The image build is untested here (Docker is not installed on the estate computers); the
container files pass `check-container.js` C1 to C5 statically.

**Values NCSA supplies at the move** (every Radiant value in `platform\targets.json` reads
TBD until then): the PostgreSQL host, port and TLS mode (`DB_HOST`, `DB_PORT`,
`DB_SSLMODE`); the database names (`<app>_test`, `<app>_live`); the passwords of the two
roles; the proxy's header names for the NetID, address and groups (`AUTH_USER_HEADER`,
`AUTH_EMAIL_HEADER`, `AUTH_GROUPS_HEADER`, `AUTH_GROUPS_SEPARATOR`); the campus group names
that map to viewer, editor and admin; the proxy host names; how the image reaches Radiant.

**Two roles per database.** `<app>_owner` owns the database and runs migrations and
`tools/roles.php`; `<app>_app` is what the running site uses, with rows only:

```sql
-- run as <app>_owner after tools/migrate.php, once per database
GRANT CONNECT ON DATABASE <db> TO <app>_app;
GRANT USAGE ON SCHEMA public TO <app>_app;
GRANT SELECT, INSERT, UPDATE ON activities, awards, settings TO <app>_app;
GRANT SELECT ON user_roles TO <app>_app;
```

The tracker never deletes a record, so the app role gets no DELETE, and it cannot change
`user_roles` or the schema.

**Two environment files per tier**, beside `compose.yaml` on the server, readable only by
the service account, never in git (copy `.env.example`): `pri-district-tracker-<tier>.env`
holds the app role and is the one compose.yaml names; `pri-district-tracker-<tier>-owner.env`
holds the owner role and is used only for the one-off commands below.

Steps, test tier first, then live with the same image tag:

1. Build and tag the image once (drez-app-move, `tag.js`); transfer it.
2. Schema, as the owner (the image carries `tools/migrate.php`, `tools/roles.php` and
   `tools/load-pg.php`; Apache refuses every web request for them):
   `docker run --rm --network <proxy network> --env-file pri-district-tracker-test-owner.env <image:tag> php tools/migrate.php --test`
   (`--test` targets the database named by `DB_TEST_NAME`, which must end in `_test`). On the live
   tier, with `pri-district-tracker-live-owner.env`, run `php tools/migrate.php --live --confirm-live`,
   which targets `DB_NAME`.
3. Grant the app role its rows (the SQL above).
4. Load the records, verified, from the current `data/activities.json` mounted read-only:
   `docker run --rm --network <proxy network> --env-file pri-district-tracker-test-owner.env -v <path>/activities.json:/src/activities.json:ro <image:tag> php tools/load-pg.php --source /src/activities.json --live --confirm-live`
   It must end with `VERIFIED: <n> rows of activities match the source`.
5. Authority by NetID and group (D-018, D-020), as the owner:
   `... php tools/roles.php --live --confirm-live seed` makes NetID dreslik
   (configure-me@example.edu) admin and nothing else; then the owner grants everyone else, for example
   `grant "group:<PRI group>" viewer` and `grant "group:<editors group>" editor` with the
   group names NCSA's proxy sends. `list` shows every grant; `revoke` keeps the row.
   Until the table holds grants, `AUTH_ADMINS`, `AUTH_EDITORS` and `AUTH_VIEWERS` in the
   tier file decide.
6. Start the tier (`docker compose up -d pri-district-tracker-test`); `health.php?db=1` must
   answer 200 with `"db":"ok"`. Open `php/admin_ingest.php` through the proxy as a viewer
   (no edit controls) and as an editor (Edit, Save, Retire).
7. Nightly `pg_dump` of `<app>_live` to Taiga runs as the owner role (the estate backup job,
   pri-radiant-migration); restore it once into `<app>_test` to prove it.

The app trusts the proxy's headers only because the container publishes no port: the proxy
must strip incoming `X-Forwarded-*` headers before it sets its own.

Schema changes after go-live are new numbered files in `migrations/` (`.pgsql.sql`),
applied with `php tools/migrate.php`; an applied file is never
edited (the runner refuses a changed checksum).

## Moving to the host (PHP on PostgreSQL)

The owner retired MySQL on 2026-10-20 (Q-11). The steps that referred to cPanel and
phpMyAdmin are gone with it; the target is PostgreSQL on Radiant, and the "On Radiant"
section above is the live procedure. What follows is the short form.

1. **Create the database and role** on the tier, then put the credentials in
   `<dataFolder>/pg.env` or the environment. Never a file in the repository;
   `.env.example` lists the names.
2. **Apply the schema:** `php tools/migrate.php --live --confirm-live`. The runner
   checksums each file and refuses one that changed after it was applied.
3. **Load the data:** `php tools/load-pg.php`, which compares every row after loading.
   `py scripts/pri_sql.py` writes `sql/data.sql` for `psql` as the same data in
   PostgreSQL form, and the Data Console's *Export SQL* button does the same.
4. **Upload** to the web root: `index.html`, `handout.html`, `assets/`, the `php/` and
   `includes/` folders, and `data/geo.json` plus `data/reps.json`.
5. **Go live with the timer:** in the hosted `index.html`, change
   `<script src="data.js"></script>` to `<script src="php/data.php"></script>`.
   Records then expire the instant `show_until` passes, with no rebuild.
6. **Ingest on the host:** visit `php/admin_ingest.php` through the campus login proxy.
   The same date-stamping and *Show until* rules as the local tool, with the form and
   CSV upload. The Data Console stays the editor of record until Q-13 says otherwise.

---

## File map

| path | role |
|---|---|
| `scripts/pri_data.py` | shared data layer: load/save, freshness rule, lat/long→district |
| `scripts/admin_server.py` + `scripts/admin_ui.html` | local back-office Data Console |
| `scripts/pri_sql.py` | export `data/activities.json` → `sql/data.sql` (PostgreSQL) |
| `scripts/build_site.py` | builds the static site; filters expired records out |
| `migrations/` | numbered schema files, `.pgsql.sql` |
| `tools/migrate.php` | applies them; checksums in `schema_migrations` |
| `tools/load-pg.php` | loads `activities.json` into PostgreSQL and verifies every row |
| `sql/data.sql` | generated activity rows (upsert) |
| `includes/db.php` | the one data-access module: credentials, freshness clause, identity |
| `includes/activities.php` | the activities statements (upsert, retire, lists, JSON mapping) |
| `php/data.php` | public live read (drop-in for `data.js`) |
| `php/admin_ingest.php` | hosted back-office ingest (auth-protected) |

> **Security:** the local Data Console binds to `127.0.0.1` only and is never linked from the
> public pages. On the host, `admin_ingest.php` is the only writable surface; the campus
> login proxy supplies the identity and `ADMIN_EMAILS` decides who may write.
