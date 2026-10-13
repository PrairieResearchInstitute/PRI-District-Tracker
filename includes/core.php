<?php
/**
 * core.php: escaping, CSRF, flash messages, settings and database helpers.
 *
 * Part of drez-php-core. PHP 8.1 or later, no Composer, no extensions beyond
 * PDO and the driver the caller uses.
 *
 * Sources
 *   PaCELab Equip  includes/functions.php  h, csrf_token, csrf_field,
 *                                          csrf_valid, csrf_require, flash,
 *                                          flash_render, safe_return_to, the
 *                                          exception handler
 *   PaCELab Equip  includes/auth.php       session_boot
 *   PaCELab Equip  includes/db.php         db, db_run, db_all, db_one, db_value
 *   PRI Facilities Request  facilities/lib/settings.php  settings_all,
 *                                          settings_forget, setting (typed and
 *                                          strict; canonical for settings)
 *
 * Deliberate changes from the sources
 *   1. h() refuses an array or an object with no __toString (TypeError)
 *      instead of printing the word "Array" with a warning. Integers, floats,
 *      booleans and null are accepted, as in PaCELab; ENT_SUBSTITUTE is kept.
 *   2. csrf_valid() takes optional request arrays so it can be tested without
 *      superglobals; with none given it reads $_POST and $_SERVER as before.
 *      A posted array (csrf_token[]=x) is rejected, never cast to "Array"
 *      (the Facilities defect).
 *   3. flash() has one argument order, message first (PaCELab), and throws
 *      when the type is not one of the known kinds. A call written in the
 *      Facilities order, flash('error', 'Saved'), therefore fails loudly
 *      instead of showing the word "error" styled as "Saved".
 *   4. Settings: the table and column names come from settings_configure(),
 *      not a hard-coded schema. setting() is the Facilities shape: typed, and
 *      a missing key with no default throws. set_setting() clears the cache
 *      (the PaCELab defect: a read later in the same request returned the old
 *      value). A "number" setting holding text throws instead of becoming 0.
 *      set_setting() works on SQLite, Postgres, MySQL and SQL Server by doing
 *      a lookup and then an UPDATE or INSERT inside a transaction.
 *   5. The database handle is given by the caller (db_use(), or db_open_sqlite()
 *      with a path the caller supplies); this file never decides where a
 *      database lives.
 *   6. db_run() checks the statement before running it: every named
 *      placeholder must be bound, no unused named parameter may be passed,
 *      and the number of positional values must equal the number of question
 *      marks. SQLite binds a missing parameter as NULL without complaint, so
 *      "WHERE lab_id = :lab" with no :lab used to match nothing, silently.
 *      String literals, quoted identifiers, comments and Postgres "::" casts
 *      are skipped by the scan.
 *   7. db_in_list(n) builds an IN list of question marks and refuses n < 1.
 *   8. session_boot() takes the session name from the caller, so two apps on
 *      one host never share a session by accident.
 *   9. safe_return_to() takes the list of allowed pages from the caller.
 *  10. core_install_exception_handler() takes the label written to the error
 *      log from the caller.
 *  11. FIX (App_to_Migrate decision D-012; sqlite-on-synced-folders rule 3):
 *      db_open_sqlite() set journal_mode WAL unconditionally and left
 *      synchronous to the compiled default. It now sets synchronous=FULL always, WAL on a local or
 *      exFAT drive path, DELETE on a path inside OneDrive, Dropbox, Google
 *      Drive, iCloud Drive or Box (db_sqlite_journal_mode()), and checks the
 *      mode took. db_close() folds the WAL into the main file with a
 *      TRUNCATE checkpoint and runs at shutdown; db_use() can forget a handle.
 */

declare(strict_types=1);

// ---------------------------------------------------------------------------
// Output
// ---------------------------------------------------------------------------

/**
 * Escape for HTML. Every echoed value passes through this one funnel.
 *
 * ENT_SUBSTITUTE keeps a string with one bad byte (it becomes U+FFFD) instead
 * of returning an empty string, which is how a malformed value used to print
 * as nothing at all.
 */
