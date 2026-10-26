"""Build the PRI District Tracker prototype (index.html).

Header/footer are the official Illinois Web Toolkit components (footer cloned from
prairie.illinois.edu). Reps refreshed every build via fetch_reps.py. Cards show up to
3 random entries (reshuffled each load); entries drill into a detail modal; the count
numbers open a full list of that category, whose rows also drill into the detail.
Pure stdlib. Run: py scripts/build_site.py

Developed by M. J. Dreslik, with Claude Opus 5 (drez-ui-elements rule 27).
"""
import json, math, os, re, subprocess, sys, base64
import pri_data
import ui_dialog
import ui_tokens
import ui_fonts

# Derived from this file's location (never hardcode): the build always writes next to its
# own source, so a copy of the project can't scatter its output into a different folder.
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJ, "data")

GEOJSON = {
    "us_house": os.path.join(DATA, "il_congress_current.geojson"),
    "il_senate": os.path.join(DATA, "il_senate.geojson"),
    "il_house": os.path.join(DATA, "il_house.geojson"),
}


def rings(geom):
    t = geom["type"]; c = geom["coordinates"]; out = []
    if t == "Polygon":
        out = [r for r in c]
    elif t == "MultiPolygon":
        for poly in c:
            out.extend(poly)
    return out


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def state_bbox(path):
    gj = load(path)
    minx = miny = 1e18; maxx = maxy = -1e18
    for ft in gj["features"]:
        if not str(ft["properties"].get("BASENAME", "")).strip().isdigit():
            continue
        for r in rings(ft["geometry"]):
            for x, y in r:
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    return minx, miny, maxx, maxy


def make_proj(bb, width=1000.0, pad=6.0):
    minx, miny, maxx, maxy = bb
    k = math.cos(math.radians((miny + maxy) / 2.0))
    gw = (maxx - minx) * k; gh = (maxy - miny)
    scale = (width - 2 * pad) / gw
    H = gh * scale + 2 * pad
    def tx(x, y):
        return ((x - minx) * k * scale + pad, H - ((y - miny) * scale + pad))
    return tx, width, H


def build_chamber(path, tx):
    gj = load(path); out = {}
    for ft in gj["features"]:
        bn = str(ft["properties"].get("BASENAME", "")).strip()
        if not bn.isdigit():
            continue
        dparts = []; minx = miny = 1e18; maxx = maxy = -1e18
        for r in rings(ft["geometry"]):
            seg = []
            for x, y in r:
                px, py = tx(x, y)
                seg.append("%.1f,%.1f" % (px, py))
                minx = min(minx, px); maxx = max(maxx, px)
                miny = min(miny, py); maxy = max(maxy, py)
            if seg:
                dparts.append("M" + "L".join(seg) + "Z")
        w = maxx - minx; h = maxy - miny
        side = max(w, h) * 1.14
        cx = (minx + maxx) / 2.0; cy = (miny + maxy) / 2.0
        vb = [round(cx - side / 2, 1), round(cy - side / 2, 1), round(side, 1), round(side, 1)]
        out[bn] = {"d": "".join(dparts), "vb": vb}
    return out


tx, W, H = make_proj(state_bbox(GEOJSON["us_house"]))
GEO = {"w": round(W, 1), "h": round(H, 1), "chambers": {}}
for key, path in GEOJSON.items():
    GEO["chambers"][key] = build_chamber(path, tx)

# Full database of record stays on disk; the front end only renders records whose
# show_until is blank (evergreen) or still in the future. Nothing is ever deleted.
_ACT_ALL = load(os.path.join(DATA, "activities.json"))["activities"]
ACT = [a for a in _ACT_ALL if pri_data.fresh(a)]
_HIDDEN = len(_ACT_ALL) - len(ACT)

if os.environ.get("PRI_SKIP_REPS"):
    print("rep refresh skipped (PRI_SKIP_REPS set)")
else:
    try:
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_reps.py")], check=False, timeout=240)
    except Exception as e:
        print("rep refresh skipped:", e)
_rp = os.path.join(DATA, "reps.json")
REPS = load(_rp) if os.path.exists(_rp) else {"us_house": {}, "us_senate": {}, "il_senate": {}, "il_house": {}}


