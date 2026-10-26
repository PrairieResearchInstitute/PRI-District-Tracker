<?php
/**
 * tests/php/run-tests.php: the hosted layer's test suite. Dependency-free, one line
 * per check, exit code 1 on any failure (the PaCELab shape, pri-php-webapp).
 *
 *   php tests/php/run-tests.php                         unit checks, no database
 *   DT_TEST_DRIVER=pgsql php tests/php/run-tests.php    + the whole layer on PostgreSQL
 *
 * The PostgreSQL run is an explicit opt-in and works only on the test database:
 * it sets DT_DB_TARGET=test, and includes/db.php refuses any database whose name
 * does not end in _test before it connects (drez-sqlite-to-postgres-port rule 5).
 * It empties that database first and builds it from migrations/ through
 * tools/migrate.php, so each run starts from the same state and a second run in a
 * row passes too. Credentials come from includes/db.php (the environment or
 * <dataFolder>/pg.env) and are never printed.
 *
 * The data the loader checks use is a COPY of data/activities.json in .tmp/; the
 * original is never opened for writing, and its hash is compared at the end.
 * Python is needed only for the cross-check with scripts/pri_sql.py: $DT_PYTHON,
 * else py, python3 or python on the PATH.
 */

declare(strict_types=1);

$ROOT = dirname(__DIR__, 2);
$PG = strtolower((string) getenv('DT_TEST_DRIVER')) === 'pgsql';
if ($PG) {
    putenv('DB_DRIVER=pgsql');
    putenv('DT_DB_TARGET=test');
}
require $ROOT . '/includes/activities.php';
require $ROOT . '/includes/auth.php';

$passed = 0;
$failed = 0;
function check(string $name, bool $ok, string $detail = ''): void {
    global $passed, $failed;
    if ($ok) {
        $passed++;
        echo "pass  $name\n";
    } else {
        $failed++;
        echo "FAIL  $name" . ($detail !== '' ? ": $detail" : '') . "\n";
    }
}
function throws(callable $f, string $needle = ''): bool {
    try {
        $f();
    } catch (Throwable $e) {
        return $needle === '' || str_contains($e->getMessage(), $needle);
    }
    return false;
}

/** This PHP, with the same extensions, for child processes. */
function php_cmd(): array {
    $cmd = [PHP_BINARY];
    if (php_ini_loaded_file() === false) {
        $cmd[] = '-n';
        $dir = (string) ini_get('extension_dir');
        if ($dir !== '') {
            $cmd[] = '-d';
            $cmd[] = 'extension_dir=' . $dir;
        }
        foreach (['pdo_pgsql', 'pdo_sqlite', 'mbstring'] as $e) {
            if (extension_loaded($e)) {
                $cmd[] = '-d';
                $cmd[] = 'extension=' . $e;
            }
        }
    }
    return $cmd;
}

/** Run a command (an argument list, no shell) with extra environment; [exit code, output]. */
function run(array $cmd, array $env = [], ?string $cwd = null): array {
    $full = array_merge(getenv(), $env);
    foreach ($full as $k => $v) {
        if ($v === null) {
            unset($full[$k]);
        }
    }
    $p = proc_open($cmd, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, $cwd ?? $GLOBALS['ROOT'], $full);
    if (!is_resource($p)) {
        return [-1, 'could not start ' . $cmd[0]];
    }
    $out = stream_get_contents($pipes[1]) . stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    return [proc_close($p), $out];
}

/** A fresh scratch folder on the drive, beside the app (never the data folder). */
$TMP = $ROOT . DIRECTORY_SEPARATOR . '.tmp' . DIRECTORY_SEPARATOR . 'tests-php-' . getmypid();
@mkdir($TMP, 0777, true);
register_shutdown_function(function () use ($TMP) {
    foreach (glob($TMP . '/*') ?: [] as $f) {
        @unlink($f);
    }
    @rmdir($TMP);
});

echo "Unit checks (no database)\n";

// ---- the freshness rule: one clause, standard SQL, identical on both engines
check('FRESH_WHERE is the standard-SQL freshness clause',
      FRESH_WHERE === '(show_until IS NULL OR show_until >= CURRENT_DATE)', FRESH_WHERE);
check('no CURDATE() or DATE_SUB left in the layer', (function () use ($ROOT) {
    foreach (array_merge(glob($ROOT . '/includes/*.php'), glob($ROOT . '/php/*.php'), glob($ROOT . '/tools/*.php')) as $f) {
        $src = (string) file_get_contents($f);
        if (basename($f) === 'core.php') {
            continue;
        }
        if (preg_match('/CURDATE\s*\(|DATE_SUB\s*\(/', $src)) {
            return false;
        }
    }
    return true;
})());

// ---- the upsert (PostgreSQL only since Q-11, 2026-10-20)
$cols = ['id', 'title', 'group', 'ingested_at'];
$pgUp = db_upsert_sql('activities', $cols, 'id', ['ingested_at'], ['version']);
check('pgsql upsert uses ON CONFLICT ... EXCLUDED', str_contains($pgUp, 'ON CONFLICT ("id") DO UPDATE SET')
      && str_contains($pgUp, '"title" = EXCLUDED."title"'), $pgUp);
check('pgsql upsert keeps the first ingested_at', str_contains($pgUp, '"ingested_at" = COALESCE("activities"."ingested_at", EXCLUDED."ingested_at")'), $pgUp);
check('pgsql upsert bumps version', str_contains($pgUp, '"version" = "activities"."version" + 1'), $pgUp);
check('pgsql upsert double-quotes "group" and uses no back-quote', str_contains($pgUp, '"group"') && !str_contains($pgUp, '`'), $pgUp);
check('the upsert carries no MySQL form at all (Q-11)', !str_contains($pgUp, 'ON DUPLICATE KEY UPDATE')
      && !str_contains($pgUp, 'VALUES(`') && !str_contains($pgUp, '`'), $pgUp);
check('placeholders are named columns, never values', substr_count($pgUp, ':') === count($cols)
      && str_contains($pgUp, ':group'), $pgUp);
check('db_ident refuses anything but a plain name', throws(fn() => db_ident('id; DROP TABLE x'), 'Not a plain'));

