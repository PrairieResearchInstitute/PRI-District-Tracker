"""One-time: add lifecycle stamps (ingested_at, updated_at, show_until) to every existing
activity in data/activities.json. Existing curated records are stamped today and left
evergreen (blank show_until) so nothing that shows now suddenly disappears. Idempotent.
Run: py scripts/migrate_add_dates.py
"""
import pri_data as db

obj = db.load_db()
today = db.today_iso()
added = 0
for a in obj["activities"]:
    if "ingested_at" not in a:
        a["ingested_at"] = today
        added += 1
    a.setdefault("updated_at", a.get("ingested_at", today))
    a.setdefault("show_until", "")  # blank = evergreen; preserves current visibility
db.save_db(obj)
print("activities:", len(obj["activities"]), "| newly stamped:", added,
      "| all evergreen (blank show_until) by default")
