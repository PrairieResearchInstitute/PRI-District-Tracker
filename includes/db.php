<?php
// PRI District Tracker - the one data-access module of the hosted layer.
//
// Every page, tool and test opens the database here and nowhere else. Pages run
// their SQL through the drez-php-core helpers db_run, db_all, db_one and db_value
// (includes/core.php, pulled with the library's tools/sync.php), always with bound
// values (drez-db-access rule 1, decision D-015).
//
// Engine (one setting, read once, so a request can never talk to two databases):
//   DB_DRIVER=pgsql   the default (owner Q-06, 2026-10-12): PostgreSQL, the Radiant target;
//                     until the move the estate cluster on the portable drive,
//                     127.0.0.1 port 5433 (platform D-028)
//   DB_DRIVER=mysql   the MySQL layer as first written; never deployed, kept selectable
//                     only until go-live on Radiant, then deleted (D-017)
//
// Credentials (PRI rules in .claude/skills/pri-secrets and pri-auth):
//   1. the environment: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD and the
//      optional DB_SSLMODE (the hosted tiers' environment files; .env.example lists
//      the names). Used whenever DB_NAME is set. On Radiant every value comes from
//      the tier's file, so the move fills in values and changes no code: DB_PORT
//      defaults to the engine's standard port (5432 on PostgreSQL), never to the
//      drive cluster's 5433.
//   2. PostgreSQL only: <dataFolder>/pg.env, written by the owner for the estate
//      cluster on the drive with PGHOST, PGPORT (5433), PGDATABASE, PGUSER,
//      PGPASSWORD and PGTESTDATABASE; a pg.env naming another port is refused.
//      dataFolder comes from config.local.json and is relative to the app folder,
//      so no path is written here. The cluster is started and stopped by
//      scripts/estate_pg.py (platform D-028, decision D-015).
// No value is ever printed: errors name variables and files, never their contents.
//
// Tests: DT_DB_TARGET=test selects the test database (DB_TEST_NAME, or
// PGTESTDATABASE from pg.env) and refuses any name that does not end in _test,
// before connecting (drez-sqlite-to-postgres-port rule 5).
//
// Identity: no username/password table and no custom login. An authenticating
// proxy in front of the app verifies the user's NetID; includes/auth.php reads the
// proxy's headers and decides the user's role (admin, editor, viewer).

declare(strict_types=1);

require_once __DIR__ . '/core.php';

const DB_DRIVERS = ['mysql', 'pgsql'];
const PG_ENV_KEYS = ['PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD', 'PGTESTDATABASE'];
// The estate cluster on the portable drive (platform D-028). pg.env exists only on the
// drive, so a pg.env naming any other port points at a server the estate does not use.
const PG_DRIVE_PORT = '5433';
// A server named in the environment (Radiant) listens on PostgreSQL's own port unless
// DB_PORT says otherwise.
const PG_STANDARD_PORT = '5432';
const PG_SSLMODES = ['disable', 'allow', 'prefer', 'require', 'verify-ca', 'verify-full'];

/** Stop with a configuration message. A command line gets an exception it can report. */
function db_fail(string $message): never {
    if (PHP_SAPI === 'cli') {
        throw new RuntimeException($message);
    }
    http_response_code(500);
    error_log('pri-district-tracker: ' . $message);
    exit('Configuration error: ' . htmlspecialchars($message));
}

/** Read a required environment variable, or fail loudly. Never returns a secret default. */
function env_str(string $name, ?string $default = null): string {
    $v = getenv($name);
    if ($v === false || $v === '') {
        if ($default !== null) {
            return $default;
        }
        db_fail('environment variable ' . $name . ' is not set. Copy .env.example to .env and fill it in.');
    }
    return $v;
}

/** The app folder (the parent of includes/). */
function app_root(): string {
    return dirname(__DIR__);
}

/**
 * The data folder named by config.local.json (dataFolder, relative to the app
 * folder), or null when there is none. The same rule as scripts/app_config.py:
 * an absolute path is refused, and a backslash counts as a separator on Linux too.
 */
function app_data_folder(?string $root = null): ?string {
    $root = $root ?? app_root();
    $file = $root . DIRECTORY_SEPARATOR . 'config.local.json';
    if (!is_file($file)) {
        return null;
    }
    $cfg = json_decode((string) file_get_contents($file), true);
    if (!is_array($cfg)) {
        db_fail('config.local.json does not hold a JSON object.');
    }
    $value = trim((string) ($cfg['dataFolder'] ?? ''));
    if ($value === '') {
        return null;
    }
    if (preg_match('/^([A-Za-z]:|[\\\\\/])/', $value)) {
        db_fail('dataFolder in config.local.json must be relative to the app folder.');
    }
    $parts = [];
    foreach (preg_split('/[\\\\\/]+/', $root . '/' . $value) as $p) {
        if ($p === '..') {
            array_pop($parts);
        } elseif ($p !== '.' && $p !== '') {
            $parts[] = $p;
        }
    }
    $lead = (str_starts_with($root, '/') ? '/' : '');
    return $lead . implode(DIRECTORY_SEPARATOR, $parts);
}