// ---- credentials: pg.env parsing, data folder resolution, the _test guard
$fake = $TMP . DIRECTORY_SEPARATOR . 'pg.env';
file_put_contents($fake, "# comment\nPGHOST=h1\nPGPORT=5999\nPGDATABASE=dbx\nPGUSER=ux\nPGPASSWORD=\"p w\"\nPGTESTDATABASE=dbx_test\nOTHER=zzz\n");
$pe = pg_env_read($fake);
check('pg.env: the six PG names are read, quotes stripped', ($pe['PGPASSWORD'] ?? '') === 'p w' && ($pe['PGPORT'] ?? '') === '5999'
      && ($pe['PGTESTDATABASE'] ?? '') === 'dbx_test');
check('pg.env: any other name is ignored', !array_key_exists('OTHER', $pe));

$fakeRoot = $TMP . DIRECTORY_SEPARATOR . 'app';
@mkdir($fakeRoot);
file_put_contents($fakeRoot . '/config.local.json', json_encode(['dataFolder' => '..\\data\\dt']));
$df = app_data_folder($fakeRoot);
check('dataFolder resolves relative to the app folder, backslashes included',
      $df !== null && str_replace('\\', '/', $df) === str_replace('\\', '/', $TMP . '/data/dt'), (string) $df);
file_put_contents($fakeRoot . '/config.local.json', json_encode(['dataFolder' => '/srv/data']));
check('an absolute dataFolder is refused', throws(fn() => app_data_folder($fakeRoot), 'relative'));
@unlink($fakeRoot . '/config.local.json');
check('no config.local.json means no data folder', app_data_folder($fakeRoot) === null);
@rmdir($fakeRoot);

$probe = 'require ' . var_export($ROOT . '/includes/db.php', true) . '; try { $s = db_settings(); echo "NAME=", $s["name"], " SRC=", $s["source"]; } catch (Throwable $e) { echo "ERR=", $e->getMessage(); }';
[, $o] = run(array_merge(php_cmd(), ['-r', $probe]), ['DB_DRIVER' => 'pgsql', 'DT_DB_TARGET' => 'test', 'DB_NAME' => 'tracker', 'DB_TEST_NAME' => 'tracker_live',
                                                     'DB_USER' => 'u', 'DB_PASSWORD' => 'not-a-real-password']);
check('the test target refuses a database not named *_test, before connecting', str_contains($o, 'Refusing to run') && !str_contains($o, 'not-a-real-password'), trim($o));
[, $o] = run(array_merge(php_cmd(), ['-r', $probe]), ['DB_DRIVER' => 'pgsql', 'DT_DB_TARGET' => 'test', 'DB_NAME' => 'tracker', 'DB_TEST_NAME' => 'tracker_test',
                                                     'DB_USER' => 'u', 'DB_PASSWORD' => 'not-a-real-password']);
check('the test target accepts a *_test name from the environment', str_contains($o, 'NAME=tracker_test SRC=environment'), trim($o));
// pg.env lives only on the drive, so it must point at the drive cluster (platform D-028).
$pgRoot = $TMP . DIRECTORY_SEPARATOR . 'pgapp';
$pgData = $TMP . DIRECTORY_SEPARATOR . 'pgdata';
@mkdir($pgRoot);
@mkdir($pgData);
file_put_contents($pgRoot . '/config.local.json', json_encode(['dataFolder' => '..\\pgdata']));
$pgProbe = 'require ' . var_export($ROOT . '/includes/db.php', true) . '; try { $s = db_settings(' . var_export($pgRoot, true)
         . '); echo "PORT=", $s["port"], " DSN=", db_dsn($s); } catch (Throwable $e) { echo "ERR=", $e->getMessage(); }';
$pgEnv = ['DB_DRIVER' => 'pgsql', 'DT_DB_TARGET' => null, 'DB_NAME' => null];
file_put_contents($pgData . '/pg.env', "PGDATABASE=dbx\nPGUSER=ux\nPGPASSWORD=not-a-real-password\nPGTESTDATABASE=dbx_test\n");
[, $o] = run(array_merge(php_cmd(), ['-r', $pgProbe]), $pgEnv);
check('pg.env with no PGPORT connects to the drive cluster on 5433', str_contains($o, 'PORT=5433 DSN=pgsql:host=127.0.0.1;port=5433;'), trim($o));
file_put_contents($pgData . '/pg.env', "PGPORT=5999\nPGDATABASE=dbx\nPGUSER=ux\nPGPASSWORD=not-a-real-password\nPGTESTDATABASE=dbx_test\n");
[, $o] = run(array_merge(php_cmd(), ['-r', $pgProbe]), $pgEnv);
check('pg.env naming another port is refused before connecting, password unprinted',
      str_contains($o, 'names port 5999') && str_contains($o, 'D-028') && !str_contains($o, 'not-a-real-password'), trim($o));
@unlink($pgData . '/pg.env');
@unlink($pgRoot . '/config.local.json');
@rmdir($pgData);
@rmdir($pgRoot);

[, $o] = run(array_merge(php_cmd(), ['-r', $probe]), ['DB_DRIVER' => 'oracle']);
check('an unknown DB_DRIVER is refused', str_contains($o, 'DB_DRIVER must be pgsql'), trim($o));
[, $o] = run(array_merge(php_cmd(), ['-r', 'require ' . var_export($ROOT . '/includes/db.php', true) . '; echo db_driver();']), ['DB_DRIVER' => null]);
check('with no DB_DRIVER the engine is PostgreSQL (owner Q-06, 2026-10-12)', trim($o) === 'pgsql', trim($o));

// ---- Radiant: every server value comes from the tier's environment file
$dsnProbe = 'require ' . var_export($ROOT . '/includes/db.php', true) . '; try { echo "DSN=", db_dsn(db_settings()); } catch (Throwable $e) { echo "ERR=", $e->getMessage(); }';
$srvEnv = ['DB_DRIVER' => null, 'DT_DB_TARGET' => null, 'DB_HOST' => 'pg.example.test', 'DB_NAME' => 'pri_district_tracker_live',
           'DB_USER' => 'pri_district_tracker_app', 'DB_PASSWORD' => 'not-a-real-password', 'DB_PORT' => null, 'DB_SSLMODE' => null];
[, $o] = run(array_merge(php_cmd(), ['-r', $dsnProbe]), $srvEnv);
check('a server named in the environment uses port 5432 by default, never the drive cluster port',
      str_contains($o, 'DSN=pgsql:host=pg.example.test;port=5432;dbname=pri_district_tracker_live') && !str_contains($o, 'not-a-real-password'), trim($o));
