<?php

declare(strict_types=1);

/**
 * The back office's shared chrome (UI Elements deviation PDT-14).
 *
 * admin_ingest.php drew its own navy bar, the Data Console drew a slightly different
 * one, and the 401 and 403 replies were bare text on a white page: no bar, no styling,
 * nothing to say which application had refused. One partial now draws all of them.
 *
 * The token block is a copy of scripts/ui_tokens.py, because PHP cannot import Python.
 * tests/test_tokens.py compares the two character for character and fails if they
 * drift, the way tests/test_freshness.py holds the display timer's two copies together.
 *
 * Developed by M. J. Dreslik, with Claude Opus 5 (drez-ui-elements rule 27): every back-office
 * page closes with dt_back_office_foot(), and tools/check.py looks for the line.
 *
 * The 500 page in includes/core.php is NOT routed through here: that file is synced
 * from drez-php-core (drez-php-core.sync.json records its hash) and is not this app's
 * to edit. Changing it belongs in the library.
 */

const DT_TOKENS = <<<'CSS'
:root{
  /* Colour */
  --blue:#13294B;
  --blue-deep:#0E1F3A;
  --orange:#FF5F05;
  --orange-hover:#D94E00;
  --il-altgeld:#C84113;
  --on-accent:#13294B;
  --link:#1D58A7;
  --ink:#1A1A1A;
  --storm:#707372;
  --storm-dark:#4A4C4B;
  --line:#E3E3E2;
  --field:#C9C9C7;
  --soft:#F0F1F0;
  --page:#F4F6F8;
  --ok-bg:#E8F5EC;   --ok-line:#B7DFC4;   --ok-text:#14532D;
  --warn-bg:#FFF8EF; --warn-line:#F2D9B3; --warn-text:#7A5312;
  --err-bg:#FDECEA;  --err-line:#F5C2BC;  --err-text:#7F1D1D;
  --backdrop:rgba(19,41,75,.55);
  /* Type */
  --font-body:'Source Sans 3','Source Sans Pro',Arial,sans-serif;
  --font-head:'Montserrat',Arial,sans-serif;
  --font-mono:Consolas,'Courier New',monospace;
  --fs-badge:11px;  --fs-label:12px; --fs-second:13px; --fs-control:14px;
  --fs-body:15px;   --fs-card:17px;  --fs-dialog:22px; --fs-page:26px;
  --fs-table-head:11.5px; --fs-table-cell:13.5px;
  /* Shape, space, elevation, layers, motion */
  --radius-xs:4px; --radius-sm:6px; --radius-md:8px; --radius-lg:10px;
  --radius-dialog:12px; --radius-pill:999px;
  --shadow-2:0 24px 60px rgba(0,0,0,.3);
  --z-tabs:40; --z-dialog:50; --z-toast:60;
  --dur-fast:.12s;
  /* Focus: navy on light grounds; the orange form is used on navy bars. */
  --focus:2px solid #13294B;
  --focus-on-dark:2px solid #FF5F05;
}
CSS;

/**
 * The record Status list (Q-16). A copy of scripts/pri_data.py STATUSES, because
 * PHP cannot import it; tests/test_tokens.py fails if the two drift apart.
 */
const DT_STATUSES = ['Active', 'Ongoing', 'Completed', 'Planned', 'Published', 'Pending'];

/**
 * The 500 page, in the back office's chrome.
 *
 * Passed to core_install_exception_handler() as its page renderer. The handler tells
 * it nothing about the error on purpose: the detail goes to the server log, and the
 * visitor gets a sentence. If this throws, the handler prints its own plain page.
 */
function dt_error_page(): void
{
    echo dt_back_office_page(
        'PRI District Tracker: Data Console (host)',
        'Back-office / something went wrong',
        '<div class="notice err">The server hit an error and did not save anything. '
        . 'Reload the page, and tell the web person if it keeps happening.</div>'
    );
}

/** The navy bar every back-office page opens with. */
function dt_back_office_head(string $title, string $subtitle): string
{
    return '<div class="top"><h1>' . h($title) . '</h1>'
        . ($subtitle === '' ? '' : '<div class="sub">' . h($subtitle) . '</div>')
        . '</div>';
}

/** The authorship credit that closes every back-office page (drez-ui-elements rule 27). */
const DT_CREDIT = 'Developed by M. J. Dreslik, with Claude Opus 5';

function dt_back_office_foot(): string
{
    return '<footer class="foot">' . DT_CREDIT . '</footer>';
}

/** The CSS for that footer, shared by every back-office page. */
const DT_FOOT_CSS = '.foot{max-width:1060px;margin:0 auto;padding:0 26px 24px;font-size:12px;color:var(--storm-dark)}';

/** The app icon, inlined from the one committed file so nothing is fetched. */
function dt_icon_link(): string
{
    $path = __DIR__ . '/../assets/favicon.svg';
    if (!is_file($path)) {
        return '';
    }
    return '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,'
        . base64_encode((string) file_get_contents($path)) . '">';
}

/**
 * A whole page in the back office's chrome, for a reply that has no page of its own.
 *
 * Used by the 401 and 403 replies, which were bare exit() strings.
 */
function dt_back_office_page(string $title, string $subtitle, string $bodyHtml): string
{
    return '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        . '<meta name="viewport" content="width=device-width,initial-scale=1">'
        . '<title>' . h($title) . '</title>' . dt_icon_link()
        . '<link rel="stylesheet" href="../assets/fonts.css">'
        . '<style>' . DT_TOKENS
        . 'body{font-family:var(--font-body);font-size:var(--fs-body);line-height:1.45;'
        . 'margin:0;background:var(--page);color:var(--ink)}'
        . '.top{background:var(--blue);border-top:6px solid var(--orange);color:#fff;padding:14px 26px}'
        . '.top h1{margin:0;font-size:20px;letter-spacing:.01em}'
        . '.top .sub{color:#B9C4D6;font-size:12px;margin-top:3px;text-transform:uppercase;letter-spacing:.06em}'
        . '.wrap{max-width:1060px;margin:0 auto;padding:20px 26px 60px}'
        . '.notice{border-radius:var(--radius-md);padding:10px 14px;font-size:13.5px;line-height:1.45;margin:0 0 16px}'
        . '.notice.err{background:var(--err-bg);border:1px solid var(--err-line);color:var(--err-text)}'
        . DT_FOOT_CSS
        . '</style></head><body>'
        . dt_back_office_head($title, $subtitle)
        . '<div class="wrap">' . $bodyHtml . '</div>' . dt_back_office_foot() . '</body></html>';
}
