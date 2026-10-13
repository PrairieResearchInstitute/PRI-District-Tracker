<?php
/**
 * tools/load-pg.php: load data/activities.json (or a copy of it) into PostgreSQL
 * and prove the load, row by row and by checksum.
 *
 * Verification is the point of this script (drez-sqlite-to-postgres-port rule 9):
 * a load that silently drops or mangles rows looks exactly like one that worked.
 * After writing, every field of every row is read back and compared with the
 * source in a normalised form (numbers as numbers, dates as dates, district lists
 * as integer lists), the id sets must be identical, and a SHA-256 over the
 * normalised rows must agree on both sides. Any difference prints FAILED and the
 * exit code is 1.
 *
 * The source is opened read-only and its hash is checked again at the end, so the
 * run proves it did not change the file. Records keep their own ids; nothing is
 * re-stamped (ingested_at, updated_at and show_until come from the source). The
 * tables carry no sequences, so no sequence needs resetting after the load.
 *
 * Usage (credentials from includes/db.php: the environment or <dataFolder>/pg.env):
 *   php tools/load-pg.php --source <file.json> --test
 *   php tools/load-pg.php --source data/activities.json --live --confirm-live
 *   --verify-only    compare without writing
 *   --refresh        allow loading into a table that already holds rows (upsert)
 *   --allow-unmapped load although some source fields have no column (they are dropped)
 *
 * Exit codes: 0 VERIFIED, 1 FAILED, 2 usage or refused.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {   // a command-line tool; never served (the image also refuses tools/)
    http_response_code(404);
    exit;
}

$opts = getopt('', ['source:', 'test', 'live', 'confirm-live', 'verify-only', 'refresh', 'allow-unmapped']);
$say = fn(string $s) => fwrite(STDOUT, $s . PHP_EOL);
$stop = function (string $s, int $code = 2): never { fwrite(STDERR, $s . PHP_EOL); exit($code); };

if ((string) getenv('DB_DRIVER') === '') {
    putenv('DB_DRIVER=pgsql');
}
if (isset($opts['test'])) {
    putenv('DT_DB_TARGET=test');
}
require __DIR__ . '/../includes/activities.php';

if (db_driver() !== 'pgsql') {
    $stop('This loader targets PostgreSQL; DB_DRIVER is ' . db_driver() . '.');
}
if (!isset($opts['source'])) {
    $stop('Usage: php tools/load-pg.php --source <activities.json> (--test | --live --confirm-live) [--verify-only] [--refresh]');
}
if (db_target() !== 'test' && !(isset($opts['live']) && isset($opts['confirm-live']))) {
    $stop('Refusing to touch the real database without --live --confirm-live. Use --test for the test database.');
}

// ---- the source, read-only ----
$src = (string) $opts['source'];
if (!is_file($src)) {
    $stop('No source file at ' . $src . '.');
}
$hashBefore = hash_file('sha256', $src);
$doc = json_decode((string) file_get_contents($src), true);
if (!is_array($doc) || !isset($doc['activities']) || !is_array($doc['activities'])) {
    $stop($src . ' does not hold an "activities" list.');
}
$records = $doc['activities'];
$cols = activity_columns();
$expected = [];
$unmapped = [];
foreach ($records as $i => $rec) {
    $id = trim((string) ($rec['id'] ?? ''));
    if ($id === '') {
        $stop('Record ' . ($i + 1) . ' has no id; every record must keep its own id.');
    }
    if (isset($expected[$id])) {
        $stop('Two records share the id ' . $id . '.');
    }
    foreach (array_diff(array_keys($rec), $cols) as $k) {
        $unmapped[$k] = ($unmapped[$k] ?? 0) + 1;
    }
    $expected[$id] = activity_from_json($rec);
}
if ($unmapped && !isset($opts['allow-unmapped'])) {
    $list = [];
    foreach ($unmapped as $k => $n) { $list[] = $k . ' (' . $n . ')'; }
    $stop('Source fields with no column would be dropped: ' . implode(', ', $list)
          . '. Add a migration for them, or pass --allow-unmapped to drop them knowingly.');
}

// ---- the database ----
try {
    pdo();
    $s = db_settings();
} catch (Throwable $e) {
    $stop('Cannot connect: ' . $e->getMessage());
}
$say('source   ' . $src . ' (' . count($records) . ' records, sha256 ' . substr($hashBefore, 0, 16) . ')');
$say('target   PostgreSQL ' . $s['name'] . ' (' . db_target() . ', settings from ' . $s['source'] . ')');

$migrations = glob(dirname(__DIR__) . '/migrations/[0-9][0-9][0-9][0-9]_*.pgsql.sql') ?: [];
$hasRegistry = (int) db_value("SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = current_schema() AND table_name = 'schema_migrations'") > 0;
$ok = $hasRegistry ? (int) db_value("SELECT COUNT(*) FROM schema_migrations WHERE status = 'ok'") : 0;
if ($ok < count($migrations)) {
    $stop('The schema is behind: ' . $ok . ' of ' . count($migrations) . ' migrations applied. Run tools/migrate.php first.');
}

$before = (int) db_value('SELECT COUNT(*) FROM activities');
if (!isset($opts['verify-only'])) {
    if ($before > 0 && !isset($opts['refresh'])) {
        $stop('activities already holds ' . $before . ' rows. Pass --refresh to upsert over them, or --verify-only to compare.');
    }
    try {
        db_transaction(function () use ($expected) {
            foreach ($expected as $row) {
                activity_write($row);
            }
        });
    } catch (Throwable $e) {
        $stop('Load failed and was rolled back: ' . $e->getMessage(), 1);
    }
    $say('loaded   ' . count($expected) . ' rows (table held ' . $before . ' before)');
}

// ---- verification ----
$problems = [];
$actual = [];
foreach (db_all('SELECT * FROM activities ORDER BY id') as $r) {
    $actual[(string) $r['id']] = $r;
}
foreach (array_diff(array_keys($expected), array_keys($actual)) as $id) {
    $problems[] = 'missing in the database: ' . $id;
}
foreach (array_diff(array_keys($actual), array_keys($expected)) as $id) {
    $problems[] = 'in the database but not in the source: ' . $id;
}
$kinds = activity_kinds();
$expNorm = [];
$actNorm = [];
foreach ($expected as $id => $row) {
    $expNorm[$id] = activity_normalise($row);
    if (!isset($actual[$id])) {
        continue;
    }
    $actNorm[$id] = activity_normalise($actual[$id]);
    foreach ($kinds as $c => $kind) {
        if ($expNorm[$id][$c] !== $actNorm[$id][$c]) {
            $problems[] = $id . '.' . $c . ': source ' . json_encode($expNorm[$id][$c]) . ', database ' . json_encode($actNorm[$id][$c]);
        }
    }
}
ksort($expNorm, SORT_STRING);
ksort($actNorm, SORT_STRING);
$sumExp = hash('sha256', json_encode(array_values($expNorm)));
$sumAct = hash('sha256', json_encode(array_values($actNorm)));
if ($sumExp !== $sumAct) {
    $problems[] = 'checksum differs: source ' . substr($sumExp, 0, 16) . ', database ' . substr($sumAct, 0, 16);
}
clearstatcache();
if (hash_file('sha256', $src) !== $hashBefore) {
    $problems[] = 'the source file changed during the run';
}

if ($problems) {
    $say('FAILED: ' . count($problems) . ' difference(s). The PostgreSQL copy is not trustworthy.');
    foreach (array_slice($problems, 0, 20) as $p) {
        $say('  ' . $p);
    }
    exit(1);
}
$say('VERIFIED: ' . count($expected) . ' rows of activities match the source, ' . count($kinds)
     . ' columns each; checksum ' . substr($sumAct, 0, 16) . '; source unchanged.');
exit(0);
