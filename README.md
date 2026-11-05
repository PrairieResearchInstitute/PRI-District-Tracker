# PRI District Tracker

A district-by-district view of what the Prairie Research Institute does, for
legislators, funders and PRI staff. One curated dataset produces three things:

| Deliverable | What it is |
|---|---|
| `index.html` | The interactive tracker — pick a chamber and district, see the work. |
| `handout.html` | A print-exact one-page 8.5×11 profile for a single district. |
| `PRI-Tracker-Kit.html` | One self-contained file for the working group: explore the tracker, collate data, and read how the data works. Opens by double-click. |

Everything renders **with no internet connection**, and everything is built with the
Python standard library — nothing to install.

## Run it from a fresh clone

```bash
py scripts/make_vendor.py     # ONCE, while online: vendor the toolkit/fonts offline
py scripts/build_site.py      # build all three deliverables
```

`PRI_SKIP_REPS=1` skips the legislator refresh for a faster rebuild.
`PRI-Tracker-Kit.html` also opens by double-click.

## The main page and the backend

Run `SETUP.bat` once on each computer. Then:

| What | Start | Stop |
|---|---|---|
| **Main page**: the PHP web site users see, `index.html` served as on the host | double-click **PRI District Tracker.exe** | `tools\serve.ps1 stop` |
| **Backend**: the Data Console, where staff add and edit records | `tools\data-console.ps1 start -Open` | `tools\data-console.ps1 stop` |

Each command runs as
`powershell -NoProfile -ExecutionPolicy Bypass -File tools\<script>.ps1 <action>`.

The `.exe` runs `tools\serve.ps1 start -Open`. It starts the drive's PostgreSQL, then
PHP's own server with the app folder as the web root (as in the container), at
`http://127.0.0.1:8780` or the next free port up to 8789, and opens the page.
`serve.ps1 stop` ends the server and asks PostgreSQL to stop, which it does only when
no other app still uses it. Start the main page from a normal window: PostgreSQL
refuses to run as an administrator.

The Data Console answers at `http://127.0.0.1:8770` or the next free port up to 8779.
`status` with either script says whether it runs and on which port, and `start -Console`
runs it in the window for debugging. `py scripts/admin_server.py` still works by hand.
The server log is `data\server.log`.

The Console runs on your machine only and is never linked from the public pages. It
date-stamps every record, sets its display timer, and works out the legislative
districts from a latitude/longitude so nobody has to look them up. Click **Publish**
to rebuild the site.

## Fixing it without a code editor

Open the Data Console and choose **Code & scripts**. It lists the project's own
source - the build scripts, the PHP layer, the SQL, the docs - and lets you edit and
save any of it in the browser. Every save is syntax-checked first (a Python file that
would not import is refused rather than saved), the previous version is kept and can
be put back with one click, and every change is recorded in
`backups/studio/history.log`.

After editing a `scripts/*.py` file, restart the console (`tools\data-console.ps1 stop`,
then `start -Open`) so the change is loaded, then
press **Publish** to rebuild the site.

## Keeping it safe

```bash
py scripts/backup_data.py            # verified snapshot of the database of record
py scripts/backup_data.py --verify   # prove the newest snapshot still restores
py scripts/run_tests.py              # run the test suite
```

Schedule the backup daily (Windows Task Scheduler -> daily -> `py` with argument
`scripts\backup_data.py`, starting in the app folder). Set `PRI_BACKUP_DIR` to somewhere outside the synced
folder so a sync failure cannot take the backups with it.

## How data behaves

Nothing is ever deleted. Each record has a `show_until` date: blank means it shows
until someone retires it, a date means it drops off by itself. Retiring hides a record
but keeps it in the database. Staff collate new entries with
`templates/activities_template.csv` (or the Kit's *Add data* tab) and hand the CSV to
the data manager.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — components, workflows, known risks
- [`docs/schema.md`](docs/schema.md) — every table and field
- [`docs/api.md`](docs/api.md) — Data Console and hosted endpoints
- [`data-sources.yaml`](data-sources.yaml) — inputs, owned data and outputs
- [`docs/hosting.md`](docs/hosting.md) - deploying to a server
- [`AGENTS.md`](AGENTS.md) — rules for AI coding assistants working on this project

## Configuration

Copy `.env.example` to `.env` and fill it in. Credentials are read from the
environment and never hardcoded; `.env` is gitignored, and in production it lives
outside the repository. There is no login form — a campus authenticating proxy
supplies the user's identity.

## Status

Local build and Data Console are working. The hosted layer (`php/`, `sql/`) is
written but not yet deployed; see *Known risks* in `docs/architecture.md`.
