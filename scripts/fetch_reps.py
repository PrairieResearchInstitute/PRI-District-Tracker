"""Fetch current representatives for every Illinois district and write data/reps.json.

Federal (U.S. House + Senate) from the unitedstates/congress-legislators dataset;
Illinois State Senate + House from Open States bulk data. Re-downloads each run so
the roster is re-verified on every build; falls back to cached files if offline.
Pure standard library. Called automatically by build_site.py.
"""
import json, csv, os, re, urllib.request

# Relative to this file, not to whoever's desktop. The absolute path that was
# here pointed at a folder that no longer exists, so the script could not run.
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FED_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
ST_URL = "https://data.openstates.org/people/current/il.csv"
FED_F = os.path.join(DATA, "legislators-current.json")
ST_F = os.path.join(DATA, "il_legislators.csv")


def dl(url, path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (PRI District Tracker build)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print("  download failed for %s (%s); using cached copy if present" % (url.rsplit('/', 1)[-1], e))
        return os.path.exists(path)


reps = {"us_house": {}, "us_senate": {}, "il_senate": {}, "il_house": {}}

# ---- Federal ----
if dl(FED_URL, FED_F):
    for p in json.load(open(FED_F, encoding="utf-8")):
        t = p["terms"][-1]
        if t.get("state") != "IL":
            continue
        nm = p["name"].get("official_full") or " ".join(filter(None, [p["name"].get("first"), p["name"].get("last")]))
        party = {"Democrat": "D", "Republican": "R", "Independent": "I"}.get(t.get("party"), "")
        url = t.get("url", "")
        if t.get("type") == "rep":
            reps["us_house"][str(t.get("district"))] = {"name": "Rep. " + nm, "party": party, "url": url}
        elif t.get("type") == "sen":
            key = "durbin" if "Durbin" in nm else ("duckworth" if "Duckworth" in nm else nm.split()[-1].lower())
            reps["us_senate"][key] = {"name": "Sen. " + nm, "party": party, "url": url}


# ---- Illinois state ----
def pick_url(links, chamber):
    parts = [x.strip() for x in (links or "").split(";") if x.strip()]
    seg = "Senate" if chamber == "upper" else "House"
    for x in parts:
        if re.search(r"ilga\.gov/%s/Members/Details/\d+" % seg, x, re.I):
            return x
    for x in parts:
        if re.search(r"ilga\.gov/[A-Za-z]+/Members/Details/\d+", x, re.I):
            return x
    for x in parts:
        if not re.search(r"ballotpedia|wikipedia|votesmart|linkedin|ilga\.gov|cdn\.ilga|wikidata", x, re.I):
            return x
    for x in parts:
        if "ilga.gov" in x.lower():
            return x
    return parts[0] if parts else ""


def strip_columns(path, drop):
    """Remove columns from a downloaded CSV before it is cached.

    Open States publishes a wide roster. This tracker reads five fields -
    name, chamber, district, party and links - so everything else is carried
    for nothing. birth_date is dropped here rather than from the checked-in
    file, because the file is re-downloaded on every run and a one-off edit
    would simply come back.
    """
    try:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        if not rows:
            return
        header = rows[0]
        keep = [i for i, name in enumerate(header) if name.strip() not in drop]
        if len(keep) == len(header):
            return
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for r in rows:
                w.writerow([r[i] if i < len(r) else "" for i in keep])
    except Exception as e:
        print("  could not strip columns from %s (%s)" % (path, e))


if dl(ST_URL, ST_F):
    strip_columns(ST_F, {"birth_date"})
    with open(ST_F, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ch = (row.get("current_chamber") or "").strip()
            d = (row.get("current_district") or "").strip()
            if not d or ch not in ("upper", "lower"):
                continue
            party = {"Democratic": "D", "Republican": "R"}.get(row.get("current_party", ""), "")
            prefix = "Sen. " if ch == "upper" else "Rep. "
            entry = {"name": prefix + (row.get("name") or "").strip(), "party": party, "url": pick_url(row.get("links", ""), ch)}
            (reps["il_senate"] if ch == "upper" else reps["il_house"])[d] = entry

with open(os.path.join(DATA, "reps.json"), "w", encoding="utf-8") as f:
    json.dump(reps, f, ensure_ascii=False)

print("reps refreshed: us_house=%d us_senate=%d il_senate=%d il_house=%d"
      % (len(reps["us_house"]), len(reps["us_senate"]), len(reps["il_senate"]), len(reps["il_house"])))
FULL = {"us_house": 17, "us_senate": 2, "il_senate": 59, "il_house": 118}
print("coverage:", {c: str(len(reps[c])) + "/" + str(FULL[c]) for c in reps})