/** <dataFolder>/pg.env, or null when no data folder is configured. */
function pg_env_file(?string $root = null): ?string {
    $folder = app_data_folder($root);
    return $folder === null ? null : $folder . DIRECTORY_SEPARATOR . 'pg.env';
}

/** The PG* settings in a pg.env file. Only the six known names are kept; nothing is echoed. */
function pg_env_read(string $path): array {
    $out = [];
    $lines = @file($path, FILE_IGNORE_NEW_LINES);
    if ($lines === false) {
        db_fail('cannot read ' . basename($path) . ' in the data folder.');
    }
    foreach ($lines as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#' || !str_contains($line, '=')) {
            continue;
        }
        [$k, $v] = explode('=', $line, 2);
        $k = trim($k);
        $v = trim($v);
        if (strlen($v) >= 2 && ($v[0] === '"' || $v[0] === "'") && substr($v, -1) === $v[0]) {
            $v = substr($v, 1, -1);
        }
        if (in_array($k, PG_ENV_KEYS, true)) {
            $out[$k] = $v;
        }
    }
    return $out;
}

/** The engine: DB_DRIVER, read once per process. */
function db_driver(): string {
    static $driver = null;
    if ($driver === null) {
        $v = strtolower(trim((string) (getenv('DB_DRIVER') ?: 'pgsql')));
        if (!in_array($v, DB_DRIVERS, true)) {
            db_fail('DB_DRIVER must be mysql or pgsql.');
        }
        $driver = $v;
    }
    return $driver;
}

/** 'test' when DT_DB_TARGET=test, else 'live'. */
function db_target(): string {
    return strtolower(trim((string) (getenv('DT_DB_TARGET') ?: ''))) === 'test' ? 'test' : 'live';
}

/**
 * Where to connect: driver, host, port, name, user, password, source.
 * The password stays inside this array; callers never print it.
 */
function db_settings(?string $root = null): array {
    $driver = db_driver();
    $test = db_target() === 'test';
    if ((string) getenv('DB_NAME') !== '') {
        $s = [
            'host' => env_str('DB_HOST', $driver === 'pgsql' ? '127.0.0.1' : 'localhost'),
            'port' => (string) (getenv('DB_PORT') ?: ($driver === 'pgsql' ? PG_STANDARD_PORT : '')),
            'name' => $test ? env_str('DB_TEST_NAME') : env_str('DB_NAME'),
            'sslmode' => strtolower(trim((string) (getenv('DB_SSLMODE') ?: ''))),
            'user' => env_str('DB_USER'),
            'password' => env_str('DB_PASSWORD'),
            'source' => 'environment',
        ];
    } elseif ($driver === 'pgsql') {
        $file = pg_env_file($root);
        if ($file === null) {
            db_fail('no DB_NAME in the environment and no dataFolder in config.local.json, so there is no pg.env to read. Run SETUP.bat.');
        }
        if (!is_file($file)) {
            db_fail('no DB_NAME in the environment and no pg.env in the data folder. The owner writes it for the estate cluster on the drive (port 5433).');
        }
        $pg = pg_env_read($file);
        foreach (['PGUSER', 'PGPASSWORD', $test ? 'PGTESTDATABASE' : 'PGDATABASE'] as $k) {
            if (($pg[$k] ?? '') === '') {
                db_fail('pg.env in the data folder has no ' . $k . '.');
            }
        }
        $s = [
            'host' => $pg['PGHOST'] ?? '127.0.0.1',
            'port' => ($pg['PGPORT'] ?? '') !== '' ? $pg['PGPORT'] : PG_DRIVE_PORT,
            'name' => $test ? $pg['PGTESTDATABASE'] : $pg['PGDATABASE'],
            'user' => $pg['PGUSER'],
            'password' => $pg['PGPASSWORD'],
            'source' => 'pg.env',
        ];
        if ($s['port'] !== PG_DRIVE_PORT) {
            db_fail('pg.env in the data folder names port ' . $s['port'] . ', but the estate PostgreSQL on the drive listens on '
                    . PG_DRIVE_PORT . ' (platform D-028). The owner regenerates pg.env for the drive cluster.');
        }
    } else {
        db_fail('environment variable DB_NAME is not set. Copy .env.example to .env and fill it in.');
    }
    if ($test && !str_ends_with($s['name'], '_test')) {
        db_fail('Refusing to run: the test target must be a database whose name ends in _test, and "'
                . $s['name'] . '" does not.');
    }
    $s['driver'] = $driver;
    return $s;
}

/** The DSN for a settings array (no user or password in it). */
function db_dsn(array $s): string {
    if ($s['driver'] === 'pgsql') {
        $ssl = (string) ($s['sslmode'] ?? '');
        if ($ssl !== '' && !in_array($ssl, PG_SSLMODES, true)) {
            db_fail('DB_SSLMODE must be one of ' . implode(', ', PG_SSLMODES) . '.');
        }
        return 'pgsql:host=' . $s['host'] . ';port=' . ($s['port'] !== '' ? $s['port'] : PG_DRIVE_PORT) . ';dbname=' . $s['name']
             . ($ssl !== '' ? ';sslmode=' . $ssl : '');
    }
    return 'mysql:host=' . $s['host'] . ($s['port'] !== '' ? ';port=' . $s['port'] : '')
         . ';dbname=' . $s['name'] . ';charset=utf8mb4';
}

