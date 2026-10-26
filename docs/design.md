# UI Elements: PRI District Tracker

The UI Elements spec for PRI District Tracker (the product name is an open decision, section 9). Read it before adding or changing anything on screen. It builds on the estate baseline, the skill drez-ui-elements: the baseline sets the rules, and this file sets the values. Owner decisions Q-25 to Q-28 (2026-10-17) apply. Source audit: `reference\UI Audit 2026-10-17.docx` (findings PDT-01 to PDT-35). The owner reads the rendered copy, `reference\UI Elements.docx`.

Where styles live. The public pages `index.html`, `handout.html`, `PRI-Tracker-Kit.html` and `data.js` are build outputs: never edit them. Their styles, markup and scripts live in constants in `scripts/build_site.py`; edit those and rebuild with `PRI_SKIP_REPS=1 py scripts/build_site.py`, then run `py tools/check.py`.

| Constant in `scripts/build_site.py` | Holds |
|---|---|
| `_HEAD_META` | charset, viewport, `<title>`, the inline favicon |
| `PRI_HEADER` | the toolkit `<ilw-header>` markup |
| `MYCSS` | public tracker CSS, scoped to `#pdt`, with the `#pdt{--blue..}` token block |
| `MARKUP` | public tracker markup: intro, controls, layout, modal shell |
| `APP` | public tracker script: `SURVEYS`, `KINDS`, `chamberLabel()`, `svgmap()`, the modal |
| `HANDOUT_CSS` | handout CSS with its `:root{--blue..}` token block and print sizes |
| `HANDOUT_APP` | handout script: `SURVCOL`, `TAGCOL`, `ICONS`, tiles |
| `KIT_CSS` | Working Group Kit CSS (tabs, Add Data form, staged table, backend cards); literals only |
| `KIT_TABBAR` | the Kit tab strip |
| `KIT_ADD`, `KIT_BACKEND` | Kit Add Data and How the Data Works tabs |
| `KIT_JS` | Kit script: staged list, CSV export, the native dialogs to replace |

The two back-office pages are source files, not build outputs: `scripts/admin_ui.html` (Data Console and Studio, local, served by `scripts/admin_server.py`, with its own `:root{--navy..}` block) and `php/admin_ingest.php` (hosted back office, literals only). The PRI footer markup comes from `data/pri_footer.html` and `assets/vendor/pri_footer.local.html`. Never regenerate `assets/vendor`.

## 1. Identity

| Item | Value |
|---|---|
| Palette family | Illinois: navy `#13294B` primary, Illinois Orange `#FF5F05` accent (Q-26), storm `#707372` muted text, the five survey colours |
| Fonts | public pages and Kit: Source Sans 3 (body) and Montserrat (headings, figures), base64 inside the vendored `toolkit.local.css`; back offices: Segoe UI system stack. Open decision: one font pairing (section 9). |
| Themes shipped | one light screen theme; a print profile (handout 8.5 by 11, tracker print rules) |
| Token sheet | today three hand-copied blocks (`MYCSS`, `HANDOUT_CSS`, `admin_ui.html`) plus literals in `KIT_CSS` and `admin_ingest.php`; target one block generated in `build_site.py` that aliases the toolkit `--il-*` variables and that `admin_ui.html` reuses (PDT-32) |
| Framework | Illinois Web Toolkit v3 web components (`ilw-header`, `ilw-footer`, `ilw-header-menu`, `ilw-columns`), vendored offline by `scripts/make_vendor.py` and inlined into every public page; no other library |
| Offline | every page renders from a double-clicked file with no network (AGENTS.md, drez-illinois-brand-offline) |
| Icons | the handout stroke set `ICONS` in `HANDOUT_APP`; the finial SVG for photo placeholders; favicon `assets/favicon.svg`, inlined by `_HEAD_META` |

### Shared PRI web look

Identical in the specs of PaCELab Equip, PRI Facilities Request and PRI District Tracker; change all three together.

The three PRI web apps share one look where they already agree. PaCELab named its tokens after Facilities on purpose, so those two share eight token names; District Tracker reaches the same navy and orange under other names.

