"""
Test na `source_hashes` i błąd standardowy w `deltas` (#102).

`source_hashes` w #87 policzył się bez `features.py` — dokładnie tego pliku,
który wtedy zmieniał mierzoną politykę. Ten test przypina jawną listę modułów,
żeby dopisanie kolejnego pliku wpływającego na wynik wymagało dotknięcia testu.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import (
    HASHED_SOURCES,
    file_hash,
    paired_delta,
    source_hashes,
    weights_file_for_spec,
)
from features import FEATURE_NAMES

REQUIRED_SOURCES = {
    "game.py",
    "scoring.py",
    "generator.py",
    "pieces.py",
    "features.py",
    "policies.py",
    "benchmark.py",
}


class TestSourceHashes(unittest.TestCase):
    def test_hashed_sources_is_exactly_the_required_set(self):
        self.assertEqual(set(HASHED_SOURCES), REQUIRED_SOURCES)

    def test_source_hashes_covers_required_set(self):
        hashes = source_hashes()
        self.assertEqual(set(hashes), REQUIRED_SOURCES)
        for value in hashes.values():
            self.assertIsInstance(value, str)
            self.assertTrue(value)


class TestWeightsFileForSpec(unittest.TestCase):
    def test_recognizes_known_prefixes(self):
        self.assertEqual(weights_file_for_spec("tray:weights.json"), "weights.json")
        self.assertEqual(weights_file_for_spec("lookahead:weights.json"), "weights.json")
        self.assertEqual(weights_file_for_spec("heuristic:w.json"), "w.json")

    def test_bare_spec_has_no_weights_file(self):
        self.assertIsNone(weights_file_for_spec("greedy"))
        self.assertIsNone(weights_file_for_spec("model/model.pth"))

    def test_hash_matches_file_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"weights": [0.0] * len(FEATURE_NAMES)}, fh)
            spec_path = weights_file_for_spec("tray:" + path)
            self.assertEqual(file_hash(spec_path), file_hash(path))


class TestPairedDeltaStandardError(unittest.TestCase):
    def test_existing_keys_unchanged_meaning(self):
        candidate = [10.0, 12.0, 8.0, 14.0]
        baseline = [8.0, 8.0, 8.0, 8.0]
        d = paired_delta(candidate, baseline, threshold_pct=10)
        self.assertEqual(d["mean_diff"], 3.0)
        self.assertEqual(d["pct"], 37.5)
        self.assertEqual(d["label"], "poprawa")

    def test_adds_standard_error_fields(self):
        candidate = [10.0, 12.0, 8.0, 14.0]
        baseline = [8.0, 8.0, 8.0, 8.0]
        d = paired_delta(candidate, baseline, threshold_pct=10)
        self.assertIn("se_diff", d)
        self.assertIn("se_pct", d)
        self.assertIn("mean_diff_over_se", d)
        self.assertGreaterEqual(len(d), 7)
        expected_se = round(d["sd_diff"] / (len(candidate) ** 0.5), 2)
        self.assertEqual(d["se_diff"], expected_se)
        self.assertEqual(d["mean_diff_over_se"], round(d["mean_diff"] / d["se_diff"], 2))

    def test_zero_se_does_not_divide_by_zero(self):
        candidate = [5.0, 5.0, 5.0]
        baseline = [5.0, 5.0, 5.0]
        d = paired_delta(candidate, baseline, threshold_pct=10)
        self.assertEqual(d["se_diff"], 0.0)
        self.assertEqual(d["mean_diff_over_se"], 0.0)


if __name__ == "__main__":
    unittest.main()