/** The time zone whose calendar decides "today" for the display timer. */
function app_timezone(): string {
    $tz = trim((string) (getenv('APP_TIMEZONE') ?: 'America/Chicago'));
    if (!in_array($tz, timezone_identifiers_list(), true)) {
        db_fail('APP_TIMEZONE is not a known time zone name.');
    }
    return $tz;
}

/** The shared connection, opened once. Every page calls this or the db_* helpers. */
function pdo(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $s = db_settings();
        $opts = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ];
        if ($s['driver'] === 'pgsql') {
            // Real server-side prepares: a value never becomes part of the SQL text.
            $opts[PDO::ATTR_EMULATE_PREPARES] = false;
        }
        // Least privilege: the user should be the app role, not the database admin.
        $pdo = new PDO(db_dsn($s), $s['user'], $s['password'], $opts);
        db_use($pdo);
        if ($s['driver'] === 'pgsql') {
            // CURRENT_DATE follows the session time zone, and a server's default is
            // whatever its installer chose (often UTC on a VM). The display timer
            // means the Illinois calendar, as fresh() does on the staff computer,
            // so the session and PHP's own clock both use APP_TIMEZONE.
            $tz = app_timezone();
            date_default_timezone_set($tz);
            db_run("SELECT set_config('TimeZone', ?, false)", [$tz]);
        }
    }
    return $pdo;
}

/** Run $fn inside one transaction: commit when it returns, roll back and rethrow when it throws. */
function db_transaction(callable $fn): mixed {
    $pdo = pdo();
    $pdo->beginTransaction();
    try {
        $result = $fn();
        $pdo->commit();
        return $result;
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }
}

// ----------------------------------------------------------------- dialect
// Only what has no form both engines accept lives here; everything else is
// written once in SQL both understand (CURRENT_DATE, NOW(), INTERVAL '1' DAY).

/** Quote a column or table name for the engine. Names come from code, never from a request. */
function db_ident(string $name, ?string $driver = null): string {
    if (!preg_match('/^[a-z_][a-z0-9_]*$/', $name)) {
        throw new InvalidArgumentException('Not a plain column or table name: ' . $name);
    }
    return ($driver ?? db_driver()) === 'pgsql' ? '"' . $name . '"' : '`' . $name . '`';
}

/**
 * INSERT ... that updates the row when the key exists.
 *   $keepFirst  columns whose stored value wins once set (ingested_at)
 *   $bump       integer columns incremented on every update (version)
 * MySQL: ON DUPLICATE KEY UPDATE c = VALUES(c). PostgreSQL: ON CONFLICT (key) DO
 * UPDATE SET c = EXCLUDED.c. Named placeholders :<column>. $driver defaults to
 * db_driver(); the tests pass it to see both forms.
 */
function db_upsert_sql(string $table, array $cols, string $key, array $keepFirst = [], array $bump = [], ?string $driver = null): string {
    $driver = $driver ?? db_driver();
    $id = fn(string $n) => db_ident($n, $driver);
    $t = $id($table);
    $q = array_map($id, $cols);
    $ph = array_map(fn($c) => ':' . $c, $cols);
    $pg = $driver === 'pgsql';
    $set = [];
    foreach ($cols as $c) {
        if ($c === $key) {
            continue;
        }
        $new = $pg ? 'EXCLUDED.' . $id($c) : 'VALUES(' . $id($c) . ')';
        $set[] = in_array($c, $keepFirst, true)
            ? $id($c) . ' = COALESCE(' . $t . '.' . $id($c) . ', ' . $new . ')'
            : $id($c) . ' = ' . $new;
    }
    foreach ($bump as $c) {
        $set[] = $id($c) . ' = ' . $t . '.' . $id($c) . ' + 1';
    }
    $sql = 'INSERT INTO ' . $t . ' (' . implode(', ', $q) . ') VALUES (' . implode(', ', $ph) . ') ';
    return $sql . ($pg
        ? 'ON CONFLICT (' . $id($key) . ') DO UPDATE SET ' . implode(', ', $set)
        : 'ON DUPLICATE KEY UPDATE ' . implode(', ', $set));
}

// ----------------------------------------------------------------- identity
// Identity and authority live in includes/auth.php (NetID from the campus proxy,
// role from the user's NetID or campus group, owner 2026-10-12, D-018).

// ----------------------------------------------------------------- shared SQL
// The freshness rule lives in ONE place (mirrors scripts/pri_data.py `fresh`):
// a row shows only while show_until is NULL (evergreen) or today or later.
// CURRENT_DATE is standard SQL, so the clause is identical on MySQL and PostgreSQL.
const FRESH_WHERE = '(show_until IS NULL OR show_until >= CURRENT_DATE)';