| Role | Shared value | PaCELab Equip | PRI Facilities Request | PRI District Tracker |
|---|---|---|---|---|
| Primary | `#13294B` navy | `--accent` | `--accent` | `--blue` (public), `--navy` (Data Console) |
| Highlight | `#FF5F05` Illinois Orange (Q-26) | `--accent2`, today `#e84a27` | `--accent2`, today `#e84a27` | `--orange` |
| White-text orange, orange text on light grounds | `#C84113` (`--il-altgeld`) | new `--il-altgeld` | new `--il-altgeld` | `--il-altgeld` in the vendored toolkit |
| Body text | `#1a1a1a` | `--ink` | `--ink` | `--ink` (public pages) |
| Page ground | `#f5f4f1` warm paper | `--paper` | `--paper` | differs: toolkit white on public pages, `#f4f6f8` in the back office |
| Panel | `#ffffff` | `--panel` | `--panel` | white literals |
| Line | `#d8d5cf` warm grey | `--line` | `--line` | differs: `#e3e3e2` public, `#e3e6ea` back office |
| Success | `#1b6b2f` | `--good` | `--good` | differs: `#14532d` on `#e8f5ec` |
| Danger | `#a4210c` | `--bad` | `--bad` | differs: `#7f1d1d` on `#fdecea` |
| Focus ring | 2 px solid navy, 2 px offset; `#FF5F05` on navy bars | `--focus` | `--focus` | `--focus` |

Orange rule (Q-26). Illinois Orange `#FF5F05` replaces the retired Altgeld `#E84A27` everywhere, favicons included. White text never sits on `#FF5F05` (about 3.0 to 1). A fill that carries white text uses `#C84113` (`--il-altgeld`, about 4.97 to 1 with white); a fill that stays `#FF5F05` carries navy `#13294B` text (about 4.7 to 1). Orange text on white or paper uses `#C84113`. Pure `#FF5F05` stays for rules, borders, underlines, dots and fills with navy text. Navy `#13294B` stays the primary colour.

Header and footer pattern. Each app opens with navy or the Illinois toolkit header, one orange rule as the only accent line, then white panels on a light ground. PaCELab: toolkit `<ilw-header>` with the lab bar below it and the toolkit `<ilw-footer>`. District Tracker: vendored toolkit `<ilw-header>` and the PRI `<ilw-footer>` on public pages; a navy bar with a 6 px orange top rule and a one-line credit footer in the back office. Facilities: its own navy `header.site` with a 4 px orange bottom rule, the PRIOps lockup and a right-aligned text footer `footer.foot`.

Dialog helper. All three apps use one plain JavaScript helper with one API, `PriDialog.ask`, `PriDialog.confirm` and `PriDialog.notify`, plus the server-rendered confirm page for PHP forms (Q-27). Each app's section 4 names its file.

Open shared decisions, each listed in every app's `reference\open-questions.md`:

- Fonts. PaCELab mixes Georgia, a system sans and the Illinois kit; Facilities uses Georgia with no web font; District Tracker uses Source Sans 3 and Montserrat, vendored offline. Recommendation: Source Sans 3 for body and controls and Montserrat for headings in all three, vendored offline by the District Tracker method (drez-illinois-brand-offline; drez-inhs-document-branding rule 3 names Source Sans 3 for screens), with Georgia retired from screens.
- Header. PaCELab and District Tracker use the toolkit `<ilw-header>`; Facilities draws its own navy bar. Recommendation: the toolkit header in all three, vendored offline for Facilities (which loads nothing from a CDN), with the PRIOps lockup in the site-name slot.
- Neutral greys. PaCELab and Facilities use the warm paper set (`#f5f4f1`, `#d8d5cf`); District Tracker uses cool greys. Recommendation: the warm set for app screens and back offices; the toolkit neutrals stay on District Tracker's public pages.

## 2. Tokens

Target: one block, emitted once by `build_site.py` into `MYCSS`, `HANDOUT_CSS` and `KIT_CSS`, and copied into `admin_ui.html` and `admin_ingest.php`, using the names below. "Today" names where the value lives now. Rows marked "new" carry values already in code.

### Colour

