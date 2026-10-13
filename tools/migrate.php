<?php
/**
 * tools/migrate.php: numbered schema migrations for the hosted layer, on MySQL or
 * PostgreSQL, run from the command line through includes/db.php.
 *
 * Built from the drez-db-access PHP track template (decision D-003) with the
 * registry rules of drez-append-only-migrations: never edit an applied migration
 * (a checksum proves it), record failures, one transaction per migration on
 * PostgreSQL, stop at the first failure.
 *
 * Files, in migrations/:
 *   0001_baseline.pgsql.sql     PostgreSQL, beside
 *   0001_baseline.mysql.sql     its MySQL twin (same number and name)
 *   0004_x.sql                  one file that runs on both engines
 *
 * Engine and credentials come from includes/db.php: DB_DRIVER (mysql default,
 * pgsql), then the environment or <dataFolder>/pg.env. Nothing is read from the
 * command line, so no password ever appears in a process list.
 *
 * Usage:
 *   php tools/migrate.php [--test] [--status] [--dry]
 *   php tools/migrate.php --live --confirm-live            the real database
 *   php tools/migrate.php ... --mark-applied 0001 --owner-approved
 *   --test   the test database (name must end in _test); same as DT_DB_TARGET=test
 *   --live   required, with --confirm-live, to change the real database
 *
 * Registry: schema_migrations(version, name, checksum, applied_at, status, error).
 * Only status 'ok' counts as applied; a failed row is retried next run.
 * MySQL commits each DDL statement by itself, so a failed MySQL migration can be
 * half applied; the failure is still recorded and nothing after it runs.
 * Exit codes: 0 done, 1 a migration failed or a checksum changed, 2 usage.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {   // a command-line tool; never served (the image also refuses tools/)
    http_response_code(404);
    exit;
}

$opts = getopt('', ['test', 'live', 'confirm-live', 'dry', 'status', 'mark-applied:', 'owner-approved', 'dir:']);
$say = fn(string $s) => fwrite(STDOUT, $s . PHP_EOL);
$fail = function (string $s, int $code = 1): never { fwrite(STDERR, $s . PHP_EOL); exit($code); };

if (isset($opts['test'])) {
    putenv('DT_DB_TARGET=test');
}
require __DIR__ . '/../includes/db.php';

$readOnly = isset($opts['status']) || isset($opts['dry']);
if (db_target() !== 'test' && !$readOnly && !(isset($opts['live']) && isset($opts['confirm-live']))) {
    $fail('Refusing to change the real database without --live --confirm-live. Use --test for the test database, or --status to look.', 2);
}

try {
    $pdo = pdo();
    $s = db_settings();
} catch (Throwable $e) {
    $fail('Cannot connect: ' . $e->getMessage(), 2);
}
$driver = db_driver();
$say($driver . ' database ' . $s['name'] . ' as ' . db_value($driver === 'pgsql' ? 'SELECT current_user' : 'SELECT CURRENT_USER()')
     . ' (' . db_target() . ', settings from ' . $s['source'] . ')');

$dir = $opts['dir'] ?? (dirname(__DIR__) . DIRECTORY_SEPARATOR . 'migrations');
if (!is_dir($dir)) {
    $fail('No migrations folder at ' . $dir, 2);
}
$found = [];
foreach (scandir($dir) as $f) {
    if (!preg_match('/^(\d{4})_([a-z0-9_]+?)(?:\.(mysql|pgsql))?\.sql$/', $f, $m)) {
        continue;
    }
    [, $v, $name] = $m;
    $engine = $m[3] ?? '';
    if ($engine !== '' && $engine !== $driver) {
        $found[$v]['twin'] = true;
        continue;
    }
    if (isset($found[$v]['file'])) {
        $fail('Two migrations claim number ' . $v . ': ' . basename($found[$v]['file']) . ' and ' . $f, 2);
    }
    $found[$v] = ($found[$v] ?? []) + ['name' => $name, 'file' => $dir . DIRECTORY_SEPARATOR . $f];
}
ksort($found, SORT_STRING);
foreach ($found as $v => $m) {
    if (!isset($m['file'])) {
        $fail('Migration ' . $v . ' has no file for ' . $driver . ' (only its twin for the other engine).', 2);
    }
}

// The registry is created only when something is about to be recorded, so
// --status, --dry and a refused --mark-applied never write to the database.
$ensureRegistry = fn() => db_run('CREATE TABLE IF NOT EXISTS schema_migrations (
    version    VARCHAR(16) PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    checksum   VARCHAR(64) NOT NULL,
    applied_at VARCHAR(32) NOT NULL,
    status     VARCHAR(8) NOT NULL,
    error      TEXT
)');
$hasRegistry = (int) db_value($driver === 'pgsql'
    ? "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = 'schema_migrations'"
    : "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'schema_migrations'") > 0;
$applied = [];
if ($hasRegistry) {
    foreach (db_all('SELECT version, name, checksum, status FROM schema_migrations') as $r) {
        $applied[$r['version']] = $r;
    }
}
$sum = fn(string $file) => hash('sha256', str_replace("\r\n", "\n", (string) file_get_contents($file)));
$now = fn() => gmdate('Y-m-d\TH:i:s\Z');
$record = function (string $v, string $name, string $checksum, string $status, ?string $error) use ($now) {
    db_run('DELETE FROM schema_migrations WHERE version = ?', [$v]);
    db_run('INSERT INTO schema_migrations (version, name, checksum, applied_at, status, error) VALUES (?, ?, ?, ?, ?, ?)',
        [$v, $name, $checksum, $now(), $status, $error]);
};

// Frozen check: an applied migration may never change or disappear.
$problems = [];
foreach ($applied as $v => $r) {
    if ($r['status'] !== 'ok') {
        continue;
    }
    if (!isset($found[$v])) {
        $problems[] = 'migration ' . $v . ' (' . $r['name'] . ') was applied but its file is gone';
    } elseif ($sum($found[$v]['file']) !== $r['checksum']) {
        $problems[] = 'migration ' . $v . ' changed after it was applied; put the change in a new migration';
    }
}
if ($problems) {
    $fail('Refusing to run: ' . implode('; ', $problems) . '.');
}

$pending = array_filter($found, fn($v) => !isset($applied[$v]) || $applied[$v]['status'] !== 'ok', ARRAY_FILTER_USE_KEY);

if (isset($opts['mark-applied'])) {
    $v = (string) $opts['mark-applied'];
    if (!isset($opts['owner-approved'])) {
        $fail('Stop and ask: marking ' . $v . ' writes to the database. Rerun with --owner-approved once the owner has said yes.');
    }
    if (!isset($found[$v])) {
        $fail('No migration numbered ' . $v . '.', 2);
    }
    if (count($applied) > 0) {
        $fail('Refusing: schema_migrations already records ' . implode(', ', array_keys($applied)) . '.');
    }
    $ensureRegistry();
    $record($v, $found[$v]['name'], $sum($found[$v]['file']), 'ok', null);
    $say('marked ' . $v . '_' . $found[$v]['name'] . ' as applied without running it.');
    exit(0);
}

$say('declared ' . count($found) . ', applied ' . (count($found) - count($pending)) . ', pending ' . count($pending));
if ($readOnly) {
    foreach ($pending as $v => $m) {
        $say('  pending ' . $v . '_' . $m['name'] . ' (' . basename($m['file']) . ')');
    }
    exit(0);
}

if ($pending) {
    $ensureRegistry();
}
foreach ($pending as $v => $m) {
    $sql = (string) file_get_contents($m['file']);
    $checksum = $sum($m['file']);
    try {
        if ($driver === 'pgsql') {
            $pdo->beginTransaction();
            $pdo->exec($sql);   // a whole migration file: DDL with no values, so nothing to bind
            $record($v, $m['name'], $checksum, 'ok', null);
            $pdo->commit();
        } else {
            $pdo->exec($sql);
            $record($v, $m['name'], $checksum, 'ok', null);
        }
        $say('applied ' . $v . '_' . $m['name']);
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        $record($v, $m['name'], $checksum, 'failed', $e->getMessage());
        $fail('FAILED ' . $v . '_' . $m['name'] . ': ' . $e->getMessage() . ' (recorded; later migrations not run)');
    }
}
$say('done.');
