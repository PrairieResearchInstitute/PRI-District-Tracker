"""The one token block, from docs/design.md section 2 (UI Elements deviation PDT-32).

Five surfaces drew their own colours: MYCSS, HANDOUT_CSS and admin_ui.html each kept a
hand-copied block, and KIT_CSS and admin_ingest.php used bare literals. They had drifted
into eleven muted greys, seven hairlines, two navies, two link blues and eleven radii.
Everything now comes from here.

build_site.py emits the block into the three public pages, admin_server.py stamps it into
admin_ui.html, and php/admin_ingest.php carries a copy that tests/test_tokens.py compares
against this file character for character, the way test_freshness.py holds the display
timer's two copies together.

One value is deliberately not shared: the font stack. The public pages carry Source Sans 3
and Montserrat from the vendored toolkit; the back offices run on the system stack. Picking
one pairing is Q-19 (PDT-03), still open, so the caller passes the stack and only the call
site changes when the owner decides.

Pure stdlib (no imports at all).
"""

# The public pages' faces, vendored offline inside toolkit.local.css.
FONT_BODY_WEB = "'Source Sans 3','Source Sans Pro',Arial,sans-serif"
FONT_HEAD_WEB = "'Montserrat',Arial,sans-serif"

# Q-19 (owner, 2026-10-17): the campus faces everywhere, back offices included.
# scripts/ui_fonts.py lifts the @font-face rules out of the vendored toolkit so the
# back offices actually load them; naming a face they do not load was PDT-03.
FONT_BODY_SYSTEM = FONT_BODY_WEB
FONT_HEAD_SYSTEM = FONT_HEAD_WEB

_BLOCK = """__S__{
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
  --font-body:__BODY__;
  --font-head:__HEAD__;
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
"""


def tokens_css(scope=":root", body=FONT_BODY_WEB, head=FONT_HEAD_WEB):
    """The block, under `scope`, with the font stack the surface actually loads.

    White text on navy and on --il-altgeld stays a literal #fff; --on-accent is the
    text colour that sits on --orange, which Q-26 fixes at navy.
    """
    return _BLOCK.replace("__S__", scope).replace("__BODY__", body).replace("__HEAD__", head)