| Token | Value | Baseline role | Today | Notes |
|---|---|---|---|---|
| `--blue` | `#13294B` (`--il-blue`) | `--accent` | `MYCSS`, `HANDOUT_CSS` `--blue`; console `--navy` | headings, fund card, dark buttons, back-office bar |
| `--blue-deep` (new) | `#0E1F3A` | `--surface` (dark bar) | `KIT_CSS` `.kit-tabs`, `HANDOUT_CSS` `.ho-bar`; console `#0B1A33` | tab bars and action bars (PDT-12) |
| `--orange` | `#FF5F05` (`--il-orange`) | `--accent` (highlight) | `--orange` | primary button fill with navy text, selected district, active tab rule, card top rules |
| `--orange-hover` (new) | `#D94E00` | `--accent-hover` | `.printbtn:hover` | primary hover, navy text stays |
| `--il-altgeld` | `#C84113` | highlight, text-safe | vendored toolkit; `KINDS` News | orange text on white (`.m-eyebrow`, `.req` asterisk, `.m-arrow`, `.kb-arrow`), white-text orange fills (`.c.clickable:hover`) |
| `--on-accent` (new) | `#13294B` on orange, `#FFFFFF` on navy and `--il-altgeld` | `--on-accent` | literals | Q-26 |
| `--link` (new) | `#1D58A7` (`--il-industrial`) | `--info-text` (link) | `#185FA5` | inline links (PDT-11) |
| `--ink` | `#1A1A1A` | `--text` | `--ink` public; `#23272c` Kit, console, host | body text (PDT-09) |
| `--storm` | `#707372` (`--il-storm`) | `--text-muted` | `--storm`; `#5b6069` back office | muted text at 14px and larger |
| `--storm-dark` (new) | `#4A4C4B` (`--il-storm-darker-1`) | `--text-muted` (small) | ten other greys | muted text below 14px |
| `--line` | `#E3E3E2` | `--line` | `--line` public; `#e3e6ea` back office | card and table rules (PDT-10) |
| `--field` (new) | `#C9C9C7` | `--line` (field) | `.controls select` | every input border |
| `--soft` (new) | `#F0F1F0` | `--surface-2` | `.stat`, `.c`, `.m-row:hover` | tiles, counters, row hover |
| `--page` (new) | `#F4F6F8` | `--bg` (back office) | console `--bg`, host body | back-office ground; open decision Q-21 |
| `--ok-bg`, `--ok-line`, `--ok-text` (new) | `#E8F5EC`, `#B7DFC4`, `#14532D` | `--ok-*` | console `.smsg.ok`, host `.msg` | success notice |
| `--warn-bg`, `--warn-line`, `--warn-text` (new) | `#FFF8EF`, `#F2D9B3`, `#7A5312` | `--warn-*` | `.kit-note`, console `.note`, `.swarn` | warning notice, flags (PDT-15) |
| `--err-bg`, `--err-line`, `--err-text` (new) | `#FDECEA`, `#F5C2BC`, `#7F1D1D` | `--danger-*` | console `.smsg.bad` | error notice |
| `--backdrop` (new) | `rgba(19,41,75,.55)` | overlay | `MYCSS` `.modal`; console `rgba(15,22,35,.55)` | every dialog |

Orange text rule (owner ruling relayed 2026-10-17, refining Q-26). Orange text on white or
paper takes `#FF5F05` only at 18px bold or larger, where 3 to 1 is the threshold that applies;
below that it takes `--il-altgeld` `#C84113`. The handout's display text is the case the rule
exists for: `.ho-lh-tag` (34px, 800) and `.ho-kicker` (22px, 700) stay pure orange, and the tag
is binding in AGENTS.md besides. `.m-eyebrow`, `.m-arrow`, `.kb-arrow`, the `.req` asterisk and
`.ho-focal .lbl` are all below the threshold and take `--il-altgeld`. Icons, rules, borders,
underlines and dots are not text and keep `--orange` at any size.

Survey colours (one set, PDT-01): INHS `#006230`, ISGS `#7D3E13`, ISWS `#007E8E`, ISAS `#5C0E41`, ISTC `#1D58A7`, from `SURVEYS` in `APP`. One Python dict in `build_site.py` feeds `SURVEYS`, `SURVCOL`, the `TAGCOL` text colours, the Kit staged badge and a field the Console reads in place of `survColor()`. Survey badges carry white text on these fills.

Lifecycle chips (back office only): Evergreen `#13294B`, Fresh `#1C7A3F` (console `--green`), Soon `#B9761B` (`--amber`), Expired `#8A9099` (`--gray`). Console `--red` and `--blue70` are defined and unused.

