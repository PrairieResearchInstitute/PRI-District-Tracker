<?php
/**
 * tools/roles.php: grant, revoke and list roles by NetID or campus group
 * (decision D-018, migration 0004). The running app only reads user_roles; this
 * tool writes it, run from the command line as the owner role (<app>_owner on
 * Radiant), through includes/db.php.
 *
 * Usage:
 *   php tools/roles.php [--test] list
 *   php tools/roles.php (--test | --live --confirm-live) grant <netid | group:NAME> <admin|editor|viewer> [--note TEXT] [--by NETID]
 *   php tools/roles.php (--test | --live --confirm-live) revoke <netid | group:NAME>
 *   php tools/roles.php (--test | --live --confirm-live) seed
 *        the owner (NetID dreslik, configure-me@example.edu) as admin, the top role,
 *        and nothing else (D-020); run once on a new database, then the owner
 *        grants every other role. A second run changes nothing.
 *
 * A NetID may be given as a campus address (configure-me@example.edu). A revoke stamps
 * revoked_at and keeps the row; a later grant clears it. Names are stored in
 * lowercase. Nothing is read from the environment but what includes/db.php reads,
 * and no credential is ever printed.
 * Exit codes: 0 done, 1 refused or failed, 2 usage.
 */

declare(strict_types=1);

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

$rest = 0;
$opts = getopt('', ['test', 'live', 'confirm-live', 'note:', 'by:'], $rest);
$args = array_slice($argv, $rest);
$say = fn(string $s) => fwrite(STDOUT, $s . PHP_EOL);
$fail = function (string $s, int $code = 1): never { fwrite(STDERR, $s . PHP_EOL); exit($code); };
$usage = 'Usage: php tools/roles.php [--test | --live --confirm-live] list | seed | grant <netid|group:NAME> <admin|editor|viewer> [--note TEXT] [--by NETID] | revoke <netid|group:NAME>';

// The owner, superadmin to start (owner decision 2026-10-12, D-020).
const OWNER_NETID = 'dreslik';
const OWNER_EMAIL = 'configure-me@example.edu';
const OWNER_ROLE = 'admin';

if (isset($opts['test'])) {
    putenv('DT_DB_TARGET=test');
}
require __DIR__ . '/../includes/auth.php';

$cmd = $args[0] ?? '';
if (!in_array($cmd, ['list', 'seed', 'grant', 'revoke'], true)) {
    $fail($usage, 2);
}
if ($cmd !== 'list' && db_target() !== 'test' && !(isset($opts['live']) && isset($opts['confirm-live']))) {
    $fail('Refusing to change the real database without --live --confirm-live. Use --test for the test database.', 2);
}

/** [kind, principal] from "group:NAME", a NetID or a campus address. */
function principal_of(string $raw, callable $fail): array {
    $raw = trim($raw);
    if (stripos($raw, 'group:') === 0) {
        $g = strtolower(trim(substr($raw, 6)));
        if ($g === '' || strlen($g) > 255) {
            $fail('A group name must be 1 to 255 characters.', 2);
        }
        return ['group', $g];
    }
    $netid = auth_netid_from($raw);
    if ($netid === null) {
        $fail('"' . $raw . '" is not a NetID, a campus address in AUTH_NETID_DOMAINS, or group:NAME.', 2);
    }
    return ['netid', $netid];
}

try {
    pdo();
    if ($cmd === 'list') {
        $rows = db_all('SELECT principal_kind, principal, role, note, granted_by, granted_at, revoked_at FROM user_roles
                        ORDER BY revoked_at IS NOT NULL, role, principal_kind, principal');
        $say(count($rows) . ' grant(s) in ' . db_settings()['name']);
        foreach ($rows as $r) {
            $say(sprintf('  %-6s %-5s %-32s %s%s', $r['role'], $r['principal_kind'], $r['principal'],
                $r['revoked_at'] ? 'revoked ' . substr((string) $r['revoked_at'], 0, 19) : 'since ' . substr((string) $r['granted_at'], 0, 19),
                $r['note'] !== '' ? '  (' . $r['note'] . ')' : ''));
        }
        exit(0);
    }
    if ($cmd === 'seed') {
        $have = db_value("SELECT role FROM user_roles WHERE principal_kind = 'netid' AND principal = ? AND revoked_at IS NULL", [OWNER_NETID]);
        if ($have === OWNER_ROLE) {
            $say('unchanged: ' . OWNER_NETID . ' (' . OWNER_EMAIL . ') is already ' . OWNER_ROLE);
            exit(0);
        }
        $note = 'owner, superadmin to start (' . OWNER_EMAIL . ')';
        db_transaction(function () use ($note) {
            $n = db_run('UPDATE user_roles SET role = ?, note = ?, granted_by = ?, granted_at = CURRENT_TIMESTAMP, revoked_at = NULL
                         WHERE principal_kind = ? AND principal = ?', [OWNER_ROLE, $note, OWNER_NETID, 'netid', OWNER_NETID])->rowCount();
            if ($n === 0) {
                db_run('INSERT INTO user_roles (principal_kind, principal, role, note, granted_by) VALUES (?, ?, ?, ?, ?)',
                       ['netid', OWNER_NETID, OWNER_ROLE, $note, OWNER_NETID]);
            }
        });
        $say('seeded ' . OWNER_ROLE . ' to netid ' . OWNER_NETID . ' (' . OWNER_EMAIL . '); grant every other role with grant');
        exit(0);
    }
    [$kind, $principal] = principal_of((string) ($args[1] ?? ''), $fail);
    if ($cmd === 'grant') {
        $role = strtolower((string) ($args[2] ?? ''));
        if (!isset(AUTH_ROLES[$role])) {
            $fail($usage, 2);
        }
        $note = substr(trim((string) ($opts['note'] ?? '')), 0, 255);
        $by = substr(strtolower(trim((string) ($opts['by'] ?? ''))), 0, 255);
        db_transaction(function () use ($kind, $principal, $role, $note, $by) {
            $n = db_run('UPDATE user_roles SET role = ?, note = ?, granted_by = ?, granted_at = CURRENT_TIMESTAMP, revoked_at = NULL
                         WHERE principal_kind = ? AND principal = ?', [$role, $note, $by, $kind, $principal])->rowCount();
            if ($n === 0) {
                db_run('INSERT INTO user_roles (principal_kind, principal, role, note, granted_by) VALUES (?, ?, ?, ?, ?)',
                       [$kind, $principal, $role, $note, $by]);
            }
        });
        $say('granted ' . $role . ' to ' . $kind . ' ' . $principal);
        exit(0);
    }
    $n = db_run('UPDATE user_roles SET revoked_at = CURRENT_TIMESTAMP WHERE principal_kind = ? AND principal = ? AND revoked_at IS NULL',
                [$kind, $principal])->rowCount();
    if ($n === 0) {
        $fail('No active grant for ' . $kind . ' ' . $principal . '.', 1);
    }
    $say('revoked ' . $kind . ' ' . $principal);
    exit(0);
} catch (PDOException $e) {
    if (auth_table_missing($e)) {
        $fail('The user_roles table does not exist yet: run tools/migrate.php (migration 0004) first.', 1);
    }
    $fail('Database error ' . $e->getCode() . '.', 1);
} catch (Throwable $e) {
    $fail($e->getMessage(), 1);
}
