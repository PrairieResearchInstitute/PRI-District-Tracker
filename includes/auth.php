<?php
// PRI District Tracker - who the user is, and what the user may do.
//
// Identity (never a password table, never a custom login): the university's
// authenticating proxy in front of the app verifies the user's NetID and passes
// it on in request headers. The header names are settings, because NCSA names
// the proxy at the move:
//   AUTH_USER_HEADER     the NetID            (default X-Forwarded-User)
//   AUTH_EMAIL_HEADER    the campus address   (default X-Forwarded-Email)
//   AUTH_GROUPS_HEADER   the campus groups    (default X-Forwarded-Groups)
//   AUTH_GROUPS_SEPARATOR  between groups     (default ","; ";" for Shibboleth isMemberOf)
//   AUTH_NETID_DOMAINS   address domains whose local part is the NetID (default illinois.edu)
// The headers are trustworthy only while the app is reachable EXCLUSIVELY through
// the proxy: compose.yaml publishes no port, and the proxy strips these headers
// from the incoming request before it sets its own.
//
// Authority (owner, 2026-10-12: "we will be using netid to determine the level of
// authority for user groups across the board"; decision D-018): a user's role is
// the highest role granted to the user's NetID or to any campus group the user
// belongs to. Roles, lowest first:
//   viewer   opens the back office and reads the records
//   editor   also saves, edits and retires records
//   admin    also imports a CSV file
// Grants come from, in this order, all of them counted:
//   1. the user_roles table (migration 0004), managed with tools/roles.php by the
//      owner role; the running app only reads it
//   2. the fallback allowlists in the environment: AUTH_ADMINS, AUTH_EDITORS,
//      AUTH_VIEWERS, each a comma-separated list of NetIDs, addresses and
//      group:<name> entries; ADMIN_EMAILS (the allowlist before D-018) still
//      grants admin
// Authorization is checked here on the server, never by hiding a control.
//
// Local development only: DEV_USER (a NetID or an address) and DEV_GROUPS stand in
// for the proxy when no header arrives. Both MUST be empty on Radiant.

declare(strict_types=1);

require_once __DIR__ . '/db.php';

const AUTH_ROLES = ['viewer' => 1, 'editor' => 2, 'admin' => 3];
const AUTH_NETID_PATTERN = '/^[a-z][a-z0-9._-]{0,63}$/';

/** A setting from the environment, trimmed, or the default. */
function auth_setting(string $name, string $default = ''): string {
    $v = getenv($name);
    return ($v === false || trim($v) === '') ? $default : trim($v);
}

/** One request header by its HTTP name (X-Forwarded-User -> HTTP_X_FORWARDED_USER). */
function auth_header(string $name, ?array $server = null): string {
    $server = $server ?? $_SERVER;
    $key = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
    return trim((string) ($server[$key] ?? ''));
}

/** The domains whose addresses carry a NetID as their local part. */
function auth_netid_domains(): array {
    return array_values(array_filter(array_map('strtolower', array_map('trim',
        explode(',', auth_setting('AUTH_NETID_DOMAINS', 'illinois.edu'))))));
}

/** A NetID from a bare NetID or a campus address, or null when it is neither. */
function auth_netid_from(string $value): ?string {
    $value = strtolower(trim($value));
    if ($value === '') {
        return null;
    }
    if (str_contains($value, '@')) {
        [$local, $domain] = explode('@', $value, 2);
        if (!in_array($domain, auth_netid_domains(), true)) {
            return null;
        }
        $value = $local;
    }
    return preg_match(AUTH_NETID_PATTERN, $value) ? $value : null;
}

/** Group names from one header value, split on the configured separator, case kept. */
function auth_split_groups(string $value): array {
    $sep = auth_setting('AUTH_GROUPS_SEPARATOR', ',');
    $out = [];
    foreach (explode($sep, $value) as $g) {
        $g = trim($g);
        if ($g !== '' && strlen($g) <= 255) {
            $out[strtolower($g)] = $g;
        }
    }
    return array_values($out);
}

/**
 * The signed-in user: ['netid' => ?string, 'email' => ?string, 'groups' => string[]],
 * or null when the request carries no identity at all.
 */