Activity kind colours (`KINDS`): Projects `#1D58A7`, Active grants `#006230`, Publications `#5C0E41`, News `#C84113`, Outreach `#007E8E`; they reuse survey colours, an open decision (Q-15, PDT-13).

District map: selected district `#FF5F05` with a navy stroke; other districts `#E4E5E5` with a white stroke.

### Type

| Token | Value | Baseline role | Use |
|---|---|---|---|
| `--font-body` (new) | 'Source Sans 3', 'Source Sans Pro', Arial, sans-serif | body face | body, controls, buttons (`font: inherit` in a shorthand is invalid, PDT-02) |
| `--font-head` (new) | 'Montserrat', Arial, sans-serif | heading face | h1 to h4, `.stat .n`, `.fund-amt` |
| `--font-mono` (new) | Consolas, 'Courier New', monospace | code face | Studio editor, `.kb-tag` |
| screen scale (new) | 11, 12, 13, 14, 15, 17, 22, 26px | `--fs-badge` to `--fs-page` | badges 11; labels and captions 12; secondary 13; buttons and cells 14; body 15; card titles 17; dialog titles 22; page title 26 (PDT-31) |
| `--fs-table-head`, `--fs-table-cell` (new) | 11.5px, 13.5px | `--fs-xs`, `--fs-sm` | the two table sizes in section 3, named so the scale and the table component agree (owner ruling relayed 2026-10-17) |

The fund figure (30px) and stat figures (21px) sit outside the scale, as do the two table sizes above, which are named rather than rounded. The handout keeps its print sizes (8.2px, 9px and the 800 weight display). Weights: 400 body, 600 labels and buttons, 700 headings and figures. Uppercase labels: 12px, 600, `letter-spacing: .04em`.

### Shape, space, elevation, layers, motion

| Token | Value | Baseline role | Use |
|---|---|---|---|
| `--radius-xs` (new) | 4px | `--radius-sm` | survey badges, `.fund-tag` |
| `--radius-sm` (new) | 6px | `--radius-sm` | small buttons, list items |
| `--radius-md` (new) | 8px | `--radius-md` | buttons, inputs, notices, stat tiles |
| `--radius-lg` (new) | 10px | `--radius-lg` | cards, map box, tables, toast |
| `--radius-dialog` (new) | 12px | `--radius-lg` (dialog) | dialogs |
| `--radius-pill` (new) | 999px | `--radius-pill` | lifecycle chips, counters |
| spacing | 4, 8, 12, 16, 24px | `--space-1` to `--space-5` | card padding 14px 16px; page gutter 26px |
| `--shadow-2` (new) | 0 24px 60px rgba(0,0,0,.3) | `--shadow-2` | console dialog; public screen cards carry no shadow |
| `--z-tabs` (new) | 40 | `--z-menu` | sticky Kit tab bar |
| `--z-dialog` (new) | 50 | `--z-dialog` | console overlay; the public modal uses 9999 today and moves to 50 |
| `--z-toast` (new) | 60 | `--z-toast` | console toast |
| `--dur-fast` (new) | .12s | `--dur-fast` | console pill hover |

### Active state and focus

- Active-state class: `.on`, as the Kit tabs (`.kit-tab.on`), the Console tabs (`.tabs button.on`) and the Studio rail (`.srail a.on`) use today. Console filter pills move from `.pill.active` to `.on` with `aria-pressed` (PDT-36). Visibility uses the `hidden` attribute, as the public modal does; the console overlay and toast stop using `.on` for visibility (PDT-36). The host page's colour class `.on` becomes `.chip.shown` (PDT-36).
- Focus ring: `--focus: 2px solid var(--blue)` with `outline-offset: 2px` on `:focus-visible` for every button, link, select, input, tab, stat, count and list row; on navy and deep-navy bars (`.kit-tabs`, `.tabs`, `.top`, `.fund`) the ring uses `--orange`. No focus rule exists today (PDT-07).

## 3. Components

One component per family. Copy the markup; change the text, never the classes.

### Buttons

One `.btn` (PDT-05): radius 8px, padding 9px 16px, `600 14px/1 var(--font-body)`. Variants:

