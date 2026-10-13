<?php
// PRI District Tracker - the activities table: column list, the two ways a row
// arrives (a back-office form or CSV line, and a record of data/activities.json),
// and the statements that write it. Pages and tools call these; all SQL is bound.

declare(strict_types=1);

require_once __DIR__ . '/db.php';

const ACTIVITY_SURVEYS = ['INHS', 'ISGS', 'ISWS', 'ISAS', 'ISTC'];
const ACTIVITY_TYPES   = ['Program', 'Project', 'Facility', 'Grant', 'Publication', 'News', 'Community science'];
const ACTIVITY_SCOPES  = ['statewide', 'sited', 'regional', 'external'];

/**
 * The canonical column list, identical to the migrations, sql/schema.sql and
 * scripts/pri_sql.py COLUMNS (tests/test_schema_parity.py holds them together).
 * `version` is left out: the database owns it (default 1, +1 on every write).
 */
function activity_columns(): array {
    return ['id','survey','title','type','topic','group','summary','description','lead',
            'program','funder','partners','status','start_year','end_year','url','image','scope',
            'latitude','longitude','county','location','us_house','il_senate','il_house',
            'featured','confirm','keywords','notes','theme','ingested_at','updated_at','show_until',
            'region','historic'];
}

/** How each column is stored, for loading and comparing. */
function activity_kinds(): array {
    $k = array_fill_keys(activity_columns(), 'str');
    foreach (['summary', 'description', 'notes'] as $c)          { $k[$c] = 'text'; }
    foreach (['latitude', 'longitude'] as $c)                    { $k[$c] = 'num'; }
    foreach (['us_house', 'il_senate', 'il_house'] as $c)        { $k[$c] = 'json'; }
    foreach (['featured', 'confirm', 'historic'] as $c)          { $k[$c] = 'bool'; }
    foreach (['ingested_at', 'updated_at'] as $c)                { $k[$c] = 'dt'; }
    $k['show_until'] = 'date';
    return $k;
}

function slugify(string $s): string {
    $s = strtolower(trim($s));
    $s = preg_replace('/[^a-z0-9]+/', '-', $s);
    return trim($s, '-') ?: 'item';
}

function districts_json($v): string {
    if (is_array($v)) { $items = $v; }
    else { $items = preg_split('/[,;\s]+/', trim((string)$v), -1, PREG_SPLIT_NO_EMPTY); }
    $out = [];
    foreach ($items as $x) { if (ctype_digit((string)$x)) { $out[] = (int)$x; } }
    return json_encode($out);
}

/** Bind one row of canonical values (null where the column takes NULL) and run the upsert. */
function activity_write(array $row): void {
    $cols = activity_columns();
    $params = [];
    foreach ($cols as $c) {
        $v = $row[$c] ?? null;
        if (is_bool($v)) {
            $v = $v ? 1 : 0;
        }
        $params[$c] = $v;
    }
    db_run(db_upsert_sql('activities', $cols, 'id', ['ingested_at'], ['version']), $params);
}

/**
 * Upsert one record from the back-office form or a CSV line. Stamps dates; sets
 * show_until. Returns the id. Mirrors the local tool's rules 1:1.
 */
function upsert_activity(array $d): string {
    $id = trim((string) ($d['id'] ?? '')) ?: slugify((string) ($d['title'] ?? ''));
    // districts: for statewide/external force empty
    $scope = $d['scope'] ?? 'statewide';
    foreach (['us_house', 'il_senate', 'il_house'] as $k) {
        $d[$k] = in_array($scope, ['statewide', 'external']) ? '[]' : districts_json($d[$k] ?? '');
    }
    $d['id']         = $id;
    $d['featured']   = !empty($d['featured']) ? 1 : 0;
    $d['confirm']    = !empty($d['confirm']) ? 1 : 0;
    $d['historic']   = !empty($d['historic']) ? 1 : 0;
    $d['latitude']   = ($d['latitude']  ?? '') === '' ? null : (float)$d['latitude'];
    $d['longitude']  = ($d['longitude'] ?? '') === '' ? null : (float)$d['longitude'];
    $d['show_until'] = trim((string)($d['show_until'] ?? '')) ?: null;   // blank = evergreen = NULL
    $d['updated_at'] = date('Y-m-d H:i:s');
    $d['ingested_at'] = date('Y-m-d H:i:s');   // COALESCE in the upsert keeps the original on update

    $row = [];
    foreach (activity_columns() as $c) {
        $v = array_key_exists($c, $d) ? $d[$c] : null;
        // numeric/date columns keep real NULLs; text columns fall back to '' (some are NOT NULL)
        if ($v === null && !in_array($c, ['latitude', 'longitude', 'show_until'], true)) {
            $v = '';
        }
        $row[$c] = $v;
    }
    activity_write($row);
    return $id;
}

