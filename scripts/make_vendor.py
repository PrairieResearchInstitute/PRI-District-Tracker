"""Build a fully OFFLINE vendor bundle so the app renders with no internet connection.

The site's chrome (the official Illinois Web Toolkit banner/footer) and its fonts normally
load from CDNs. This script downloads them ONCE (while online) and rewrites every remaining
network reference to an inline `data:` URI, producing three self-contained files in
assets/vendor/:

    toolkit.local.css   fonts (Montserrat + Source Sans, base64) + illinois.css (font rules
                        localised) + toolkit.css (dead SVG url()s neutralised)
    child-theme.local.css   PRI theme CSS with all external refs stripped
    toolkit.local.js    toolkit.js with its footer.json fetch and search icon inlined as data:

build_site.py then links these for index/handout and inlines them for the single-file Kit,
so nothing is fetched at render time. Re-run this whenever the toolkit is updated.

Pure stdlib. Run (needs internet): py scripts/make_vendor.py
"""
import os, re, base64, urllib.request, urllib.parse

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(PROJ, "assets", "vendor")
os.makedirs(VENDOR, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
# 1x1 transparent PNG - what stripped-out external images resolve to (valid, no network).
BLANK = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0"
         "lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
EMPTY_SVG = "data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'/%3E"


def get(url, referer=None, binary=False):
    hdr = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        hdr["Referer"] = referer
    with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=45) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


# ---------------------------------------------------------------- fonts (Google, OFL)
def font_face_css(family, weights, out_family=None):
    """Fetch a Google Fonts css2 sheet, keep only the `latin` subset blocks, and inline
    each woff2 as base64. Optionally re-label the family (e.g. Source Sans 3 -> Pro)."""
    out_family = out_family or family
    css = get("https://fonts.googleapis.com/css2?family=%s:wght@%s&display=swap"
              % (family.replace(" ", "+"), ";".join(weights)),
              referer="https://www.prairie.illinois.edu/")
    blocks = re.findall(r"/\*\s*latin\s*\*/\s*(@font-face\s*\{[^}]*\})", css)
    out = []
    for b in blocks:
        m = re.search(r"src:\s*url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)", b)
        w = re.search(r"font-weight:\s*(\d+)", b)
        if not m:
            continue
        data = base64.b64encode(get(m.group(1), binary=True)).decode("ascii")
        out.append("@font-face{font-family:'%s';font-style:normal;font-weight:%s;font-display:swap;"
                   "src:url(data:font/woff2;base64,%s) format('woff2')}"
                   % (out_family, (w.group(1) if w else "400"), data))
    return "".join(out)


def build_fonts():
    print("  fonts: Montserrat + Source Sans (latin, base64)")
    css = font_face_css("Montserrat", ["400", "600", "700", "800"])
    ss = font_face_css("Source Sans 3", ["400", "600", "700"])
    ss_pro = font_face_css("Source Sans 3", ["400", "600", "700"], out_family="Source Sans Pro")
    return css + ss + ss_pro


# ---------------------------------------------------------------- css/js localisation
_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon"}


def _data_uri(url):
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    if ext == ".svg":
        return "data:image/svg+xml," + urllib.parse.quote(get(url, referer="https://www.prairie.illinois.edu/"), safe="")
    raw = get(url, referer="https://www.prairie.illinois.edu/", binary=True)
    return "data:%s;base64,%s" % (_MIME.get(ext, "application/octet-stream"), base64.b64encode(raw).decode("ascii"))


def localize_html_assets(html):
    """Inline every external image referenced by src=... or url(...) as a data: URI, so a
    cloned HTML fragment (e.g. the PRI footer's social icons) needs no network."""
    pat = r'(src=|url\()(["\']?)(https?://[^"\')\s]+?\.(?:svg|png|jpe?g|gif|webp|ico))\2'

    def repl(m):
        try:
            return m.group(1) + m.group(2) + _data_uri(m.group(3)) + m.group(2)
        except Exception as e:
            print("  WARN could not inline", m.group(3), e)
            return m.group(0)
    return re.sub(pat, repl, html, flags=re.I)