| Variant | Look | Use |
|---|---|---|
| `.btn.pri` | `--orange` fill, navy `#13294B` text (Q-26), `--orange-hover` on hover | the one main action: Open One-Page Handout, Add to List, Save Record |
| `.btn.dk` | navy fill, white text | second strong action: Export CSV, Publish to Site |
| `.btn.gh` | white, `--line` border, `--ink` text | other actions: Clear List, Cancel |
| `.btn.sm` | 4px 9px, radius 6px, 12.5px | row actions: Edit, Retire (PDT-06) |
| `.btn-link` | text in `--link` | Back, See All |

States: hover, `:focus-visible` ring, active, `:disabled` at opacity .5 with `cursor: default`. Today `.printbtn`, `.ho-bar button`, `.kbtn`, console `.btn`, host `.btn`, `.rowbtn`, `.kx` and `.sinfo li button` each define a button; they become `.btn` with variants.

```html
<div class="kadd-actions">
  <button type="button" class="btn gh">Clear List</button>
  <button type="button" class="btn pri">Add to List</button>
</div>
```

### Inputs and selects

8px 10px padding, radius 8px, `--field` border, `font: inherit` as its own declaration (PDT-18). The district picker on the public page may stay 15px.

### Checkboxes

`.ck` flex row, gap 7px, sentence-case label, no `&nbsp;` spacers (PDT-35).

```html
<label class="ck"><input type="checkbox" name="featured"> Featured on the handout</label>
```

### Forms, labels and validation

Field `.f` (column), uppercase label above, `.req` adds the asterisk in `--il-altgeld`, `.hint` 12px `--storm-dark` below; `.f.full` and `.sec` span `grid-column: 1 / -1` (PDT-19). The Console editor wording is canonical for the Kit and the host (PDT-17). Validation messages show inline as `.notice.err` above the actions, never through `alert()`.

### Dialogs and confirm pages

See section 4. The one shell is the public modal (`MARKUP` `#pdt-modal`): `.modal > .modal-card`. A navy-header "editor" variant for the Console is an open decision (Q-14).

### Menus

The toolkit `<ilw-header-menu>` inside `PRI_HEADER` carries the PRI main menu on the tracker and the Kit; the handout hides it.

### Tabs and filters

One tab strip (Kit and Console): `--blue-deep` bar, tabs `600 14px var(--font-body)`, 13px 20px, inactive `#B9C4D6`, active `.on` white with a 3px `--orange` bottom rule; tabs are `button` elements.

```html
<div class="kit-tabs" role="tablist"><button class="kit-tab on" data-tab="explore" aria-selected="true">Explore the Tracker</button><button class="kit-tab" data-tab="add">Add Data</button></div>
```

Filters: the public `.controls` panel (Survey, Level, Chamber, District selects with uppercase labels); the Console `.toolbar` (search, selects, buttons) and filter pills (`.pill` with `.on`).

### Tables

White, 1px `--line`, radius 10px; `th` 11.5px uppercase `.05em` `--storm` on `#FAFBFC`; `td` 9px 12px 13.5px; last row without a rule; empty state `td.empty` centred in `--storm`; every table inside an `overflow-x: auto` wrapper (PDT-16, PDT-19).

### Panels and cards

Card: white, 1px `--line`, radius 10px, padding 14px 16px (`.bigcard`, `.controls`, `.mapbox`, `.kb-card`, host `.card`). Survey card: `.bigcard` with a 2px header rule and a 12px `.bigcard-dot` in the survey colour. Fund card `.fund`: navy, white figure, `.fund-tag` navy on `--orange`. Kit steps `.kb-step`: 4px `--orange` top rule.

### Stat tiles

`.stats > .stat` with `.n` (Montserrat 21px navy) and `.l` (12px `--storm`), `--soft` fill, radius 8px. A stat that opens a list is a `button.stat` (PDT-07). The handout tiles (coloured, print only) are a print design.

### Page header and footer

Public tracker and Kit: `PRI_HEADER` toolkit `<ilw-header>` with the Prairie Research Institute site name, utility links, search and the PRI menu; PRI `<ilw-footer>` from `pri_footer.local.html` (fix the `aria-labelledby` ids, PDT-33). Handout: `<ilw-header>` with the site name only plus the orange "Legislative District / Profile" tag `.ho-lh-tag` (binding, AGENTS.md); navy print footer with address, URL and QR. Back office: one shared partial for `admin_ui.html`, `admin_ingest.php`, the error page and the 401 and 403 pages: navy bar, 6px `--orange` top rule, Montserrat 20px title, 12.5px uppercase subtitle in `#B9C4D6`, favicon (PDT-14), and one footer line, `footer.foot` from `dt_back_office_foot()` (12px, `--storm-dark`, the page width), carrying the credit.

