PRI Project District Tracker - data intake guide
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
