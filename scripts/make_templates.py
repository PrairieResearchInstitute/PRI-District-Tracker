"""Generate the staff intake templates (activities + awards), the controlled-vocabulary
reference, and a fill-in guide. Every categorical column has a canonical value list so
sorting/queries stay clean; activities and awards both carry descriptive text.
Pure stdlib. Run: py scripts/make_templates.py
"""
import csv, os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "templates")
os.makedirs(OUT, exist_ok=True)

# ---- controlled vocabularies (single source of truth) ----
SURVEYS = ["INHS", "ISGS", "ISWS", "ISAS", "ISTC"]
TYPES = ["Program", "Project", "Facility", "Grant", "Publication", "News", "Community science"]
SCOPES = ["statewide", "sited", "regional", "external"]
ACT_STATUS = ["Active", "Ongoing", "Completed", "Planned", "Published"]
AWD_STATUS = ["Active", "Completed", "Pending"]
TOPICS = ["Biodiversity & wildlife", "Fisheries & aquatic life", "Water resources",
          "Plants & vegetation", "Insects & pollinators", "Wildlife disease & health",
          "Geology & minerals", "Climate & sustainability", "Cultural & archaeological",
          "Collections & data", "Monitoring & compliance", "Outreach & community science"]
FUNDERS = ["IDNR", "IDOT", "Illinois Tollway (ISTHA)", "IEPA", "Illinois Dept. of Agriculture",
           "Illinois Dept. of Public Health", "USFWS", "USGS", "USACE", "USDA", "USDA APHIS",
           "U.S. EPA", "NSF", "NOAA", "U.S. DOE", "The Nature Conservancy",
           "Illinois Audubon Society", "Illinois Native Plant Society", "University of Illinois",
           "Other (name it in notes)"]
YESNO = ["yes", "no"]
COUNTIES = ["Adams", "Alexander", "Bond", "Boone", "Brown", "Bureau", "Calhoun", "Carroll", "Cass",
            "Champaign", "Christian", "Clark", "Clay", "Clinton", "Coles", "Cook", "Crawford",
            "Cumberland", "DeKalb", "De Witt", "Douglas", "DuPage", "Edgar", "Edwards", "Effingham",
            "Fayette", "Ford", "Franklin", "Fulton", "Gallatin", "Greene", "Grundy", "Hamilton",
            "Hancock", "Hardin", "Henderson", "Henry", "Iroquois", "Jackson", "Jasper", "Jefferson",
            "Jersey", "Jo Daviess", "Johnson", "Kane", "Kankakee", "Kendall", "Knox", "Lake",
            "LaSalle", "Lawrence", "Lee", "Livingston", "Logan", "Macon", "Macoupin", "Madison",
            "Marion", "Marshall", "Mason", "Massac", "McDonough", "McHenry", "McLean", "Menard",
            "Mercer", "Monroe", "Montgomery", "Morgan", "Moultrie", "Ogle", "Peoria", "Perry",
            "Piatt", "Pike", "Pope", "Pulaski", "Putnam", "Randolph", "Richland", "Rock Island",
            "Saline", "Sangamon", "Schuyler", "Scott", "Shelby", "St. Clair", "Stark", "Stephenson",
            "Tazewell", "Union", "Vermilion", "Wabash", "Warren", "Washington", "Wayne", "White",
            "Whiteside", "Will", "Williamson", "Winnebago", "Woodford"]

ACT_HEADER = ["survey", "title", "type", "topic", "summary", "description", "lead", "program",
              "funder", "partners", "status", "start_year", "end_year", "url", "scope",
              "latitude", "longitude", "county", "location_text", "us_house", "il_senate",
              "il_house", "featured", "confirm", "keywords", "notes", "activity_id"]