Credit (drez-ui-elements rule 27, D-031): every page carries "Developed by M. J. Dreslik, with Claude Opus 5". Public tracker and Kit: `CREDIT_HTML` in `build_site.py`, a centred `div.app-credit` (Source Sans, 13px, `--storm-dark`) after the toolkit `<footer>`, never inside the toolkit markup. Handout: a last line in the navy print footer `.ho-foot .c`. Back office: `DT_CREDIT` and `dt_back_office_foot()` in `includes/ui.php`, used by `admin_ingest.php` and the 401 and 403 pages; `admin_ui.html` repeats the same `footer.foot`. The gate fails when any of these or the NOTICE file loses the line.

### Navigation

Page title `h1` in `.page-intro` with a lead paragraph and the handout button beside it. "See all" (`.more`) and list rows (`.m-row`, `.mini-item`) become `button` or `a href` elements with the same look (PDT-07). Back inside the modal: `.m-back` as `.btn-link`.

### Flash messages and alerts

One notice component `.notice` with `.ok`, `.warn`, `.err` (radius 8px, padding 10px 14px, 13.5px, the status tokens) replaces `.m-flag`, `.kit-note`, `.note`, `.swarn`, `.smsg`, `.msg` and the unstyled `.flash` from `flash_html()` (PDT-15). The host maps `flash-success`, `flash-notice` and `flash-error` to `.notice.ok`, `.warn` and `.err` in CSS. Toast (back office only): `.toast`, navy, 5px `--orange` left rule, radius 10px, bottom right, `--z-toast`.

### Status badges and pills

Survey badge `.svy`: 11px 700 white on the survey colour, radius 4px, 2px 6px. Counter `.c`: `--soft`, radius 999px. Lifecycle chip `.chip` with a dot: radius 999px, the chip colour as text (`.chip.evergreen`, `.fresh`, `.soon`, `.expired`); display text waits on Q-18.

### Tooltips

None. Help sits in `.hint` text.

### Empty, loading and error pages

Empty: one sentence with a period, in `.none` (public) or `td.empty`; wording "Nothing recorded for this district yet." (PDT-24). Officeholder unknown: "Officeholder to be verified." (PDT-24). Funding placeholder `$&mdash;`. Loading: the pages carry their data inline (`data.js`), so no loading state exists. Error pages: the 500 page from `includes/core.php` and the 401 and 403 texts from `includes/auth.php` render inside the back-office partial (PDT-14).

### Icons

One set: the stroke SVGs in `HANDOUT_APP` `ICONS` (24px grid, stroke 2, `currentColor`), reused on index cards (PDT-28); the finial SVG once, shared by `APP` and `HANDOUT_APP`. Approved glyphs: `&times;` close, `&rarr;` and `&larr;` on See All and Back. No emoji (the Console toast drops its warning emoji) and no "+" text prefix on buttons. Favicon: navy square, Illinois outline, three dots that move from `#E84A27` to `#FF5F05` (Q-26, PDT-29); both back-office heads carry it.

### Maps and charts

District maps: `svgmap(mapK, sel, vb)` in `APP` draws inline SVG paths from `data/geo.json` into `#mapZoom` (zoomed district) and `#mapLoc` (state locator) inside `.mapbox` (white card, `#insetTitle` 13px navy); selected district `--orange` fill with a navy stroke, others `#E4E5E5`. No chart library and no charts; figures show as stat tiles and the fund card. Any future chart follows the dataviz skill and takes its colours from this file.

## 4. Dialogs and feedback

In-app dialog helper (Q-27): `PriDialog`, plain JavaScript. Because the public pages are single offline files, its source is one constant, `DIALOG_JS` with its CSS in `DIALOG_CSS` (to build in `build_site.py`), emitted into the tracker, the handout and the Kit; `scripts/admin_ui.html` carries the same code inline.

