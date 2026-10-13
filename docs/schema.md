# Database schema

Written from `migrations/` (PostgreSQL `*.pgsql.sql`, MySQL `*.mysql.sql`) and `sql/schema.sql` (the MySQL schema in one file). Update this page whenever a migration is added; `tests/test_schema_parity.py` checks the column lists agree.

Types differ only where the engines do: `TINYINT(1)` on MySQL is `BOOLEAN` on PostgreSQL, `DATETIME` is `TIMESTAMP`, `DECIMAL` is `NUMERIC`. The tables are listed with their MySQL types.

The same field names are used end to end: the JSON records in `data/activities.json`, the Data Console, `scripts/pri_sql.py` and the PHP layer all share them, so nothing has to be renamed as data moves from the local tool to the hosted database. The SQL reserved word `group` is quoted: back-quoted on MySQL, double-quoted on PostgreSQL. `lead` is back-quoted on MySQL, where it is reserved from version 8.0.2.


## `activities`

| column | type | meaning |
|---|---|---|
| `id` | VARCHAR(64) | stable slug, matches the local JSON id (required, primary key) |
| `survey` | VARCHAR(8) | INHS/ISGS/ISWS/ISAS/ISTC (required, default 'INHS') |
| `title` | VARCHAR(255) | (required) |
| `type` | VARCHAR(40) | (required, default 'Project') |
| `topic` | VARCHAR(80) | (default '') |
| `group` | VARCHAR(120) | "Program area" (reserved word -> backticked) (default '') |
| `summary` | TEXT |  |
| `description` | TEXT |  |
| `lead` | VARCHAR(160) | (default '') |
| `program` | VARCHAR(160) | (default '') |
| `funder` | VARCHAR(255) | (default '') |
| `partners` | VARCHAR(255) | (default '') |
| `status` | VARCHAR(60) | (default '') |
| `start_year` | VARCHAR(20) | (default '') |
| `end_year` | VARCHAR(20) | (default '') |
| `url` | VARCHAR(400) | (default '') |
| `image` | VARCHAR(400) | photo shown in the drill-in popup / handout feature (default '') |
| `scope` | VARCHAR(20) | statewide/sited/regional/external (required, default 'statewide') |
| `latitude` | DECIMAL(9,6) |  |
| `longitude` | DECIMAL(9,6) |  |
| `county` | VARCHAR(60) | (default '') |
| `location` | VARCHAR(255) | (default '') |
| `us_house` | VARCHAR(160) | JSON int array, e.g. [13] (default '[]') |
| `il_senate` | VARCHAR(160) | (default '[]') |
| `il_house` | VARCHAR(160) | (default '[]') |
| `featured` | TINYINT(1) | (required, default 0) |
| `confirm` | TINYINT(1) | (required, default 0) |
| `keywords` | VARCHAR(255) | (default '') |
| `notes` | TEXT |  |
| `theme` | VARCHAR(60) | (default '') |
| `ingested_at` | DATETIME | first load (set once) |
| `updated_at` | DATETIME | last edit / re-ingest (resets freshness) |
| `show_until` | DATE | NULL = evergreen; else hides after this date |
| `version` | INT | +1 on every write (migration 0002) (required, default 1) |
| `region` | VARCHAR(60) | e.g. "Chicago metro", from activities.json (migration 0003) (default '') |
| `historic` | TINYINT(1) | the historic flag from activities.json (migration 0003) (required, default 0) |

## `awards`

| column | type | meaning |
|---|---|---|
| `award_id` | VARCHAR(64) | (required, primary key) |
| `survey` | VARCHAR(8) | (required, default 'INHS') |
| `activity_id` | VARCHAR(64) | links the money to an activity (and its districts) (default '') |
| `activity_title` | VARCHAR(255) | (default '') |
| `award_title` | VARCHAR(255) | (required) |
| `description` | TEXT |  |
| `sponsor` | VARCHAR(160) | (default '') |
| `amount` | BIGINT | whole dollars (default 0) |
| `start_year` | VARCHAR(20) | (default '') |
| `end_year` | VARCHAR(20) | (default '') |
| `pi` | VARCHAR(160) | (default '') |
| `status` | VARCHAR(40) | (default '') |
| `url` | VARCHAR(400) | (default '') |
| `notes` | TEXT |  |
| `ingested_at` | DATETIME |  |
| `updated_at` | DATETIME |  |
| `show_until` | DATE |  |

## `settings`

| column | type | meaning |
|---|---|---|
| `k` | VARCHAR(64) | (required, primary key) |
| `v` | VARCHAR(255) | (required) |

## `user_roles`

Migration 0004 (D-018). Who holds which role, by NetID or campus group. The running app
only reads it; `tools/roles.php`, run as the owner role, writes it.

| Column | PostgreSQL | MySQL | Notes |
|---|---|---|---|
| `principal_kind` | `VARCHAR(10)` | `VARCHAR(10)` | `netid` or `group`; part of the key |
| `principal` | `VARCHAR(255)` | `VARCHAR(255)` | lowercase NetID or campus group name; part of the key |
| `role` | `VARCHAR(10)` | `VARCHAR(10)` | `admin`, `editor` or `viewer` |
| `note` | `VARCHAR(255)` | `VARCHAR(255)` | why the grant exists |
| `granted_by` | `VARCHAR(255)` | `VARCHAR(255)` | NetID of whoever ran the grant |
| `granted_at` | `TIMESTAMP` | `DATETIME` | set on each grant |
| `revoked_at` | `TIMESTAMP NULL` | `DATETIME NULL` | set by a revoke; the row stays, a later grant clears it |

A user's role is the highest active grant to the user's NetID or any of the user's
groups, together with the fallback allowlists in the environment (`includes/auth.php`).

## The lifecycle stamps

Three columns drive the display timer. They behave identically in the JSON file and
in SQL:

| field | meaning |
|---|---|
| `ingested_at` | when the record was first loaded (set once) |
| `updated_at` | last edit or re-ingest — re-ingesting refreshes the record |
| `show_until` | **NULL/blank = evergreen**; a date hides the record after it passes |

Nothing is deleted. "Retire" sets `show_until` to yesterday, so the record leaves the
public site but stays in the database and can be revived by clearing the date.

The freshness rule exists in exactly two places and must stay identical:
`scripts/pri_data.py::fresh()` and `includes/db.php::FRESH_WHERE`
(`show_until IS NULL OR show_until >= CURRENT_DATE`, standard SQL on both engines).

## District fields

`us_house`, `il_senate` and `il_house` hold **integer** district numbers (stored as a
JSON array in SQL, e.g. `[13]`). The front end matches with `indexOf(Number(n))`, so
strings will silently fail to match. For `scope = statewide` the arrays are empty and
the record shows in every district; `external` shows in none.