function current_identity(?array $server = null): ?array {
    $user   = auth_header(auth_setting('AUTH_USER_HEADER', 'X-Forwarded-User'), $server);
    $email  = strtolower(auth_header(auth_setting('AUTH_EMAIL_HEADER', 'X-Forwarded-Email'), $server));
    $groups = auth_header(auth_setting('AUTH_GROUPS_HEADER', 'X-Forwarded-Groups'), $server);
    if ($user === '' && $email === '') {
        $dev = strtolower(auth_setting('DEV_USER'));
        if ($dev === '') {
            return null;
        }
        if (str_contains($dev, '@')) {
            $email = $dev;
        } else {
            $user = $dev;
        }
        $groups = auth_setting('DEV_GROUPS');
    }
    if ($email === '' && str_contains($user, '@')) {
        $email = strtolower($user);
    }
    $netid = auth_netid_from($user) ?? auth_netid_from($email);
    if ($netid === null && $email === '') {
        return null;
    }
    return ['netid' => $netid, 'email' => $email !== '' ? $email : null, 'groups' => auth_split_groups($groups)];
}

/** The fallback allowlist of one role: entries lowercased, groups prefixed "group:". */
function auth_allowlist(string $role): array {
    $names = ['admin' => 'AUTH_ADMINS', 'editor' => 'AUTH_EDITORS', 'viewer' => 'AUTH_VIEWERS'];
    $raw = auth_setting($names[$role]);
    if ($role === 'admin') {
        $raw .= ',' . auth_setting('ADMIN_EMAILS');
    }
    $out = [];
    foreach (explode(',', $raw) as $e) {
        $e = strtolower(trim($e));
        if ($e !== '') {
            $out[] = $e;
        }
    }
    return $out;
}

/** True when an allowlist entry names this user (NetID, address or group:<name>). */
function auth_entry_matches(string $entry, array $who): bool {
    if (str_starts_with($entry, 'group:')) {
        $g = substr($entry, 6);
        return in_array($g, array_map('strtolower', $who['groups']), true);
    }
    if (str_contains($entry, '@')) {
        return $who['email'] !== null && $entry === $who['email'];
    }
    return $who['netid'] !== null && $entry === $who['netid'];
}

/**
 * Grants from the user_roles table for this user, as a list of role names.
 * A database without migration 0004 yet holds no grants, so the allowlists decide.
 */
function auth_table_roles(array $who): array {
    $where = [];
    $params = [];
    if ($who['netid'] !== null) {
        $where[] = "(principal_kind = 'netid' AND principal = ?)";
        $params[] = $who['netid'];
    }
    if ($who['groups']) {
        $where[] = "(principal_kind = 'group' AND principal IN (" . db_in_list(count($who['groups'])) . '))';
        foreach ($who['groups'] as $g) {
            $params[] = strtolower($g);
        }
    }
    if (!$where) {
        return [];
    }
    try {
        pdo();
        $rows = db_all('SELECT role FROM user_roles WHERE revoked_at IS NULL AND (' . implode(' OR ', $where) . ')', $params);
    } catch (PDOException $e) {
        if (auth_table_missing($e)) {
            return [];
        }
        throw $e;
    }
    return array_column($rows, 'role');
}

/** True when the error says user_roles does not exist (PostgreSQL 42P01, MySQL 42S02). */
function auth_table_missing(PDOException $e): bool {
    return in_array((string) $e->getCode(), ['42P01', '42S02'], true);
}

/** The highest role this user holds, or null for none. */
function user_role(array $who, bool $useTable = true): ?string {
    $best = null;
    $consider = function (string $role) use (&$best): void {
        if (isset(AUTH_ROLES[$role]) && ($best === null || AUTH_ROLES[$role] > AUTH_ROLES[$best])) {
            $best = $role;
        }
    };
    foreach (array_keys(AUTH_ROLES) as $role) {
        foreach (auth_allowlist($role) as $entry) {
            if (auth_entry_matches($entry, $who)) {
                $consider($role);
                break;
            }
        }
    }
    if ($useTable) {
        foreach (auth_table_roles($who) as $role) {
            $consider((string) $role);
        }
    }
    return $best;
}

/** True when $role is at least $min. */
function role_at_least(?string $role, string $min): bool {
    return $role !== null && isset(AUTH_ROLES[$min]) && (AUTH_ROLES[$role] ?? 0) >= AUTH_ROLES[$min];
}

/** How the user is named on a page: the NetID, else the address. */
function identity_label(array $who): string {
    return (string) ($who['netid'] ?? $who['email'] ?? '');
}

/**
 * Gate a page. Returns ['who' => identity, 'role' => role] when the user holds at
 * least $min, or stops with 401 (no identity) or 403 (no such role).
 */
function require_role(string $min): array {
    $who = current_identity();
    if ($who === null) {
        http_response_code(401);
        exit('Not signed in. This page must be reached through the campus login proxy.');
    }
    $role = user_role($who);
    if (!role_at_least($role, $min)) {
        http_response_code(403);
        exit('Signed in as ' . h(identity_label($who)) . ', which holds no ' . h($min)
             . ' role for tracker data. Ask an administrator to grant your NetID or one of your campus groups a role.');
    }
    return ['who' => $who, 'role' => $role];
}