/**
 * The fields the back-office form shows. A save from the form writes these and
 * nothing else, so theme, program, county, keywords, notes, featured, confirm,
 * region and historic keep the values the Data Console gave them (owner Q-08).
 */
const ACTIVITY_FORM_FIELDS = ['survey', 'type', 'title', 'summary', 'description', 'lead', 'status', 'funder', 'group',
                              'url', 'topic', 'image', 'scope', 'location', 'latitude', 'longitude',
                              'us_house', 'il_senate', 'il_house', 'show_until'];

/** A save that would overwrite someone else's newer save, or a record that is not there. */
class ActivityConflict extends RuntimeException {}

/**
 * The stored values of the given columns, from submitted input, by the same rules
 * as upsert_activity(): districts become JSON (empty when the scope is statewide or
 * external), coordinates numbers or NULL, a blank show_until NULL, flags 1 or 0.
 * Only the columns in $fields that are activity columns come back.
 */
function activity_input_values(array $d, array $fields): array {
    $allowed = array_diff(activity_columns(), ['id', 'ingested_at', 'updated_at']);
    $kinds = activity_kinds();
    $scope = array_key_exists('scope', $d) ? (string) $d['scope'] : null;
    $out = [];
    foreach ($fields as $c) {
        if (!in_array($c, $allowed, true)) {
            continue;
        }
        $v = $d[$c] ?? '';
        switch ($kinds[$c]) {
            case 'json':
                $out[$c] = ($scope !== null && in_array($scope, ['statewide', 'external'], true)) ? '[]' : districts_json($v);
                break;
            case 'num':
                $v = trim((string) $v);
                $out[$c] = $v === '' ? null : (float) $v;
                break;
            case 'date':
                $v = trim((string) $v);
                $out[$c] = $v === '' ? null : $v;
                break;
            case 'bool':
                $out[$c] = in_array(strtolower(trim((string) $v)), ['1', 'yes', 'true', 'on'], true) ? 1 : 0;
                break;
            default:
                $out[$c] = (string) $v;
        }
    }
    return $out;
}

/** One record by id, or null. */
function get_activity(string $id): ?array {
    return db_one('SELECT * FROM activities WHERE id = ?', [$id]);
}

/**
 * Change only $values on an existing record. With $expectedVersion the update
 * happens only while the record still carries that version, and a newer save
 * raises ActivityConflict instead of being overwritten. Returns the new version.
 */
function update_activity_fields(string $id, array $values, ?int $expectedVersion): int {
    if (!$values) {
        throw new InvalidArgumentException('Nothing to save.');
    }
    $set = [];
    $params = ['id' => $id, 'updated_at' => date('Y-m-d H:i:s')];
    foreach ($values as $c => $v) {
        $set[] = db_ident($c) . ' = :' . $c;
        $params[$c] = $v;
    }
    $sql = 'UPDATE activities SET ' . implode(', ', $set) . ', updated_at = :updated_at, version = version + 1 WHERE id = :id';
    if ($expectedVersion !== null) {
        $sql .= ' AND version = :expected';
        $params['expected'] = $expectedVersion;
    }
    if (db_run($sql, $params)->rowCount() === 0) {
        $now = db_value('SELECT version FROM activities WHERE id = ?', [$id]);
        if ($now === null || $now === false) {
            throw new ActivityConflict('No record "' . $id . '" exists any more.');
        }
        throw new ActivityConflict('Someone saved "' . $id . '" after you opened it (it is now at version ' . (int) $now
            . ', you opened version ' . (int) $expectedVersion . '). Nothing was saved: open it again with Edit and redo your change.');
    }
    return (int) db_value('SELECT version FROM activities WHERE id = ?', [$id]);
}

/**
 * Add a new record from submitted input. Every column gets a value (a new record
 * has nothing to lose); an id that already exists is refused rather than
 * overwritten. Returns the id.
 */
function insert_activity(array $d): string {
    $id = trim((string) ($d['id'] ?? '')) ?: slugify((string) ($d['title'] ?? ''));
    if (get_activity($id) !== null) {
        throw new ActivityConflict('A record with the id "' . $id . '" already exists. Open it with Edit to change it.');
    }
    $row = array_fill_keys(activity_columns(), '');
    $row = array_merge($row, activity_input_values($d + ['scope' => 'statewide'], activity_columns()));
    foreach (['latitude', 'longitude', 'show_until'] as $c) {
        $row[$c] = $row[$c] === '' ? null : $row[$c];
    }
    $row['id'] = $id;
    $row['ingested_at'] = $row['updated_at'] = date('Y-m-d H:i:s');
    $cols = activity_columns();
    db_run('INSERT INTO activities (' . implode(', ', array_map('db_ident', $cols)) . ') VALUES (:'
           . implode(', :', $cols) . ')', array_intersect_key($row, array_flip($cols)));
    return $id;
}

