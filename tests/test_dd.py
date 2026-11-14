import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from dd import run, scoring
from dd.screening import Screener, load_lists, normalize

FIX = Path(__file__).parent / "fixtures"
DATA = Path(__file__).parent.parent / "data"

RISK = {"Singapore": ("Low", ""), "Cuba": ("Restricted", "Comprehensive US embargo"),
        "Nigeria": ("High", "Elevated corruption risk"), "Turkey": ("Medium", ""),
        "United Arab Emirates": ("Medium", ""), "Panama": ("Medium", "")}


def tp(**kw):
    base = dict(id="T1", name="Test Co", type="Reseller", country="Singapore", owners="A Person",
                government_ties="No", interacts_with_officials="No", services="", commission_pct="5",
                payment_country="Singapore", contract_value_usd="1000", other_red_flags="")
    base.update(kw)
    return base


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.screener = Screener(load_lists(FIX))

    def test_normalize_strips_legal_suffixes_and_punctuation(self):
        self.assertEqual(normalize("Green Leaf General Trading L.L.C."), "green leaf general trading")
        self.assertEqual(normalize("Sakura Annotation K.K."), "sakura annotation")

    def test_spacing_variant_still_matches(self):
        hits = self.screener.screen("Greenleaf General Trading LLC")
        self.assertEqual(hits[0].entry_id, "100")
        self.assertGreaterEqual(hits[0].score, 90)

    def test_word_order_variant_matches(self):
        self.assertEqual(self.screener.screen("Wei Zhang")[0].entry_id, "101")

    def test_unrelated_name_does_not_match(self):
        self.assertEqual(self.screener.screen("Sakura Annotation KK"), [])


class ScoringTests(unittest.TestCase):
    def test_restricted_country_is_prohibited(self):
        a = scoring.assess(tp(country="Cuba"), RISK, [])
        self.assertEqual(a.tier, "Prohibited")

    def test_payment_to_restricted_country_is_prohibited(self):
        a = scoring.assess(tp(payment_country="Cuba"), RISK, [])
        self.assertEqual(a.tier, "Prohibited")

    def test_any_sanctions_hit_is_hold_even_if_otherwise_low(self):
        screener = Screener(load_lists(FIX))
        a = scoring.assess(tp(), RISK, screener.screen("Green Leaf General Trading"))
        self.assertEqual(a.tier, "Hold")

    def test_bribery_red_flags_add_up_to_high(self):
        a = scoring.assess(tp(country="Nigeria", government_ties="Yes - former official",
                              interacts_with_officials="Yes", commission_pct="20"), RISK, [])
        self.assertEqual(a.tier, "High")
        self.assertTrue(any("former official" in r for r in a.reasons))

    def test_clean_low_risk(self):
        a = scoring.assess(tp(), RISK, [])
        self.assertEqual((a.tier, a.points), ("Low", 0))

    def test_unrated_country_defaults_to_medium(self):
        a = scoring.assess(tp(country="Atlantis", payment_country="Atlantis"), RISK, [])
        self.assertTrue(any("not on the risk list" in r for r in a.reasons))


class EndToEndTests(unittest.TestCase):
    def test_full_run_with_cleared_match(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            data = d / "data"
            shutil.copytree(DATA, data)
            readme = d / "README.md"
            readme.write_text("x\n<!-- RESULTS:START -->\n<!-- RESULTS:END -->\n")
            self.assertEqual(run.main(["--lists", str(FIX), "--data", str(data),
                                       "--out", str(d / "out"), "--readme", str(readme)]), 0)
            rows = {r["id"]: r for r in csv.DictReader((d / "out" / "results.csv").open())}
            self.assertEqual(rows["TP-006"]["tier"], "Prohibited")
            self.assertEqual(rows["TP-005"]["tier"], "Hold")
            # The fixture's ZHANG, Wei is entry 101, not the cleared OFAC #45391,
            # so the owner match must stay open: clearing one entry clears only that entry.
            self.assertEqual(rows["TP-002"]["tier"], "Hold")
            self.assertEqual(rows["TP-010"]["tier"], "Low")
            self.assertIn("| TP-006 |", readme.read_text())

    def test_no_lists_means_no_clearance(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run.main(["--lists", d, "--out", str(Path(d) / "o"),
                                       "--readme", str(Path(d) / "r.md")]), 1)


if __name__ == "__main__":
    unittest.main()
