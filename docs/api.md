# API reference

Two surfaces: the **local Data Console** (used today) and the **hosted PHP endpoints**
(used once the app runs on a server). Both apply the same freshness rule.

## Local Data Console — `scripts/admin_server.py`

Bound to `127.0.0.1:8770` only, and never linked from the public pages. Start it with
`py scripts/admin_server.py`. Reads and writes `data/activities.json` through
`scripts/pri_data.py`.

| Method | Path | Takes | Returns / effect |
|---|---|---|---|
| GET | `/` | — | The console UI (`scripts/admin_ui.html`). |
| GET | `/api/records` | — | Every record plus `_status` (evergreen / fresh / soon / expired) and `_shown`, with today's date and counts. Reads `activities.json`. |
| GET | `/api/meta` | — | Controlled vocabularies for the form: surveys, types, scopes, statuses. |
| GET | `/api/export_sql` | — | Writes `sql/data.sql` from the current records; returns the path and row count. |
| POST | `/api/upsert` | One record as JSON | Creates or updates by `id`. Sets `ingested_at` once, refreshes `updated_at`, applies `show_until` (or clears it when evergreen), and assigns districts from lat/long when the district fields are blank. Writes `activities.json`. |
| POST | `/api/retire` | `{"id": "..."}` | Sets `show_until` to yesterday. The record leaves the public site but stays in the database. |
| POST | `/api/import_csv` | Raw CSV body | Bulk upsert in the intake-template shape. Maps `location_text`/`county` → `location` and `program`/`topic` → `group`, so nothing a collator fills in is dropped. Returns added/updated counts and per-row errors. |
| POST | `/api/build` | `{}` | Runs `scripts/build_site.py` (with `PRI_SKIP_REPS=1`) and returns the tail of the build log. |

### Authentication of console calls

Every `/api/` call must carry `X-CSRF-Token`, matching the per-run token the server
stamps into the served page as `<meta name="pri-csrf">`. The server also requires a
recognised `Host` and, when the browser sends one, a same-origin `Origin`. Anything else
gets **403**. This is not optional hardening: without it any web page open in the same
browser could POST to `127.0.0.1:8770` and overwrite project code, because a
`text/plain` body is sent cross-site with no CORS preflight to block it.

### The Studio (editing the app's own code)

| Method | Path | Takes | Returns / effect |
|---|---|---|---|
| GET | `/api/studio/tree` | - | Every file the Studio will open, with size and whether it is writable. Build outputs and the vendored bundle are excluded. |
| GET | `/api/studio/file` | `?path=` | The file's text plus the list of kept previous versions. 404 if the path is not part of the application. |
| GET | `/api/studio/backups` | `?path=` | Kept copies of one file, newest first. |
| GET | `/api/studio/log` | - | The audit trail: who saved what, when, and the size change. |
| POST | `/api/studio/save` | `{path, code}` | Parses the file, keeps the old copy, then writes atomically. **400** with a message if the parse fails - nothing is written. |
| POST | `/api/studio/restore` | `{path, name}` | Puts a kept copy back, keeping the current one first. |

Paths are resolved and then checked to be inside the project folder, so `..`, a
symlink or a Windows short name cannot reach a file outside it.

### Concurrency

Any write can return **409 Conflict** with `{"conflict": true, "error": ..., "hint": ...}`
when `data/activities.json` changed on disk since the request loaded it — someone else,
or another synced machine, saved in the meantime. Nothing is written; reload the console
and re-apply the change. `GET /api/records` also returns a `warnings` array when a sync
conflict copy is found beside the database.

## Hosted endpoints — `php/`

| File | Purpose |
|---|---|
| `php/data.php` | Public read. Emits `window.GEO`, `window.REPS` and `window.ACT` as JavaScript, so it is a drop-in replacement for the static `data.js`: change `<script src="data.js">` to `<script src="php/data.php">` and the display timer becomes live. Selects `WHERE (show_until IS NULL OR show_until >= CURRENT_DATE)`, decodes the district JSON columns back to integer arrays, and casts the booleans. |
| `php/admin_ingest.php` | Back-office ingest (form, Edit, CSV upload), gated by role (`includes/auth.php`, D-018): viewer reads, editor adds, edits and retires, admin also imports CSV. A new record is inserted whole and refused when its id exists; Edit loads a record with its `version`, and a save updates only the form's fields and is refused (409) when the record changed since it was opened (`save_activity_form()`, D-019). A CSV line for an existing id changes only the columns its file has. Every POST carries the drez-php-core CSRF token. Retire sets `show_until` to yesterday (`CURRENT_DATE - INTERVAL '1' DAY`). `DT_BACKOFFICE_WRITES=0` makes the page read-only. |
| `includes/db.php` | The one data-access module: engine switch `DB_DRIVER` (`pgsql` default, `mysql` until go-live), credentials from the environment (`DB_HOST`, `DB_PORT`, `DB_SSLMODE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) or `<dataFolder>/pg.env`, the `_test` guard, the dialect helpers and the `FRESH_WHERE` clause. Pages call the drez-php-core helpers `db_run`, `db_all`, `db_one`, `db_value` (`includes/core.php`) with bound values. |
| `includes/auth.php` | Identity and authority (D-018): the NetID, address and groups from the proxy's headers (names are settings), and the user's role from `user_roles` and the `AUTH_*` allowlists. `require_role()` stops a request with 401 or 403. |
| `tools/roles.php` | Command line, owner role: `list`, `grant <netid or group:NAME> <role>`, `revoke`. |
| `includes/activities.php` | The activities table: the canonical column list, the form/CSV upsert, retire, the public and console lists, and the JSON-record mapping the loader uses. |
| `health.php` | Process check; `?db=1` also runs `SELECT 1` through `includes/db.php` and answers 503 when the database does not. |

### Authentication and authorisation

There is no login form and no password table. An authenticating proxy (oauth2-proxy
over Campus AD or CILogon) verifies the user and passes the address in the
`X-Forwarded-Email` header, which PHP sees as `HTTP_X_FORWARDED_EMAIL`.

- `current_user_email()` reads that header, falling back to `DEV_USER` for local
  development only — it must be empty in production.
- `require_admin()` checks the address against the `ADMIN_EMAILS` allowlist and stops
  the request with 401 (not signed in) or 403 (not authorised).

The header is only trustworthy while the app is reachable **exclusively** through the
proxy. Do not publish the app's own port. An OIDC client registration for AD or
CILogon must be requested from ODSC.
