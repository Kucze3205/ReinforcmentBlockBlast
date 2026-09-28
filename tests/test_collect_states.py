"""
Testy `tools/collect_states.py` (#168): rozłączność seedów zbierania z
`bench/seeds_fixed.json` i format pliku wyjściowego.

Szybkie: `--move-cap` mały, wagi N-tuple domyślne (nieuczone) — wystarczy do
sprawdzenia mechaniki, nie jakości zebranych plansz.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from ntuple import NTupleValue
from tools.collect_states import episode_seed, load_bench_seeds, main as collect_main

CONFIG_PATH = "bench/config.json"


def _config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


class TestEpisodeSeed(unittest.TestCase):
    def test_disjoint_from_forbidden_set(self):
        forbidden = set(range(1, 51))
        for episode in range(1, 20):
            seed = episode_seed(1, episode, forbidden)
            self.assertNotIn(seed, forbidden)

    def test_disjoint_from_real_bench_seeds_file(self):
        forbidden = load_bench_seeds(_config())
        for episode in range(1, 10):
            self.assertNotIn(episode_seed(0, episode, forbidden), forbidden)

    def test_deterministic_for_same_seed_and_episode(self):
        forbidden = set()
        self.assertEqual(episode_seed(3, 5, forbidden), episode_seed(3, 5, forbidden))

    def test_different_episode_numbers_differ(self):
        forbidden = set()
        self.assertNotEqual(episode_seed(3, 1, forbidden), episode_seed(3, 2, forbidden))


class TestCollectMain(unittest.TestCase):
    def _weights_path(self, tmp):
        path = os.path.join(tmp, "weights.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(NTupleValue().to_dict(), fh)
        return path

    def test_output_format_and_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            weights = self._weights_path(tmp)
            out = os.path.join(tmp, "states.json")
            collect_main([
                "--weights", weights, "--episodes", "2", "--seed", "1",
                "--move-cap", "20", "--out", out,
            ])
            with open(out, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["n_games"], 2)
            self.assertIn("boards", data)
            self.assertGreater(len(data["boards"]), 0)
            for entry in data["boards"]:
                self.assertIn("board", entry)
                self.assertIn("placement", entry)
                self.assertEqual(len(entry["board"]), 8)
                self.assertEqual(len(entry["board"][0]), 8)

    def test_sample_every_reduces_board_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            weights = self._weights_path(tmp)
            out_every1 = os.path.join(tmp, "s1.json")
            out_every5 = os.path.join(tmp, "s5.json")
            args = ["--weights", weights, "--episodes", "3", "--seed", "1", "--move-cap", "30"]
            collect_main(args + ["--out", out_every1, "--sample-every", "1"])
            collect_main(args + ["--out", out_every5, "--sample-every", "5"])
            with open(out_every1, encoding="utf-8") as fh:
                n1 = len(json.load(fh)["boards"])
            with open(out_every5, encoding="utf-8") as fh:
                n5 = len(json.load(fh)["boards"])
            self.assertGreater(n1, n5)

    def test_jobs_matches_single_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            weights = self._weights_path(tmp)
            out_seq = os.path.join(tmp, "seq.json")
            out_par = os.path.join(tmp, "par.json")
            args = ["--weights", weights, "--episodes", "4", "--seed", "2", "--move-cap", "20"]
            collect_main(args + ["--out", out_seq, "--jobs", "1"])
            collect_main(args + ["--out", out_par, "--jobs", "2"])
            with open(out_seq, encoding="utf-8") as fh:
                seq = json.load(fh)["boards"]
            with open(out_par, encoding="utf-8") as fh:
                par = json.load(fh)["boards"]
            self.assertEqual(seq, par)


if __name__ == "__main__":
    unittest.main(verbosity=2)
