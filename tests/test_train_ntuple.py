"""
Testy `tools/train_ntuple.py` (#123): rozłączność seedów treningowych,
wznawialność trybu `--state` (ten sam przebieg co ciągły) i format wyjścia.

Szybkie: `move_cap` mały, po jednej-dwóch partiach — pełny przebieg treningu
(budżet z #120) jest osobnym, ręcznym zadaniem `rola:bench`.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from ntuple import NTupleValue
from tools.train_ntuple import episode_seed, load_bench_seeds, main as train_main, run_episode

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

    def test_collision_is_resolved_deterministically(self):
        forbidden = set()
        # Wywolaj raz, zeby poznac "naturalny" wynik bez kolizji...
        natural = episode_seed(9, 1, set())
        # ...potem wymus kolizje: wynik powinien byc inny, ale wciaz deterministyczny.
        forced = episode_seed(9, 1, {natural})
        self.assertNotEqual(natural, forced)
        self.assertEqual(forced, episode_seed(9, 1, {natural}))


class TestRunEpisode(unittest.TestCase):
    def test_updates_weights_away_from_zero(self):
        ntuple = NTupleValue()
        stats = run_episode(ntuple, seed=42, move_cap=40, alpha=0.01)
        self.assertGreater(stats["placements"], 0)
        self.assertTrue(any(any(t) for t in ntuple.weights), "wagi zostaly nietkniete")

    def test_stats_have_required_fields(self):
        ntuple = NTupleValue()
        stats = run_episode(ntuple, seed=7, move_cap=40, alpha=0.01)
        for key in ("seed", "score", "placements", "steps", "mean_abs_td_error"):
            self.assertIn(key, stats)


class TestResumableTraining(unittest.TestCase):
    def test_resumed_run_matches_continuous_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_a = os.path.join(tmp, "a.state.json")
            out_a = os.path.join(tmp, "a.out.json")
            state_b = os.path.join(tmp, "b.state.json")
            out_b = os.path.join(tmp, "b.out.json")

            # Ciag A: dwa odcinki w jednym wywolaniu.
            train_main([
                "--state", state_a, "--out", out_a,
                "--episodes", "2", "--episodes-per-run", "2",
                "--seed", "5", "--move-cap", "40",
            ])

            # Ciag B: dwa wywolania, po jednym odcinku kazde (wznowienie).
            train_main([
                "--state", state_b, "--out", out_b,
                "--episodes", "2", "--seed", "5", "--move-cap", "40",
            ])
            train_main([
                "--state", state_b, "--out", out_b,
                "--episodes", "2", "--seed", "5", "--move-cap", "40",
            ])

            with open(state_a, encoding="utf-8") as fh:
                a = json.load(fh)
            with open(state_b, encoding="utf-8") as fh:
                b = json.load(fh)

            self.assertEqual(a["weights"], b["weights"])
            seeds_a = [entry["seed"] for entry in a["log"]]
            seeds_b = [entry["seed"] for entry in b["log"]]
            self.assertEqual(seeds_a, seeds_b)

    def test_second_invocation_advances_one_episode(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            args = ["--state", state, "--out", out, "--episodes", "2", "--seed", "1", "--move-cap", "40"]

            train_main(args)
            with open(state, encoding="utf-8") as fh:
                after_first = json.load(fh)
            self.assertEqual(after_first["episode"], 1)

            train_main(args)
            with open(state, encoding="utf-8") as fh:
                after_second = json.load(fh)
            self.assertEqual(after_second["episode"], 2)

    def test_mismatched_params_on_resume_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            train_main(["--state", state, "--out", out, "--episodes", "2", "--seed", "1", "--move-cap", "40"])
            with self.assertRaises(ValueError):
                train_main(["--state", state, "--out", out, "--episodes", "2", "--seed", "2", "--move-cap", "40"])


class TestOutputLoadableByNTupleValue(unittest.TestCase):
    def test_out_file_round_trips_through_ntuple_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            train_main(["--state", state, "--out", out, "--episodes", "1", "--seed", "3", "--move-cap", "40"])
            loaded = NTupleValue.load(out)
            with open(state, encoding="utf-8") as fh:
                self.assertEqual(loaded.weights, json.load(fh)["weights"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
