<?php
// BACK-OFFICE ingest view for the hosted site (the PHP counterpart of the local
// scripts/admin_server.py). NOT linked from the public site. Identity comes from the
// campus login proxy (the NetID); the role comes from includes/auth.php (D-018).
// Every save is date-stamped; show_until drives the display timer; "Retire" hides a
// record without deleting it. Every statement lives in includes/activities.php and
// runs through includes/db.php with bound values.
//
// Safe saves (owner Q-08, 2026-10-12, D-019):
//   - the form saves only the fields it shows, so a re-save never blanks theme,
//     program, county, keywords, notes, featured, confirm, region or historic;
//   - Edit loads a record with its version, and a save is refused when someone else
//     saved the record after it was opened (no silent overwrite between editors);
//   - every POST carries the drez-php-core CSRF token (csrf_field, csrf_require);
//   - a CSV line changes only the columns its file has.
require __DIR__ . '/../includes/activities.php';
require __DIR__ . '/../includes/auth.php';

session_boot('pri_district_tracker');

// ---- auth ----
// No password table and no custom login. The campus proxy verifies the NetID;
// includes/auth.php turns the NetID and campus groups into a role (D-018):
// viewer reads, editor saves, edits and retires, admin also imports CSV.
$AUTH = require_role('viewer');
$ADMIN_EMAIL = identity_label($AUTH['who']);

pdo();
$SURVEYS = ACTIVITY_SURVEYS;
$TYPES   = ACTIVITY_TYPES;
$SCOPES  = ACTIVITY_SCOPES;
$msg = '';
$msgKind = 'ok';

// ---- handle actions ----
// Writes are allowed by default once the form is safe (owner, 2026-10-12, D-019);
// DT_BACKOFFICE_WRITES=0 makes the back office read-only again. The Data Console
// stays the editor of record until the owner says otherwise: a publish reload
// (tools/load-pg.php --refresh) overwrites a record changed here.
define('BACKOFFICE_WRITES', getenv('DT_BACKOFFICE_WRITES') !== '0');
$CAN_EDIT   = BACKOFFICE_WRITES && role_at_least($AUTH['role'], 'editor');
$CAN_IMPORT = BACKOFFICE_WRITES && role_at_least($AUTH['role'], 'admin');
if ($_SERVER['REQUEST_METHOD'] === 'POST' && !BACKOFFICE_WRITES) {
    http_response_code(403);
    $msg = 'The back office is read-only: edit activities in the Data Console, then publish.';
    $msgKind = 'err';
} elseif ($_SERVER['REQUEST_METHOD'] === 'POST' && !role_at_least($AUTH['role'], !empty($_FILES['csv']['tmp_name']) ? 'admin' : 'editor')) {
    http_response_code(403);
    $msg = 'Your role (' . h((string) $AUTH['role']) . ') may not make this change.';
    $msgKind = 'err';
} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_require();   // stops with 400 unless the form carried this session's token
    try {
        if (isset($_POST['action']) && $_POST['action'] === 'retire') {
            retire_activity((string) $_POST['id']);
            $msg = 'Retired "' . h((string) $_POST['id']) . '" (hidden from the public site, still in the database).';
        } elseif (!empty($_FILES['csv']['tmp_name'])) {
            $fh = fopen($_FILES['csv']['tmp_name'], 'r');
            $head = array_map('trim', fgetcsv($fh) ?: []);
            $fields = $head;
            if (in_array('activity_id', $head, true)) { $fields[] = 'id'; }
            if (in_array('program', $head, true) && !in_array('group', $head, true)) { $fields[] = 'group'; }
            $added = $updated = 0;
            while (($row = fgetcsv($fh)) !== false) {
                $r = @array_combine($head, array_pad($row, count($head), ''));
                if (!$r || trim($r['title'] ?? '') === '' || stripos($r['notes'] ?? '', 'EXAMPLE') === 0) continue;
                $r['id']    = $r['activity_id'] ?? $r['id'] ?? '';
                $r['group'] = $r['group'] ?? ($r['program'] ?? '');
                if (trim($r['show_until'] ?? '') === '' && !in_array($r['type'] ?? '', ['Program', 'Facility'])) {
                    $r['show_until'] = date('Y-m-d', strtotime('+548 days'));
                }
                import_activity_csv_row($r, $fields) === 'added' ? $added++ : $updated++;
            }
            fclose($fh);
            $msg = "Imported/updated " . ($added + $updated) . " record(s) from CSV ($added added, $updated updated; "
                 . 'an existing record changed only in the columns the file has).';
        } else {
            $id = save_activity_form($_POST);
            $msg = 'Saved "' . h($id) . '".';
        }
    } catch (ActivityConflict $e) {
        http_response_code(409);
        $msg = h($e->getMessage());
        $msgKind = 'err';
    } catch (Throwable $e) {
        $msg = 'Error: ' . h($e->getMessage());
        $msgKind = 'err';
    }
}

