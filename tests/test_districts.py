"""Latitude/longitude -> legislative district. Staff rely on this so they never have
to look a district up by hand; a wrong answer puts work in the wrong legislator's
profile."""
import unittest
import _ctx  # noqa: F401
import pri_data as db


class DistrictAssignment(unittest.TestCase):
    def test_champaign(self):
        got = db.assign_districts(40.1106, -88.2073)
        self.assertEqual(got["us_house"], [13])
        self.assertEqual(got["il_senate"], [52])
        self.assertEqual(got["il_house"], [103])

    def test_chicago_is_a_different_district(self):
        got = db.assign_districts(41.8781, -87.6298)
        self.assertEqual(got["us_house"], [7])

    def test_districts_are_integers_not_strings(self):
        """The front end matches with indexOf(Number(n)); strings silently fail."""
        got = db.assign_districts(40.1106, -88.2073)
        for chamber, vals in got.items():
            for v in vals:
                self.assertIsInstance(v, int, "%s returned a non-int: %r" % (chamber, v))

    def test_point_outside_illinois_matches_nothing(self):
        got = db.assign_districts(39.7392, -104.9903)   # Denver
        self.assertEqual(got["us_house"], [])
        self.assertEqual(got["il_senate"], [])
        self.assertEqual(got["il_house"], [])

    def test_every_chamber_is_answered(self):
        self.assertEqual(set(db.assign_districts(40.1106, -88.2073)),
                         set(db.CHAMBER_FILES))


if __name__ == "__main__":
    unittest.main()
