# Instructions for AI Coding Assistants

This project adheres to the **PRI AI project guide**. The institutional rules live in
`.claude/skills/pri-*` (architecture, auth, compute, data-sources, database,
documentation, secrets, sensitive-data, storage, testing) — read the relevant skill
before changing that area. The rules below are what is *specific to this project*.
When a request conflicts with an established rule, flag the conflict and propose a
compliant alternative rather than silently breaking it.

Audience: legislators, funders and PRI staff — not software engineers. Keep the
interface and any explanation plain.

## What this project is

A district-by-district view of what the Prairie Research Institute does, in three
deliverables built from one dataset:

1. `index.html` — the interactive tracker (pick a chamber + district).
2. `handout.html` — a print-exact one-page 8.5x11 profile.
3. `PRI-Tracker-Kit.html` — a single self-contained file for the working group:
   explore, add data, and read how the data works.

## Hard rules for this codebase

**Workspace.** The canonical copy is the cloud-synced
`…\OneDrive…\Desktop\Apps\PRI District Tracker`. Never edit a local Desktop copy;
two copies in parallel caused real, silent divergence. Build scripts derive their
root from `__file__`, so they always write next to their own source — never hardcode
a project path.

**It must render with no internet.** `scripts/make_vendor.py` (run once, online)
vendors the Illinois toolkit, fonts and brand assets into `assets/vendor/`, turning
every external URL into a `data:` URI. `build_site.py` then inlines that bundle.
Two traps, both already paid for:
- The toolkit registers web components and needs **module scope** — a classic
  `<script>` loads but never calls `customElements.define`, and the banner silently
  degrades. Keep `type="module"`.
- A *linked* module is CORS-blocked on `file://`. The outputs therefore **inline**
  `<script type="module">…</script>`, which works from both `file://` and http.
After any change to the head or vendor bundle, re-verify with a forced-offline
render (below). Zero external *resources* is the standard; page hyperlinks are fine.

**The handout header is the real toolkit `<ilw-header>`.** Hand-drawn or rebuilt
banners have been rejected repeatedly. The orange "Legislative District / Profile"
tag sits top-right of the header (`.ho-lh-tag`) and is required.

**Nothing is ever deleted.** Every record carries `ingested_at`, `updated_at` and
`show_until`. Blank `show_until` = evergreen; a date hides the record after it
passes; "Retire" sets it into the past. The rule lives in exactly two places and
must stay identical: `scripts/pri_data.py::fresh()` and `includes/db.php::FRESH_WHERE`.

**Saves are guarded against clobbering.** `pri_data.load_db()` fingerprints the file
and `save_db()` refuses to write if it changed underneath, raising
`ConcurrentEditError` (the console turns that into a 409 and tells the user to
reload). Pass `check=False` only for a deliberate whole-file rewrite such as a
migration. Do not remove this while the database of record is a file on a synced share.

**Every /api/ call must carry the console's session token.** Binding to `127.0.0.1`
keeps other machines out; it does NOT keep other web pages out. A page open in the same
browser can POST to localhost, and a `text/plain` body is a "simple" request that is sent
cross-site with no CORS preflight to stop it - which, against the Studio, meant any
website could rewrite this project's code. `admin_server.py` therefore checks three
things on every `/api/` call: the `Host` header (defeats DNS rebinding), the `Origin` if
present, and a per-run token (`CSRF_TOKEN`) that the server stamps into the page's
`<head>` and the UI echoes back as `X-CSRF-Token`. Only a same-origin page can read that
token, and a cross-origin request cannot set a custom header without a preflight the
server refuses. Do not remove any of the three, and keep `api()` in `admin_ui.html`
sending the header or the console locks itself out.

**The Studio edits this app's own code, and its guard rails are load-bearing.**
`scripts/studio.py` (modelled on the Studio in PRI Facilities Request) is reachable
from the Data Console's *Code & scripts* tab so someone other than the original author
can fix things. Four properties must hold; do not weaken any of them:
*confined* (paths are RESOLVED then checked to be inside the project, so `..`, a
symlink or a Windows short name cannot walk out), *checked* (Python and JSON are
parsed before writing; a file that would not import is refused, not saved),
*reversible* (every save copies the old file aside first), *recorded*
(`backups/studio/history.log` gets who/what/when/delta). Build outputs are not
editable there - the next build would silently undo the edit. If the Console is ever
exposed beyond `127.0.0.1`, the Studio needs its own access grant, the way Facilities
grants `studio` separately from being an administrator.

**Districts are integers.** The front end matches with `indexOf(Number(n))`, so
`us_house`/`il_senate`/`il_house` must hold ints, not strings.

**Ingest is off the front end.** `scripts/admin_server.py` binds to `127.0.0.1`
only and is never linked from the public pages.

## Security and data

- Read every credential from an environment variable (`includes/db.php` does; on this
  computer it reads `<dataFolder>/pg.env` for PostgreSQL).
  `.env` is gitignored; add new variable names to `.env.example`.
- No username/password table and no custom login. An authenticating proxy over
  Campus AD or CILogon supplies the identity in `X-Forwarded-Email`;
  `require_admin()` checks it against `ADMIN_EMAILS`. `DEV_USER` is local-only and
  must be empty in production.
- Do not load real personnel, HR or restricted data. Activity records describe
  public research work.

## Documentation

With each change, update `docs/`, `data-sources.yaml` and the tests, then tell the
user which documents changed.

## Standard commands

```bash
py scripts/make_vendor.py        # once, ONLINE: build the offline bundle
py scripts/build_site.py         # build index/handout/Kit  (PRI_SKIP_REPS=1 skips the rep refresh)
py scripts/make_templates.py     # regenerate the staff intake CSV templates
py scripts/admin_server.py       # local Data Console -> http://127.0.0.1:8770
py scripts/pri_sql.py            # activities.json -> sql/data.sql (--dialect pgsql -> sql/data.pgsql.sql)
py scripts/backup_data.py        # verified snapshot of owned data (schedule this daily)
py scripts/run_tests.py          # the test suite - run before and after a change
```

Forced-offline verification (a dead proxy fails all http; `file://` and `data:` still work):

```bash
chrome --headless=new --proxy-server="127.0.0.1:1" \
  --screenshot=out.png "file:///…/PRI-Tracker-Kit.html"
```
