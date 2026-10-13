"""Render the real District 13 inset from current Census geometry into preview.html.
Pure standard library. Run with:  py scripts/make_inset.py
"""
import json, math, os

# Derived from this file's location (never hardcode): the script works from whichever
# copy of the project it is run in. Matches build_site.py / make_templates.py / pri_data.py.
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "data", "il_congress_current.geojson")

with open(SRC, encoding="utf-8") as f:
    gj = json.load(f)


def rings(geom):
    t = geom["type"]
    c = geom["coordinates"]
    out = []
    if t == "Polygon":
        out = [r for r in c]
    elif t == "MultiPolygon":
        for poly in c:
            out.extend(poly)
    return out


# Keep only the 17 real numbered districts (drop "Congressional Districts not defined")
feats = {}
for ft in gj["features"]:
    bn = str(ft["properties"].get("BASENAME", "")).strip()
    if bn.isdigit():
        feats[int(bn)] = ft["geometry"]

nums = sorted(feats)
all_rings = [(n, rings(feats[n])) for n in nums]


def bounds(geoms_rings):
    minx = miny = 1e9
    maxx = maxy = -1e9
    for _, rs in geoms_rings:
        for r in rs:
            for x, y in r:
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
    return minx, miny, maxx, maxy


S = bounds(all_rings)
lat0 = (S[1] + S[3]) / 2.0
K = math.cos(math.radians(lat0))  # equirectangular longitude correction


def make_proj(b, width, pad):
    minx, miny, maxx, maxy = b
    gw = (maxx - minx) * K
    gh = (maxy - miny)
    scale = (width - 2 * pad) / gw
    height = gh * scale + 2 * pad

    def tx(x, y):
        return ((x - minx) * K * scale + pad, height - ((y - miny) * scale + pad))

    return tx, width, height


def to_path(rs, tx, nd=1):
    parts = []
    for r in rs:
        seg = []
        for x, y in r:
            px, py = tx(x, y)
            seg.append("%.*f,%.*f" % (nd, px, nd, py))
        if seg:
            parts.append("M" + "L".join(seg) + "Z")
    return "".join(parts)


# Locator: whole state, district 13 highlighted
txL, wL, hL = make_proj(S, 170, 5)
loc = []
for n, rs in all_rings:
    fill = "#FF5F05" if n == 13 else "#DADCDC"
    loc.append('<path d="%s" fill="%s" stroke="#FFFFFF" stroke-width="0.4"/>' % (to_path(rs, txL, 1), fill))
locator_svg = ('<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" width="100%%" style="display:block">%s</svg>'
               % (round(wL), round(hL), "".join(loc)))

# Zoom: district 13 alone, to its own bounds
rs13 = rings(feats[13])
b13 = bounds([(13, rs13)])
txZ, wZ, hZ = make_proj(b13, 320, 12)
zoom_svg = ('<svg viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg" width="100%%" style="display:block">'
            '<path d="%s" fill="#FF5F05" stroke="#13294B" stroke-width="1.4"/></svg>'
            % (round(wZ), round(hZ), to_path(rs13, txZ, 1)))

CSS = """
<style>
*{box-sizing:border-box}
body{margin:0;font-family:'Source Sans 3','Source Sans Pro',Arial,sans-serif;color:#13294B;background:#f4f4f3}
.bar{background:#13294B;height:8px}
.head{background:#fff;border-bottom:3px solid #FF5F05;padding:16px 28px}
.wordmark{font-family:'Montserrat','Arial Black',sans-serif;font-weight:700;font-size:20px;color:#13294B;margin:0}
.tag{font-size:13px;color:#707372;margin:2px 0 0}
.wrap{max-width:980px;margin:26px auto;padding:0 28px}
.sheet{display:flex;gap:30px;align-items:flex-start}
.main{flex:1}
.main h2{font-family:'Montserrat','Arial Black',sans-serif;font-weight:700;color:#13294B;font-size:27px;margin:0 0 4px}
.rep{color:#707372;margin:0 0 16px;font-size:15px}
.main p{color:#333;max-width:48ch;line-height:1.6}
.inset{flex:0 0 300px;border:1px solid #e3e3e2;border-radius:10px;padding:16px;background:#fff}
.inset h3{font-family:'Montserrat',sans-serif;font-weight:600;font-size:14px;margin:0 0 10px;color:#13294B}
.loc{width:118px;margin:14px auto 0}
.loc-cap{text-align:center;font-size:11px;color:#707372;margin-top:5px}
.note{background:#fff;border:1px solid #e3e3e2;border-left:4px solid #FF5F05;border-radius:0 8px 8px 0;padding:14px 18px;margin-top:24px;font-size:14px;color:#333;line-height:1.6}
</style>
"""

html = "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
html += "<meta name='viewport' content='width=device-width,initial-scale=1'><title>District map preview</title>"
html += "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
html += "<link href='https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Source+Sans+3:wght@400;600&display=swap' rel='stylesheet'>"
html += CSS + "</head><body>"
html += "<div class='bar'></div>"
html += "<div class='head'><p class='wordmark'>PRI Project District Tracker</p><p class='tag'>What the Prairie Research Institute does in your legislative district</p></div>"
html += "<div class='wrap'><div class='sheet'>"
html += "<div class='main'><h2>Illinois 13th Congressional District</h2><p class='rep'>119th Congress &middot; map placement preview</p>"
html += "<p>This left column will hold PRI project cards grouped by survey. The map at the upper right is the <strong>real District 13 boundary</strong> from current U.S. Census data, drawn in Illini orange and blue.</p></div>"
html += "<div class='inset'><h3>13th Congressional District</h3>" + zoom_svg
html += "<div class='loc'>" + locator_svg + "</div><div class='loc-cap'>Where it sits in Illinois</div></div>"
html += "</div>"
html += "<div class='note'><strong>Map check:</strong> accurate Illinois shape, the district zoomed in, inset in the upper right, Illini orange/blue. If this is right, I'll build the full page and load the other chambers.</div>"
html += "</div></body></html>"

OUT = os.path.join(PROJ, "reference", "preview.html")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print("Districts found:", nums)
print("State bounds lon/lat:", [round(v, 3) for v in S])
print("Locator viewBox:", round(wL), "x", round(hL))
print("Zoom viewBox:", round(wZ), "x", round(hZ))
sx, sy = txZ(*rs13[0][0])
print("Zoom first projected point:", round(sx, 1), round(sy, 1))
print("Wrote:", OUT)