function h(mixed $value): string
{
    if (is_array($value) || (is_object($value) && !method_exists($value, '__toString'))) {
        throw new TypeError('h() was given ' . get_debug_type($value)
            . '; pass the value you mean to print, not the container it is in.');
    }
    if (is_bool($value)) {
        $value = $value ? '1' : '';
    }
    return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/**
 * A local page to go back to, or the fallback.
 *
 * Only a page named in $allowed, never an address somewhere else: a crafted
 * link must not be able to bounce anybody off the site.
 */
function safe_return_to(?string $raw, array $allowed, string $fallback): string
{
    $raw = (string) $raw;
    if ($raw === '' || preg_match('#^[a-z][a-z0-9+.-]*:|^//|^\\\\#i', $raw)
        || preg_match('/[\x00-\x1F\x7F]/', $raw)) {
        return $fallback;
    }
    $file = basename((string) (parse_url($raw, PHP_URL_PATH) ?: ''));
    if (!in_array($file, $allowed, true)) {
        return $fallback;
    }
    $query = parse_url($raw, PHP_URL_QUERY);
    return $file . ($query ? '?' . $query : '');
}

/**
 * Nothing gets to hand a stack trace to a browser.
 *
 * The detail goes to the server error log; the visitor gets a sentence. A
 * request that expects JSON gets JSON.
 */
function core_install_exception_handler(string $logLabel): void
{
    set_exception_handler(function (Throwable $e) use ($logLabel): void {
        error_log($logLabel . ': ' . get_class($e) . ': ' . $e->getMessage()
            . ' in ' . $e->getFile() . ':' . $e->getLine());
        if (PHP_SAPI === 'cli') {
            fwrite(STDERR, $logLabel . ': ' . $e->getMessage() . PHP_EOL);
            exit(1);
        }
        if (headers_sent()) {
            echo '<p>Something went wrong and this page stopped part way. Nothing was saved. '
               . 'Reload, and tell the web person if it happens again.</p>';
            exit;
        }
        http_response_code(500);
        header('Retry-After: 30');
        $wantsJson = str_contains((string) ($_SERVER['HTTP_ACCEPT'] ?? ''), 'application/json');
        if ($wantsJson) {
            header('Content-Type: application/json; charset=UTF-8');
            echo json_encode(['ok' => false, 'error' => 'The server hit an error and did not save anything. Try again.']);
            exit;
        }
        header('Content-Type: text/html; charset=UTF-8');
        echo '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Something went wrong</title></head>'
           . '<body><h1>Something went wrong</h1><p>The page stopped before it finished, and nothing was saved. '
           . 'Try again in a moment.</p><p>If it keeps happening, tell the web person: the detail is in the '
           . 'server error log, with the time stamp of this attempt.</p></body></html>';
        exit;
    });
}

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

/**
 * Start the session, eagerly, before any output.
 *
 * Starting it lazily means the first call that needs it (a CSRF token inside a
 * form, say) can land after the headers have gone out, and PHP refuses. The
 * name is the caller's, so two apps on one host do not share a session.
 */
function session_boot(string $name = 'PHPAPP'): void
{
    if (session_status() === PHP_SESSION_ACTIVE) {
        return;
    }
    // A command-line script has no session to start, and a page that has
    // already sent output would only produce warnings.
    if (PHP_SAPI === 'cli' || headers_sent()) {
        if (!isset($_SESSION) || !is_array($_SESSION)) {
            $_SESSION = [];
        }
        return;
    }
    $https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || (($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https');
    session_set_cookie_params([
        'lifetime' => 0,
        'path'     => '/',
        'httponly' => true,
        'secure'   => $https,
        'samesite' => 'Lax',
    ]);
    session_name($name);
    session_start();
}

// ---------------------------------------------------------------------------
// Cross-site request forgery
// ---------------------------------------------------------------------------

/** The session CSRF token, created on first use. */
function csrf_token(): string
{
    session_boot();
    if (empty($_SESSION['csrf_token']) || !is_string($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

/** A hidden input carrying the token. Every state-changing form includes this. */
function csrf_field(): string
{
    return '<input type="hidden" name="csrf_token" value="' . h(csrf_token()) . '">';
}

/**
 * True when the request carries a valid token, in the form field or the
 * X-CSRF-Token header. Only a non-empty string can match; an array posted as
 * csrf_token[]=x is refused rather than turned into the text "Array".
 */
function csrf_valid(?array $post = null, ?array $server = null): bool
{
    $post   = $post ?? $_POST;
    $server = $server ?? $_SERVER;
    $sent = $post['csrf_token'] ?? $server['HTTP_X_CSRF_TOKEN'] ?? '';
    return is_string($sent) && $sent !== '' && hash_equals(csrf_token(), $sent);
}

/** Refuse the request unless it carries a valid token. */
function csrf_require(): void
{
    if (!csrf_valid()) {
        http_response_code(400);
        exit('This form expired or was submitted from another site. Go back, reload the page, and try again.');
    }
}

// ---------------------------------------------------------------------------
// Flash messages
// ---------------------------------------------------------------------------

/** The kinds a flash message may be. */
const FLASH_TYPES = ['success', 'notice', 'warning', 'error'];

/**
 * Queue a message for the next page. Message first, then its type.
 *
 * Throws on an unknown type, which is what a call in the other argument order
 * produces: flash('error', 'Saved') names a type of "Saved".
 */
function flash(string $message, string $type = 'success'): void
{
    if (!in_array($type, FLASH_TYPES, true)) {
        throw new InvalidArgumentException('flash() type "' . $type . '" is not one of '
            . implode(', ', FLASH_TYPES) . '. The message comes first: flash($message, $type).');
    }
    session_boot();
    $_SESSION['flash'][] = ['message' => $message, 'type' => $type];
}

/** The queued messages as HTML, cleared from the session. Every message is kept, in order. */
function flash_html(): string
{
    session_boot();
    $queued = $_SESSION['flash'] ?? [];
    unset($_SESSION['flash']);
    $out = '';
    foreach ($queued as $item) {
        $out .= '<div class="flash flash-' . h($item['type'] ?? 'notice') . '">' . h($item['message'] ?? '') . '</div>';
    }
    return $out;
}

/** Print and clear queued messages. Call it from the page header so no page forgets. */
function flash_render(): void
{
    echo flash_html();
}

// ---------------------------------------------------------------------------
// Database
// ---------------------------------------------------------------------------

/** Hand the library its PDO handle, or read it back with no argument. $forget clears it. */
function db_use(?PDO $pdo = null, bool $forget = false): ?PDO
{
    static $handle = null;
    if ($forget) {
        $handle = null;
        return null;
    }
    if ($pdo !== null) {
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
        $handle = $pdo;
    }
    return $handle;
}

/** The shared PDO handle. Throws when the caller has not given one. */
function db(): PDO
{
    $pdo = db_use();
    if (!$pdo instanceof PDO) {
        throw new RuntimeException('No database handle: call db_use($pdo) or db_open_sqlite($path) first.');
    }
    return $pdo;
}

/**
 * The journal mode a SQLite file at $path should use.
 *
 * DELETE inside a folder a sync client uploads (OneDrive, Dropbox, Google
 * Drive, iCloud Drive, Box): WAL keeps recent writes in a second file, and a
 * sync client uploads the two files separately and out of order, which is how
 * a database becomes unreadable on the other computer
 * (sqlite-on-synced-folders rule 3).
 *
 * WAL everywhere else, the exFAT drive included (App_to_Migrate decision
 * D-012, db-access rule 7): a commit appends to one reused -wal file instead
 * of creating and deleting a rollback journal on a volume that does not
 * journal its own directory entries, and the main file is untouched until a
 * checkpoint.
 */
function db_sqlite_journal_mode(string $path): string
{
    if (preg_match('~(^|[\\\\/])(OneDrive([ -][^\\\\/]*)?|Dropbox|Google Drive|GoogleDrive|My Drive|iCloudDrive|iCloud Drive|Box)([\\\\/]|$)~i', $path)) {
        return 'DELETE';
    }
    return 'WAL';
}

/**
 * Open a SQLite file with the settings the apps rely on and make it the
 * shared handle. The path is the caller's; nothing here decides it.
 *
 * synchronous=FULL always, so a save that returned survives a power cut.
 * Journal mode by location (db_sqlite_journal_mode), checked after setting it.
 * In WAL mode, db_close() folds the -wal into the main file with a TRUNCATE
 * checkpoint; it is also registered to run when the request or script ends.
 */
function db_open_sqlite(string $path): PDO
{
    $pdo = new PDO('sqlite:' . $path, null, null, [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ]);
    $pdo->exec('PRAGMA foreign_keys = ON');
    // Several users post at once; a writer should wait its turn rather than fail.
    $pdo->exec('PRAGMA busy_timeout = 5000');
    if ($path !== ':memory:' && $path !== '') {
        $mode = db_sqlite_journal_mode($path);
        $got = strtoupper((string) $pdo->query('PRAGMA journal_mode = ' . $mode)->fetchColumn());
        if ($got !== $mode) {
            throw new RuntimeException('SQLite would not switch ' . $path . ' to journal_mode ' . $mode . ' (it reports ' . $got . ').');
        }
    }
    $pdo->exec('PRAGMA synchronous = FULL');
    db_use($pdo);
    static $registered = false;
    if (!$registered) {
        register_shutdown_function('db_close');
        $registered = true;
    }
    return $pdo;
}

/**
 * Close the shared handle. A SQLite database in WAL mode is checkpointed with
 * TRUNCATE first, so a cleanly closed database is one file again (before a
 * copy, a backup, or ejecting the drive). Safe to call twice.
 */
function db_close(): void
{
    $pdo = db_use();
    if (!$pdo instanceof PDO) {
        return;
    }
    try {
        if ($pdo->getAttribute(PDO::ATTR_DRIVER_NAME) === 'sqlite'
            && strtolower((string) $pdo->query('PRAGMA journal_mode')->fetchColumn()) === 'wal') {
            $pdo->query('PRAGMA wal_checkpoint(TRUNCATE)')->fetchAll();
        }
    } finally {
        db_use(null, true);
    }
}

/**
 * The placeholders a statement uses: ['named' => [names], 'positional' => n].
 *
 * Skips string literals, double-quoted and backquoted identifiers, line and
 * block comments, and the Postgres "::" cast operator.
 */
function db_placeholders(string $sql): array
{
    $named = [];
    $positional = 0;
    $len = strlen($sql);
    for ($i = 0; $i < $len; $i++) {
        $ch = $sql[$i];
        if ($ch === "'" || $ch === '"' || $ch === '`') {
            // Skip to the closing quote; a doubled quote is an escaped one.
            for ($i++; $i < $len; $i++) {
                if ($sql[$i] === $ch) {
                    if ($i + 1 < $len && $sql[$i + 1] === $ch) {
                        $i++;
                        continue;
                    }
                    break;
                }
            }
            continue;
        }
        if ($ch === '-' && $i + 1 < $len && $sql[$i + 1] === '-') {
            $end = strpos($sql, "\n", $i);
            $i = $end === false ? $len : $end;
            continue;
        }
        if ($ch === '/' && $i + 1 < $len && $sql[$i + 1] === '*') {
            $end = strpos($sql, '*/', $i + 2);
            $i = $end === false ? $len : $end + 1;
            continue;
        }
        if ($ch === '?') {
            $positional++;
            continue;
        }
        if ($ch === ':') {
            if ($i + 1 < $len && $sql[$i + 1] === ':') {
                $i++;               // a "::" cast, not a placeholder
                continue;
            }
            if ($i > 0 && $sql[$i - 1] === ':') {
                continue;
            }
            if (preg_match('/\G:([A-Za-z_][A-Za-z0-9_]*)/', $sql, $m, 0, $i)) {
                $named[$m[1]] = true;
                $i += strlen($m[0]) - 1;
            }
        }
    }
    return ['named' => array_keys($named), 'positional' => $positional];
}

/**
 * Throw unless $params binds exactly the placeholders $sql uses.
 * Keys may be written with or without the leading colon.
 */
function db_check_params(string $sql, array $params): void
{
    $found = db_placeholders($sql);
    if ($found['named'] && $found['positional']) {
        throw new InvalidArgumentException('The statement mixes named and question-mark placeholders; PDO cannot bind that.');
    }
    if ($found['named']) {
        if (array_is_list($params) && $params !== []) {
            throw new InvalidArgumentException('The statement uses named placeholders but was given a list of values.');
        }
        $keys = [];
        foreach (array_keys($params) as $k) {
            $keys[ltrim((string) $k, ':')] = true;
        }
        $missing = array_values(array_diff($found['named'], array_keys($keys)));
        if ($missing) {
            throw new InvalidArgumentException('Unbound placeholder' . (count($missing) > 1 ? 's' : '') . ': :'
                . implode(', :', $missing) . '. SQLite would bind it as NULL and match nothing.');
        }
        $extra = array_values(array_diff(array_keys($keys), $found['named']));
        if ($extra) {
            throw new InvalidArgumentException('Parameter given that the statement does not use: :' . implode(', :', $extra) . '.');
        }
        return;
    }
    if (!array_is_list($params)) {
        if ($params !== []) {
            throw new InvalidArgumentException('Named values were given for a statement with no named placeholders.');
        }
    }
    if (count($params) !== $found['positional']) {
        throw new InvalidArgumentException('The statement has ' . $found['positional'] . ' question mark'
            . ($found['positional'] === 1 ? '' : 's') . ' but ' . count($params) . ' value'
            . (count($params) === 1 ? ' was' : 's were') . ' given.');
    }
}

/** Run a prepared statement and return the statement. Checks the binding first. */
function db_run(string $sql, array $params = []): PDOStatement
{
    db_check_params($sql, $params);
    $stmt = db()->prepare($sql);
    $stmt->execute($params);
    return $stmt;
}

/** Every matching row. */
function db_all(string $sql, array $params = []): array
{
    return db_run($sql, $params)->fetchAll(PDO::FETCH_ASSOC);
}

/** The first matching row, or null. */
function db_one(string $sql, array $params = []): ?array
{
    $row = db_run($sql, $params)->fetch(PDO::FETCH_ASSOC);
    return $row === false ? null : $row;
}

/** The first column of the first matching row, or null. */
function db_value(string $sql, array $params = []): mixed
{
    $value = db_run($sql, $params)->fetchColumn();
    return $value === false ? null : $value;
}

/** "?,?,?" for an IN list of $n values. An empty IN list is a mistake, so it throws. */
function db_in_list(int $n): string
{
    if ($n < 1) {
        throw new InvalidArgumentException('An IN list needs at least one value; check for an empty list before querying.');
    }
    return implode(',', array_fill(0, $n, '?'));
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

/**
 * Say where settings live. Names are checked against a strict pattern and
 * quoted, so they can never carry SQL.
 *
 *   table  settings table, optionally schema-qualified (default "settings")
 *   key    key column (default "key")
 *   value  value column (default "value")
 *   type   value type column, or null when the table has none (default null)
 *   quote  identifier quote: '"' (default, SQLite, Postgres, SQL Server),
 *          '`' (MySQL) or '[' (SQL Server)
 */
function settings_configure(array $cfg = []): array
{
    static $config = null;
    if ($config === null || func_num_args() > 0) {
        $merged = $cfg + ['table' => 'settings', 'key' => 'key', 'value' => 'value', 'type' => null, 'quote' => '"'];
        foreach (['table', 'key', 'value', 'type'] as $part) {
            $name = $merged[$part];
            if ($name === null && $part === 'type') {
                continue;
            }
            if (!is_string($name) || !preg_match('/^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$/', $name)) {
                throw new InvalidArgumentException('Settings ' . $part . ' name is not a plain identifier.');
            }
        }
        if (!in_array($merged['quote'], ['"', '`', '['], true)) {
            throw new InvalidArgumentException('Settings quote must be ", ` or [.');
        }
        $config = $merged;
        if (func_num_args() > 0) {
            settings_forget();
        }
    }
    return $config;
}

/** Quote an identifier that settings_configure() has already checked. */
function settings_ident(string $name): string
{
    $q = settings_configure()['quote'];
    $close = $q === '[' ? ']' : $q;
    return implode('.', array_map(fn($p) => $q . $p . $close, explode('.', $name)));
}

/** Every setting row, keyed by setting key, cached for the request. */
function settings_all(bool $reload = false): array
{
    static $cache = null;
    if ($reload) {
        $cache = null;
        return [];
    }
    if ($cache === null) {
        $c = settings_configure();
        $cols = settings_ident($c['key']) . ' AS k, ' . settings_ident($c['value']) . ' AS v'
              . ($c['type'] !== null ? ', ' . settings_ident($c['type']) . ' AS t' : '');
        $cache = [];
        foreach (db_all('SELECT ' . $cols . ' FROM ' . settings_ident($c['table'])) as $row) {
            $cache[(string) $row['k']] = ['value' => $row['v'] === null ? null : (string) $row['v'],
                                          'type' => isset($row['t']) ? (string) $row['t'] : 'text'];
        }
    }
    return $cache;
}

/** Drop the cache, so the next read is the stored value. set_setting() calls this. */
function settings_forget(): void
{
    settings_all(true);
}

/**
 * A typed setting value.
 *
 *   number   int or float; text that is not a number throws (it never becomes 0)
 *   bool     true for 1, true, yes, on; false for 0, false, no, off, ''; anything else throws
 *   json     the decoded value; invalid JSON throws
 *   other    the stored string
 *
 * A missing key with no default throws: a constant that silently falls back
 * is a rule nobody can see being broken. Pass a default only for wording.
 */
function setting(string $key, mixed $default = null): mixed
{
    $all = settings_all();
    if (!array_key_exists($key, $all) || $all[$key]['value'] === null) {
        if (func_num_args() >= 2) {
            return $default;
        }
        throw new RuntimeException('Setting not seeded: ' . $key);
    }
    $v = $all[$key]['value'];
    switch (strtolower($all[$key]['type'])) {
        case 'number':
        case 'int':
        case 'float':
            $t = trim($v);
            if (!is_numeric($t)) {
                throw new RuntimeException('Setting ' . $key . ' is a number but holds "' . $v . '".');
            }
            return (preg_match('/^[+-]?\d+$/', $t) && abs((float) $t) <= PHP_INT_MAX) ? (int) $t : (float) $t;
        case 'bool':
        case 'boolean':
            $t = strtolower(trim($v));
            if (in_array($t, ['1', 'true', 'yes', 'on'], true)) {
                return true;
            }
            if (in_array($t, ['0', 'false', 'no', 'off', ''], true)) {
                return false;
            }
            throw new RuntimeException('Setting ' . $key . ' is a yes or no value but holds "' . $v . '".');
        case 'json':
            try {
                return json_decode($v, true, 512, JSON_THROW_ON_ERROR);
            } catch (JsonException $e) {
                throw new RuntimeException('Setting ' . $key . ' is JSON but does not parse: ' . $e->getMessage());
            }
        default:
            return $v;
    }
}

/**
 * Write a setting and clear the cache, so a read later in the same request
 * sees the new value. $type is written only when the table has a type column
 * and a type is given.
 */
function set_setting(string $key, mixed $value, ?string $type = null): void
{
    if (is_bool($value)) {
        $value = $value ? '1' : '0';
    } elseif (is_array($value)) {
        $value = json_encode($value, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    } elseif ($value !== null) {
        $value = (string) $value;
    }
    $c = settings_configure();
    $t = settings_ident($c['table']);
    $k = settings_ident($c['key']);
    $v = settings_ident($c['value']);
    $pdo = db();
    $own = !$pdo->inTransaction();
    if ($own) {
        $pdo->beginTransaction();
    }
    try {
        $exists = db_value('SELECT COUNT(*) FROM ' . $t . ' WHERE ' . $k . ' = ?', [$key]);
        $withType = $c['type'] !== null && $type !== null;
        if ((int) $exists > 0) {
            if ($withType) {
                db_run('UPDATE ' . $t . ' SET ' . $v . ' = ?, ' . settings_ident($c['type']) . ' = ? WHERE ' . $k . ' = ?',
                       [$value, $type, $key]);
            } else {
                db_run('UPDATE ' . $t . ' SET ' . $v . ' = ? WHERE ' . $k . ' = ?', [$value, $key]);
            }
        } elseif ($withType) {
            db_run('INSERT INTO ' . $t . ' (' . $k . ', ' . $v . ', ' . settings_ident($c['type']) . ') VALUES (?, ?, ?)',
                   [$key, $value, $type]);
        } else {
            db_run('INSERT INTO ' . $t . ' (' . $k . ', ' . $v . ') VALUES (?, ?)', [$key, $value]);
        }
        if ($own) {
            $pdo->commit();
        }
    } catch (Throwable $e) {
        if ($own && $pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    } finally {
        settings_forget();
    }
}