/**
 * Save the back-office form: a new record when no id came with it, otherwise an
 * update of the form's fields only, refused when the record changed since the
 * editor opened it. Returns the id.
 */
function save_activity_form(array $post): string {
    $id = trim((string) ($post['id'] ?? ''));
    if ($id === '') {
        return insert_activity($post);
    }
    $version = trim((string) ($post['version'] ?? ''));
    if (!ctype_digit($version)) {
        throw new ActivityConflict('The form carried no record version. Open the record again with Edit.');
    }
    update_activity_fields($id, activity_input_values($post, ACTIVITY_FORM_FIELDS), (int) $version);
    return $id;
}

/**
 * One CSV line: a new id is added whole; an existing id changes only the columns
 * the CSV file has, so a short CSV never blanks the rest of a record.
 * Returns 'added' or 'updated'.
 */
function import_activity_csv_row(array $r, array $header): string {
    $id = trim((string) ($r['id'] ?? '')) ?: slugify((string) ($r['title'] ?? ''));
    if (get_activity($id) === null) {
        insert_activity(['id' => $id] + $r);
        return 'added';
    }
    $fields = array_values(array_intersect(activity_columns(), $header));
    update_activity_fields($id, activity_input_values($r, $fields), null);
    return 'updated';
}

/** Hide a record from the public site without deleting it: show_until becomes yesterday. */
function retire_activity(string $id): int {
    return db_run("UPDATE activities SET show_until = CURRENT_DATE - INTERVAL '1' DAY, updated_at = NOW(),
                   version = version + 1 WHERE id = ?", [$id])->rowCount();
}

/** Every record still shown on the public site, in display order. */
function fresh_activities(): array {
    return db_all('SELECT * FROM activities WHERE ' . FRESH_WHERE . ' ORDER BY survey, title');
}

/** The back-office list: every record, with whether the public site shows it. */
function console_activities(): array {
    return db_all('SELECT id, survey, title, type, scope, updated_at, show_until, (' . FRESH_WHERE . ') AS shown
                   FROM activities ORDER BY updated_at DESC, survey');
}

/**
 * The row a record of data/activities.json becomes, in canonical form: the same
 * mapping as scripts/pri_sql.py (blank survey -> INHS, blank show_until -> NULL,
 * a date stamp -> midnight, district lists -> JSON text). Values are kept as the
 * source has them; nothing is re-stamped.
 */
function activity_from_json(array $rec): array {
    $row = [];
    foreach (activity_kinds() as $c => $kind) {
        $v = $rec[$c] ?? null;
        switch ($kind) {
            case 'str':
            case 'text':
                $row[$c] = $v === null ? '' : (string) $v;
                break;
            case 'bool':
                $row[$c] = $v ? 1 : 0;
                break;
            case 'num':
                $s = $v === null ? '' : trim((string) $v);
                $row[$c] = $s === '' ? null : $s;
                break;
            case 'date':
                $s = trim((string) ($v ?? ''));
                $row[$c] = $s === '' ? null : $s;
                break;
            case 'dt':
                $s = trim((string) ($v ?? ''));
                $row[$c] = $s === '' ? null : (strlen($s) === 10 ? $s . ' 00:00:00' : $s);
                break;
            case 'json':
                $row[$c] = json_encode(is_array($v) ? array_values($v) : []);
                break;
        }
    }
    if (trim($row['survey']) === '') {
        $row['survey'] = 'INHS';   // the front end's surveyOf default; keeps the database clean
    }
    return $row;
}

/**
 * One value in a form both engines and the JSON source agree on, so a row read
 * back can be compared with the row that was written. Used by the loader's check.
 */
function activity_norm(string $kind, $v) {
    if ($v === null) {
        return null;
    }
    switch ($kind) {
        case 'bool':
            return (is_bool($v) ? $v : in_array(strtolower((string) $v), ['1', 't', 'true'], true)) ? 1 : 0;
        case 'num':
            return rtrim(rtrim(number_format((float) $v, 6, '.', ''), '0'), '.');
        case 'json':
            $a = json_decode((string) $v, true);
            return is_array($a) ? json_encode(array_map('intval', $a)) : (string) $v;
        case 'dt':
            return substr((string) $v, 0, 19);
        case 'date':
            return substr((string) $v, 0, 10);
        default:
            return (string) $v;
    }
}

/** A row reduced to its normalised values, in column order. */
function activity_normalise(array $row): array {
    $out = [];
    foreach (activity_kinds() as $c => $kind) {
        $out[$c] = activity_norm($kind, $row[$c] ?? null);
    }
    return $out;
}