```js
PriDialog.ask({ title, message, label, value = '', placeholder = '', okLabel = 'OK', cancelLabel = 'Cancel', required = false })
  // Promise<string|null>: the text, or null on Cancel, Escape or a backdrop click
PriDialog.confirm({ title, message, okLabel = 'OK', cancelLabel = 'Cancel', danger = false })
  // Promise<boolean>
PriDialog.notify({ title, message, okLabel = 'OK' })
  // Promise<void>
```

Shell: the public modal. `.modal[role=dialog][aria-modal=true][aria-labelledby]` over `--backdrop`, `.modal-card` white, radius 12px, max 780px, padding 24px 28px; title `.m-title` (22px navy) with the close button `.m-close` (`aria-label="Close"`, `&times;`) top right; body; actions in one row with Cancel (`.btn.gh`) on the left and the main action on the right as the only primary (`.btn.pri`, or `.btn.dk` for a destructive action). Escape and a backdrop click cancel; focus moves into the dialog and returns to the trigger (PDT-34). The Console record editor uses the same shell, with or without the navy header per Q-14.

Server-rendered confirm page, for `php/admin_ingest.php` (Retire): the form posts without `confirmed=1`; the handler renders `dt_confirm_page($title, $question, $okLabel, $fields, $cancelHref)` (to build in a new `includes/ui.php` or inside `admin_ingest.php`, never in the synced `includes/core.php`), the back-office partial with one card holding the question, the posted fields as hidden inputs plus `csrf_field()` and `confirmed=1`, Cancel on the left and the main action on the right. On the page, `data-confirm` on the form lets `PriDialog.confirm` answer first and add `confirmed=1`.

Order of replacement: `prompt()` first (none in this app), then the five `confirm()` calls (`KIT_JS` Clear All Entries; `admin_ui.html` Retire Record, Discard Unsaved Changes, Put Older Version Back; `admin_ingest.php` Retire), then the three `alert()` calls in `KIT_JS` (fill in Title and Summary, add an entry first, allow pop-ups). Each keeps its text and result handling; the two validation alerts become an inline `.notice.err`, and the pop-up message becomes `PriDialog.notify`.

Feedback places: inline `.notice.err` beside the form for validation; the Console toast for completed background actions (save, publish, import); a `.notice` banner at the top of the host page after a redirect; public pages report nothing beyond their content.

## 5. Layout

| Item | Value |
|---|---|
| Page container | 1060px with a 26px gutter (16px under 820px) on every screen page; today `.kit-wrap` 1000px, Console 1180px, host 1080px (PDT-20) |
| Public layout | `.layout` flex: `.leftcol` and a 280px `.inset` map column; `.bigcards` two columns, gap 14px |
| Breakpoints | 820px (one column, map below), 680px (dialog columns stack); the Kit and host adopt 820px (PDT-19) |
| Kit | sticky tab bar at the top; tab bodies in the shared container |
| Back office | navy bar 14px 26px; content in the shared container |
| Handout | 8.5 by 11 sheet, its own print geometry; on screen the `.ho-bar` action bar over a grey ground |
| Print | toolkit chrome, controls, intro, note and modal hidden; colours kept with `print-color-adjust: exact` |

## 6. Copy

Casing (Q-25): Title Case for buttons, tabs, menu items, dialog titles and page titles: Open One-Page Handout, Explore the Tracker, Add Data, How the Data Works, Add to List, Export CSV, Clear List, Save Record, Publish to Site, Import CSV, Restore Version. Sentence case for body text, help, form field labels (Q-29), notices, placeholders, empty states and confirm questions. Uppercase labels stay as CSS `text-transform` over sentence-case text. Verb plus object on buttons; one verb per action (PDT-25). Writing rules: no em dashes, no contractions, no filler, no bare "This" (PDT-26).

Glossary:

| Thing | Name on screen | Note |
|---|---|---|
| Product | open: "PRI District Tracker" (Console title, CLAUDE.md), "Project District Tracker" (`MARKUP` h1), "PRI Project District Tracker" (`_HEAD_META` title on all three public pages), "PRI District handout" (unused), "PRI Data Console" and "PRI Data Console (host)" | owner decision (Q-17, PDT-21) |
| Kit tabs | Explore the Tracker, Add Data, How the Data Works | Title Case (Q-25) |
| Surveys | INHS, ISGS, ISWS, ISAS, ISTC; long names from `SURVEYS`; "All PRI" in the picker | |
| Chambers | U.S. House, U.S. Senate, Illinois House, Illinois Senate (`chamberLabel()`); "IL Senate" only where width forces | PDT-23 |
| Activity kinds | Projects, Active Grants, Publications, News, Outreach & Community Science | `KINDS` labels; card titles in Title Case |
| Display-timer states | open: raw keys evergreen, fresh, soon, expired; host "On site" with yes and hidden | owner decision (Q-18, PDT-22) |
| Record status | open: a select in the Console, free text in the Kit and host | owner decision (Q-16, PDT-17) |
| Editor of record | Data Console | D-019 |