// ---- the record being edited (GET ?edit=<id>) ----
$EDIT = null;
if ($CAN_EDIT && isset($_GET['edit']) && is_string($_GET['edit'])) {
    $EDIT = get_activity($_GET['edit']);
    if ($EDIT === null) {
        $msg = 'No record "' . h($_GET['edit']) . '".';
        $msgKind = 'err';
    }
}
/** The value a form field shows: the record's when editing, else empty. */
function fv(?array $rec, string $col): string {
    if ($rec === null || !array_key_exists($col, $rec) || $rec[$col] === null) {
        return '';
    }
    if (in_array($col, ['us_house', 'il_senate', 'il_house'], true)) {
        $a = json_decode((string) $rec[$col], true);
        return is_array($a) ? implode(', ', $a) : '';
    }
    if ($col === 'show_until') {
        return substr((string) $rec[$col], 0, 10);
    }
    if (in_array($col, ['latitude', 'longitude'], true)) {
        return activity_norm('num', $rec[$col]) ?? '';
    }
    return (string) $rec[$col];
}

$rows = console_activities();
function opt(array $a, $sel = '') { return implode('', array_map(fn($v) => '<option' . ($v === $sel ? ' selected' : '') . '>' . htmlspecialchars($v) . '</option>', $a)); }
?><!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PRI Data Console (host)</title>
<style>
body{font:15px/1.45 "Segoe UI",system-ui,sans-serif;margin:0;background:#f4f6f8;color:#23272c}
.top{background:#13294B;border-top:6px solid #FF5F05;color:#fff;padding:14px 26px}
.top h1{margin:0;font-size:19px}.top .sub{color:#b9c4d6;font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.wrap{max-width:1080px;margin:0 auto;padding:20px 26px 60px}
.msg{background:#e8f5ec;border:1px solid #b7dfc4;border-radius:8px;padding:10px 14px;margin-bottom:16px}
.msg.err{background:#fdecea;border-color:#f3b8b0}
.note{background:#fff7e6;border:1px solid #f5d79e;border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:13.5px}
.card{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:18px 20px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
.f{display:flex;flex-direction:column;gap:4px}.f.full{grid-column:1/3}
label{font-size:12px;font-weight:600;color:#5b6069;text-transform:uppercase;letter-spacing:.03em}
input,select,textarea{padding:8px 10px;border:1px solid #e3e6ea;border-radius:8px;font:inherit}
.btn{border:0;border-radius:8px;padding:9px 16px;font-weight:600;cursor:pointer}
.pri{background:#FF5F05;color:#fff}.dk{background:#13294B;color:#fff}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e3e6ea;border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid #eee;font-size:13.5px}
th{background:#fafbfc;font-size:11px;text-transform:uppercase;color:#5b6069}
.chip{font-size:11.5px;font-weight:600;padding:2px 8px;border-radius:20px;border:1px solid #e3e6ea}
.on{color:#1c7a3f}.off{color:#8a9099}
.hint{font-size:12px;color:#5b6069}.sec{grid-column:1/3;font-weight:700;color:#13294B;border-top:1px solid #eee;padding-top:10px}
</style></head><body>
<div class="top"><h1>PRI District Tracker &mdash; Data Console (host)</h1>
<div class="sub">Back-office &middot; signed in as <?= htmlspecialchars($ADMIN_EMAIL) ?> (<?= h((string) $AUTH['role']) ?>) &middot; not the public site</div></div>
<div class="wrap">
<?php if ($msg): ?><div class="msg<?= $msgKind === 'err' ? ' err' : '' ?>"><?= $msg ?></div><?php endif; ?>
<div class="note">The Data Console on the staff computer is the editor of record. Each publish reloads this
database from <b>data/activities.json</b>, which replaces any change saved here. Make lasting changes in the
Data Console.</div>

<?php if ($CAN_EDIT): ?>
<div class="card"><h2 style="margin-top:0"><?= $EDIT ? 'Edit "' . h($EDIT['title']) . '"' : 'Add a record' ?></h2>
<form method="post" class="grid" action="admin_ingest.php">
<?= csrf_field() ?>
<?php if ($EDIT): ?><input type="hidden" name="id" value="<?= h($EDIT['id']) ?>"><input type="hidden" name="version" value="<?= (int) $EDIT['version'] ?>">
<div class="f full hint">Record <b><?= h($EDIT['id']) ?></b>, version <?= (int) $EDIT['version'] ?>. Saving changes only the fields
on this form; if someone else saves this record first, your save is refused and nothing is lost.</div><?php endif; ?>
<div class="f"><label>Survey</label><select name="survey"><?= opt($SURVEYS, fv($EDIT, 'survey')) ?></select></div>
<div class="f"><label>Type</label><select name="type"><?= opt($TYPES, fv($EDIT, 'type')) ?></select></div>
<div class="f full"><label>Title *</label><input name="title" required value="<?= h(fv($EDIT, 'title')) ?>"></div>
<div class="f full"><label>Summary * (card blurb)</label><textarea name="summary" required><?= h(fv($EDIT, 'summary')) ?></textarea></div>
<div class="f full"><label>Description</label><textarea name="description"><?= h(fv($EDIT, 'description')) ?></textarea></div>
<div class="f"><label>Lead</label><input name="lead" value="<?= h(fv($EDIT, 'lead')) ?>"></div>
<div class="f"><label>Status</label><input name="status" value="<?= h(fv($EDIT, 'status')) ?>"></div>
<div class="f"><label>Funder / partners</label><input name="funder" value="<?= h(fv($EDIT, 'funder')) ?>"></div>
<div class="f"><label>Program area (group)</label><input name="group" value="<?= h(fv($EDIT, 'group')) ?>"></div>
<div class="f"><label>URL</label><input name="url" value="<?= h(fv($EDIT, 'url')) ?>"></div>
<div class="f"><label>Topic</label><input name="topic" value="<?= h(fv($EDIT, 'topic')) ?>"></div>
<div class="f full"><label>Photo URL (drill-in popup / handout feature)</label><input name="image" value="<?= h(fv($EDIT, 'image')) ?>"></div>
<div class="sec">Location &amp; districts</div>
<div class="f"><label>Scope</label><select name="scope"><?= opt($SCOPES, fv($EDIT, 'scope')) ?></select></div>
<div class="f"><label>Location text</label><input name="location" value="<?= h(fv($EDIT, 'location')) ?>"></div>
<div class="f"><label>Latitude</label><input name="latitude" value="<?= h(fv($EDIT, 'latitude')) ?>"></div>
<div class="f"><label>Longitude</label><input name="longitude" value="<?= h(fv($EDIT, 'longitude')) ?>"></div>
<div class="f"><label>US House</label><input name="us_house" placeholder="13" value="<?= h(fv($EDIT, 'us_house')) ?>"></div>
<div class="f"><label>IL Senate</label><input name="il_senate" placeholder="52" value="<?= h(fv($EDIT, 'il_senate')) ?>"></div>
<div class="f"><label>IL House</label><input name="il_house" placeholder="103" value="<?= h(fv($EDIT, 'il_house')) ?>"></div>
<div class="f"><label>Show until (blank = never expires)</label><input type="date" name="show_until" value="<?= h(fv($EDIT, 'show_until')) ?>"></div>
<div class="f full hint">Districts: enter numbers, or leave blank for statewide. (The local
tool auto-assigns districts from lat/long; on the host either enter them here or curate
locally and import the SQL.)</div>
<div class="f full"><button class="btn pri" type="submit"><?= $EDIT ? 'Save changes' : 'Add record' ?></button>
<?php if ($EDIT): ?> <a href="admin_ingest.php">Cancel</a><?php endif; ?></div>
</form></div>
<?php endif; ?>

<?php if ($CAN_IMPORT): ?>
<div class="card"><h3 style="margin-top:0">Bulk import (CSV, same template as the local tool)</h3>
<form method="post" enctype="multipart/form-data" action="admin_ingest.php">
<?= csrf_field() ?>
<input type="file" name="csv" accept=".csv" required>
<button class="btn dk" type="submit">Upload &amp; ingest</button>
<div class="hint">A new id is added whole; an existing record changes only in the columns the file has.</div>
</form></div>
<?php endif; ?>

<h3>Current records (<?= count($rows) ?>)</h3>
<table><thead><tr><th>Survey</th><th>Title</th><th>Type</th><th>Updated</th><th>Show until</th><th>On site</th><th></th></tr></thead><tbody>
<?php foreach ($rows as $r): ?>
<tr>
<td><b><?= htmlspecialchars($r['survey']) ?></b></td>
<td><?= htmlspecialchars($r['title']) ?><br><span class="hint"><?= htmlspecialchars($r['id']) ?></span></td>
<td><?= htmlspecialchars($r['type']) ?></td>
<td><?= htmlspecialchars($r['updated_at']) ?></td>
<td><?= $r['show_until'] ? htmlspecialchars($r['show_until']) : '<i class="hint">never</i>' ?></td>
<td><span class="chip <?= $r['shown'] ? 'on' : 'off' ?>"><?= $r['shown'] ? 'yes' : 'hidden' ?></span></td>
<td><?php if ($CAN_EDIT): ?><a class="btn" style="border:1px solid #e3e6ea;background:#fff;text-decoration:none;color:inherit;display:inline-block" href="admin_ingest.php?edit=<?= rawurlencode((string) $r['id']) ?>">Edit</a>
<?php if ($r['shown']): ?><form method="post" action="admin_ingest.php" onsubmit="return confirm('Retire (hide) this record? It stays in the database.')" style="margin:4px 0 0">
<?= csrf_field() ?><input type="hidden" name="action" value="retire"><input type="hidden" name="id" value="<?= htmlspecialchars($r['id']) ?>">
<button class="btn" style="border:1px solid #e3e6ea;background:#fff">Retire</button></form><?php endif; ?><?php endif; ?></td>
</tr>
<?php endforeach; ?>
</tbody></table>
</div></body></html>
