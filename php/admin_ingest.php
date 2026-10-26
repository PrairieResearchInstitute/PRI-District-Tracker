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
require __DIR__ . '/../includes/ui.php';

core_install_exception_handler('pri-district-tracker', 'dt_error_page');
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
// Set when a retire needs confirming, so the page asks on itself rather than
// through a native confirm() that cannot be styled and dies with JavaScript off
// (PDT-37, Q-27). Holds the record id waiting for a yes.
$confirmRetire = null;

/**
 * One confirmation card for a post that cannot be undone casually.
 *
 * docs/design.md section 4. The question stands on the page the reader is already
 * looking at, the posted fields ride along as hidden inputs with a fresh CSRF token
 * and confirmed=1, and Cancel sits on the left with the action on the right.
 *
 * Here rather than in includes/core.php, which is synced from drez-php-core and
 * shared; the spec allows a local includes/ui.php when a second page needs it.
 *
 * @param array<string,string> $fields the posted fields to carry forward
 */
function dt_confirm_page(string $title, string $question, string $okLabel,
                         array $fields, string $cancelHref): string
{
    $html = '<div class="confirm" role="group" aria-labelledby="dt-confirm-t">'
          . '<h2 id="dt-confirm-t">' . h($title) . '</h2>'
          . '<p>' . h($question) . '</p>'
          . '<form method="post" action="admin_ingest.php">' . csrf_field()
          . '<input type="hidden" name="confirmed" value="1">';
    foreach ($fields as $name => $value) {
        $html .= '<input type="hidden" name="' . h($name) . '" value="' . h($value) . '">';
    }
    return $html
         . '<a class="btn gh" href="' . h($cancelHref) . '">Cancel</a>'
         . '<button class="btn pri" type="submit">' . h($okLabel) . '</button>'
         . '</form></div>';
}

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
        if (isset($_POST['action']) && $_POST['action'] === 'retire' && empty($_POST['confirmed'])) {
            $confirmRetire = (string) $_POST['id'];
        } elseif (isset($_POST['action']) && $_POST['action'] === 'retire') {
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
<title>PRI District Tracker: Data Console (host)</title>
<?= dt_icon_link() ?>
<link rel="stylesheet" href="../assets/fonts.css">
<style>
<?= DT_TOKENS ?>
body{font-family:var(--font-body);font-size:var(--fs-body);line-height:1.45;margin:0;background:var(--page);color:var(--ink)}
.top{background:var(--blue);border-top:6px solid var(--orange);color:#fff;padding:14px 26px}
.top h1{margin:0;font-size:17px}.top .sub{color:#b9c4d6;font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.wrap{max-width:1060px;margin:0 auto;padding:20px 26px 60px}
<?= DT_FOOT_CSS ?>
.notice{border-radius:var(--radius-md);padding:10px 14px;font-size:13px;line-height:1.45;margin:0 0 16px}
.notice.ok,.flash-success{background:var(--ok-bg);border:1px solid var(--ok-line);color:var(--ok-text)}
.notice.warn,.flash-notice{background:var(--warn-bg);border:1px solid var(--warn-line);color:var(--warn-text)}
.notice.err,.flash-error{background:var(--err-bg);border:1px solid var(--err-line);color:var(--err-text)}
.flash{border-radius:var(--radius-md);padding:10px 14px;font-size:13px;margin:0 0 16px}
.card{background:#fff;border:1px solid var(--line);border-radius:var(--radius-lg);padding:18px 20px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
.f{display:flex;flex-direction:column;gap:4px}.f.full{grid-column:1 / -1}
label{font-size:12px;font-weight:600;color:var(--storm-dark);text-transform:uppercase;letter-spacing:.03em}
input,select,textarea{padding:8px 10px;border:1px solid var(--field);border-radius:var(--radius-md);font:inherit}
/* The same button as the public pages (PDT-05; build_site.py buttons_css). Q-26:
   white never sits on var(--orange), so the primary carries navy and hovers to var(--il-altgeld). */
.btn{border:0;border-radius:var(--radius-md);padding:9px 16px;cursor:pointer;text-decoration:none;
  display:inline-block;font-family:inherit;font-size:14px;line-height:1.15;font-weight:600}
.btn.pri{background:var(--orange);color:var(--blue)}
.btn.pri:hover{background:var(--il-altgeld);color:#fff}
.btn.dk{background:var(--blue);color:#fff}
.btn.dk:hover{background:var(--blue-deep)}
.btn.gh{background:#fff;border:1px solid var(--line);color:#23272C}
.btn.gh:hover{background:var(--soft)}
.btn.gh{background:#fff;border:1px solid var(--line);color:var(--ink)}
.btn.gh:hover{background:var(--soft)}
.btn.sm{padding:4px 9px;border-radius:var(--radius-sm);font-size:12px}
.btn:disabled{opacity:.5;cursor:default}
.confirm{background:#fff;border:1px solid var(--line);border-left:5px solid var(--orange);border-radius:var(--radius-lg);
  padding:16px 20px;margin-bottom:16px}
.confirm h2{margin:0 0 6px;font-size:17px;color:var(--blue)}
.confirm p{margin:0 0 14px;font-size:14px;line-height:1.5}
.confirm form{display:flex;gap:10px;align-items:center;margin:0}
/* PDT-07: one visible focus ring. */
:focus-visible{outline:3px solid var(--link);outline-offset:2px;border-radius:var(--radius-xs)}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:var(--radius-lg);overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);font-size:var(--fs-table-cell)}
th{background:#FAFBFC;font-size:var(--fs-table-head);text-transform:uppercase;letter-spacing:.05em;color:var(--storm)}
tr:last-child td{border-bottom:0}
td.empty{text-align:center;color:var(--storm);padding:26px}
.chip{font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;border:1px solid var(--line)}
.chip.shown{color:#1C7A3F}.chip.hidden-state{color:#8A9099}
.hint{font-size:12px;color:var(--storm-dark)}.sec{grid-column:1 / -1;font-weight:700;color:var(--blue);border-top:1px solid #eee;padding-top:10px}
.tscroll{overflow-x:auto}
@media(max-width:820px){.wrap{padding-left:16px;padding-right:16px}
  .grid{grid-template-columns:1fr}}
</style></head><body>
<?= dt_back_office_head('PRI District Tracker: Data Console (host)',
      'Back-office / signed in as ' . $ADMIN_EMAIL . ' (' . (string) $AUTH['role'] . ') / not the public site') ?>
<div class="wrap">
<?php if ($msg): ?><div class="notice <?= $msgKind === 'err' ? 'err' : 'ok' ?>" role="status"><?= $msg ?></div><?php endif; ?>
<?php if ($confirmRetire !== null): ?>
<?= dt_confirm_page('Retire This Record?',
      'The record leaves the public site and stays in the database, so you can show it again later.',
      'Retire Record', ['action' => 'retire', 'id' => $confirmRetire], 'admin_ingest.php') ?>
<?php endif; ?>
<div class="notice warn">The Data Console on the staff computer is the editor of record. Each publish reloads this
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
<div class="f"><label>Status</label><select name="status">
<option value=""></option>
<?php foreach (DT_STATUSES as $s): ?><option<?= fv($EDIT, 'status') === $s ? ' selected' : '' ?>><?= h($s) ?></option><?php endforeach; ?>
</select></div>
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
<div class="tscroll"><table><thead><tr><th>Survey</th><th>Title</th><th>Type</th><th>Updated</th><th>Show until</th><th>On Site</th><th></th></tr></thead><tbody>
<?php foreach ($rows as $r): ?>
<tr>
<td><b><?= htmlspecialchars($r['survey']) ?></b></td>
<td><?= htmlspecialchars($r['title']) ?><br><span class="hint"><?= htmlspecialchars($r['id']) ?></span></td>
<td><?= htmlspecialchars($r['type']) ?></td>
<td><?= htmlspecialchars($r['updated_at']) ?></td>
<td><?= $r['show_until'] ? htmlspecialchars($r['show_until']) : '<i class="hint">never</i>' ?></td>
<td><span class="chip <?= $r['shown'] ? 'shown' : 'hidden-state' ?>"><?= $r['shown'] ? 'Showing' : 'Expired' ?></span></td>
<td><?php if ($CAN_EDIT): ?><a class="btn gh sm" href="admin_ingest.php?edit=<?= rawurlencode((string) $r['id']) ?>">Edit</a>
<?php if ($r['shown']): ?><form method="post" action="admin_ingest.php" style="margin:4px 0 0">
<?= csrf_field() ?><input type="hidden" name="action" value="retire"><input type="hidden" name="id" value="<?= htmlspecialchars($r['id']) ?>">
<button class="btn gh sm" type="submit">Retire</button></form><?php endif; ?><?php endif; ?></td>
</tr>
<?php endforeach; ?>
</tbody></table></div>
</div><?= dt_back_office_foot() ?></body></html>
