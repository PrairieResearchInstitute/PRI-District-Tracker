"""Seed a public database of record for a clean clone (the GitHub Actions checks).

data/activities.json is git-ignored because it holds institutional data (D-021), so a
fresh clone has none and scripts/build_site.py cannot start. This script writes a
database built only from the example rows of the committed intake template
(templates/activities_template.csv), or from one fictitious placeholder record when the
template holds only its header (the public PRI copy), imported through the Data
Console's own CSV path (admin_server.import_csv), so the build and the tests run on
public material only.

It never touches an existing file: on the owner's computer the real database is always
present and the script exits without writing.

Run: py scripts/seed_ci_data.py
"""
import csv, io, json, os, sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(SCRIPTS)
DB = os.path.join(PROJ, "data", "activities.json")
TEMPLATE = os.path.join(PROJ, "templates", "activities_template.csv")
SEED_NOTE = "Public example row from templates/activities_template.csv (CI seed)."


# The public PRI copy ships the template cut to its header row (its example rows name
# real programs and sponsors). The seed then falls back to this one fictitious record,
# because an empty database is not a valid seed: scripts/backup_data.py refuses to
# verify one (an empty file is treated as a damaged one) and the concurrency tests edit
# its first record.
PLACEHOLDER = {
    "survey": "INHS", "title": "CI placeholder activity", "type": "Program",
    "topic": "Water resources", "summary": "Fictitious record for the automated checks.",
    "description": "Fictitious record written by scripts/seed_ci_data.py; it names no real work.",
    "status": "Ongoing", "start_year": "2020", "scope": "statewide",
    "location_text": "Statewide", "activity_id": "ci-placeholder",
}


def template_rows_as_csv():
    """The template rows with their EXAMPLE note replaced, because import_csv skips
    rows marked EXAMPLE (a collator is meant to delete them). A header-only template
    yields the PLACEHOLDER record instead."""
    with open(TEMPLATE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]
    if not rows:
        rows = [{k: PLACEHOLDER.get(k, "") for k in fields}]
    for r in rows:
        r["notes"] = SEED_NOTE
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return out.getvalue(), sorted({r["survey"] for r in rows if r.get("survey")})


def main():
    if os.path.exists(DB):
        print("seed skipped: data/activities.json exists (the real database stays untouched)")
        return 0
    text, surveys = template_rows_as_csv()
    empty = {
        "generated": "",
        "source": "Seed written by scripts/seed_ci_data.py from templates/activities_template.csv.",
        "note": "No institutional data. The real database of record stays on the owner's disk.",
        "surveys": surveys,
        "activities": [],
    }
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with open(DB, "x", encoding="utf-8") as f:   # "x": fail rather than overwrite
        json.dump(empty, f, indent=2)
        f.write("\n")
    sys.path.insert(0, SCRIPTS)
    import admin_server
    res = admin_server.import_csv(text)
    if res["errors"] or not res["added"]:
        print("seed FAILED:", res)
        return 1
    print("seeded data/activities.json with %d public example activities" % res["added"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
