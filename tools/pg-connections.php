<?php
// PRI District Tracker - count the other client sessions on the estate's PostgreSQL.
//
// scripts/estate_pg.py runs this before it stops the drive cluster on a computer
// with no Node (platform D-028). estate-pg.js counts as the superuser; this file
// counts as the tracker's own role, through includes/db.php and the test database,
// so no credential beyond the app's pg.env is used and nothing is printed but a
// number. A role without pg_read_all_stats cannot see another role's backend_type,
// so every session it cannot see into counts as a connection: the count can only
// err towards leaving the cluster running.
//
//     DB_DRIVER=pgsql DT_DB_TARGET=test php tools/pg-connections.php   -> 0

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {   // a command-line tool; never served (the image also refuses tools/)
    http_response_code(404);
    exit;
}

putenv('DB_DRIVER=pgsql');
putenv('DT_DB_TARGET=test');
require_once __DIR__ . '/../includes/db.php';

try {
    pdo();
    $n = db_value(
        "SELECT count(*) FROM pg_stat_activity
          WHERE pid <> pg_backend_pid()
            AND usesysid IS NOT NULL
            AND (backend_type = 'client backend' OR backend_type IS NULL)"
    );
    echo (int) $n, "\n";
} catch (Throwable $e) {
    // db_fail() messages name settings and files, never values; a driver error is named only.
    $why = ($e instanceof PDOException) ? get_class($e) : $e->getMessage();
    fwrite(STDERR, 'count failed: ' . $why . "\n");
    exit(1);
}