ACT_ROWS = [
    ["INHS", "Critical Trends Assessment Program (CTAP)", "Program", "Monitoring & compliance",
     "Statewide five-year-rotation monitoring of forest, grassland, stream, and wetland condition.",
     "Provides Illinois' baseline on ecosystem health: randomized plots resurveyed on a five-year cycle, tracking plant, bird, and arthropod communities to detect long-term change and guide land-management and policy decisions.",
     "INHS botany/zoology", "Critical Trends Assessment", "IDNR", "", "Ongoing", "1997", "",
     "https://ctap.inhs.illinois.edu", "statewide", "", "", "", "Statewide", "", "", "", "yes", "",
     "monitoring; ecosystems; indicators", "EXAMPLE ROW - delete. statewide shows on every district.", "ctap"],
    ["INHS", "Eastern massasauga rattlesnake demography", "Project", "Biodiversity & wildlife",
     "Long-term demographic study of a threatened rattlesnake supporting federal recovery planning.",
     "A multi-decade mark-recapture study of one of Illinois' last eastern massasauga populations; estimates survival, reproduction, and viability to inform the federal recovery plan and state conservation decisions.",
     "PaCE Lab (M. Dreslik)", "Population & Community Ecology Lab", "IDNR", "U.S. State Wildlife Grant",
     "Ongoing", "1999", "", "", "sited", "38.62", "-89.35", "Clinton", "Carlyle Lake, Clinton Co.",
     "", "", "", "", "yes", "herpetology; endangered species; demography",
     "EXAMPLE - lat/long auto-assign the districts; leave us_house/il_senate/il_house blank.", "massasauga"],
    ["INHS", "Waterfowl aerial inventories", "Program", "Biodiversity & wildlife",
     "World's longest-running waterfowl inventory; weekly aerial counts on the Illinois and Mississippi rivers.",
     "Since 1948, weekly fall and winter flights track ~30 waterfowl species through the Mississippi Flyway; data guide IDNR hunting seasons, sanctuary planning, and wetland acquisition.",
     "Forbes Biological Station", "Forbes Biological Station", "USFWS", "IDNR", "Ongoing", "1948", "",
     "", "sited", "40.30", "-90.06", "Mason", "Havana, Mason Co.", "15", "47", "94", "", "",
     "waterfowl; aerial survey; wetlands", "EXAMPLE - districts known, so they're filled in here.", "waterfowl"],
    ["INHS", "Rock Elm / Elm Zigzag Sawfly survey", "Grant", "Plants & vegetation",
     "Statewide survey for endangered Rock Elm and screening for the invasive Elm Zigzag Sawfly.",
     "Surveys 18+ sites across 10+ counties for the Illinois-endangered Rock Elm and the candidate September Elm, while screening for the newly arrived Elm Zigzag Sawfly; updates IDNR records.",
     "D. Pohl", "Forestry", "IDNR", "Illinois Native Plant Society", "Active", "2025", "2025", "",
     "statewide", "", "", "", "10+ counties incl. Hardin, Jackson, DuPage, Cook", "", "", "", "", "",
     "forestry; invasive pest; endangered plant", "EXAMPLE - a grant; lands in the Active grants card.", "elm-sawfly"],
    ["INHS", "Snake-mediated seed dispersal", "Publication", "Biodiversity & wildlife",
     "Study finding snakes can act as secondary seed-dispersal agents.",
     "Experimental work showing seeds can survive rattlesnake gut transit, with higher germination when planted with snake excrement - suggesting a previously overlooked seed-dispersal pathway.",
     "INHS-affiliated authors", "", "Other (name it in notes)", "", "Published", "2025", "2025",
     "https://doi.org/10.1098/rsos.251226", "external", "", "", "", "Experimental (Arizona conditions)",
     "", "", "", "", "", "seed dispersal; herpetology", "EXAMPLE - publication done outside Illinois (external).", "snake-seed"],
]

AWD_HEADER = ["survey", "activity_id", "activity_title", "award_title", "description", "sponsor",
              "amount", "start_year", "end_year", "pi", "status", "url", "notes", "award_id"]

AWD_ROWS = [
    ["INHS", "massasauga", "Eastern massasauga rattlesnake demography", "Massasauga demography & recovery",
     "Supports field mark-recapture, genetic sampling, and viability modeling for the state's massasauga recovery work.",
     "IDNR", "185000", "2021", "2025", "M. Dreslik", "Active", "", "EXAMPLE ROW - delete. amount = whole dollars, digits only.", "awd-massasauga-1"],
    ["INHS", "waterfowl", "Waterfowl aerial inventories", "Waterfowl aerial inventory (Federal Aid)",
     "Funds weekly aerial waterfowl counts and analysis along the Illinois and Mississippi river valleys.",
     "USFWS", "320000", "2022", "2027", "Forbes Biological Station", "Active", "", "EXAMPLE - linked to a project via activity_id.", "awd-waterfowl-1"],
    ["INHS", "", "", "Household drinking-water monitoring (subaward)",
     "PRI/U of I portion of a multi-institution NSF project developing household water-quality testing.",
     "NSF", "450000", "2025", "2028", "PRI / U of I", "Active", "", "EXAMPLE - survey-level award, no activity link.", "awd-water-1"],
]

# ---- columns added after the first draft. Appended at the END so the example rows above
# ---- stay aligned with their headers (CSV import matches on column NAME, not position).
#   image      = photo URL shown in the drill-in pop-up and the handout's feature panel
#   show_until = optional display-timer date; blank = shows until someone retires it
ACT_HEADER += ["image", "show_until"]
ACT_ROWS = [r + ["", ""] for r in ACT_ROWS]
ACT_ROWS[0][-2] = "assets/photos/ctap.jpg"   # example of what an image entry looks like

AWD_HEADER += ["show_until"]
AWD_ROWS = [r + [""] for r in AWD_ROWS]