[, $o] = run(array_merge(php_cmd(), ['-r', $dsnProbe]), array_merge($srvEnv, ['DB_PORT' => '6543', 'DB_SSLMODE' => 'verify-full']));
check('DB_PORT and DB_SSLMODE from the environment reach the DSN', str_contains($o, 'port=6543;') && str_ends_with(trim($o), ';sslmode=verify-full'), trim($o));
[, $o] = run(array_merge(php_cmd(), ['-r', $dsnProbe]), array_merge($srvEnv, ['DB_SSLMODE' => 'sometimes']));
check('an unknown DB_SSLMODE is refused', str_contains($o, 'DB_SSLMODE must be one of'), trim($o));

// ---- the JSON record -> row mapping (the loader's source side)
$row = activity_from_json(['id' => 'x1', 'title' => 'T', 'survey' => '', 'us_house' => [13, 15], 'confirm' => true,
                           'ingested_at' => '2026-07-01', 'show_until' => '', 'region' => 'Chicago metro', 'historic' => true]);
check('blank survey becomes INHS, as pri_sql.py does', $row['survey'] === 'INHS');
check('a date stamp becomes midnight', $row['ingested_at'] === '2026-07-01 00:00:00');
check('blank show_until becomes NULL (evergreen)', $row['show_until'] === null);
check('district lists become JSON text', $row['us_house'] === '[13,15]' && $row['il_senate'] === '[]');
check('flags become 1/0, region and historic carried', $row['confirm'] === 1 && $row['featured'] === 0 && $row['historic'] === 1
      && $row['region'] === 'Chicago metro');
check('every column has a value or NULL', array_keys($row) === activity_columns());
check('normalising treats engine forms alike', activity_norm('num', '41.100000') === activity_norm('num', 41.1)
      && activity_norm('bool', true) === activity_norm('bool', '1') && activity_norm('json', '[ 13 ]') === '[13]'
      && activity_norm('dt', '2026-07-01 00:00:00') === '2026-07-01 00:00:00');

// ---- the drez-php-core copy was not edited in the app
$man = json_decode((string) @file_get_contents($ROOT . '/drez-php-core.sync.json'), true);
check('includes/core.php matches its drez-php-core sync manifest',
      is_array($man) && hash_file('sha256', $ROOT . '/includes/core.php') === ($man['files']['includes/core.php']['copy'] ?? ''));

// ---- every page goes through the module: no PDO outside includes/db.php
check('no page constructs PDO or calls ->query/->prepare itself', (function () use ($ROOT) {
    foreach (array_merge(glob($ROOT . '/php/*.php'), [$ROOT . '/health.php'], [$ROOT . '/includes/activities.php']) as $f) {
        if (preg_match('/new\s+PDO\b|->(query|prepare|exec)\s*\(/', (string) file_get_contents($f))) {
            return false;
        }
    }
    return true;
})());

// ---- identity and authority (D-018): NetID from the proxy, role from NetID or group
foreach (['AUTH_USER_HEADER', 'AUTH_EMAIL_HEADER', 'AUTH_GROUPS_HEADER', 'AUTH_GROUPS_SEPARATOR', 'AUTH_NETID_DOMAINS',
          'AUTH_ADMINS', 'AUTH_EDITORS', 'AUTH_VIEWERS', 'ADMIN_EMAILS', 'DEV_USER', 'DEV_GROUPS'] as $k) {
    putenv($k);
}
check('no header and no DEV_USER means nobody is signed in', current_identity([]) === null);
$who = current_identity(['HTTP_X_FORWARDED_USER' => 'JDoe2', 'HTTP_X_FORWARDED_GROUPS' => 'PRI Staff, INHS-Editors ,']);
check('the NetID comes from X-Forwarded-User, lowercased', ($who['netid'] ?? null) === 'jdoe2', json_encode($who));
check('groups split on the separator, blanks dropped', ($who['groups'] ?? []) === ['PRI Staff', 'INHS-Editors'], json_encode($who));
$who = current_identity(['HTTP_X_FORWARDED_EMAIL' => 'configure-me@example.edu']);
check('a campus address alone yields its NetID', ($who['netid'] ?? null) === 'jdoe2' && $who['email'] === 'configure-me@example.edu', json_encode($who));
$who = current_identity(['HTTP_X_FORWARDED_EMAIL' => 'someone@example.edu']);
check('an address outside AUTH_NETID_DOMAINS keeps the address and no NetID', $who !== null && $who['netid'] === null
      && $who['email'] === 'someone@example.edu', json_encode($who));
check('a NetID that is not a NetID is refused', auth_netid_from('x; drop') === null && auth_netid_from('9abc') === null);
putenv('AUTH_USER_HEADER=X-Remote-User');
putenv('AUTH_GROUPS_HEADER=X-IsMemberOf');
putenv('AUTH_GROUPS_SEPARATOR=;');
$who = current_identity(['HTTP_X_REMOTE_USER' => 'jdoe2', 'HTTP_X_ISMEMBEROF' => 'cn=a,ou=x;cn=b,ou=y']);
check('header names and the group separator are settings (Shibboleth style)', ($who['netid'] ?? null) === 'jdoe2'
      && $who['groups'] === ['cn=a,ou=x', 'cn=b,ou=y'], json_encode($who));
putenv('AUTH_USER_HEADER');
putenv('AUTH_GROUPS_HEADER');
putenv('AUTH_GROUPS_SEPARATOR');
putenv('DEV_USER=devnetid');
putenv('DEV_GROUPS=Dev Group');
$who = current_identity([]);
check('DEV_USER and DEV_GROUPS stand in for the proxy when no header arrives', ($who['netid'] ?? null) === 'devnetid'
      && $who['groups'] === ['Dev Group'], json_encode($who));
check('a proxy header wins over DEV_USER', (current_identity(['HTTP_X_FORWARDED_USER' => 'real1'])['netid'] ?? null) === 'real1');
putenv('DEV_USER');
putenv('DEV_GROUPS');
putenv('AUTH_ADMINS=boss1');
putenv('AUTH_EDITORS=group:INHS-Editors, configure-me@example.edu');
putenv('AUTH_VIEWERS=group:pri staff');
putenv('ADMIN_EMAILS=legacy@example.edu');
$id = fn(array $h) => current_identity($h);
check('a NetID on AUTH_ADMINS is admin', user_role($id(['HTTP_X_FORWARDED_USER' => 'boss1']), false) === 'admin');
check('a group on AUTH_EDITORS makes its members editors, case aside',
      user_role($id(['HTTP_X_FORWARDED_USER' => 'u1', 'HTTP_X_FORWARDED_GROUPS' => 'inhs-editors']), false) === 'editor');
