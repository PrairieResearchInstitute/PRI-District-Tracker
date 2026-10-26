"""The display timer. If this breaks, records silently vanish from - or linger on -
the public site, which is the whole point of the feature."""
import unittest, datetime
import _ctx  # noqa: F401
import pri_data as db


class FreshnessRule(unittest.TestCase):
    def test_blank_show_until_is_evergreen(self):
        self.assertTrue(db.fresh({"show_until": ""}))
        self.assertTrue(db.fresh({}))
        self.assertTrue(db.fresh({"show_until": None}))

    def test_future_date_still_shows(self):
        self.assertTrue(db.fresh({"show_until": "2099-01-01"}))

    def test_past_date_is_hidden(self):
        self.assertFalse(db.fresh({"show_until": "2020-01-01"}))

    def test_today_still_shows(self):
        """Inclusive: a record set to expire today is visible for all of today."""
        self.assertTrue(db.fresh({"show_until": db.today_iso()}))

    def test_yesterday_is_hidden(self):
        y = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        self.assertFalse(db.fresh({"show_until": y}))

    def test_whitespace_is_treated_as_blank(self):
        self.assertTrue(db.fresh({"show_until": "   "}))


class SuggestedWindow(unittest.TestCase):
    def test_programs_default_to_evergreen(self):
        for t in sorted(db.EVERGREEN_TYPES):
            self.assertEqual(db.suggest_show_until(t), "")

    def test_dated_types_get_a_window(self):
        got = db.suggest_show_until("News", "2026-01-01")
        expect = (datetime.date(2026, 1, 1)
                  + datetime.timedelta(days=db.DEFAULT_WINDOW_DAYS)).isoformat()
        self.assertEqual(got, expect)


class RuleParity(unittest.TestCase):
    """The rule exists in two places and they must not drift apart."""

    def test_php_clause_matches_python_semantics(self):
        """CURRENT_DATE is standard SQL, and
        inclusive of today, as fresh() is. The PHP suite runs it on PostgreSQL."""
        import os
        with open(os.path.join(_ctx.ROOT, "includes", "db.php"), encoding="utf-8") as f:
            php = f.read()
        self.assertIn("const FRESH_WHERE = '(show_until IS NULL OR show_until >= CURRENT_DATE)';", php,
                      "includes/db.php FRESH_WHERE no longer mirrors pri_data.fresh()")
        self.assertNotIn("CURDATE()", php, "CURDATE() is MySQL-only; PostgreSQL rejects it")


class DatesAreParsedNotCompared(unittest.TestCase):
    """The timer used to compare raw strings. A staff member typing "12/31/2099" in a
    spreadsheet therefore hid their project for ever, while "soon" showed for ever, and
    neither raised anything. Dates are parsed now, and unreadable ones are refused."""

    def test_us_style_dates_are_understood(self):
        self.assertEqual(db.normalize_date("12/31/2099"), "2099-12-31")
        self.assertEqual(db.normalize_date("2099/12/31"), "2099-12-31")
        self.assertEqual(db.normalize_date("2099-12-31"), "2099-12-31")

    def test_blank_stays_blank(self):
        self.assertEqual(db.normalize_date(""), "")
        self.assertEqual(db.normalize_date(None), "")

    def test_unreadable_dates_are_refused_with_a_usable_message(self):
        for bad in ("soon", "31-12-2099", "13/45/2099", "next year"):
            with self.assertRaises(db.BadDateError, msg="%r was accepted" % bad) as cm:
                db.normalize_date(bad)
            self.assertIn("YYYY-MM-DD", str(cm.exception))

    def test_a_far_future_us_date_shows_rather_than_hides(self):
        """The exact silent failure: string comparison put 12/31/2099 before today."""
        iso = db.normalize_date("12/31/2099")
        self.assertTrue(db.fresh({"show_until": iso}))

    def test_comparison_is_by_date_not_by_text(self):
        self.assertFalse(db.fresh({"show_until": "2020-01-01"}))
        self.assertTrue(db.fresh({"show_until": "2099-01-01"}))

    def test_an_unparseable_stored_value_shows_rather_than_disappears(self):
        """Ingest refuses bad dates; if one somehow exists, showing real work is the
        safer failure than hiding it with no trace."""
        self.assertTrue(db.fresh({"show_until": "whenever"}))


if __name__ == "__main__":
    unittest.main()