# ---- controlled_values.csv (field,value) - the importer validates against this ----
CV = []
for v in SURVEYS: CV.append(["survey", v])
for v in TYPES: CV.append(["type", v])
for v in SCOPES: CV.append(["scope", v])
for v in ACT_STATUS: CV.append(["activity_status", v])
for v in AWD_STATUS: CV.append(["award_status", v])
for v in TOPICS: CV.append(["topic", v])
for v in FUNDERS: CV.append(["funder", v])
for v in COUNTIES: CV.append(["county", v])
for v in YESNO: CV.append(["yesno", v])

GUIDE = """PRI Project District Tracker - data intake guide
================================================

Two files to fill in (one copy per survey is fine - the importer merges by the "survey"
column). Keep the header row; delete the EXAMPLE rows. Districts and representatives are
fetched automatically; the importer computes which districts each project touches.

CONTROLLED VALUES: every categorical field must use a value from controlled_values.csv
(also listed in CONTROLLED_VALUES.md). The importer rejects/flags anything else, so that
sorting and queries stay clean. Map of column -> value list:
  survey -> survey | type -> type | topic -> topic | scope -> scope
  status (activities) -> activity_status | status (awards) -> award_status
  funder, sponsor -> funder | county -> county | featured, confirm -> yesno

--------------------------------------------------------------------
activities_template.csv  (one row per project / program / grant / publication)
--------------------------------------------------------------------
REQUIRED : survey, title, type, topic, summary

THE TWO TEXT FIELDS - fill in BOTH, they are used in different places:
  summary     = ONE LINE (about 15-25 words). This is the blurb on the card and the
                headline sentence in the pop-up. Keep it plain-English.
  description = THE PARAGRAPH (2-4 sentences). Shown under the summary when someone
                drills into the item. This is where the detail goes - what the work is,
                why it matters, who it serves. Don't repeat the summary verbatim.

IMAGE    : image = a photo for the item. Either a file you supply (put it in assets/photos/
           and write assets/photos/yourfile.jpg) or a full https:// link. It appears in the
           drill-in pop-up beside the details, and in the handout's feature panel. Landscape
           photos work best. Leave blank and a branded placeholder is used instead.
META     : lead, program (shows as "Program area"), funder (controlled), partners (free text;
           use funder names), status (controlled), start_year, end_year, url
LOCATION (give ONE so the project maps to districts):
           latitude + longitude (best) | county | (scope = statewide)
           location_text = the human-readable place ("Havana, Mason Co.") shown in the pop-up.
           Districts fill in AUTOMATICALLY from latitude/longitude - you do not have to look
           them up. Only set us_house / il_senate / il_house to override that.
TIMER    : show_until = optional date (YYYY-MM-DD). Leave BLANK for ongoing work (it then
           shows until someone retires it). Set a date for time-limited items (news, a
           one-off project) and it drops off the site by itself. Nothing is ever deleted.
FLAGS    : featured (yes), confirm (yes = district needs checking), notes, activity_id (blank = new)

--------------------------------------------------------------------
awards_template.csv  (one row per grant/award; drives the $ funding card)
--------------------------------------------------------------------
REQUIRED : survey, award_title, description, sponsor (controlled), amount (whole dollars, digits only)
LINK     : activity_id OR activity_title to attach the money to a project (and its districts)
OTHER    : start_year, end_year, pi, status (controlled: Active/Completed/Pending), url, notes, award_id
TIMER    : show_until = same rule as activities; blank means it keeps showing until retired.
"""

CONTROLLED_MD = "PRI District Tracker - controlled vocabularies\n" + "=" * 46 + "\n\n"
CONTROLLED_MD += "Use EXACTLY these values in the matching columns (case-sensitive).\n\n"
for label, vals in [("survey", SURVEYS), ("type", TYPES), ("topic", TOPICS), ("scope", SCOPES),
                    ("status - activities (activity_status)", ACT_STATUS),
                    ("status - awards (award_status)", AWD_STATUS),
                    ("funder / sponsor", FUNDERS), ("featured / confirm (yesno)", YESNO)]:
    CONTROLLED_MD += "%s:\n  %s\n\n" % (label, " | ".join(vals))
CONTROLLED_MD += "county (all 102 Illinois counties):\n  " + ", ".join(COUNTIES) + "\n"

with open(os.path.join(OUT, "activities_template.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(ACT_HEADER); w.writerows(ACT_ROWS)
with open(os.path.join(OUT, "awards_template.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(AWD_HEADER); w.writerows(AWD_ROWS)
with open(os.path.join(OUT, "controlled_values.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["field", "value"]); w.writerows(CV)
with open(os.path.join(OUT, "CONTROLLED_VALUES.md"), "w", encoding="utf-8") as f:
    f.write(CONTROLLED_MD)
with open(os.path.join(OUT, "HOW_TO_FILL_IN.md"), "w", encoding="utf-8") as f:
    f.write(GUIDE)

print("activities columns:", len(ACT_HEADER))
print("awards columns:", len(AWD_HEADER))
print("controlled fields:", len(set(r[0] for r in CV)), "| total allowed values:", len(CV))
print("counties:", len(COUNTIES))