check('an address on an allowlist matches the address', user_role($id(['HTTP_X_FORWARDED_EMAIL' => 'configure-me@example.edu']), false) === 'editor');
check('the highest role wins when several apply',
      user_role($id(['HTTP_X_FORWARDED_USER' => 'boss1', 'HTTP_X_FORWARDED_GROUPS' => 'PRI Staff']), false) === 'admin');
check('a group on AUTH_VIEWERS gives viewer only', user_role($id(['HTTP_X_FORWARDED_USER' => 'u2', 'HTTP_X_FORWARDED_GROUPS' => 'PRI Staff']), false) === 'viewer');
check('ADMIN_EMAILS still grants admin (the allowlist before D-018)', user_role($id(['HTTP_X_FORWARDED_EMAIL' => 'legacy@example.edu']), false) === 'admin');
check('someone on no list holds no role', user_role($id(['HTTP_X_FORWARDED_USER' => 'stranger']), false) === null);
check('role order: admin covers editor covers viewer', role_at_least('admin', 'editor') && role_at_least('editor', 'viewer')
      && !role_at_least('viewer', 'editor') && !role_at_least(null, 'viewer'));
foreach (['AUTH_ADMINS', 'AUTH_EDITORS', 'AUTH_VIEWERS', 'ADMIN_EMAILS'] as $k) {
    putenv($k);
}
[$code, $o] = run(array_merge(php_cmd(), [$ROOT . '/tools/roles.php', 'grant', 'jdoe2', 'emperor']), ['DT_DB_TARGET' => null, 'DB_NAME' => null]);
check('tools/roles.php refuses an unknown command form before connecting', $code === 2, trim($o));
[$code, $o] = run(array_merge(php_cmd(), [$ROOT . '/tools/roles.php', 'grant', 'jdoe2', 'editor']), ['DT_DB_TARGET' => null]);
check('tools/roles.php refuses the real database without --live --confirm-live', $code === 2 && str_contains($o, 'Refusing'), trim($o));

if (!$PG) {
    echo "\nPostgreSQL checks not run (set DT_TEST_DRIVER=pgsql to run them on the _test database).\n";
    echo "\n$passed passed, $failed failed\n";
    exit($failed ? 1 : 0);
}

// =========================================================================
echo "\nPostgreSQL checks (test database only)\n";
try {
    pdo();
    $S = db_settings();
} catch (Throwable $e) {
    check('connect to the test database', false, $e->getMessage());
    echo "\n$passed passed, $failed failed\n";
    exit(1);
}
check('connected to a database whose name ends in _test', str_ends_with($S['name'], '_test'), $S['name']);
check('the server is PostgreSQL', str_starts_with((string) db_value('SELECT version()'), 'PostgreSQL'));

// Empty the test database: the app's tables only, in dependency order.
foreach (['activities', 'awards', 'settings', 'user_roles', 'schema_migrations'] as $t) {
    db_run('DROP TABLE IF EXISTS ' . db_ident($t) . ' CASCADE');
}
[$code, $o] = run(array_merge(php_cmd(), [$ROOT . '/tools/migrate.php', '--test']));
check('tools/migrate.php builds the schema from migrations/', $code === 0 && str_contains($o, 'applied 0003_region_historic')
      && str_contains($o, 'applied 0004_user_roles'), trim($o));
[$code, $o] = run(array_merge(php_cmd(), [$ROOT . '/tools/migrate.php', '--test']));
check('a second migrate run applies nothing', $code === 0 && str_contains($o, 'pending 0'), trim($o));
[$code, $o] = run(array_merge(php_cmd(), [$ROOT . '/tools/migrate.php']), ['DT_DB_TARGET' => null]);
check('migrate refuses the real database without --live --confirm-live', $code === 2 && str_contains($o, 'Refusing'), trim($o));

$types = [];
foreach (db_all("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'activities'") as $r) {
    $types[$r['column_name']] = $r['data_type'];
}
check('activities has every canonical column plus version', !array_diff(array_merge(activity_columns(), ['version']), array_keys($types))
      && count($types) === count(activity_columns()) + 1, implode(',', array_keys($types)));
check('types: boolean flags, timestamp stamps, date timer, numeric coordinates',
      ($types['featured'] ?? '') === 'boolean' && ($types['historic'] ?? '') === 'boolean'
      && ($types['ingested_at'] ?? '') === 'timestamp without time zone' && ($types['show_until'] ?? '') === 'date'
      && ($types['latitude'] ?? '') === 'numeric' && ($types['version'] ?? '') === 'integer', json_encode($types));
check('settings holds its seed row', db_value("SELECT v FROM settings WHERE k = 'default_window_days'") === '548');
check('the session calendar is APP_TIMEZONE, the same day PHP sees', (string) db_value('SELECT CURRENT_DATE') === date('Y-m-d'));

// ---- the owner seed (D-020): a fresh database gets exactly one superadmin
$roles = array_merge(php_cmd(), [$ROOT . '/tools/roles.php', '--test']);
check('a freshly migrated database holds no grants', (int) db_value('SELECT COUNT(*) FROM user_roles') === 0);
[$code, $o] = run(array_merge($roles, ['seed']));
[$code2, $o2] = run(array_merge($roles, ['seed']));
$seeded = db_all('SELECT principal_kind, principal, role, revoked_at FROM user_roles');
check('a fresh seed yields exactly one grant: dreslik as admin, the top role', $code === 0 && count($seeded) === 1
      && $seeded[0]['principal_kind'] === 'netid' && $seeded[0]['principal'] === 'dreslik' && $seeded[0]['role'] === 'admin'
      && $seeded[0]['revoked_at'] === null, trim($o) . ' ' . json_encode($seeded));
check('seeding twice changes nothing', $code2 === 0 && str_contains($o2, 'unchanged')
      && (int) db_value('SELECT COUNT(*) FROM user_roles') === 1, trim($o2));
check('the app reads the owner as admin, by NetID or by his campus address',
      user_role(['netid' => 'dreslik', 'email' => null, 'groups' => []]) === 'admin'
      && user_role(['netid' => auth_netid_from('configure-me@example.edu'), 'email' => 'configure-me@example.edu', 'groups' => []]) === 'admin');