def strip_external(css):
    """Remove @font-face and @import, and point any remaining external url() at a blank."""
    css = re.sub(r"@font-face\s*\{[^}]*\}", "", css)
    css = re.sub(r"@import[^;]+;", "", css)
    css = re.sub(r"url\(\s*['\"]?(?:https?:)?//[^)]*\)", "url(%s)" % BLANK, css)
    return css


def main():
    print("Downloading toolkit + brand assets...")
    toolkit_css = get("https://cdn.toolkit.illinois.edu/3/toolkit.css")
    toolkit_js = get("https://cdn.toolkit.illinois.edu/3/toolkit.js")
    illinois_css = get("https://cdn.brand.illinois.edu/illinois.css")
    child_css = get("https://www.prairie.illinois.edu/wp-content/themes/pri-flagship-theme/css/child-theme.min.css",
                    referer="https://www.prairie.illinois.edu/")
    footer_json = get("https://cdn.brand.illinois.edu/data/footer.json", binary=True)
    search_png = get("https://cdn.brand.illinois.edu/icons/solid/orange/search.png", binary=True)

    fonts_css = build_fonts()

    # illinois.css: keep everything EXCEPT its external font machinery (we supply fonts above)
    illinois_local = strip_external(illinois_css)

    # toolkit.css: drop its external illinois.css @import; neutralise the two legacy-header
    # SVG url()s (the component renders its marks from toolkit.js, not these).
    tk_css = re.sub(r"@import[^;]+;", "", toolkit_css)   # bundled inline now -> no imports
    # The web component (once it upgrades) draws its own block-I/wordmark; these CSS-background
    # url()s are the un-upgraded fallback only, so point them at a blank to avoid a 404.
    tk_css = tk_css.replace("../svg/block-i.svg", EMPTY_SVG).replace("../svg/wordmark.svg", EMPTY_SVG)
    tk_css = re.sub(r"url\(\s*['\"]?https?://cdn\.brand\.illinois\.edu[^)]*\)", "url(%s)" % BLANK, tk_css)

    toolkit_local_css = ("/* OFFLINE bundle built by make_vendor.py - do not edit by hand */\n"
                         + fonts_css + "\n" + illinois_local + "\n" + tk_css)

    child_local = "/* OFFLINE - external refs stripped by make_vendor.py */\n" + strip_external(child_css)

    # toolkit.js: inline the one runtime fetch (footer.json) and the search icon as data: URIs.
    tk_js = toolkit_js.replace(
        "https://cdn.brand.illinois.edu/data/footer.json",
        "data:application/json;base64," + base64.b64encode(footer_json).decode("ascii"))
    tk_js = tk_js.replace(
        "//cdn.brand.illinois.edu/icons/solid/orange/search.png",
        "data:image/png;base64," + base64.b64encode(search_png).decode("ascii"))
    # Neutralise the OneTrust cookie loader so nothing is fetched offline (the banner is
    # removed anyway by COOKIE_KILL); an inert data: script loads instantly with no network.
    tk_js = re.sub(r"https://onetrust\.techservices\.illinois\.edu/[^\s\"')]*", "data:text/javascript,", tk_js)

    # PRI footer clone: inline its social-icon images so it renders offline.
    footer_src = os.path.join(PROJ, "data", "pri_footer.html")
    footer_local = ""
    if os.path.exists(footer_src):
        with open(footer_src, encoding="utf-8") as f:
            footer_local = localize_html_assets(f.read())

    out = {
        "toolkit.local.css": toolkit_local_css,
        "child-theme.local.css": child_local,
        "toolkit.local.js": tk_js,
    }
    if footer_local:
        out["pri_footer.local.html"] = footer_local
    for name, content in out.items():
        with open(os.path.join(VENDOR, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("  wrote assets/vendor/%s (%.0f KB)" % (name, len(content.encode("utf-8")) / 1024))

    # Sanity: no external render-time hosts should remain in the CSS/JS we emit.
    bad = []
    for name in out:
        txt = out[name]
        for host in ["cdn.toolkit.illinois.edu", "cdn.brand.illinois.edu", "fonts.googleapis.com", "fonts.gstatic.com", "onetrust.techservices.illinois.edu"]:
            if host in txt:
                bad.append("%s still references %s (%d)" % (name, host, txt.count(host)))
    print("OFFLINE CHECK:", "clean - no external render hosts remain" if not bad else " | ".join(bad))


if __name__ == "__main__":
    main()
