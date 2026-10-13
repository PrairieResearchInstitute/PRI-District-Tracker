"""CSV intake round-trip. Staff fill in a template and hand it over; if a column is
silently dropped here, the work simply never appears on the site. This has happened
before (location_text and program were both being discarded)."""
import unittest, tempfile, shutil, os, json
import _ctx  # noqa: F401
import pri_data as db
import admin_server as adm

HEADER = ("survey,title,type,topic,summary,description,lead,program,funder,partners,"
          "status,start_year,end_year,url,scope,latitude,longitude,county,location_text,"
          "us_house,il_senate,il_house,featured,confirm,keywords,notes,activity_id,image,show_until")

ROW = ('ISGS,Mahomet Aquifer Study,Project,Geology,One-line blurb.,'
       'The fuller paragraph shown on drill-in.,Dr. A. Lead,Groundwater Program,USGS,IEPA,'
       'Active,2024,2027,https://example.org,sited,40.1106,-88.2073,Champaign,"Champaign, IL",'
       ',,,yes,no,aquifer;water,a note,,assets/photos/x.jpg,2099-06-30')


class CsvRoundTrip(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "activities.json")
        shutil.copy(db.DB_PATH, self.db)
        self._orig = db.DB_PATH
        db.DB_PATH = self.db          # resolved at call time, so this redirects load/save

    def tearDown(self):
        db.DB_PATH = self._orig
        shutil.rmtree(self.dir, ignore_errors=True)

    def _import(self, csv_text):
        return adm.import_csv(csv_text)

    def _all(self):
        with open(self.db, encoding="utf-8") as f:
            return json.load(f)["activities"]

    def _find(self, title):
        with open(self.db, encoding="utf-8") as f:
            obj = json.load(f)
        for a in obj["activities"]:
            if a.get("title") == title:
                return a
        return None

    def test_every_field_survives(self):
        res = self._import(HEADER + "\n" + ROW + "\n")
        self.assertTrue(res["ok"])
        self.assertEqual(res["added"], 1)
        r = self._find("Mahomet Aquifer Study")
        self.assertIsNotNone(r, "imported record not found")

        self.assertEqual(r["survey"], "ISGS")
        self.assertEqual(r["type"], "Project")
        self.assertEqual(r["summary"], "One-line blurb.")
        self.assertEqual(r["description"], "The fuller paragraph shown on drill-in.")
        self.assertEqual(r["funder"], "USGS")
        self.assertEqual(r["image"], "assets/photos/x.jpg")
        self.assertEqual(r["show_until"], "2099-06-30")
        self.assertEqual(r["keywords"], "aquifer;water")
        self.assertTrue(r["featured"])
        self.assertFalse(r["confirm"])

    def test_template_columns_map_to_runtime_fields(self):
        """location_text -> location and program -> group, or the pop-up shows blanks."""
        self._import(HEADER + "\n" + ROW + "\n")
        r = self._find("Mahomet Aquifer Study")
        self.assertEqual(r["location"], "Champaign, IL")
        self.assertEqual(r["group"], "Groundwater Program")

    def test_districts_assigned_from_latlong(self):
        self._import(HEADER + "\n" + ROW + "\n")
        r = self._find("Mahomet Aquifer Study")
        self.assertEqual(r["us_house"], [13])
        self.assertEqual(r["il_senate"], [52])
        self.assertEqual(r["il_house"], [103])
        self.assertIsInstance(r["us_house"][0], int)

    def test_lifecycle_stamps_are_set(self):
        self._import(HEADER + "\n" + ROW + "\n")
        r = self._find("Mahomet Aquifer Study")
        self.assertEqual(r["ingested_at"], db.today_iso())
        self.assertEqual(r["updated_at"], db.today_iso())

    def test_reimport_updates_instead_of_duplicating(self):
        self._import(HEADER + "\n" + ROW + "\n")
        before = len(self._all())
        changed = ROW.replace("One-line blurb.", "Revised blurb.")
        res = self._import(HEADER + "\n" + changed + "\n")
        after = len(self._all())
        self.assertEqual(after, before, "re-import duplicated the record")
        self.assertEqual(res["updated"], 1)
        self.assertEqual(self._find("Mahomet Aquifer Study")["summary"], "Revised blurb.")

    def test_example_rows_are_skipped(self):
        ex = ROW.replace(",a note,", ",EXAMPLE ROW - delete,")
        res = self._import(HEADER + "\n" + ex + "\n")
        self.assertEqual(res["added"], 0)
        self.assertIsNone(self._find("Mahomet Aquifer Study"))

    def test_statewide_record_gets_no_districts(self):
        sw = ROW.replace(",sited,40.1106,-88.2073,", ",statewide,,,")
        self._import(HEADER + "\n" + sw + "\n")
        r = self._find("Mahomet Aquifer Study")
        self.assertEqual(r["us_house"], [])
        self.assertEqual(r["scope"], "statewide")


if __name__ == "__main__":
    unittest.main()