[$code, $o] = run(array_merge(php_cmd(), [$ROOT . '/tools/roles.php', 'seed']), ['DT_DB_TARGET' => null]);
check('seeding the real database stops without --live --confirm-live', $code === 2 && str_contains($o, 'Refusing'), trim($o));
db_run('DELETE FROM user_roles');   // the test database only; the checks below start from no grants

// ---- roles in the database (D-018): tools/roles.php writes, the app reads
[$code, $o] = run(array_merge($roles, ['grant', 'configure-me@example.edu', 'editor', '--note', 'test grant', '--by', 'owner1']));
check('roles.php grants editor to a NetID given as an address', $code === 0 && str_contains($o, 'granted editor to netid jdoe2'), trim($o));
[$code, $o] = run(array_merge($roles, ['grant', 'group:PRI Staff', 'viewer']));
check('roles.php grants viewer to a campus group, stored lowercase', $code === 0
      && db_value("SELECT role FROM user_roles WHERE principal_kind = 'group' AND principal = 'pri staff'") === 'viewer', trim($o));
check('the table gives the NetID its role', user_role(['netid' => 'jdoe2', 'email' => null, 'groups' => []]) === 'editor');
check('the table gives a group member the group role, case aside', user_role(['netid' => 'u9', 'email' => null, 'groups' => ['PRI STAFF']]) === 'viewer');
[$code, $o] = run(array_merge($roles, ['list']));
check('roles.php lists the grants', $code === 0 && str_contains($o, '2 grant(s)') && str_contains($o, 'jdoe2'), trim($o));
[$code, $o] = run(array_merge($roles, ['revoke', 'jdoe2']));
check('a revoke keeps the row and ends the role', $code === 0 && user_role(['netid' => 'jdoe2', 'email' => null, 'groups' => []]) === null
      && (int) db_value("SELECT COUNT(*) FROM user_roles WHERE principal = 'jdoe2'") === 1, trim($o));
[$code, $o] = run(array_merge($roles, ['revoke', 'jdoe2']));
check('revoking twice says there is no active grant', $code === 1 && str_contains($o, 'No active grant'), trim($o));
[$code] = run(array_merge($roles, ['grant', 'jdoe2', 'admin']));
check('a later grant restores the row with the new role', $code === 0 && user_role(['netid' => 'jdoe2', 'email' => null, 'groups' => []]) === 'admin');
[$code, $o] = run(array_merge($roles, ['grant', 'group:', 'viewer']));
check('an empty group name is refused', $code === 2, trim($o));

// ---- the back-office upsert
$id = upsert_activity(['title' => 'Test Wetland Survey', 'summary' => 'one', 'scope' => 'sited', 'us_house' => '13, 15',
                       'il_senate' => '52', 'il_house' => '', 'show_until' => '', 'featured' => '1']);
$r = db_one('SELECT * FROM activities WHERE id = ?', [$id]);
check('upsert inserts with the slug id', $id === 'test-wetland-survey' && $r !== null);
check('upsert stores districts, NULL timer, a real boolean, version 1', $r['us_house'] === '[13,15]' && $r['il_senate'] === '[52]'
      && $r['show_until'] === null && $r['featured'] === true && (int) $r['version'] === 1, json_encode($r));
db_run("UPDATE activities SET ingested_at = '2020-01-02 03:04:05' WHERE id = ?", [$id]);
upsert_activity(['id' => $id, 'title' => 'Test Wetland Survey', 'summary' => 'two', 'scope' => 'statewide', 'us_house' => '13']);
$r = db_one('SELECT * FROM activities WHERE id = ?', [$id]);
check('a second upsert updates in place and bumps version', $r['summary'] === 'two' && (int) $r['version'] === 2, json_encode($r));
check('a second upsert keeps the first ingested_at', $r['ingested_at'] === '2020-01-02 03:04:05', (string) $r['ingested_at']);
check('statewide forces empty district lists', $r['us_house'] === '[]');
check('one row per id after two upserts', (int) db_value('SELECT COUNT(*) FROM activities WHERE id = ?', [$id]) === 1);

// ---- the display timer
foreach (['t-evergreen' => 'NULL', 't-today' => 'CURRENT_DATE', 't-tomorrow' => "CURRENT_DATE + INTERVAL '1' DAY",
          't-yesterday' => "CURRENT_DATE - INTERVAL '1' DAY"] as $tid => $expr) {
    upsert_activity(['id' => $tid, 'title' => $tid, 'summary' => 's', 'scope' => 'statewide']);
    db_run('UPDATE activities SET show_until = ' . $expr . ' WHERE id = ?', [$tid]);   // $expr is a constant above
}
$shown = array_column(fresh_activities(), 'id');
check('evergreen shows', in_array('t-evergreen', $shown, true));
check('a record ending today shows for all of today (inclusive, as fresh() does)', in_array('t-today', $shown, true));
check('a record ending tomorrow shows', in_array('t-tomorrow', $shown, true));
check('a record that ended yesterday is hidden', !in_array('t-yesterday', $shown, true));

// ---- retire
$v0 = (int) db_value('SELECT version FROM activities WHERE id = ?', [$id]);
check('retire touches one row', retire_activity($id) === 1);
$r = db_one('SELECT show_until, version, (show_until = CURRENT_DATE - 1) AS yesterday FROM activities WHERE id = ?', [$id]);
check('retire sets show_until to yesterday and bumps version', $r['yesterday'] === true && (int) $r['version'] === $v0 + 1, json_encode($r));
check('a retired record leaves the public list but stays in the table', !in_array($id, array_column(fresh_activities(), 'id'), true)
      && (int) db_value('SELECT COUNT(*) FROM activities WHERE id = ?', [$id]) === 1);
$console = array_column(console_activities(), 'shown', 'id');
check('the console marks it hidden with a real boolean', ($console[$id] ?? null) === false && ($console['t-evergreen'] ?? null) === true);
check('retiring an unknown id changes nothing', retire_activity('no-such-id') === 0);

// ---- the verified loader, on a copy of the database of record
$orig = $ROOT . '/data/activities.json';
$origHash = hash_file('sha256', $orig);
$origTime = filemtime($orig);
$copy = $TMP . DIRECTORY_SEPARATOR . 'activities.json';
copy($orig, $copy);
$srcCount = count(json_decode((string) file_get_contents($copy), true)['activities']);
db_run('DELETE FROM activities');
$loader = array_merge(php_cmd(), [$ROOT . '/tools/load-pg.php', '--source', $copy]);
[$code, $o] = run(array_merge($loader, ['--test']));
check('load-pg.php loads the copy and prints VERIFIED', $code === 0 && str_contains($o, 'VERIFIED: ' . $srcCount . ' rows'), trim($o));
check('the loaded rows keep their own ids', (int) db_value('SELECT COUNT(*) FROM activities') === $srcCount
      && db_value("SELECT id FROM activities WHERE id = 'ctap'") === 'ctap');