def rd(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return f.read()

_footer_local = os.path.join(PROJ, "assets", "vendor", "pri_footer.local.html")
PRI_FOOTER = (open(_footer_local, encoding="utf-8").read()
              if os.path.exists(_footer_local) else rd("pri_footer.html"))
# The authorship credit (drez-ui-elements rule 27). It follows the toolkit <footer> in the
# app's own footer area, never inside the toolkit markup; tools/check.py looks for it in
# every generated page.
CREDIT = "Developed by M. J. Dreslik, with Claude Opus 5"
CREDIT_HTML = '<div class="app-credit">' + CREDIT + '</div>'
PRI_FOOTER = PRI_FOOTER + CREDIT_HTML
# --- OFFLINE chrome bundle (assets/vendor, built by scripts/make_vendor.py) ------------
# When the bundle exists the app renders with NO internet: the toolkit banner/footer and the
# fonts all come from local files (with data: URIs inside), so nothing is fetched at render
# time. Without the bundle we fall back to the CDN (online) so the build never breaks.
VENDOR_DIR = os.path.join(PROJ, "assets", "vendor")
_VENDOR_FILES = ["toolkit.local.css", "toolkit.local.js"]
OFFLINE = all(os.path.exists(os.path.join(VENDOR_DIR, f)) for f in _VENDOR_FILES)


def _vread(name):
    with open(os.path.join(VENDOR_DIR, name), encoding="utf-8") as f:
        return f.read()


_HEAD_META = ('<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
              '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"><meta http-equiv="Pragma" content="no-cache"><meta http-equiv="Expires" content="0">'
              '<title>PRI District Tracker</title>')
# The app icon (platform D-037, D-038) as a data: URI from the committed assets/favicon.svg,
# so the pages still load nothing from anywhere, from file:// or http alike.
_ICON_SVG = os.path.join(PROJ, "assets", "favicon.svg")
if os.path.exists(_ICON_SVG):
    with open(_ICON_SVG, "rb") as _f:
        _HEAD_META += ('<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,'
                       + base64.b64encode(_f.read()).decode("ascii") + '">')

if OFFLINE:
    # Fonts live inside toolkit.local.css, so the Google-Fonts block (GF) is empty.
    # The toolkit bundle registers web components and needs MODULE scope to do so (a classic
    # <script> loads but never calls customElements.define). A *linked* module is CORS-blocked
    # on file:// (double-click), but an *inline* module works from both file:// and http -- so
    # every offline output inlines the module. HEAD_ASSETS (linked) is kept for a future hosted
    # build where caching matters and pages are always served over http.
    HEAD_ASSETS = (_HEAD_META
                   + '<link rel="stylesheet" href="assets/vendor/toolkit.local.css">'
                   + '<script type="module" src="assets/vendor/toolkit.local.js"></script>')
    HEAD_ASSETS_INLINE = (_HEAD_META
                          + '<style>' + _vread("toolkit.local.css") + '</style>'
                          + '<script type="module">' + _vread("toolkit.local.js") + '</script>')
    GF = ""
else:
    # Rendering without an internet connection is a hard requirement, so a missing
    # bundle is an error, not a warning: exiting 0 here would quietly ship a build that
    # only works online and nobody would find out until someone opened it offline.
    if not os.environ.get("PRI_ALLOW_ONLINE"):
        sys.exit("ERROR: assets/vendor bundle missing, so this build would need the internet."
                 "\n       Run 'py scripts/make_vendor.py' once while online to build it."
                 "\n       To build an online-only copy on purpose, set PRI_ALLOW_ONLINE=1.")
    print("WARNING: PRI_ALLOW_ONLINE set - building against the CDN. This copy needs the internet.")
    HEAD_ASSETS = (_HEAD_META
                   + '<link rel="stylesheet" href="https://cdn.toolkit.illinois.edu/3/toolkit.css">'
                   + '<script type="module" src="https://cdn.toolkit.illinois.edu/3/toolkit.js"></script>')
    HEAD_ASSETS_INLINE = HEAD_ASSETS  # cannot inline without the local bundle
    GF = ("<link rel='preconnect' href='https://fonts.googleapis.com'>"
          "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
          "<link href='https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Source+Sans+3:wght@400;600&display=swap' rel='stylesheet'>")
PRI_SCRIPTS = ""
PRI_HEADER = '''<header>
  <ilw-header>
    <a slot="site-name" href="https://www.prairie.illinois.edu">Prairie Research Institute</a>
    <nav slot="links" class="il-links" aria-label="Utility"><ul>
      <li><a href="https://www.prairie.illinois.edu/about/give/">Give</a></li>
      <li><a href="mailto:configure-me@example.edu">Contact</a></li>
    </ul></nav>
    <form slot="search" method="get" action="https://www.prairie.illinois.edu" role="search"><input type="search" name="s" aria-label="Search PRI"><button type="submit">Search</button></form>
    <ilw-header-menu slot="navigation"><ul>
      <li><a href="https://www.prairie.illinois.edu/">Home</a></li>
      <li><a href="https://www.prairie.illinois.edu/about/about-pri/">About</a></li>
      <li><a href="https://www.prairie.illinois.edu/impact/">Impact</a></li>
      <li><a href="https://www.prairie.illinois.edu/research/">Research</a></li>
      <li><a href="https://www.prairie.illinois.edu/resources/collections/">Resources</a></li>
      <li><a href="https://www.prairie.illinois.edu/news/">News</a></li>
    </ul></ilw-header-menu>
  </ilw-header>
</header>'''

BLOCK_I = ('<svg class="ho-lh-i" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 34.67" role="img" aria-label="Block I">'
  '<path class="o" d="M24 9.33V0H0v9.33h5.33v16H0v9.33h24v-9.33h-5.33v-16H24zm-5.33 17.34h4v6.67H1.33v-6.67h4c.74 0 1.33-.6 1.33-1.33v-16C6.67 8.6 6.07 8 5.33 8h-4V1.33h21.33V8h-4c-.74 0-1.33.6-1.33 1.33v16c0 .74.6 1.34 1.34 1.34z"/>'
  '<path class="f" d="M18.67 8h4V1.33H1.33V8h4c.74 0 1.33.6 1.33 1.33v16c0 .74-.6 1.33-1.33 1.33h-4v6.67h21.33v-6.67h-4c-.74 0-1.33-.6-1.33-1.33v-16c0-.73.6-1.33 1.34-1.33z"/></svg>')
WORDMARK = ('<svg class="ho-lh-wm" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 378.6 10.1" role="img" aria-label="University of Illinois Urbana-Champaign"><path d="M376.4.2v5.9L371.5.2h-1.9V10h2.3V4l4.8 6h1.9V.2zM361.1 2.3c.5-.3 1-.4 1.7-.4 1 0 1.8.4 2.5 1.1l1.5-1.3c-.5-.6-1.1-1-1.8-1.3-.7-.3-1.5-.4-2.3-.4-1 0-2 .2-2.8.7-.8.4-1.5 1-1.9 1.8-.5.8-.7 1.6-.7 2.6s.2 1.8.7 2.6c.5.8 1.1 1.4 1.9 1.8.8.4 1.7.6 2.7.6.7 0 1.4-.1 2.1-.3.7-.2 1.3-.5 1.8-.9v-4h-2.1v2.9c-.5.3-1.1.4-1.8.4-.6 0-1.2-.1-1.7-.4-.5-.3-.8-.6-1.1-1.1-.3-.5-.4-1-.4-1.6 0-.6.1-1.2.4-1.6.5-.5.8-.9 1.3-1.2zM352.4.2h2.3V10h-2.3zM343.8.2l-4.4 9.8h2.3l.9-2.1h4.5l.9 2.1h2.4L346 .2h-2.2zm-.4 5.9 1.6-3.8 1.6 3.8h-3.2zM336.7.6c-.6-.3-1.4-.4-2.3-.4h-4.2V10h2.3V7.3h2c.9 0 1.6-.1 2.3-.4.6-.3 1.1-.7 1.5-1.2.3-.5.5-1.2.5-1.9s-.2-1.4-.5-1.9c-.4-.6-.9-1-1.6-1.3zm-.8 4.4c-.4.3-.9.4-1.6.4h-1.8V2h1.8c.7 0 1.2.1 1.6.4.4.3.5.7.5 1.3 0 .6-.1 1-.5 1.3zM325.1.2l-3.6 6.1-3.7-6.1H316V10h2.1V4.2l2.8 4.7h1.1l2.9-4.8V10h2.1V.2zM307.4.2 303 10h2.3l.9-2.1h4.6l.9 2.1h2.4L309.7.2h-2.3zm-.4 5.9 1.6-3.8 1.6 3.8H307zM298.8 4h-4.4V.2h-2.3V10h2.3V6h4.4v4h2.3V.2h-2.3zM284.1 2.3c.5-.3 1-.4 1.6-.4 1 0 1.8.4 2.5 1.1l1.5-1.3c-.5-.6-1-1-1.7-1.3-.7-.3-1.4-.4-2.3-.4-1 0-1.9.2-2.7.7-.8.4-1.4 1-1.9 1.8s-.7 1.6-.7 2.6.2 1.8.7 2.6c.5.8 1.1 1.4 1.9 1.8.8.4 1.7.6 2.7.6.8 0 1.6-.1 2.3-.4.7-.3 1.3-.7 1.7-1.3L288.2 7c-.7.8-1.5 1.2-2.5 1.2-.6 0-1.1-.1-1.6-.4-.5-.3-.9-.6-1.1-1.1-.3-.5-.4-1-.4-1.6 0-.6.1-1.1.4-1.6.3-.5.6-.9 1.1-1.2zM274.1 5.2h4V7h-4zM266.3.2 262 10h2.3l.9-2.1h4.6l.9 2.1h2.4L268.7.2h-2.4zm-.4 5.9 1.6-3.8 1.6 3.8h-3.2zM257.8 6.1 252.9.2H251V10h2.3V4l4.9 6h1.8V.2h-2.2zM242.5.2l-4.4 9.8h2.3l.9-2.1h4.5l.9 2.1h2.4L244.7.2h-2.2zm-.5 5.9 1.6-3.8 1.6 3.8H242zM235 4.9c.4-.2.7-.5 1-.9.2-.4.4-.8.4-1.3 0-.8-.3-1.4-1-1.9-.6-.5-1.5-.7-2.7-.7h-4.8V10h5.1c1.3 0 2.2-.2 2.9-.7.7-.5 1-1.1 1-2 0-.6-.2-1.1-.5-1.5-.4-.5-.8-.8-1.4-.9zm-4.9-3h2.3c.6 0 1 .1 1.3.3.3.2.4.5.4.9s-.1.7-.4.9-.7.3-1.3.3h-2.3V1.9zM234 8c-.3.2-.7.3-1.3.3h-2.6V5.8h2.6c1.2 0 1.8.4 1.8 1.2 0 .5-.1.8-.5 1zM224.6 5.6c.4-.5.5-1.2.5-1.9s-.2-1.4-.5-1.9-.8-.9-1.5-1.2c-.6-.3-1.4-.4-2.3-.4h-4.2V10h2.3V7.2h2.1l1.9 2.7h2.4l-2.2-3.1c.6-.3 1.1-.7 1.5-1.2zm-2.3-.6c-.4.3-.9.4-1.6.4h-1.8V2h1.8c.7 0 1.2.1 1.6.4.4.3.5.7.5 1.3 0 .6-.2 1-.5 1.3zM211.2 5.6c0 .9-.2 1.6-.6 2-.4.4-.9.6-1.6.6-1.5 0-2.2-.9-2.2-2.6V.2h-2.3v5.5c0 1.4.4 2.5 1.2 3.3.8.8 1.9 1.2 3.3 1.2s2.5-.4 3.3-1.2c.8-.8 1.2-1.9 1.2-3.3V.2h-2.2v5.4zM195.6 4.7c-.5-.2-1.1-.4-1.8-.5-.7-.2-1.3-.3-1.6-.5-.3-.2-.5-.4-.5-.8s.1-.6.4-.8c.3-.2.8-.3 1.4-.3.9 0 1.8.3 2.7.8l.7-1.7c-.4-.3-1-.5-1.6-.6-.6-.1-1.2-.2-1.8-.2-.9 0-1.7.1-2.3.4-.6.3-1.1.6-1.4 1.1-.3.5-.5 1-.5 1.5 0 .7.2 1.2.5 1.6.3.4.8.7 1.2.9.5.2 1.1.4 1.8.5.5.1.9.2 1.1.3.3.1.5.2.7.4.2.1.3.3.3.6s-.2.6-.5.8c-.3.2-.8.3-1.4.3-.6 0-1.2-.1-1.7-.3s-1.1-.4-1.5-.7l-.6 1.5c.4.3 1 .6 1.7.8.7.2 1.5.3 2.3.3.9 0 1.7-.1 2.3-.4s1.1-.6 1.4-1.1c.3-.5.5-1 .5-1.5 0-.7-.2-1.2-.5-1.6-.4-.3-.8-.6-1.3-.8zM184.4.2h2.3V10h-2.3zM179.2.7c-.8-.4-1.7-.7-2.7-.7-1 0-1.9.2-2.8.7-.8.4-1.5 1-1.9 1.8-.5.8-.7 1.6-.7 2.6s.2 1.8.7 2.6c.5.8 1.1 1.4 1.9 1.8.8.4 1.7.7 2.8.7 1 0 1.9-.2 2.7-.7.8-.4 1.5-1 1.9-1.8.5-.8.7-1.6.7-2.6s-.2-1.8-.7-2.6c-.4-.8-1.1-1.4-1.9-1.8zm-.1 6c-.3.5-.6.8-1.1 1.1-.5.3-1 .4-1.6.4-.6 0-1.1-.1-1.6-.4-.5-.3-.8-.6-1.1-1.1-.3-.5-.4-1-.4-1.6 0-.6.1-1.1.4-1.6.3-.5.6-.8 1.1-1.1.5-.3 1-.4 1.6-.4.6 0 1.1.1 1.6.4.5.3.8.6 1.1 1.1.3.5.4 1 .4 1.6 0 .6-.1 1.1-.4 1.6zM166.2 6.1 161.4.2h-1.9V10h2.2V4l4.9 6h1.9V.2h-2.3zM154 .2h2.3V10H154zM146.9.2h-2.3V10h7.2V8.1h-4.9zM137.5.2h-2.2V10h7.2V8.1h-5zM129.8.2h2.3V10h-2.3zM115 10h2.3V6.4h4.6V4.6h-4.6V2h5.2V.2H115zM109.8.7c-.8-.5-1.7-.7-2.7-.7-1 0-1.9.2-2.8.7-.8.4-1.5 1-1.9 1.8-.5.8-.7 1.6-.7 2.6s.2 1.8.7 2.6c.5.8 1.1 1.4 1.9 1.8.8.4 1.7.7 2.8.7 1 0 1.9-.2 2.7-.7.8-.4 1.5-1 1.9-1.8.5-.8.7-1.6.7-2.6s-.2-1.8-.7-2.6c-.4-.8-1.1-1.4-1.9-1.8zm-.1 6c-.3.5-.6.8-1.1 1.1-.5.3-1 .4-1.6.4s-1.1-.1-1.6-.4c-.5-.3-.8-.6-1.1-1.1-.3-.5-.4-1-.4-1.6 0-.6.1-1.1.4-1.6.3-.5.6-.8 1.1-1.1.5-.3 1-.4 1.6-.4s1.1.1 1.6.4c.5.3.8.6 1.1 1.1.3.5.4 1 .4 1.6 0 .6-.1 1.1-.4 1.6zM90.7 4.5 88.1.2h-2.4l3.8 6.3V10h2.3V6.5L95.6.2h-2.2zM76.6 2h3.1v8H82V2h3.1V.2h-8.5zM72.2.2h2.3V10h-2.3zM68 4.7c-.5-.2-1.1-.4-1.8-.5-.7-.2-1.3-.3-1.6-.5-.4-.2-.6-.4-.6-.8s.1-.6.4-.8c.3-.2.8-.3 1.4-.3.9 0 1.8.3 2.7.8l.7-1.7c-.4-.3-1-.5-1.6-.6-.5-.2-1.1-.3-1.7-.3-.9 0-1.7.1-2.3.4-.6.3-1.1.6-1.4 1.1-.3.5-.5 1-.5 1.5 0 .7.2 1.2.5 1.6.4.4.8.7 1.3.9.5.2 1.1.3 1.8.5.5.1.9.2 1.1.3.3.1.5.2.7.4.2.1.3.3.3.6s-.2.6-.5.8c-.3.2-.8.3-1.4.3-.6 0-1.2-.1-1.7-.3-.6-.2-1.1-.4-1.5-.7L61.6 9c.4.3 1 .6 1.7.8.7.2 1.5.3 2.3.3.9 0 1.7-.1 2.3-.4.6-.3 1.1-.6 1.4-1.1.3-.5.5-1 .5-1.5 0-.7-.2-1.2-.5-1.6-.4-.3-.8-.6-1.3-.8zM59.1 5.6c.4-.5.5-1.2.5-1.9s-.2-1.4-.5-1.9-.8-.9-1.5-1.2C57 .3 56.2.2 55.3.2h-4.2V10h2.3V7.2h2.1l1.9 2.7h2.4l-2.2-3.1c.7-.3 1.2-.7 1.5-1.2zM56.8 5c-.4.3-.9.4-1.6.4h-1.8V2h1.8c.7 0 1.2.1 1.6.4.4.3.5.7.5 1.3 0 .6-.1 1-.5 1.3zM43.1 5.9h4.5V4.1h-4.5V2h5.1V.2h-7.4V10h7.6V8.1h-5.3zM33.8 7.2l-2.9-7h-2.5l4.2 9.8h2.3L39.1.2h-2.2zM24.2.2h2.3V10h-2.3zM18.8 6.1 13.9.2H12V10h2.3V4l4.9 6H21V.2h-2.2zM6.6 5.6c0 .9-.2 1.6-.6 2-.3.4-.8.6-1.5.6-1.5 0-2.2-.9-2.2-2.6V.2H0v5.5C0 7.1.4 8.2 1.2 9c.8.8 1.9 1.2 3.3 1.2S7 9.8 7.8 9C8.6 8.2 9 7.1 9 5.7V.2H6.6v5.4z"/></svg>')
PRI_PRINT_HEADER = ('<div class="ho-lh"><ilw-header>'
  '<a slot="site-name" href="https://www.prairie.illinois.edu">Prairie Research Institute</a>'
  '</ilw-header><div class="ho-lh-tag">Legislative District<br>Profile</div></div>')

# (GF is decided above, in the OFFLINE block.)

# One button definition for every page (UI Elements spec, PDT-05). The tracker, the
# handout and the Kit each carried their own, and they had drifted in padding, weight
# and hover colour. Q-26 settles the colours: #FF5F05 is the accent and white never
# sits on it, so the primary carries navy text and the hover swaps to #C84113, the
# darker orange that does take white.
# Colours are literal here because the three surfaces do not share a token block yet;
# that is PDT-32, and when it lands only this function changes.
_BUTTONS_CSS = """
__S__.btn{border:0;border-radius:8px;padding:9px 16px;cursor:pointer;text-decoration:none;
  display:inline-block;font-family:inherit;font-size:14px;line-height:1.15;font-weight:600}
__S__.btn.pri{background:#FF5F05;color:#13294B}
__S__.btn.pri:hover{background:#C84113;color:#fff}
__S__.btn.dk{background:#13294B;color:#fff}
__S__.btn.dk:hover{background:#0E1F3A}
__S__.btn.gh{background:#fff;border:1px solid #DFE1E5;color:#23272C}
__S__.btn.gh:hover{background:#F2F5F9}
__S__.btn.sm{padding:4px 9px;border-radius:var(--radius-sm);font-size:12.5px}
__S__.btn-link{background:none;border:0;padding:0;cursor:pointer;color:var(--link);
  font-family:inherit;font-size:13px;font-weight:600;text-decoration:none}
__S__.btn-link:hover{text-decoration:underline}
__S__.btn:disabled{opacity:.5;cursor:default}
/* PDT-07: one visible focus ring, so the keyboard shows where it is. Palette blue
   rather than the orange accent, because every focusable thing here sits on a light
   background and the accent would be the one place it disappears. */
__S__:focus-visible{outline:3px solid #1D58A7;outline-offset:2px;border-radius:4px}
"""


def buttons_css(scope=""):
    """The button rules, optionally scoped to one page's root selector."""
    return _BUTTONS_CSS.replace("__S__", (scope + " ") if scope else "")


MYCSS = """<style>
/*TOKENS*/
#onetrust-consent-sdk,#onetrust-banner-sdk,#ot-sdk-btn,#ot-sdk-btn-floating,.ot-sdk-show-settings,.ot-floating-button,.onetrust-pc-dark-filter,#onetrust-pc-sdk,#ot-sdk-cookie-policy{display:none !important}
ilw-header, ilw-header *, ilw-footer, ilw-footer *{font-family:'Source Sans 3','Source Sans Pro','Source Sans',Arial,sans-serif}
ilw-footer ilw-columns{display:flex;flex-wrap:wrap;gap:2.5em;align-items:flex-start}
ilw-footer ilw-columns>nav{flex:1 1 240px;min-width:200px}
ilw-footer .ilw-footer-menu ul{list-style:none;padding:0;margin:0 0 12px}
ilw-footer .ilw-footer-menu li{margin:3px 0}
ilw-footer .social{margin:8px 0 0}
ilw-footer .social-2{display:flex !important;flex-wrap:wrap;gap:10px;align-items:center;list-style:none;padding:0;margin:0}
ilw-footer .social-2 li{list-style:none;margin:0}
ilw-footer .social-2 a{display:inline-flex;line-height:0}
ilw-footer .social-2 img{width:26px !important;height:26px !important}
.app-credit{font-family:'Source Sans 3','Source Sans Pro','Source Sans',Arial,sans-serif;font-size:13px;color:var(--storm-dark,#4A4C4B);text-align:center;padding:12px 26px}
#pdt, #pdt p, #pdt li, #pdt select, #pdt h1, #pdt h2, #pdt h3, #pdt h4{font-family:'Source Sans 3','Source Sans Pro',Arial,sans-serif}
#pdt h1, #pdt h2, #pdt h3, #pdt h4, #pdt .stat .n, #pdt .fund-amt{font-family:'Montserrat',Arial,sans-serif}
#pdt .wrap{max-width:1060px;margin:24px auto 8px;padding:0 26px}
#pdt ul{list-style:none;margin:0;padding:0}
#pdt .page-intro h1{font-weight:700;color:var(--blue);font-size:26px;margin:0 0 4px}
#pdt .page-intro{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
#pdt .page-intro p{color:var(--storm);margin:0;font-size:15px}
#pdt .printbtn{flex:0 0 auto}
#pdt .controls{display:flex;gap:16px;flex-wrap:wrap;background:#fff;border:1px solid var(--line);border-radius:var(--radius-lg);padding:14px 18px;margin:18px 0 22px}
#pdt .controls label{display:flex;flex-direction:column;font-size:12px;font-weight:600;color:var(--storm);text-transform:uppercase;letter-spacing:.04em;gap:5px}
#pdt .controls select{font-size:15px;padding:8px 10px;border:1px solid var(--field);border-radius:var(--radius-md);background:#fff;color:var(--ink);min-width:150px}
#pdt .layout{display:flex;gap:24px;align-items:flex-start}
#pdt .leftcol{flex:1;min-width:0}
#pdt .headerblock{display:flex;gap:20px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;margin-bottom:14px}
#pdt .titlecol{flex:1 1 240px;min-width:0}
#pdt .fundcol{flex:0 0 auto}
#pdt .inset{flex:0 0 280px}
#pdt .mapbox{border:1px solid var(--line);border-radius:var(--radius-lg);background:#fff;padding:14px}
#pdt .inset h3{font-weight:600;font-size:13px;margin:0 0 8px;color:var(--blue)}
#pdt .zoom{width:100%;aspect-ratio:1/1}
#pdt .loc{width:104px;margin:12px auto 0}
#pdt .loc-cap{text-align:center;font-size:11px;color:var(--storm);margin-top:5px}
#pdt .titlecol h2{font-weight:700;color:var(--blue);font-size:26px;margin:0 0 3px}
#pdt .rep{margin:0 0 12px;font-size:15px}
#pdt .rep a{color:var(--link);text-decoration:none;font-weight:600}
#pdt .rep a:hover{text-decoration:underline}
#pdt .repx{color:var(--storm);font-style:italic}
#pdt .fund{background:var(--blue);color:#fff;border-radius:var(--radius-lg);padding:14px 20px;display:inline-flex;flex-direction:column;min-width:230px}
#pdt .fund-amt{font-size:30px;font-weight:700;line-height:1.05}
#pdt .fund-lbl{font-size:12px;opacity:.85;margin-top:3px}
#pdt .fund-tag{font-size:11px;text-transform:uppercase;letter-spacing:.06em;background:var(--orange);color:var(--blue);align-self:flex-start;border-radius:var(--radius-xs);padding:1px 7px;margin-top:8px;font-weight:600}
#pdt .stats{display:flex;gap:10px;flex-wrap:wrap;margin:0}
#pdt .stat{background:var(--soft);border-radius:var(--radius-md);padding:7px 13px}
#pdt .stat .n{font-size:21px;font-weight:700;color:var(--blue);line-height:1.1}
#pdt .stat .l{font-size:12px;color:var(--storm)}
/* PDT-07: the count tile, the card counts, the list entries, the "see all" link and
   the modal rows were clickable divs and spans, so a keyboard could not reach them
   and Enter did nothing. They are buttons now; these rules keep the look they had. */
#pdt .stat.clickable,#pdt .mini-item,#pdt .m-row,#pdt .c.clickable,#pdt .more{
  font:inherit;color:inherit;text-align:left;border:0;background:none}
#pdt .mini-item,#pdt .m-row{width:100%}
#pdt .m-row .m-txt,#pdt .m-row .m-sub{display:block}
#pdt .more{padding:0}
#pdt .stat .n,#pdt .stat .l{display:block}
#pdt .stat.clickable{cursor:pointer;display:block;background:var(--soft)}
#pdt .stat.clickable:hover{outline:2px solid var(--orange)}
#pdt .bigcards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:0}
#pdt .bigcard{border:1px solid var(--line);border-radius:var(--radius-lg);background:#fff;padding:14px 16px}
#pdt .bigcard-h{display:flex;align-items:center;gap:8px;border-bottom:2px solid var(--line);padding-bottom:8px;margin-bottom:8px}
#pdt .bigcard-dot{width:12px;height:12px;border-radius:var(--radius-xs);flex:0 0 auto}
#pdt .bigcard-h h3{margin:0;font-size:17px;font-weight:700;color:var(--blue)}
#pdt .bigcard-h .c{margin-left:auto;font-size:13px;color:var(--storm);background:var(--soft);border-radius:var(--radius-lg);padding:1px 10px;min-width:22px;text-align:center}
#pdt .c.clickable{cursor:pointer}
#pdt .c.clickable:hover{background:var(--il-altgeld);color:#fff}
#pdt .bigcard-sub{font-size:12px;color:var(--storm);margin:0 0 9px}
#pdt .mini{display:flex;flex-direction:column;gap:6px}
#pdt .mini-item{cursor:pointer;border-radius:var(--radius-sm);padding:6px 8px;margin:0 -8px;display:flex;flex-direction:column;gap:1px}
#pdt .mini-item:hover{background:#f6f7f6}
#pdt .mini-item b{font-size:14px;font-weight:600;color:var(--ink)}
#pdt .mini-item span{font-size:12px;color:var(--storm)}
#pdt .more{margin:10px 0 0;display:inline-block}
#pdt .none{font-size:13px;color:var(--storm);font-style:italic;margin:2px 0 0}
#pdt .protonote{font-size:12px;color:var(--storm);line-height:1.6;margin-top:20px}
#pdt .modal{position:fixed;inset:0;background:rgba(19,41,75,.55);display:flex;align-items:flex-start;justify-content:center;padding:5vh 16px;z-index:9999;overflow:auto}
#pdt .modal[hidden]{display:none}
#pdt .modal-card{background:#fff;border-radius:var(--radius-dialog);max-width:780px;width:100%;padding:24px 28px;position:relative}
#pdt .m-close{position:absolute;top:8px;right:14px;border:none;background:none;font-size:26px;line-height:1;color:var(--storm);cursor:pointer}
#pdt .m-eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--il-altgeld);font-weight:600}
#pdt .m-title{font-size:22px;color:var(--blue);margin:4px 30px 12px 0}
#pdt .m-summary{font-size:15px;line-height:1.6;color:var(--ink);margin:0 0 10px}
#pdt .m-desc{font-size:14px;line-height:1.6;color:var(--storm-dark);margin:0 0 14px}
#pdt .m-meta{display:grid;grid-template-columns:auto 1fr;gap:6px 16px;margin:0;font-size:14px;align-content:start}
#pdt .m-meta dt{color:var(--storm);font-weight:600}
#pdt .m-meta dd{margin:0;color:var(--ink)}
#pdt .m-cols{display:flex;gap:20px;margin-top:4px;align-items:stretch}
#pdt .m-cols .m-meta{flex:1.15;min-width:0}
#pdt .m-photo{flex:1;min-width:0;min-height:225px;border-radius:var(--radius-lg);overflow:hidden;border:1px solid var(--line);background:linear-gradient(150deg,#1c3a66,#13294B 62%);position:relative;display:flex;align-items:center;justify-content:center}
#pdt .m-photo img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
#pdt .m-photo .ph{display:flex;flex-direction:column;align-items:center;gap:10px;color:#fff}
#pdt .m-photo .ph svg{width:54px;height:54px;opacity:.5}
#pdt .m-photo .ph span{font-size:11px;text-transform:uppercase;letter-spacing:.1em;font-weight:600;opacity:.85}
@media(max-width:680px){#pdt .m-cols{flex-direction:column}}
#pdt .m-flag{margin-top:12px;font-size:13px;background:var(--warn-bg);color:var(--warn-text);border-radius:var(--radius-md);padding:8px 12px}
#pdt .m-list{display:flex;flex-direction:column;gap:2px;margin-top:8px}
#pdt .m-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:var(--radius-md);cursor:pointer}
#pdt .m-row:hover{background:var(--soft)}
#pdt .m-row .m-sub{font-size:12px;color:var(--storm);margin-top:2px}
#pdt .m-arrow{color:var(--il-altgeld);font-weight:700;flex:0 0 auto}
#pdt .m-back{margin:0 0 10px}
@media(max-width:820px){#pdt .wrap{padding-left:16px;padding-right:16px}#pdt .layout{flex-direction:column}#pdt .inset{flex:1 1 auto;width:100%}#pdt .bigcards{grid-template-columns:1fr}#pdt .zoom{max-width:320px}}
@media print{
@page{size:letter portrait;margin:0.5in}
header,footer,ilw-header,ilw-footer,#pdt .controls,#pdt .page-intro,#pdt .protonote,#pdt-modal{display:none !important}
body{background:#fff !important;min-width:0 !important}
#pdt .wrap{margin:0 !important;padding:0 !important;max-width:none !important}
#pdt, #pdt *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
#pdt .layout{gap:0.3in}
#pdt .inset{flex:0 0 2.6in}
#pdt .zoom{width:2.4in}
#pdt .loc{width:1.4in}
#pdt .bigcards{gap:0.18in}
#pdt .bigcard{break-inside:avoid;page-break-inside:avoid}
#pdt .more{display:none !important}
#pdt a{color:#13294B !important;text-decoration:none !important}
}
.tscroll{overflow-x:auto}
</style>"""
MYCSS = MYCSS.replace("/*TOKENS*/", ui_tokens.tokens_css("#pdt"))
MYCSS = MYCSS.replace("</style>", buttons_css("#pdt") + "</style>")

MARKUP = """
<main id="pdt">
<div class="wrap">
  <div class="page-intro"><div class="pi-text"><h1>PRI District Tracker</h1><p>What the Prairie Research Institute does in your legislative district.</p></div><button id="printBtn" class="btn pri printbtn" type="button">Open One-Page Handout</button></div>
  <div class="controls">
    <label>Survey<select id="survey"><option value="all">All PRI</option><option value="INHS">INHS</option><option value="ISGS">ISGS</option><option value="ISWS">ISWS</option><option value="ISAS">ISAS</option><option value="ISTC">ISTC</option></select></label>
    <label>Level<select id="level"><option>Federal</option><option>State</option></select></label>
    <label>Chamber<select id="chamber"><option>House</option><option>Senate</option></select></label>
    <label>District<select id="district"></select></label>
  </div>
  <div class="layout">
    <div class="leftcol">
      <div class="headerblock"><div class="titlecol" id="sheetHead"></div><div class="fundcol" id="fundCard"></div></div>
      <div id="list"></div>
    </div>
    <aside class="inset"><div class="mapbox"><h3 id="insetTitle">District</h3><div class="zoom" id="mapZoom"></div><div class="loc" id="mapLoc"></div><div class="loc-cap" id="locCap"></div></div></aside>
  </div>
  <div class="protonote">Prototype - data compiled June 2026 (currently INHS; other surveys to be added). Cards show 3 random entries, reshuffled each refresh - click the count to see all. Representatives auto-refreshed each build (federal + Open States). Funding figures are placeholders.</div>
  <div id="pdt-modal" class="modal" role="dialog" aria-modal="true" aria-labelledby="pdt-m-title" hidden><div class="modal-card"><button class="m-close" type="button" aria-label="Close">&times;</button><div id="m-body"></div></div></div>
</div>
</main>
"""

APP = """
<script>
/*SURVEYS*/
const KINDS=[{id:'projects',label:'Projects',color:'#13294B'},{id:'grants',label:'Active Grants',color:'#C84113'},{id:'publications',label:'Publications',color:'#4877B8'},{id:'news',label:'News',color:'#707372'},{id:'outreach',label:'Outreach & Community Science',color:'#4A4C4B'}];
const sv=document.getElementById('survey'),lv=document.getElementById('level'),chm=document.getElementById('chamber'),dst=document.getElementById('district');
const ACTBYID={};ACT.forEach(function(a){ACTBYID[a.id]=a;});
var CUR={matched:[],survey:'all'};var LASTLIST=null;var PRINTING=false;
function surveyOf(a){return a.survey||'INHS';}
var FINIAL_SVG='<svg viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg"><path fill="#fff" d="M58.6,0H31h-2H1.4H0v1.4V29v2v27.6V60h1.4H29h2h27.6H60v-1.4V31v-2V1.4V0H58.6z M31,1h26.6L31,27.6V1z M29,1v26.6L2.4,1H29z M1,2.4L27.6,29H1V2.4z M1,57.6V31h26.6L1,57.6z M29,59H2.4L29,32.4V59z M31,59V32.4L57.6,59H31z M59,57.6L32.4,31H59V57.6z M59,29H32.4L59,2.4V29z"/></svg>';
function kindOf(a){const t=a.type;if(t==='Grant')return 'grants';if(t==='Publication')return 'publications';if(t==='News')return 'news';if(t==='Community science')return 'outreach';return 'projects';}
function ck(){if(lv.value==='Federal')return chm.value==='House'?'us_house':'us_senate';return chm.value==='House'?'il_house':'il_senate';}
function chamberLabel(){if(lv.value==='Federal')return chm.value==='House'?'U.S. House':'U.S. Senate';return chm.value==='House'?'Illinois House':'Illinois Senate';}
function fillDistricts(){const k=ck();dst.innerHTML='';if(k==='us_senate'){[['durbin','Sen. Dick Durbin (statewide)'],['duckworth','Sen. Tammy Duckworth (statewide)']].forEach(p=>{const o=document.createElement('option');o.value=p[0];o.textContent=p[1];dst.appendChild(o);});return;}const nums=Object.keys(GEO.chambers[k]).map(Number).sort((a,b)=>a-b);nums.forEach(n=>{const o=document.createElement('option');o.value=String(n);const rep=(REPS[k]||{})[String(n)];o.textContent='District '+n+(rep&&rep.name?'  -  '+rep.name:'');dst.appendChild(o);});}
function matchAct(a,k,num){if(a.scope==='statewide')return true;if(k==='us_senate')return a.scope!=='external';if(a.scope==='external')return false;return (a[k]||[]).indexOf(Number(num))>=0;}
function svgmap(mapK,sel,vb){const ch=GEO.chambers[mapK];let other='',hot='';for(const key in ch){const isSel=(sel==='ALL')||(sel!==null&&Number(key)===Number(sel));const p='<path d="'+ch[key].d+'" fill="'+(isSel?'#FF5F05':'#E4E5E5')+'" stroke="'+(isSel?'#13294B':'#FFFFFF')+'" stroke-width="'+(isSel?1.2:0.4)+'"/>';if(isSel)hot+=p;else other+=p;}return '<svg viewBox="'+vb+'" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;display:block">'+other+hot+'</svg>';}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function repHtml(k,num){var r=(REPS[k]||{})[num];if(!r)return '<span class="repx">Officeholder to be verified.</span>';var nm=esc(r.name)+(r.party?' ('+esc(r.party)+')':'');return r.url?'<a href="'+esc(r.url)+'" target="_blank" rel="noopener">'+nm+'</a>':'<span>'+nm+'</span>';}
function fundCard(){return '<div class="fund"><div class="fund-amt">$&mdash;</div><div class="fund-lbl">Active project funding &middot; last 10 years</div><span class="fund-tag">placeholder &mdash; pending data</span></div>';}
function shuffle(arr){var a=arr.slice();for(var i=a.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1));var t=a[i];a[i]=a[j];a[j]=t;}return a;}
function entryLi(a){return '<li><button type="button" class="mini-item" data-id="'+esc(a.id)+'"><b>'+esc(a.title)+'</b><span>'+esc(a.type+(a.status?' \\u00b7 '+a.status:''))+(a.confirm?' \\u00b7 verify district':'')+'</span></button></li>';}
function catItems(type,id){if(type==='all')return CUR.matched;if(type==='survey')return CUR.matched.filter(a=>surveyOf(a)===id);if(type==='kind')return CUR.matched.filter(a=>surveyOf(a)===CUR.survey&&kindOf(a)===id);return [];}
function catLabel(type,id){if(type==='all')return 'All PRI projects in this district';if(type==='survey'){var s=SURVEYS.find(x=>x.id===id);return (s?s.name:id);}if(type==='kind'){var k=KINDS.find(x=>x.id===id);return (k?k.label:id);}return '';}
var MODAL_OPENER=null;
function showModal(html){
  var m=document.getElementById('pdt-modal');
  if(m.hidden)MODAL_OPENER=document.activeElement;
  document.getElementById('m-body').innerHTML=html;
  var t=m.querySelector('.m-title');if(t)t.id='pdt-m-title';
  m.hidden=false;
  var f=m.querySelector('.m-close');if(f)f.focus();
}
function closeModal(){
  var m=document.getElementById('pdt-modal');
  m.hidden=true;LASTLIST=null;
  if(MODAL_OPENER&&MODAL_OPENER.focus){try{MODAL_OPENER.focus();}catch(e){}}
  MODAL_OPENER=null;
}
// Escape closes it, and Tab stays inside while it is open.
document.addEventListener('keydown',function(e){
  var m=document.getElementById('pdt-modal');
  if(!m||m.hidden)return;
  if(e.key==='Escape'){e.preventDefault();closeModal();return;}
  if(e.key!=='Tab')return;
  var f=m.querySelectorAll('button,a[href],select,input,textarea,[tabindex]:not([tabindex="-1"])');
  if(!f.length)return;
  var first=f[0],last=f[f.length-1];
  if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
  else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
},true);
function countTag(n,type,id){var a=' data-list-type="'+type+'" data-list-id="'+id+'" title="See all"';
  return n?('<button type="button" class="c clickable"'+a+'>'+n+'</button>'):('<span class="c">'+n+'</span>');}
function openList(type,id){LASTLIST={type:type,id:id};var items=catItems(type,id);var h='<div class="m-eyebrow">'+esc(catLabel(type,id))+' \\u00b7 '+items.length+' result'+(items.length===1?'':'s')+'</div><h2 class="m-title">Topics in this district</h2>';if(!items.length){h+='<p class="none">Nothing recorded for this district yet.</p>';}else{h+='<ul class="m-list">';items.forEach(function(a){h+='<li><button type="button" class="m-row" data-id="'+esc(a.id)+'"><span class="m-txt"><b>'+esc(a.title)+'</b><span class="m-sub">'+esc([surveyOf(a),a.type,a.status].filter(Boolean).join(' \\u00b7 '))+'</span></span><span class="m-arrow">\\u2192</span></button></li>';});h+='</ul>';}showModal(h);}
function openDetail(id){var a=ACTBYID[id];if(!a)return;var dn=[];['us_house','il_senate','il_house'].forEach(function(c){if((a[c]||[]).length)dn.push({us_house:'U.S. House',il_senate:'Illinois Senate',il_house:'IL House'}[c]+' '+a[c].join(', '));});var where=a.scope==='statewide'?'Statewide (every district)':(a.scope==='external'?'Outside Illinois':(dn.join('  \\u00b7  ')||a.location||''));var back=LASTLIST?'<button class="m-back" data-back="1">\\u2190 Back to list</button>':'';var h=back+'<div class="m-eyebrow">'+esc(surveyOf(a)+' \\u00b7 '+a.type)+'</div><h2 class="m-title">'+esc(a.title)+'</h2>';if(a.summary)h+='<p class="m-summary">'+esc(a.summary)+'</p>';if(a.description&&a.description!==a.summary)h+='<p class="m-desc">'+esc(a.description)+'</p>';var mrows='';[['Lead',a.lead],['Funder / partners',a.funder],['Status',a.status],['Location',a.location],['Districts',where],['Program area',a.group]].forEach(function(p){if(p[1])mrows+='<dt>'+esc(p[0])+'</dt><dd>'+esc(p[1])+'</dd>';});var photo=a.image?('<img src="'+esc(a.image)+'" alt="'+esc(a.title)+'">'):('<div class="ph">'+FINIAL_SVG+'<span>'+esc(surveyOf(a))+'</span></div>');h+='<div class="m-cols"><dl class="m-meta">'+mrows+'</dl><div class="m-photo">'+photo+'</div></div>';if(a.confirm)h+='<p class="m-flag">District assignment is approximate and needs confirmation against a street address.</p>';showModal(h);}
function render(){const k=ck(),num=dst.value;if(!num)return;const full='0 0 '+GEO.w+' '+GEO.h;
  const matched=ACT.filter(a=>matchAct(a,k,num));const survey=sv.value;
  const scope=(survey==='all')?matched:matched.filter(a=>surveyOf(a)===survey);
  CUR.matched=matched;CUR.survey=survey;
  if(k==='us_senate'){document.getElementById('mapZoom').innerHTML=svgmap('us_house','ALL',full);document.getElementById('mapLoc').innerHTML='';document.getElementById('insetTitle').textContent='Illinois (statewide)';document.getElementById('locCap').textContent='Both U.S. Senators represent the whole state';}
  else{const vb=GEO.chambers[k][num].vb.join(' ');document.getElementById('mapZoom').innerHTML=svgmap(k,num,vb);document.getElementById('mapLoc').innerHTML=svgmap(k,num,full);document.getElementById('insetTitle').textContent=chamberLabel()+' District '+num;document.getElementById('locCap').textContent='Where it sits in Illinois';}
  const distLabel=(k==='us_senate')?'U.S. Senate (statewide)':(chamberLabel()+' District '+num);
  var statAttr=(survey==='all')?'data-list-type="all"':('data-list-type="survey" data-list-id="'+survey+'"');
  let head='<h2>'+esc(distLabel)+'</h2><p class="rep">'+repHtml(k,num)+'</p>';
  head+='<div class="stats"><button type="button" class="stat clickable" '+statAttr+' title="See all"><span class="n">'+scope.length+'</span><span class="l">'+(survey==='all'?'PRI projects':esc(survey)+' projects')+'</span></button>';
  if(survey==='all'){const sc=new Set(matched.map(surveyOf)).size;head+='<div class="stat"><div class="n">'+sc+'</div><div class="l">surveys active</div></div>';}
  head+='</div>';
  document.getElementById('sheetHead').innerHTML=head;
  document.getElementById('fundCard').innerHTML=fundCard();
  let html='<div class="bigcards">';
  if(survey==='all'){
    SURVEYS.forEach(s=>{const items=matched.filter(a=>surveyOf(a)===s.id);
      html+='<div class="bigcard"><div class="bigcard-h" style="border-color:'+s.color+'"><span class="bigcard-dot" style="background:'+s.color+'"></span><h3>'+s.id+'</h3>'+countTag(items.length,'survey',s.id)+'</div><p class="bigcard-sub">'+esc(s.name)+'</p>';
      if(items.length){html+='<ul class="mini">'+(PRINTING?items:shuffle(items).slice(0,3)).map(entryLi).join('')+'</ul>';if(!PRINTING&&items.length>3)html+='<button type="button" class="btn-link more" data-list-type="survey" data-list-id="'+s.id+'">see all '+items.length+' \\u2192</button>';}
      else html+='<p class="none">Nothing recorded for this district yet.</p>';
      html+='</div>';});
  } else {
    KINDS.forEach(kd=>{const list=scope.filter(a=>kindOf(a)===kd.id);
      html+='<div class="bigcard"><div class="bigcard-h" style="border-color:'+kd.color+'"><span class="bigcard-dot" style="background:'+kd.color+'"></span><h3>'+kd.label+'</h3>'+countTag(list.length,'kind',kd.id)+'</div>';
      if(list.length){html+='<ul class="mini">'+(PRINTING?list:shuffle(list).slice(0,3)).map(entryLi).join('')+'</ul>';if(!PRINTING&&list.length>3)html+='<button type="button" class="btn-link more" data-list-type="kind" data-list-id="'+kd.id+'">see all '+list.length+' \\u2192</button>';}
      else html+='<p class="none">None recorded for this district yet</p>';
      html+='</div>';});
  }
  html+='</div>';
  document.getElementById('list').innerHTML=html;
}
document.getElementById('pdt').addEventListener('click',function(e){
  var back=e.target.closest('[data-back]');if(back){if(LASTLIST)openList(LASTLIST.type,LASTLIST.id);return;}
  var mrow=e.target.closest('.m-row');if(mrow){openDetail(mrow.getAttribute('data-id'));return;}
  var num=e.target.closest('[data-list-type]');if(num&&!num.classList.contains('c')||(num&&num.classList.contains('clickable'))){LASTLIST={type:num.getAttribute('data-list-type'),id:num.getAttribute('data-list-id')};openList(LASTLIST.type,LASTLIST.id);return;}
  var item=e.target.closest('.mini-item');if(item){LASTLIST=null;openDetail(item.getAttribute('data-id'));return;}
});
document.getElementById('pdt-modal').addEventListener('click',function(e){if(e.target.id==='pdt-modal'||e.target.classList.contains('m-close'))closeModal();});
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});
sv.addEventListener('change',render);
lv.addEventListener('change',()=>{fillDistricts();render();});
chm.addEventListener('change',()=>{fillDistricts();render();});
dst.addEventListener('change',render);
var pb=document.getElementById('printBtn');if(pb)pb.addEventListener('click',function(){window.open('handout.html?c='+encodeURIComponent(ck())+'&n='+encodeURIComponent(dst.value)+'&survey='+encodeURIComponent(sv.value)+'&_='+Date.now(),'priHandout');});
window.addEventListener('beforeprint',function(){PRINTING=true;render();});
window.addEventListener('afterprint',function(){PRINTING=false;render();});
fillDistricts();
if([...dst.options].some(o=>o.value==='13'))dst.value='13';
render();
</script>
"""
# One palette for every page (UI Elements spec, PDT-01): pri_data.SURVEYS.
APP = APP.replace("/*SURVEYS*/", pri_data.survey_js())

# geo.json lets the hosted PHP endpoint (php/data.php) serve the same GEO block the
# static data.js bakes in, so switching to the live database is a one-line src swap.
with open(os.path.join(DATA, "geo.json"), "w", encoding="utf-8") as f:
    json.dump(GEO, f)

# window.ACT self-filters on the client too, so a record that expires AFTER this build
# (but before the page is opened) still drops without needing a rebuild.
DATA_JS = ("window.GEO=" + json.dumps(GEO) + ";window.REPS=" + json.dumps(REPS) +
           ";window.ACT=(function(A){var t=new Date().toISOString().slice(0,10);"
           "return A.filter(function(a){var s=(a.show_until||'').toString().trim();return !s||s>=t;});})("
           + json.dumps(ACT) + ");")
with open(os.path.join(PROJ, "data.js"), "w", encoding="utf-8") as f:
    f.write(DATA_JS)
data_script = '<script src="data.js"></script>'
COOKIE_KILL = '<script>(function(){function rm(r){try{var q=r.querySelectorAll("#onetrust-consent-sdk,#onetrust-banner-sdk,[id*=onetrust],[class*=onetrust],[id^=ot-sdk]");for(var i=0;i<q.length;i++)q[i].remove();var all=r.querySelectorAll("div,section,aside,dialog,form");var c=[];for(var j=0;j<all.length;j++){var t=all[j].textContent||"";if(/Cookie Notice|We use Cookies|Close Cookie Notice/i.test(t)&&t.length<1500)c.push(all[j]);}c.forEach(function(e){if(!c.some(function(o){return o!==e&&o.contains(e);})){try{e.remove();}catch(x){}}});}catch(e){}}function run(){rm(document);var h=document.querySelector("ilw-header");if(h&&h.shadowRoot)rm(h.shadowRoot);var f=document.querySelector("ilw-footer");if(f&&f.shadowRoot)rm(f.shadowRoot);}run();try{new MutationObserver(run).observe(document.documentElement,{childList:true,subtree:true});}catch(e){}var n=0,iv=setInterval(function(){run();if(++n>800)clearInterval(iv);},50);})();</script>'

html = ("<!doctype html><html lang=\"en\"><head>" + HEAD_ASSETS_INLINE + GF + MYCSS + "</head><body>"
        + PRI_HEADER + MARKUP + PRI_FOOTER + "\n" + PRI_SCRIPTS + "\n" + data_script + APP + COOKIE_KILL + "</body></html>")

OUT = os.path.join(PROJ, "index.html")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

# ---- handout.html : print-optimized one-pager (All-PRI or per-survey via ?survey=) ----
HANDOUT_CSS = """<style>
/*TOKENS*/
body{margin:0;background:#9aa3ad;font-family:'Source Sans 3','Source Sans Pro',Arial,sans-serif;color:var(--ink)}
.ho-bar{display:flex;gap:14px;justify-content:center;align-items:center;background:var(--blue-deep);padding:9px}
.ho-bar a{color:#fff;font-size:13px;text-decoration:none}
#ho{display:flex;justify-content:center;padding:22px 12px;overflow-x:auto}
.ho-sheet{background:#fff url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2060%2060'%3E%3Cpath%20fill='%2313294b'%20fill-opacity='.06'%20d='M58.6,0H31h-2H1.4H0v1.4V29v2v27.6V60h1.4H29h2h27.6H60v-1.4V31v-2V1.4V0H58.6z%20M31,1h26.6L31,27.6V1z%20M29,1v26.6L2.4,1H29z%20M1,2.4L27.6,29H1V2.4z%20M1,57.6V31h26.6L1,57.6z%20M29,59H2.4L29,32.4V59z%20M31,59V32.4L57.6,59H31z%20M59,57.6L32.4,31H59V57.6z%20M59,29H32.4L59,2.4V29z'/%3E%3C/svg%3E");background-size:34px 34px;width:8.5in;height:11in;box-sizing:border-box;padding:0;display:flex;flex-direction:column;overflow:hidden;flex:0 0 auto}
.ho-lh{background:#fff;position:relative;z-index:2}
.ho-sep{height:5px;background:linear-gradient(90deg,var(--acc,#FF5F05) 0,var(--acc,#FF5F05) 1.5in,var(--blue) 1.5in,var(--blue) 100%);position:relative;z-index:4;flex:0 0 auto}
.ho-lh ilw-header{display:block}
.ho-lh ilw-header-menu,.ho-lh [slot=navigation],.ho-lh [slot=search],.ho-lh form[slot=search],.ho-lh .il-links,.ho-lh [slot=links]{display:none !important}
#onetrust-consent-sdk,#onetrust-banner-sdk,#ot-sdk-btn,#ot-sdk-btn-floating,.ot-sdk-show-settings,.ot-floating-button,.onetrust-pc-dark-filter{display:none !important}
.ho-lh-tag{position:absolute;top:0.44in;right:0.5in;text-align:right;font-family:'Montserrat',Arial,sans-serif;font-weight:800;font-size:34px;line-height:1.04;color:var(--orange);z-index:6;pointer-events:none}
.ho-pad{padding:0.12in 0.5in 0.3in;flex:1;display:flex;flex-direction:column;position:relative}
.ho-kicker{font-size:22px;text-transform:uppercase;letter-spacing:.02em;color:var(--acc,#FF5F05);font-weight:700;line-height:1.05}
.ho-sheet h1{font-family:'Montserrat',Arial,sans-serif;font-weight:700;color:var(--blue);font-size:27px;margin:3px 0 2px;line-height:1.08}
.ho-sub{font-size:13px;color:var(--storm)}
.ho-rep{font-size:14px;margin-top:7px;font-weight:600}
.ho-rep a{color:var(--link);text-decoration:none}
.ho-top{display:flex;gap:22px;align-items:flex-start;margin-top:6px;position:relative;z-index:1}
.ho-tri{position:absolute;top:-0.55in;right:-0.5in;width:4.6in;height:4in;z-index:0;pointer-events:none}
.ho-tri2{position:absolute;bottom:-0.3in;left:-0.5in;width:4.6in;height:4in;z-index:0;pointer-events:none}
.ho-id,.ho-map{position:relative;z-index:1}
.ho-id{flex:1;min-width:0;display:flex;flex-direction:column}
.ho-map{flex:0 0 2.5in;text-align:center}
.ho-map .z{width:2.5in;height:2.5in;margin-left:auto;border:1px solid #d7dbe1;border-radius:var(--radius-md);background:#fafbfd;box-shadow:0 2px 7px rgba(19,41,75,.12);overflow:hidden}
.ho-loc{width:1.35in;margin:8px auto 0}
.ho-loccap{font-size:10px;color:var(--storm);margin-top:3px}
.ho-loc{overflow:visible}
.ho-map .z svg .sel{filter:drop-shadow(4px 6px 7px rgba(19,41,75,.5))}
.ho-loc svg{overflow:visible}
.ho-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:7px}
.ho-tile{border-radius:var(--radius-md);padding:9px 10px;color:#fff;display:flex;align-items:center;gap:8px;min-width:0}
.ho-tile .ho-ico{flex:0 0 auto;display:flex}
.ho-tile .ho-ico svg{width:17px;height:17px}
.ho-tile .n{font-family:'Montserrat',Arial,sans-serif;font-weight:700;font-size:18px;line-height:1}
.ho-tile .l{font-size:8.2px;margin-top:2px;opacity:.93;text-transform:uppercase;letter-spacing:.04em;line-height:1.22;font-weight:600}
.ho-focal-row{display:flex;gap:10px;margin-top:8px;align-items:stretch}
.ho-focal{background:linear-gradient(150deg,#1c3a66,#13294B 62%);color:#fff;border-radius:var(--radius-dialog);padding:14px 17px;flex:1 1 64%;min-width:0;display:flex;gap:12px;align-items:flex-start;box-shadow:0 8px 18px rgba(19,41,75,.32),0 2px 5px rgba(0,0,0,.18);border:1px solid rgba(255,255,255,.07)}
.ho-feat-img{flex:1 1 36%;min-width:0;border-radius:var(--radius-dialog);overflow:hidden;border:1px solid rgba(19,41,75,.16);box-shadow:0 8px 18px rgba(19,41,75,.25);position:relative;background:linear-gradient(150deg,#1c3a66,#13294B 62%)}
.ho-feat-img img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
.ho-feat-img .ph{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.ho-feat-img .ph svg{width:42%;height:auto;opacity:.45}
.ho-feat-img .ph:after{content:"";position:absolute;left:0;right:0;bottom:0;height:4px;background:var(--orange)}
.ho-focal-ico{flex:0 0 auto;color:var(--orange);display:flex}
.ho-focal-ico svg{width:30px;height:30px}
.ho-focal .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--il-altgeld);font-weight:700}
.ho-focal .t{font-family:'Montserrat',Arial,sans-serif;font-weight:700;font-size:17.5px;margin-top:3px;line-height:1.14}
.ho-focal .d{font-size:12px;opacity:.93;margin-top:6px;line-height:1.42}
.ho-hl{margin-top:8px;position:relative;z-index:1}
.ho-hl-head{display:flex;align-items:center;gap:9px;margin-bottom:13px}
.ho-hl-head .bar{height:3px;width:28px;background:var(--orange)}
.ho-hl-head h2{font-family:'Montserrat',Arial,sans-serif;font-weight:700;color:var(--blue);font-size:16px;margin:0}
.ho-hl-grid{display:grid;grid-template-columns:1fr 1fr;gap:11px}
.ho-item{background:#fff;border:1px solid #e1e3e6;border-left:4px solid var(--acc,#FF5F05);border-radius:var(--radius-sm);padding:10px 13px;box-shadow:0 2px 6px rgba(19,41,75,.09)}
.ho-item .t{font-weight:700;font-size:12.5px;color:var(--ink);line-height:1.2}
.ho-item .d{font-size:10.5px;color:#555;line-height:1.42;margin-top:4px}
.ho-tag{font-size:9px;border-radius:var(--radius-xs);padding:1px 7px;white-space:nowrap;font-weight:700}
.ho-more{font-size:12px;color:var(--storm);font-style:italic;margin-top:13px}
.ho-surv-cards{display:flex;flex-direction:column;gap:7px}
.ho-sc{display:flex;align-items:stretch;background:#fff;border:1px solid var(--line);border-radius:var(--radius-md);overflow:hidden;box-shadow:0 2px 6px rgba(19,41,75,.1)}
.ho-sc-tab{flex:0 0 0.92in;background:var(--sc);background-image:linear-gradient(150deg,rgba(255,255,255,.16),rgba(0,0,0,.2));color:#fff;display:flex;align-items:center;justify-content:center;padding:8px 6px}
.ho-sc-tab .ac{font-family:'Montserrat',Arial,sans-serif;font-weight:800;font-size:22px;line-height:1;letter-spacing:.01em}
.ho-sc-main{flex:1;min-width:0;padding:8px 15px 9px;display:flex;flex-direction:column;justify-content:center}
.ho-sc-main .cnt{align-self:flex-end;display:flex;align-items:flex-start;gap:6px;margin-bottom:5px}
.ho-sc-main .cnt .num{font-family:'Montserrat',Arial,sans-serif;font-size:25px;font-weight:800;color:var(--sc);line-height:.9}
.ho-sc-main .cnt .lbl{font-size:9px;font-weight:700;text-transform:uppercase;color:#5b5e62;line-height:1.05;max-width:0.5in;letter-spacing:.03em;padding-top:1px}
.ho-sc-main .proj{display:grid;grid-template-columns:repeat(3,1fr)}
.ho-sc-main .pc{font-size:11px;color:var(--ink)63a;line-height:1.34;padding:0 12px;position:relative}
.ho-sc-main .pc:first-child{padding-left:0}
.ho-sc-main .pc:last-child{padding-right:0}
.ho-sc-main .pc+.pc::before{content:"";position:absolute;left:0;top:8%;height:84%;width:1px;background:#98AFD2}
.ho-sc-main .sc-empty{font-size:11px;color:#9a9da1;font-style:italic}
.ho-foot{margin:auto -0.5in -0.3in -0.5in;background:var(--blue);color:#fff;padding:9px 0.5in;display:flex;justify-content:space-between;align-items:center;gap:18px;position:relative;z-index:1}
.ho-foot .c{font-size:10px;line-height:1.4;opacity:.92}
.ho-foot .c b{font-size:11px;opacity:1}
.ho-qr{flex:0 0 auto;display:flex;align-items:center;gap:9px}
.ho-qr .qrcap{font-size:8px;color:#cdd6e2;text-align:right;line-height:1.2;max-width:0.8in}
.ho-qr .qrimg{width:0.58in;height:0.58in;display:block;background:#fff;border-radius:var(--radius-xs);padding:2px;box-sizing:border-box}
.ho-foot-url{font-family:'Montserrat',Arial,sans-serif;font-weight:700;font-size:15px;color:#fff;text-decoration:none;letter-spacing:.02em;white-space:nowrap;flex:0 0 auto}
@media print{
@page{size:letter portrait;margin:0}
html,body{background:#fff;margin:0 !important;width:8.5in !important;min-width:0 !important;max-width:8.5in !important;overflow:hidden;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.ho-bar{display:none !important}
#ho{padding:0;overflow:visible;display:block}
.ho-sheet{width:8.5in;height:11in;box-shadow:none}
.ho-item,.ho-tile,.ho-sc{break-inside:avoid}
}
.tscroll{overflow-x:auto}
</style>"""
HANDOUT_CSS = HANDOUT_CSS.replace("/*TOKENS*/", ui_tokens.tokens_css())
HANDOUT_CSS = HANDOUT_CSS.replace("</style>", buttons_css() + "</style>")
HANDOUT_BODY = '<div class="ho-bar"><button class="btn pri" onclick="window.print()">Save as PDF</button><a href="index.html">&larr; Back to the map</a></div><div id="ho"><div class="ho-sheet">' + PRI_PRINT_HEADER + '<div class="ho-sep"></div><div class="ho-pad" id="ho-body"></div></div></div>'
HANDOUT_APP = """<script>
/*SURVEYS*/
var SURV={},TAGCOL={},SURVCOL={};SURVEYS.forEach(function(s){SURV[s.id]=s.name;TAGCOL[s.id]=[s.tint,s.ink];SURVCOL[s.id]=s.color;});
var SURVICON={INHS:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.52-4.48 10-10 10z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/></svg>',ISGS:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2 2 7l10 5 10-5z"/><path d="M2 12l10 5 10-5"/><path d="M2 17l10 5 10-5"/></svg>',ISWS:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.7s6 5.3 6 10.3a6 6 0 0 1-12 0c0-5 6-10.3 6-10.3z"/></svg>',ISAS:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V10M9 21V10M15 21V10M19 21V10"/><path d="M4 10l8-6 8 6z"/></svg>',ISTC:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M5 5l1.7 1.7M17.3 17.3 19 19M19 5l-1.7 1.7M6.7 17.3 5 19"/></svg>'};
var ICONS={projects:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v6l-4.5 8.5A2 2 0 0 0 7.3 21h9.4a2 2 0 0 0 1.8-3.5L14 9V3"/></svg>',surveys:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V8l7-4 7 4v13"/><path d="M9.5 21v-5h5v5"/></svg>',grants:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>',funding:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/></svg>',star:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.3l6.5-.9z"/></svg>',book:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',people:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',globe:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',pin:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',news:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>'};
function surveyOf(a){return a.survey||'INHS';}
function kindOf(a){var t=a.type;if(t==='Grant')return 'grants';if(t==='Publication')return 'publications';if(t==='News')return 'news';if(t==='Community science')return 'outreach';return 'projects';}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function svgmap(mapK,sel,vb,mode){var ch=GEO.chambers[mapK];var o='',h='',shp='';var loc=(mode==='loc');var nf=loc?'#13294B':'#F6F7F9';var ns=loc?'rgba(255,255,255,0.55)':'#1D58A7';var ss=loc?'#ffffff':'#13294B';var sw=loc?0.6:1.1;for(var key in ch){var isSel=(sel==='ALL')||(sel!==null&&Number(key)===Number(sel));if(isSel){h+='<path class="sel" d="'+ch[key].d+'" fill="#FF5F05" stroke="'+ss+'" stroke-width="'+sw+'"/>';}else{o+='<path d="'+ch[key].d+'" fill="'+nf+'" stroke="'+ns+'" stroke-width="0.5"/>';}if(loc)shp+='<path d="'+ch[key].d+'"/>';}var pre='';if(loc)pre='<defs><filter id="gsh" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="13"/></filter></defs><g fill="#0a1428" opacity="0.3" filter="url(#gsh)" transform="translate(500,1783) scale(1.04,0.4) skewX(-20) translate(-500,-1783)">'+shp+'</g>';return '<svg viewBox="'+vb+'" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;display:block;overflow:visible">'+pre+o+h+'</svg>';}
function matchAct(a,k,num){if(a.scope==='statewide')return true;if(k==='us_senate')return a.scope!=='external';if(a.scope==='external')return false;return (a[k]||[]).indexOf(Number(num))>=0;}
function clabel(k){return ({us_house:'U.S. House',us_senate:'U.S. Senate',il_senate:'Illinois Senate',il_house:'Illinois House'})[k]||k;}
var P=new URLSearchParams(location.search);var Q=window.__PRIQ||{};
var k=Q.c||P.get('c')||'us_house',num=Q.n||P.get('n')||'13',survey=Q.survey||P.get('survey')||'all';
var matched=ACT.filter(function(a){return matchAct(a,k,num);});
var scope=(survey==='all')?matched:matched.filter(function(a){return surveyOf(a)===survey;});
var full='0 0 '+GEO.w+' '+GEO.h;
var zoom,loc;
if(k==='us_senate'){zoom=svgmap('us_house','ALL',full,'loc');loc='';}else{zoom=svgmap(k,num,GEO.chambers[k][num].vb.join(' '),'zoom');loc=svgmap(k,num,full,'loc');}
var rep=(REPS[k]||{})[num];
var repLine=(k==='us_senate')?'Both U.S. Senators represent the whole state':(rep?esc(rep.name)+(rep.party?' ('+rep.party+')':''):'Officeholder to be verified.');
var title=(k==='us_senate')?'U.S. Senate':(clabel(k)+' District '+num);
var subtitle=(survey==='all')?'':SURV[survey];
function ct(f){return scope.filter(f).length;}
var tiles=(survey==='all')?[
['#13294B',scope.length,'PRI projects','projects'],
['#007E8E',new Set(matched.map(surveyOf)).size,'surveys active','surveys'],
['#C84113',ct(function(a){return kindOf(a)==='grants';}),'active grants','grants'],
['#006230','$\\u2014','10-yr funding','funding'],
['#4877B8',ct(function(a){return kindOf(a)==='publications';}),'publications','book'],
['#4A4C4B',ct(function(a){return kindOf(a)==='outreach';}),'community science','people'],
['#7a4a1e',ct(function(a){return a.scope==='statewide';}),'statewide programs','globe'],
['#1c3a66',ct(function(a){return a.scope==='sited';}),'local projects','pin']
]:[
['#13294B',ct(function(a){return kindOf(a)==='projects';}),'projects','projects'],
['#C84113',ct(function(a){return kindOf(a)==='grants';}),'active grants','grants'],
['#4877B8',ct(function(a){return kindOf(a)==='publications';}),'publications','book'],
['#006230','$\\u2014','10-yr funding','funding'],
['#4A4C4B',ct(function(a){return kindOf(a)==='outreach';}),'community science','people'],
['#6a1f4d',ct(function(a){return a.type==='Program';}),'programs','surveys'],
['#7a4a1e',ct(function(a){return a.scope==='sited';}),'local projects','pin'],
['#707372',ct(function(a){return kindOf(a)==='news';}),'news items','news']
];
function rank(a){return (a.featured?100:0)+(a.priority||0)+(a.scope==='sited'?5:0);}
var hi=scope.slice().sort(function(a,b){return rank(b)-rank(a);}).slice(0,5);var topItem=hi[0];
var FINIAL='<svg viewBox="0 0 60 60" xmlns="http://www.w3.org/2000/svg"><path fill="#fff" d="M58.6,0H31h-2H1.4H0v1.4V29v2v27.6V60h1.4H29h2h27.6H60v-1.4V31v-2V1.4V0H58.6z M31,1h26.6L31,27.6V1z M29,1v26.6L2.4,1H29z M1,2.4L27.6,29H1V2.4z M1,57.6V31h26.6L1,57.6z M29,59H2.4L29,32.4V59z M31,59V32.4L57.6,59H31z M59,57.6L32.4,31H59V57.6z M59,29H32.4L59,2.4V29z"/></svg>';
var fimg=(topItem&&topItem.image)?('<img src="'+esc(topItem.image)+'" alt="">'):('<div class="ph">'+FINIAL+'</div>');
var focalHTML=topItem?('<div class="ho-focal-row"><div class="ho-focal"><span class="ho-focal-ico">'+ICONS.star+'</span><div><div class="lbl">Featured in this district</div><div class="t">'+esc(topItem.title)+'</div><div class="d">'+esc(topItem.summary||topItem.description||'')+'</div></div></div><div class="ho-feat-img">'+fimg+'</div></div>'):'';
var H='<svg class="ho-tri2" viewBox="0 0 360 320" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg"><defs><pattern id="tri2" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M0,16 L8,2 L16,16 Z" fill="#1c3a66"/></pattern></defs><polygon points="0,0 0,320 360,320" fill="#13294B"/><polygon points="0,0 0,320 360,320" fill="url(#tri2)" opacity="0.55"/><line x1="0" y1="0" x2="360" y2="320" stroke="#FF5F05" stroke-width="5"/></svg><div class="ho-top"><svg class="ho-tri" viewBox="0 0 360 320" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg"><defs><pattern id="tri" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M0,16 L8,2 L16,16 Z" fill="#1c3a66"/></pattern></defs><polygon points="0,0 360,0 360,320" fill="#13294B"/><polygon points="0,0 360,0 360,320" fill="url(#tri)" opacity="0.55"/><line x1="0" y1="0" x2="360" y2="320" stroke="#FF5F05" stroke-width="5"/></svg><div class="ho-id">';
H+='<div class="ho-kicker">Prairie Research Institute in your district</div>';
H+='<h1>'+esc(title)+'</h1>'+(subtitle?('<div class="ho-sub">'+esc(subtitle)+'</div>'):'');
H+='<div class="ho-rep">'+((rep&&rep.url)?('<a href="'+esc(rep.url)+'">'+repLine+'</a>'):repLine)+'</div>';
H+='<div class="ho-metrics">';
tiles.forEach(function(t){var ic=(t[0]==='#13294B'||t[0]==='#1c3a66')?'#FF5F05':'#fff';H+='<div class="ho-tile" style="background:'+t[0]+'"><span class="ho-ico" style="color:'+ic+'">'+(ICONS[t[3]]||'')+'</span><div><div class="n">'+t[1]+'</div><div class="l">'+esc(t[2])+'</div></div></div>';});
H+='</div>'+focalHTML+'</div>';
H+='<div class="ho-map"><div class="z">'+zoom+'</div>'+(loc?('<div class="ho-loc">'+loc+'</div>'):'')+'</div></div>';
if(survey==='all'){
H+='<div class="ho-hl"><div class="ho-surv-cards">';
['INHS','ISGS','ISWS','ISAS','ISTC'].forEach(function(s){var sa=matched.filter(function(a){return surveyOf(a)===s;});var c=SURVCOL[s];var top3=sa.slice().sort(function(a,b){return rank(b)-rank(a);}).slice(0,3);var proj=top3.length?('<div class="proj">'+top3.map(function(a){return '<div class="pc">'+esc(a.title)+'</div>';}).join('')+'</div>'):'<div class="sc-empty">Supported by statewide programs</div>';H+='<div class="ho-sc" style="--sc:'+c+'"><div class="ho-sc-tab"><span class="ac">'+s+'</span></div><div class="ho-sc-main"><div class="cnt"><span class="num">'+sa.length+'</span><span class="lbl">Active Projects</span></div>'+proj+'</div></div>';});
H+='</div></div>';
}else{
H+='<div class="ho-hl"><div class="ho-hl-head"><span class="bar"></span><h2>Highlighted '+esc(survey)+' work</h2></div><div class="ho-hl-grid">';
hi.slice(1).forEach(function(a){var col=TAGCOL[surveyOf(a)]||['#f0f1f0','#444'];H+='<div class="ho-item"><div class="t">'+esc(a.title)+' <span class="ho-tag" style="background:'+col[0]+';color:'+col[1]+'">'+esc(a.type)+'</span></div><div class="d">'+esc(a.summary||a.description||'')+'</div></div>';});
H+='</div>';
if(scope.length>hi.length){H+='<div class="ho-more">+ '+(scope.length-hi.length)+' more projects in this district \\u2014 see the full interactive profile online.</div>';}
H+='</div>';
}
H+='<div class="ho-foot"><div class="c"><b>Prairie Research Institute</b> \\u00b7 University of Illinois<br>615 E. Peabody Dr., Champaign, IL 61820 \\u00b7 configure-me@example.edu \\u00b7 217-333-5111<br>Uniting INHS \\u00b7 ISGS \\u00b7 ISWS \\u00b7 ISAS \\u00b7 ISTC<br>__CREDIT__</div>';
H+='<a class="ho-foot-url" href="https://www.prairie.illinois.edu">prairie.illinois.edu</a>';
H+='<div class="ho-qr"><span class="qrcap">Scan for the<br>live profile</span><img class="qrimg" src="assets/PRI-QR.png" alt="Scan for the interactive district profile"></div></div>';
document.getElementById('ho-body').innerHTML=H;
document.querySelector('.ho-sheet').style.setProperty('--acc',(survey==='all')?'#FF5F05':(SURVCOL[survey]||'#FF5F05'));
document.title='PRI District Tracker: '+title;
(function(){function clean(){var h=document.querySelector('.ho-lh ilw-header');if(h&&h.shadowRoot){var t=h.shadowRoot.querySelector('.menu-toggle');if(t)t.style.display='none';['.menu','.nav'].forEach(function(s){var e=h.shadowRoot.querySelector(s);if(e)e.style.display='none';});}['#onetrust-consent-sdk','#onetrust-banner-sdk','.onetrust-pc-dark-filter','#ot-sdk-btn-floating','#onetrust-pc-sdk'].forEach(function(s){var ns=document.querySelectorAll(s);for(var i=0;i<ns.length;i++)ns[i].remove();});}clean();var n=0,iv=setInterval(function(){clean();if(++n>150)clearInterval(iv);},60);})();
</script>"""
HANDOUT_APP = HANDOUT_APP.replace("/*SURVEYS*/", pri_data.survey_js())
HANDOUT_APP = HANDOUT_APP.replace("__CREDIT__", CREDIT)
HANDOUT_HEAD = ('<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>PRI District Tracker: District Profile</title>')
handout_html = ("<!doctype html><html lang=\"en\"><head>" + HEAD_ASSETS_INLINE + GF + HANDOUT_CSS + "</head><body>"
                + HANDOUT_BODY + data_script + HANDOUT_APP + COOKIE_KILL + "</body></html>")
# One product name, one suffix per page (Q-17, PDT-21).
handout_html = handout_html.replace("<title>PRI District Tracker</title>",
                                    "<title>PRI District Tracker: District Profile</title>", 1)
with open(os.path.join(PROJ, "handout.html"), "w", encoding="utf-8") as f:
    f.write(handout_html)

# ============================================================================
# PRI-Tracker-Kit.html : ONE self-contained file for the working group.
# Tabs: Explore (the live tracker) | Add data (browser-only intake -> CSV) |
# How the data works (backend). Data is inlined; the handout opens fully
# functional in a new tab (QR embedded as a data URI). Double-click to run;
# only the U of I banner needs internet.
# ============================================================================
# Columns for the exported CSV -- keep in sync with make_templates.ACT_HEADER
# (plus a trailing "image" column the Data Console import understands).
INTAKE_COLS = ["survey", "title", "type", "topic", "summary", "description", "lead", "program",
               "funder", "partners", "status", "start_year", "end_year", "url", "scope",
               "latitude", "longitude", "county", "location_text", "us_house", "il_senate",
               "il_house", "featured", "confirm", "keywords", "notes", "image", "activity_id"]

_qr_path = os.path.join(PROJ, "assets", "PRI-QR.png")
if os.path.exists(_qr_path):
    _qr_uri = "data:image/png;base64," + base64.b64encode(open(_qr_path, "rb").read()).decode("ascii")
else:
    _qr_uri = ""

# Fully self-contained handout doc (data inlined, params via window.__PRIQ, QR embedded).
handout_doc = ("<!doctype html><html lang=\"en\"><head>" + HEAD_ASSETS_INLINE + GF + HANDOUT_CSS + "</head><body>"
               + HANDOUT_BODY
               + "<script>window.__PRIQ=__PRIQMARK__;</script>"
               + "<script>" + DATA_JS + "</script>"
               + HANDOUT_APP + COOKIE_KILL + "</body></html>")
if _qr_uri:
    handout_doc = handout_doc.replace("assets/PRI-QR.png", _qr_uri)
# Embed as a JS string literal; neutralise every "</" so it can't close the outer <script>.
handout_doc_js = json.dumps(handout_doc).replace("</", "<\\/")

KIT_CSS = r"""<style>
.kit-tabs{display:flex;gap:2px;background:var(--blue-deep);padding:0 clamp(14px,4vw,40px);position:sticky;top:0;z-index:40;box-shadow:0 2px 8px rgba(0,0,0,.18)}
.kit-tab{appearance:none;border:0;background:transparent;color:#b9c4d6;font:600 14px/1 'Source Sans 3','Source Sans Pro',Arial,sans-serif;padding:13px 20px;cursor:pointer;border-bottom:3px solid transparent}
.kit-tab:hover{color:#fff}
.kit-tab.on{color:#fff;border-bottom-color:var(--orange)}
.kit-wrap{max-width:1060px;margin:0 auto;padding:26px 26px 60px}
.kit-wrap h1{font-family:'Montserrat',Arial,sans-serif;color:#13294B;font-size:26px;margin:0 0 4px}
.kit-wrap .lead{color:var(--storm-dark);margin:0 0 22px;font-size:15px}
.hint{display:block;font-size:12px;color:var(--storm-dark);margin-top:3px}
.ck{display:flex;align-items:center;gap:7px}
.row{display:flex;flex-wrap:wrap;gap:16px;align-items:center}
td.empty{text-align:center;color:var(--storm);padding:26px}
.kit-note{background:var(--warn-bg);border:1px solid var(--warn-line);color:var(--warn-text);border-radius:var(--radius-md);padding:11px 15px;font-size:13px;color:#7a5312;margin:0 0 22px}
.kadd-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px;background:#fff;border:1px solid var(--line);border-radius:var(--radius-dialog);padding:20px 22px}
.kadd-grid .f{display:flex;flex-direction:column;gap:4px}
.kadd-grid .f.full{grid-column:1 / -1}
.kadd-grid label{font-size:11px;font-weight:700;color:var(--storm-dark);text-transform:uppercase;letter-spacing:.03em}
.kadd-grid input,.kadd-grid select,.kadd-grid textarea{padding:8px 10px;border:1px solid var(--field);border-radius:var(--radius-md);font:inherit}
.kadd-grid textarea{resize:vertical;min-height:52px}
.kadd-grid .sec{grid-column:1 / -1;font-weight:700;color:#13294B;border-top:1px solid #eee;padding-top:12px;font-size:13px}
.kadd-grid .ck{flex-direction:row;align-items:center;gap:8px;font-weight:600;text-transform:none;color:var(--ink);font-size:14px}
.kadd-actions{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 8px;align-items:center}
.kstaged{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:var(--radius-dialog);overflow:hidden;margin-top:8px}
.kstaged th,.kstaged td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);font-size:var(--fs-table-cell)}
.kstaged th{background:#FAFBFC;font-size:var(--fs-table-head);text-transform:uppercase;color:var(--storm);letter-spacing:.05em}
.kstaged tr:last-child td{border-bottom:0}
.kstaged .svy{font-weight:700;font-size:11px;color:#fff;border-radius:var(--radius-xs);padding:2px 6px;background:#13294B}
.kx{border:1px solid var(--line);background:#fff;border-radius:var(--radius-sm);padding:3px 9px;cursor:pointer;font-size:12px}
.kcount{color:var(--storm-dark);font-size:13px}
.kb-flow{display:flex;flex-wrap:wrap;gap:10px;align-items:stretch;margin:8px 0 26px}
.kb-step{flex:1 1 190px;background:#fff;border:1px solid var(--line);border-top:4px solid #FF5F05;border-radius:var(--radius-lg);padding:14px 16px;position:relative}
.kb-step h3{margin:0 0 5px;font-family:'Montserrat',Arial,sans-serif;font-size:15px;color:#13294B}
.kb-step p{margin:0;font-size:13px;color:var(--storm-dark);line-height:1.45}
.kb-step .kb-n{position:absolute;top:-13px;left:14px;width:24px;height:24px;border-radius:50%;background:#13294B;color:#fff;font:700 13px/24px 'Montserrat',sans-serif;text-align:center}
.kb-arrow{display:flex;align-items:center;color:var(--il-altgeld);font-size:26px;font-weight:700}
@media(max-width:820px){.kb-arrow{transform:rotate(90deg)}.kadd-grid,.kb-flow{grid-template-columns:1fr}
  .kit-wrap{padding-left:16px;padding-right:16px}}
.kb-cards{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:6px}
.kb-card{background:#fff;border:1px solid var(--line);border-radius:var(--radius-dialog);padding:18px 20px}
.kb-card h3{margin:0 0 8px;font-family:'Montserrat',Arial,sans-serif;color:#13294B;font-size:15px}
.kb-card ul{margin:8px 0 0;padding-left:18px}.kb-card li{margin:4px 0;font-size:13px;color:var(--storm-dark)}
.kb-card p{font-size:13px;color:var(--storm-dark);line-height:1.5;margin:0 0 8px}
.kb-tag{display:inline-block;background:#eef2f7;color:#13294B;border-radius:var(--radius-sm);padding:1px 7px;font:600 12px/1.6 monospace}
@media(max-width:820px){.kb-cards{grid-template-columns:1fr}}
.tscroll{overflow-x:auto}
</style>"""
KIT_CSS = KIT_CSS.replace("<style>", "<style>" + ui_tokens.tokens_css(), 1)
KIT_CSS = KIT_CSS.replace("</style>", buttons_css() + ui_dialog.DIALOG_CSS + "</style>")

KIT_TABBAR = ('<div class="kit-tabs">'
              '<button class="kit-tab on" data-tab="explore">Explore the Tracker</button>'
              '<button class="kit-tab" data-tab="add">Add Data</button>'
              '<button class="kit-tab" data-tab="backend">How the Data Works</button>'
              '</div>')

# The Status list is fixed everywhere (Q-16), so the Kit bakes the Console's in.
STATUS_OPTIONS = "".join('<option>%s</option>' % s for s in pri_data.STATUSES)

KIT_ADD = """<div class="kit-wrap">
<h1>Add Data to the Tracker</h1>
<p class="lead">Fill this in for a project, grant, publication, program, or community-science effort.
Add as many as you like, then <b>Export CSV</b> and send the file to whoever manages the data. They
load it into the Data Console, which date-stamps it, sets the display timer, and figures out the districts.</p>
<div class="notice warn kit-note"><b>Nothing here changes the live tracker.</b> The form builds a clean spreadsheet to hand off.
For a mapped location, give <b>latitude &amp; longitude</b> (or a county) and the manager's tool assigns the
legislative districts automatically, so you do not have to look them up.</div>
<div class="kadd-grid">
  <div class="f"><label>Survey</label><select id="kadd_survey"><option>INHS</option><option>ISGS</option><option>ISWS</option><option>ISAS</option><option>ISTC</option></select></div>
  <div class="f"><label>Type</label><select id="kadd_type"><option>Program</option><option>Project</option><option>Facility</option><option>Grant</option><option>Publication</option><option>News</option><option>Community science</option></select></div>
  <div class="f full"><label>Title</label><input id="kadd_title" placeholder="e.g. Mahomet Aquifer water-quality study"></div>
  <div class="f full"><label>Summary</label><span class="hint">One line for the card.</span><textarea id="kadd_summary"></textarea></div>
  <div class="f full"><label>Description</label><span class="hint">The fuller text shown when someone opens the record.</span><textarea id="kadd_description"></textarea></div>
  <div class="f"><label>Lead / contact</label><input id="kadd_lead"></div>
  <div class="f"><label>Status</label><select id="kadd_status">__STATUS_OPTIONS__</select></div>
  <div class="f"><label>Funder / partners</label><input id="kadd_funder"></div>
  <div class="f"><label>Program area</label><input id="kadd_program"></div>
  <div class="f"><label>Topic</label><input id="kadd_topic"></div>
  <div class="f"><label>Link (URL)</label><input id="kadd_url"></div>
  <div class="f full"><label>Photo URL</label><span class="hint">Optional. Shows in the pop-up and on the handout.</span><input id="kadd_image"></div>
  <div class="sec">Where is it? (for the map)</div>
  <div class="f"><label>Scope</label><select id="kadd_scope"><option value="statewide">statewide (shows in every district)</option><option value="sited">sited (a specific place)</option><option value="regional">regional</option><option value="external">external (outside Illinois)</option></select></div>
  <div class="f"><label>Location text</label><input id="kadd_location" placeholder="Havana, Mason Co."></div>
  <div class="f"><label>Latitude</label><input id="kadd_latitude" placeholder="40.11"></div>
  <div class="f"><label>Longitude</label><input id="kadd_longitude" placeholder="-88.21"></div>
  <div class="f"><label>County</label><input id="kadd_county"></div>
  <div class="f"><label>Keywords (; separated)</label><input id="kadd_keywords"></div>
  <div class="f"><label>U.S. House district(s)</label><input id="kadd_us_house" placeholder="leave blank to auto-fill"></div>
  <div class="f"><label>Illinois Senate / Illinois House</label><input id="kadd_il_senate" placeholder="Senate"><input id="kadd_il_house" placeholder="House" style="margin-top:6px"></div>
  <div class="f full"><label>Notes (for the data manager)</label><input id="kadd_notes"></div>
  <div class="f full row"><label class="ck"><input type="checkbox" id="kadd_featured"> Feature this one</label>
    <label class="ck"><input type="checkbox" id="kadd_confirm"> District needs checking</label></div>
</div>
<div class="notice err" id="kadd_notice" role="alert" hidden></div>
<div class="kadd-actions">
  <button class="btn pri" id="kadd_add">Add to List</button>
  <button class="btn dk" id="kadd_export">Export CSV</button>
  <button class="btn gh" id="kadd_clear">Clear List</button>
  <span class="kcount" id="kadd_count"></span>
</div>
<div class="tscroll"><table class="kstaged"><thead><tr><th>Survey</th><th>Title</th><th>Type</th><th>Where</th><th></th></tr></thead><tbody id="kadd_rows"></tbody></table></div>
</div>"""
KIT_ADD = KIT_ADD.replace("__STATUS_OPTIONS__", STATUS_OPTIONS)

KIT_BACKEND = """<div class="kit-wrap">
<h1>How the Data Works</h1>
<p class="lead">The tracker is driven by one master list of activities. The path a new entry takes is below,
with what it takes to run this live for everyone.</p>
<div class="kb-flow">
  <div class="kb-step"><span class="kb-n">1</span><h3>You collate</h3><p>Use the <b>Add Data</b> tab to describe each activity and export a CSV. That task belongs to the working group.</p></div>
  <div class="kb-arrow">&rarr;</div>
  <div class="kb-step"><span class="kb-n">2</span><h3>Data Console</h3><p>The data manager loads the CSV into a small tool that <b>date-stamps</b> each record, sets its <b>display timer</b>, and <b>auto-assigns districts</b> from lat/long.</p></div>
  <div class="kb-arrow">&rarr;</div>
  <div class="kb-step"><span class="kb-n">3</span><h3>Master database</h3><p>Everything is stored in one place and <b>never deleted</b>. Older items are hidden when their timer runs out.</p></div>
  <div class="kb-arrow">&rarr;</div>
  <div class="kb-step"><span class="kb-n">4</span><h3>The website</h3><p>The public tracker and handouts show <b>only the current records</b> for each legislative district.</p></div>
</div>
<div class="kb-cards">
  <div class="kb-card"><h3>The display timer</h3>
    <p>Every record has a <span class="kb-tag">show&nbsp;until</span> date. While that date is in the future the record shows on the site; once it passes, the record drops off the site and stays in the database.</p>
    <ul><li><b>Blank = evergreen:</b> shows until someone retires it (good for long-running programs).</li>
    <li><b>A date:</b> the item ages off on its own (good for news, one-off projects, grants).</li>
    <li><b>Retire:</b> hides something immediately without deleting it.</li></ul>
    <p>So the site always shows <b>current</b> work, and re-adding a record refreshes its clock.</p></div>
  <div class="kb-card"><h3>Putting it online (the backend)</h3>
    <p>The tracker runs on <b>PHP and PostgreSQL</b>, hosted on the campus Radiant service.</p>
    <ul><li>Create the PostgreSQL database and apply the schema from <span class="kb-tag">migrations/</span>.</li>
    <li>Upload the <span class="kb-tag">php/</span> folder and point the page at <span class="kb-tag">php/data.php</span>.</li>
    <li>The display timer then runs <b>live</b>, and everyone shares one database.</li>
    <li>Data managers ingest on the host through an authenticated page, with no files to email around.</li></ul>
    <p>Until then, the local Data Console and this Kit do the same job on one computer.</p></div>
</div>
</div>"""

KIT_JS = r"""<script>
(function(){
var INTAKE_COLS=__INTAKE_COLS__;
var HANDOUT_DOC=__HANDOUT_DOC__;
// --- open the fully-functional handout in a new tab, for the current selection ---
function openKitHandout(){
  var q={c:(typeof ck==='function'?ck():'us_house'),
         n:(document.getElementById('district')||{}).value||'13',
         survey:(document.getElementById('survey')||{}).value||'all'};
  var doc=HANDOUT_DOC.replace('__PRIQMARK__',JSON.stringify(q));
  var w=window.open('','_blank');
  if(!w){PriDialog.notify({title:'Pop-up Blocked',message:'The browser stopped the handout from opening. Allow pop-ups for this page, then try again.'});return;}
  w.document.open();w.document.write(doc);w.document.close();
}
// APP already wired #printBtn to a (missing) file; swap the node to drop that handler.
var pb=document.getElementById('printBtn');
if(pb){var nb=pb.cloneNode(true);nb.textContent='Open one-page handout';pb.parentNode.replaceChild(nb,pb);nb.addEventListener('click',openKitHandout);}
// --- tabs ---
var panels={explore:'kit-explore',add:'kit-add',backend:'kit-backend'};
document.querySelectorAll('.kit-tab').forEach(function(t){t.addEventListener('click',function(){
  document.querySelectorAll('.kit-tab').forEach(function(x){x.classList.remove('on')});t.classList.add('on');
  var key=t.getAttribute('data-tab');for(var k in panels){document.getElementById(panels[k]).hidden=(k!==key);}
  window.scrollTo(0,0);
});});
// --- add-data staging + CSV export (persists in this browser) ---
var KEY='pri_kit_rows_v1';
var rows=[];try{rows=JSON.parse(localStorage.getItem(KEY)||'[]')||[];}catch(e){rows=[];}
function val(id){var e=document.getElementById(id);return e?String(e.value||'').trim():'';}
function chk(id){var e=document.getElementById(id);return e&&e.checked;}
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
function render(){
  var tb=document.getElementById('kadd_rows');if(!tb)return;
  tb.innerHTML=rows.map(function(r,i){
    var where=r.scope==='statewide'?'statewide':(r.scope==='external'?'&mdash;':([r.us_house?'US '+r.us_house:'',r.location_text].filter(Boolean).join(' &middot; ')||r.county||'&mdash;'));
    return '<tr><td><span class="svy">'+esc(r.survey)+'</span></td><td><b>'+esc(r.title)+'</b></td><td>'+esc(r.type)+'</td><td>'+where+'</td><td><button class="kx" data-i="'+i+'">Remove</button></td></tr>';
  }).join('')||'<tr><td colspan="5" class="empty">No entries yet. Fill the form and select <b>Add to List</b>.</td></tr>';
  var c=document.getElementById('kadd_count');if(c)c.textContent=rows.length?(rows.length+' entr'+(rows.length===1?'y':'ies')+' ready to export'):'';
  try{localStorage.setItem(KEY,JSON.stringify(rows));}catch(e){}
}
function collect(){
  return {survey:val('kadd_survey'),title:val('kadd_title'),type:val('kadd_type'),topic:val('kadd_topic'),
    summary:val('kadd_summary'),description:val('kadd_description'),lead:val('kadd_lead'),program:val('kadd_program'),
    funder:val('kadd_funder'),partners:'',status:val('kadd_status'),start_year:'',end_year:'',url:val('kadd_url'),
    scope:val('kadd_scope'),latitude:val('kadd_latitude'),longitude:val('kadd_longitude'),county:val('kadd_county'),
    location_text:val('kadd_location'),us_house:val('kadd_us_house'),il_senate:val('kadd_il_senate'),
    il_house:val('kadd_il_house'),featured:chk('kadd_featured')?'yes':'no',confirm:chk('kadd_confirm')?'yes':'no',
    keywords:val('kadd_keywords'),notes:val('kadd_notes'),image:val('kadd_image'),activity_id:''};
}
function kNote(msg){var n=document.getElementById('kadd_notice');
  if(!n)return;
  if(msg){n.textContent=msg;n.hidden=false;}else{n.textContent='';n.hidden=true;}}
var addB=document.getElementById('kadd_add');
if(addB)addB.addEventListener('click',function(){
  var r=collect();
  if(!r.title||!r.summary){kNote('Fill in at least a title and a summary before adding the entry.');return;}
  kNote('');
  rows.push(r);render();
  ['kadd_title','kadd_summary','kadd_description','kadd_lead','kadd_funder','kadd_program','kadd_topic','kadd_url','kadd_image','kadd_location','kadd_latitude','kadd_longitude','kadd_county','kadd_keywords','kadd_notes','kadd_us_house','kadd_il_senate','kadd_il_house'].forEach(function(id){var e=document.getElementById(id);if(e)e.value='';});
  var f=document.getElementById('kadd_featured'),cf=document.getElementById('kadd_confirm');if(f)f.checked=false;if(cf)cf.checked=false;
  document.getElementById('kadd_title').focus();
});
document.getElementById('kadd_rows').addEventListener('click',function(e){
  var b=e.target.closest('[data-i]');if(!b)return;rows.splice(+b.getAttribute('data-i'),1);render();
});
var clr=document.getElementById('kadd_clear');
if(clr)clr.addEventListener('click',function(){
  if(!rows.length)return;
  PriDialog.confirm({title:'Clear the List',
    message:'Remove all '+rows.length+' entries from this list? Nothing has been sent anywhere, so this only clears what you typed.',
    okLabel:'Clear List',danger:true}).then(function(ok){if(ok){rows=[];kNote('');render();}});
});
function csvCell(v){return '"'+String(v==null?'':v).replace(/"/g,'""')+'"';}
var exp=document.getElementById('kadd_export');
if(exp)exp.addEventListener('click',function(){
  if(!rows.length){kNote('Add at least one entry to the list before exporting.');return;}
  kNote('');
  var lines=[INTAKE_COLS.map(csvCell).join(',')];
  rows.forEach(function(r){lines.push(INTAKE_COLS.map(function(c){return csvCell(r[c]);}).join(','));});
  var blob=new Blob([lines.join('\r\n')],{type:'text/csv'});
  var d=new Date().toISOString().slice(0,10);
  var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='pri-tracker-data-'+d+'.csv';
  document.body.appendChild(a);a.click();setTimeout(function(){a.remove();},100);
});
render();
})();
</script>"""
KIT_JS = KIT_JS.replace("__INTAKE_COLS__", json.dumps(INTAKE_COLS)).replace("__HANDOUT_DOC__", handout_doc_js)
# The Kit is the only generated page that asks the reader a question, so it carries
# PriDialog (PDT-37). Prepended, because the handlers above call it.
KIT_JS = KIT_JS.replace("<script>", "<script>" + ui_dialog.DIALOG_JS, 1)

kit_html = ("<!doctype html><html lang=\"en\"><head>" + HEAD_ASSETS_INLINE + GF + MYCSS + KIT_CSS + "</head><body>"
            + PRI_HEADER + KIT_TABBAR
            + '<div id="kit-explore" class="kit-panel">' + MARKUP + '</div>'
            + '<div id="kit-add" class="kit-panel" hidden>' + KIT_ADD + '</div>'
            + '<div id="kit-backend" class="kit-panel" hidden>' + KIT_BACKEND + '</div>'
            + PRI_FOOTER + "\n" + PRI_SCRIPTS + "\n"
            + '<script>' + DATA_JS + '</script>' + APP + COOKIE_KILL + KIT_JS + "</body></html>")
# One product name, one suffix per page (Q-17, PDT-21).
kit_html = kit_html.replace("<title>PRI District Tracker</title>",
                            "<title>PRI District Tracker: Working Group Kit</title>", 1)
with open(os.path.join(PROJ, "PRI-Tracker-Kit.html"), "w", encoding="utf-8") as f:
    f.write(kit_html)

print("Chambers:", {k: len(v) for k, v in GEO["chambers"].items()})
print("Reps:", {k: len(v) for k, v in REPS.items()})
print("Freshness: %d shown / %d hidden (expired show_until) of %d total on %s"
      % (len(ACT), _HIDDEN, len(_ACT_ALL), pri_data.today_iso()))
print("Wrote:", OUT, "(%.0f KB)" % (os.path.getsize(OUT) / 1024))
# The hosted back office links these; the Console gets them stamped in (Q-19).
_fonts = ui_fonts.write_fonts_css()
print("Wrote:", _fonts, "(%.0f KB, campus faces for the back office)"
      % (os.path.getsize(_fonts) / 1024))
_kit = os.path.join(PROJ, "PRI-Tracker-Kit.html")
print("Wrote:", _kit, "(%.0f KB, self-contained distributable)" % (os.path.getsize(_kit) / 1024))