Formats: dates ISO `YYYY-MM-DD` everywhere the UI shows or stores one (`updated_at`, `show_until`, the Kit CSV name); prose dates "June 2026" only in notes. Districts are integers. Money: `$` and thousands separators; unknown funding `$&mdash;`. Empty value (Q-30): the em dash, `&mdash;` alone in a table cell or read-only field; prose, labels, messages and help text never use it (PDT-26).

## 7. Adding a feature

1. Read this file; find the component in section 3.
2. If none fits, add it here first with its tokens and states.
3. Public pages: edit the constant in `build_site.py`, never the output; rebuild with `PRI_SKIP_REPS=1 py scripts/build_site.py`.
4. Use tokens only; inline styles only for data-driven survey and tile colours.
5. Build controls as `button` or `a href`; give them the focus ring.
6. Ask through `PriDialog` or `dt_confirm_page()`, never `alert()`, `confirm()` or `prompt()`.
7. Keep the page offline: nothing from a CDN, fonts from the vendored bundle.
8. Run the baseline checks (drez-ui-elements, Checks) on `build_site.py`, `admin_ui.html` and `admin_ingest.php`, then `py tools/check.py` and `py scripts/run_tests.py`.
9. Remove the section 8 row the change fixes; rebuild `reference\UI Elements.docx`.

## 8. Known deviations

| ID | Problem | Canonical target |
|---|---|---|

## 9. Decisions

Estate decisions (2026-10-17):

- Q-25: Title Case for buttons, tabs, menu items, dialog titles and page titles; sentence case for body, help, messages and placeholders. Overrides the audit's sentence-case proposal for buttons; the Kit tabs, buttons and back-office actions move to Title Case (PDT-25).
- Q-26: Illinois Orange `#FF5F05` stays the accent and replaces `#E84A27` in the favicon (PDT-29); white text never sits on `#FF5F05`, so primary buttons carry navy text and white-text orange fills use `#C84113` (PDT-08, PDT-38). Navy stays the primary.
- Q-27: native dialogs give way to `PriDialog` (`DIALOG_JS` in `build_site.py`, inline in `admin_ui.html`) and `dt_confirm_page()`, `prompt()` first (PDT-37).
- Q-28: this file in the nine baseline sections is the spec; the owner reads `reference\UI Elements.docx`; a check script joins the gate.
- Q-29: form field labels take sentence case in the Kit, the Console and the host page; buttons, tabs, menu items and titles take Title Case.
- Q-30: the em dash stays the mark for an empty value in table cells and read-only fields, including unknown funding `$&mdash;`. PDT-26 still covers em dashes in Kit and back-office prose.

App decisions that shape the UI: the AGENTS.md rules on offline rendering and the real toolkit header with the `.ho-lh-tag`; D-019 (the Data Console stays the editor of record, which the host page states on every visit); D-022 (the inline favicon); D-023 (adoption of this spec).

Fonts (owner, 2026-10-18). The estate buys the Adobe campus kit online, and an app that must work offline
keeps the same faces vendored offline. District Tracker renders from a double-clicked file with no network
(AGENTS.md), so `scripts/ui_fonts.py` lifting the Source Sans 3 and Montserrat `@font-face` rules out of the
vendored toolkit is the settled answer for this app, not an exception waiting on anything (D-026, D-028).

Open decisions: none. Q-11, the Kit's MySQL hosting card, was answered on 2026-10-20 (retire MySQL entirely), which closed the last row in section 8. Earlier answers: Q-14 the Console editor variant, Q-15 the activity kind colours, Q-16 the fixed Status list, Q-17 the product name, Q-18 the display-timer state names, Q-19 fonts, Q-20 header chrome, Q-21 neutral greys (D-024, D-025), the two rulings of 2026-10-18 (D-027) and the font ruling (D-028).