check('region and historic arrived', (int) db_value("SELECT COUNT(*) FROM activities WHERE region <> ''") === 6
      && (int) db_value('SELECT COUNT(*) FROM activities WHERE historic') === 3);
[$code, $o] = run(array_merge($loader, ['--test']));
check('a second load into a full table is refused without --refresh', $code === 2 && str_contains($o, '--refresh'), trim($o));
[$code, $o] = run(array_merge($loader, ['--test', '--verify-only']));
check('--verify-only passes on an untouched load', $code === 0 && str_contains($o, 'VERIFIED'), trim($o));
db_run("UPDATE activities SET title = title || ' (changed)' WHERE id = 'ctap'");
[$code, $o] = run(array_merge($loader, ['--test', '--verify-only']));
check('a changed field is caught: FAILED, exit 1, the field named', $code === 1 && str_contains($o, 'FAILED') && str_contains($o, 'ctap.title'), trim($o));
db_run("INSERT INTO activities (id, title) VALUES ('stray-row', 'x')");
[$code, $o] = run(array_merge($loader, ['--test', '--verify-only']));
check('a row the source does not hold is caught', $code === 1 && str_contains($o, 'stray-row'), trim($o));
db_run("DELETE FROM activities WHERE id = 'stray-row'");
[$code, $o] = run(array_merge($loader, ['--test', '--refresh']));
check('--refresh repairs the copy and verifies again', $code === 0 && str_contains($o, 'VERIFIED'), trim($o));
[$code, $o] = run(array_merge($loader, []), ['DT_DB_TARGET' => null]);
check('the loader refuses the real database without --live --confirm-live', $code === 2 && str_contains($o, 'Refusing'), trim($o));
$withExtra = $TMP . DIRECTORY_SEPARATOR . 'extra.json';
$doc = json_decode((string) file_get_contents($copy), true);
$doc['activities'][0]['brand_new_field'] = 'x';
file_put_contents($withExtra, json_encode($doc));
[$code, $o] = run(array_merge(php_cmd(), [$ROOT . '/tools/load-pg.php', '--source', $withExtra, '--test', '--verify-only']));
check('a source field with no column stops the loader rather than being dropped', $code === 2 && str_contains($o, 'brand_new_field'), trim($o));

// ---- cross-check: scripts/pri_sql.py's PostgreSQL file gives the same rows
$py = null;
foreach (array_filter([getenv('DT_PYTHON') ?: null, 'py', 'python3', 'python']) as $cand) {
    [$c] = run([$cand, '--version']);
    if ($c === 0) { $py = $cand; break; }
}
if ($py === null) {
    check('Python found for the pri_sql.py cross-check', false, 'set DT_PYTHON');
} else {
    $sqlFile = $TMP . DIRECTORY_SEPARATOR . 'data.pgsql.sql';
    [$code, $o] = run([$py, $ROOT . '/scripts/pri_sql.py', '--dialect', 'pgsql', '--source', $copy, '--out', $sqlFile]);
    check('pri_sql.py writes the PostgreSQL import file from the copy', $code === 0 && is_file($sqlFile), trim($o));
    $viaLoader = [];
    foreach (db_all('SELECT * FROM activities ORDER BY id') as $r) { $viaLoader[$r['id']] = activity_normalise($r); }
    db_run('DELETE FROM activities');
    try {
        pdo()->exec((string) file_get_contents($sqlFile));   // a generated import file, as psql would run it
        $viaSql = [];
        foreach (db_all('SELECT * FROM activities ORDER BY id') as $r) { $viaSql[$r['id']] = activity_normalise($r); }
        $diff = [];
        foreach ($viaLoader as $k => $rowL) {
            foreach ($rowL as $c => $v) {
                if (!isset($viaSql[$k]) || !array_key_exists($c, $viaSql[$k]) || $viaSql[$k][$c] !== $v) { $diff[] = "$k.$c"; }
            }
        }
        check('the import file and the loader produce identical rows', count($viaSql) === count($viaLoader) && !$diff,
              implode(', ', array_slice($diff, 0, 8)));
        pdo()->exec((string) file_get_contents($sqlFile));
        check('re-running the import file refreshes rather than duplicates', (int) db_value('SELECT COUNT(*) FROM activities') === $srcCount
              && (int) db_value('SELECT MIN(version) FROM activities') === 2);
    } catch (Throwable $e) {
        check('the PostgreSQL import file runs', false, $e->getMessage());
    }
    db_run('DELETE FROM activities');
    [$code, $o] = run(array_merge($loader, ['--test']));
    check('reload from the copy for the page checks', $code === 0 && str_contains($o, 'VERIFIED'), trim($o));
}

// ---- the pages, served by PHP's own server on 127.0.0.1, against the test database
$sock = stream_socket_server('tcp://127.0.0.1:0');
$port = (int) substr(strrchr((string) stream_socket_get_name($sock, false), ':'), 1);
fclose($sock);
$admin = 'tester@example.edu';
$srv = proc_open(array_merge(php_cmd(), ['-S', '127.0.0.1:' . $port, '-t', $ROOT]),
    [1 => ['file', $TMP . DIRECTORY_SEPARATOR . 'server.log', 'a'], 2 => ['file', $TMP . DIRECTORY_SEPARATOR . 'server.log', 'a']], $pipes, $ROOT,
    array_merge(getenv(), ['DB_DRIVER' => 'pgsql', 'DT_DB_TARGET' => 'test', 'ADMIN_EMAILS' => $admin, 'DEV_USER' => '',
                           'DT_BACKOFFICE_WRITES' => null]));   // the default: writes allowed (D-019)
