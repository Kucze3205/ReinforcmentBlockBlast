"""
Testy `benchmark.build_policy` dla ramienia `lookahead-ntuple:<plik>` (#123).

Format pliku jest inny niż `heuristic:`/`tray:`/`lookahead:` (tablice LUT po
łatach z `ntuple.py`, nie lista `FEATURE_NAMES`) — osobny prefiks,
`load_ntuple_weights`, nie `load_tuned_weights`.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import ArmUnavailable, build_policy, load_config, weights_file_for_spec
from ntuple import NTupleValue
from policies import NTupleLookaheadPolicy


class TestBuildPolicyNTupleWeights(unittest.TestCase):
    def setUp(self):
        self.config = load_config("bench/config.json")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_lookahead_ntuple_prefix_loads_weights(self):
        path = os.path.join(self.tmpdir.name, "w.json")
        NTupleValue().save(path)
        policy = build_policy("lookahead-ntuple:" + path, self.config)
        self.assertIsInstance(policy, NTupleLookaheadPolicy)
        self.assertEqual(policy.name, "lookahead-ntuple")

    def test_missing_file_raises_arm_unavailable_with_name(self):
        missing = os.path.join(self.tmpdir.name, "brak.json")
        with self.assertRaises(ArmUnavailable) as ctx:
            build_policy("lookahead-ntuple:" + missing, self.config)
        self.assertIn(missing, str(ctx.exception))

    def test_weights_file_for_spec_recognizes_prefix(self):
        self.assertEqual(weights_file_for_spec("lookahead-ntuple:w.json"), "w.json")


if __name__ == "__main__":
    unittest.main()