function http(int $port, string $path, string $method = 'GET', array $headers = [], string $body = ''): array {
    $ctx = stream_context_create(['http' => ['method' => $method, 'header' => implode("\r\n", $headers), 'content' => $body,
                                             'ignore_errors' => true, 'timeout' => 30]]);
    $out = @file_get_contents('http://127.0.0.1:' . $port . $path, false, $ctx);
    $hdrs = function_exists('http_get_last_response_headers') ? (http_get_last_response_headers() ?? []) : ($http_response_header ?? []);
    $code = preg_match('/\s(\d{3})\s/', (string) ($hdrs[0] ?? ''), $m) ? (int) $m[1] : 0;
    return [$code, (string) $out, $hdrs];
}
/**
 * A back-office session: open the page as $who (header lines) and keep its session
 * cookie and CSRF token, as a browser would. Returns [headers with the cookie, token].
 */
function bo_session(int $port, array $who): array {
    [, $b, $hdrs] = http($port, '/php/admin_ingest.php', 'GET', $who);
    $cookie = '';
    foreach ($hdrs as $h) {
        if (preg_match('/^Set-Cookie:\s*(pri_district_tracker=[^;]+)/i', $h, $m)) { $cookie = $m[1]; }
    }
    $token = preg_match('/name="csrf_token" value="([0-9a-f]+)"/', $b, $m) ? $m[1] : '';
    return [array_merge($who, ['Cookie: ' . $cookie]), $token];
}
$health = null;
for ($i = 0; $i < 40 && $health === null; $i++) {
    usleep(250000);
    [$c, $b] = http($port, '/health.php?db=1');
    if ($c === 200) { $health = json_decode($b, true); }
}
check('health.php?db=1 answers ok through includes/db.php', is_array($health) && ($health['db'] ?? '') === 'ok', json_encode($health));
check('health.php reports this folder as its root (our server, not another)', is_array($health)
      && realpath((string) $health['root']) === realpath($ROOT));

[$c, $b] = http($port, '/php/data.php');
$ok = $c === 200 && preg_match('/window\.ACT=(\[.*\]);$/s', $b, $m);
$act = $ok ? json_decode($m[1], true) : null;
$freshCount = (int) db_value('SELECT COUNT(*) FROM activities WHERE ' . FRESH_WHERE);
check('data.php serves window.GEO, window.REPS and window.ACT', $ok && str_starts_with($b, 'window.GEO='), substr($b, 0, 200));
check('data.php lists exactly the fresh records', is_array($act) && count($act) === $freshCount, (string) (is_array($act) ? count($act) : 'none'));
$one = is_array($act) && $act ? $act[0] : [];
check('data.php: district lists are integer arrays, flags are booleans, no version',
      is_array($one['us_house'] ?? null) && is_bool($one['featured'] ?? null) && is_bool($one['historic'] ?? null)
      && !array_key_exists('version', $one), json_encode($one));

[$c] = http($port, '/php/admin_ingest.php');
check('the back office answers 401 with no identity', $c === 401, (string) $c);
[$c] = http($port, '/php/admin_ingest.php', 'GET', ['X-Forwarded-Email: someone@example.edu']);
check('the back office answers 403 to an address not on ADMIN_EMAILS', $c === 403, (string) $c);
[$c, $b] = http($port, '/php/admin_ingest.php', 'GET', ['X-Forwarded-Email: ' . $admin]);
$total = (int) db_value('SELECT COUNT(*) FROM activities');
check('the back office lists every record for an admin', $c === 200 && str_contains($b, 'Current records (' . $total . ')'), (string) $c);
[$adminH, $tok] = bo_session($port, ['X-Forwarded-Email: ' . $admin]);
check('the back office hands out a session cookie and a CSRF token', $tok !== '' && str_contains(end($adminH), 'pri_district_tracker='));
$formH = array_merge($adminH, ['Content-Type: application/x-www-form-urlencoded']);
$fields = ['title' => 'HTTP Probe Record', 'summary' => 'Probe', 'survey' => 'ISWS', 'type' => 'Project',
           'scope' => 'sited', 'us_house' => '13', 'il_senate' => '', 'il_house' => '', 'show_until' => ''];
[$c] = http($port, '/php/admin_ingest.php', 'POST', $formH, http_build_query($fields));
check('a POST without the CSRF token is refused (400) and stores nothing', $c === 400
      && (int) db_value("SELECT COUNT(*) FROM activities WHERE id = 'http-probe-record'") === 0, (string) $c);
[$c] = http($port, '/php/admin_ingest.php', 'POST', $formH, http_build_query($fields + ['csrf_token' => str_repeat('0', 64)]));
check('a POST with a wrong token is refused (400)', $c === 400, (string) $c);
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $formH, http_build_query($fields + ['csrf_token' => $tok]));
check('saving the form stores the record', $c === 200 && str_contains($b, 'Saved "http-probe-record"')
      && db_value("SELECT survey FROM activities WHERE id = 'http-probe-record'") === 'ISWS', substr(strip_tags($b), 0, 300));
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $formH, http_build_query($fields + ['csrf_token' => $tok]));
check('adding a record whose id exists is refused (409), never an overwrite', $c === 409 && str_contains($b, 'already exists'), (string) $c);

// Q-08: the fields the form does not show survive an edit; a stale save is refused.
db_run("UPDATE activities SET notes = 'keep me', keywords = 'k1', theme = 'water', featured = TRUE, region = 'Chicago metro',
        historic = TRUE, county = 'Cook', program = 'P1' WHERE id = 'http-probe-record'");
$v = (int) db_value("SELECT version FROM activities WHERE id = 'http-probe-record'");
[$c, $b] = http($port, '/php/admin_ingest.php?edit=http-probe-record', 'GET', $adminH);
check('Edit loads the record with its version into the form', $c === 200 && str_contains($b, 'name="version" value="' . $v . '"')
      && str_contains($b, 'value="HTTP Probe Record"') && str_contains($b, 'value="13"'), (string) $c);
$edit = array_merge($fields, ['id' => 'http-probe-record', 'version' => (string) $v, 'summary' => 'Edited', 'csrf_token' => $tok]);
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $formH, http_build_query($edit));
$r = db_one("SELECT * FROM activities WHERE id = 'http-probe-record'");
check('an edit saves the changed field and bumps the version', $c === 200 && $r['summary'] === 'Edited' && (int) $r['version'] === $v + 1,
      substr(strip_tags($b), 0, 300));
check('an edit keeps every field the form does not show', $r['notes'] === 'keep me' && $r['keywords'] === 'k1' && $r['theme'] === 'water'
      && $r['featured'] === true && $r['region'] === 'Chicago metro' && $r['historic'] === true && $r['county'] === 'Cook'
      && $r['program'] === 'P1', json_encode($r));
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $formH, http_build_query(array_merge($edit, ['summary' => 'Stale'])));
check('a save from a stale version is refused (409) and changes nothing', $c === 409 && str_contains($b, 'after you opened it')
      && db_value("SELECT summary FROM activities WHERE id = 'http-probe-record'") === 'Edited', (string) $c);
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $formH, http_build_query(array_merge($edit, ['version' => ''])));
check('an edit without a version is refused (409)', $c === 409, (string) $c);

// Retire asks on the page itself now (PDT-37, Q-27), so an unconfirmed post must
// change nothing: the guard is the point, not the wording.
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $formH,
                 http_build_query(['action' => 'retire', 'id' => 'http-probe-record', 'csrf_token' => $tok]));
check('Retire asks before it hides anything', $c === 200 && str_contains($b, 'Retire This Record?')
      && db_value("SELECT (show_until IS DISTINCT FROM CURRENT_DATE - 1) FROM activities WHERE id = 'http-probe-record'") === true,
      substr(strip_tags($b), 0, 300));
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $formH,
                 http_build_query(['action' => 'retire', 'id' => 'http-probe-record', 'confirmed' => '1', 'csrf_token' => $tok]));
check('Retire hides the record and keeps it', $c === 200 && str_contains($b, 'Retired')
      && db_value("SELECT (show_until = CURRENT_DATE - 1) FROM activities WHERE id = 'http-probe-record'") === true);
$bnd = 'dtbnd' . bin2hex(random_bytes(6));
$multipart = function (string $csv) use ($bnd, $tok): string {
    return "--$bnd\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n$tok\r\n"
         . "--$bnd\r\nContent-Disposition: form-data; name=\"csv\"; filename=\"probe.csv\"\r\nContent-Type: text/csv\r\n\r\n$csv\r\n--$bnd--\r\n";
};
$mpH = array_merge($adminH, ['Content-Type: multipart/form-data; boundary=' . $bnd]);
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $mpH, $multipart("title,summary,type,scope,show_until\nCSV Probe Record,From a CSV,News,statewide,\n"));
$csvRow = db_one("SELECT show_until, (show_until > CURRENT_DATE) AS future FROM activities WHERE id = 'csv-probe-record'");
check('a CSV upload ingests, and a dated type gets the default window', $c === 200 && str_contains($b, 'Imported/updated 1 record(s)')
      && $csvRow !== null && $csvRow['future'] === true, json_encode($csvRow));
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', $mpH, $multipart("id,title,summary\nhttp-probe-record,HTTP Probe Record,From a short CSV\n"));
$r = db_one("SELECT * FROM activities WHERE id = 'http-probe-record'");
check('a CSV line for an existing id changes only the columns the file has', $c === 200 && str_contains($b, '1 updated')
      && $r['summary'] === 'From a short CSV' && $r['notes'] === 'keep me' && $r['survey'] === 'ISWS' && $r['us_house'] === '[13]',
      json_encode($r));
// Roles from the database through the proxy headers (D-018).
$viewerH = ['X-Forwarded-User: u9', 'X-Forwarded-Groups: PRI Staff'];
[$c, $b] = http($port, '/php/admin_ingest.php', 'GET', $viewerH);
check('a member of a viewer group opens the back office, with no edit controls', $c === 200 && str_contains($b, 'Current records')
      && !str_contains($b, 'Add record') && !str_contains($b, '>Edit</a>') && !str_contains($b, 'Upload'), (string) $c);
[$viewerS] = bo_session($port, $viewerH);
[$c, $b] = http($port, '/php/admin_ingest.php', 'POST', array_merge($viewerS, ['Content-Type: application/x-www-form-urlencoded']),
                 http_build_query(['title' => 'Viewer Probe', 'summary' => 'Probe', 'scope' => 'statewide']));
check('a viewer cannot save (403) and nothing is stored', $c === 403
      && (int) db_value("SELECT COUNT(*) FROM activities WHERE id = 'viewer-probe'") === 0, (string) $c);
[$c] = http($port, '/php/admin_ingest.php', 'GET', ['X-Forwarded-User: stranger9']);
check('a NetID with no role and no group is refused (403)', $c === 403, (string) $c);
proc_terminate($srv);

// DT_BACKOFFICE_WRITES=0: the back office is read-only again (D-019).
$sock = stream_socket_server('tcp://127.0.0.1:0');
$port2 = (int) substr(strrchr((string) stream_socket_get_name($sock, false), ':'), 1);
fclose($sock);
$srv2 = proc_open(array_merge(php_cmd(), ['-S', '127.0.0.1:' . $port2, '-t', $ROOT]),
    [1 => ['file', $TMP . DIRECTORY_SEPARATOR . 'server2.log', 'a'], 2 => ['file', $TMP . DIRECTORY_SEPARATOR . 'server2.log', 'a']], $pipes2, $ROOT,
    array_merge(getenv(), ['DB_DRIVER' => 'pgsql', 'DT_DB_TARGET' => 'test', 'ADMIN_EMAILS' => $admin, 'DEV_USER' => '', 'DT_BACKOFFICE_WRITES' => '0']));
for ($i = 0, $c = 0; $i < 40 && $c !== 200; $i++) { usleep(250000); [$c] = http($port2, '/health.php'); }
$ro = http_build_query(['title' => 'Read Only Probe', 'summary' => 'Probe', 'survey' => 'ISWS', 'type' => 'Project',
                        'scope' => 'sited', 'us_house' => '13', 'il_senate' => '', 'il_house' => '', 'show_until' => '']);
[$roH, $roTok] = bo_session($port2, ['X-Forwarded-Email: ' . $admin]);
[$c, $b] = http($port2, '/php/admin_ingest.php', 'POST', array_merge($roH, ['Content-Type: application/x-www-form-urlencoded']),
                 $ro . '&csrf_token=' . $roTok);
check('with DT_BACKOFFICE_WRITES=0 the back office shows no form, refuses writes (403) and stores nothing', $c === 403
      && str_contains($b, 'read-only') && !str_contains($b, 'Add record')
      && db_value("SELECT COUNT(*) FROM activities WHERE id = 'read-only-probe'") == 0, (string) $c);
proc_terminate($srv2);
proc_close($srv);

clearstatcache();
check('data/activities.json was not changed by any of this', hash_file('sha256', $orig) === $origHash && filemtime($orig) === $origTime);

echo "\n$passed passed, $failed failed\n";
exit($failed ? 1 : 0);
