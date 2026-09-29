"""
Testy `tools/train_ntuple_search.py` (#216, pilot: TD po stanach nastepczych z
trajektorii wiazki). Szybkie: `move_cap` maly, kilka odcinkow na runde — pelny
przebieg jest osobnym, recznym zadaniem tej sesji, nie testem jednostkowym.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from ntuple import NTupleValue
from tools.train_ntuple_search import main as train_main, run_episode_search
from policies import NTupleLookaheadPolicy


class TestParserValidation(unittest.TestCase):
    def _args(self, tmp, **overrides):
        state = os.path.join(tmp, "state.json")
        args = [
            "--state", state, "--episodes", "4", "--episodes-per-run", "4",
            "--move-cap", "30", "--jobs", "2", "--round-episodes", "4",
        ]
        for key, value in overrides.items():
            args += [key, str(value)]
        return args

    def test_round_episodes_must_divide_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                train_main(self._args(tmp, **{"--round-episodes": 3}))

    def test_episodes_must_be_multiple_of_round_episodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                train_main(self._args(tmp, **{"--episodes": 6}))

    def test_episodes_per_run_must_be_multiple_of_round_episodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                train_main(self._args(tmp, **{"--episodes-per-run": 6}))

    def test_eval_every_must_be_multiple_of_round_episodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            best = os.path.join(tmp, "best.json")
            with self.assertRaises(SystemExit):
                train_main(self._args(tmp, **{
                    "--eval-every": 2, "--eval-episodes": 5, "--best-out": best,
                }))


class TestRunEpisodeSearch(unittest.TestCase):
    def test_updates_weights_away_from_zero(self):
        ntuple = NTupleValue()
        policy = NTupleLookaheadPolicy(ntuple, beam=4, samples=0)
        stats = run_episode_search(ntuple, policy, seed=42, move_cap=30, alpha=0.05)
        self.assertGreater(stats["placements"], 0)
        self.assertTrue(any(any(t) for t in ntuple.weights), "wagi zostaly nietkniete")

    def test_stats_have_required_fields(self):
        ntuple = NTupleValue()
        policy = NTupleLookaheadPolicy(ntuple, beam=4, samples=0)
        stats = run_episode_search(ntuple, policy, seed=7, move_cap=30, alpha=0.01)
        for key in ("seed", "score", "placements", "steps", "mean_abs_td_error"):
            self.assertIn(key, stats)


class TestResumableTraining(unittest.TestCase):
    def _run(self, tmp, state, out, episodes, episodes_per_run, jobs=2, round_episodes=4):
        return train_main([
            "--state", state, "--out", out, "--episodes", str(episodes),
            "--episodes-per-run", str(episodes_per_run), "--seed", "5",
            "--move-cap", "30", "--jobs", str(jobs), "--round-episodes", str(round_episodes),
            "--alpha", "0.05", "--search-beam", "4",
        ])

    def test_resumed_run_matches_continuous_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_a = os.path.join(tmp, "a.state.json")
            out_a = os.path.join(tmp, "a.out.json")
            state_b = os.path.join(tmp, "b.state.json")
            out_b = os.path.join(tmp, "b.out.json")

            self._run(tmp, state_a, out_a, episodes=8, episodes_per_run=8)
            self._run(tmp, state_b, out_b, episodes=8, episodes_per_run=4)
            self._run(tmp, state_b, out_b, episodes=8, episodes_per_run=4)

            with open(state_a, encoding="utf-8") as fh:
                a = json.load(fh)
            with open(state_b, encoding="utf-8") as fh:
                b = json.load(fh)
            self.assertEqual(a["episode"], 8)
            self.assertEqual(a["episode"], b["episode"])
            self.assertEqual(a["weights"], b["weights"])

    def test_second_invocation_advances_one_round(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            self._run(tmp, state, out, episodes=8, episodes_per_run=4)
            with open(state, encoding="utf-8") as fh:
                after_first = json.load(fh)
            self.assertEqual(after_first["episode"], 4)

            self._run(tmp, state, out, episodes=8, episodes_per_run=4)
            with open(state, encoding="utf-8") as fh:
                after_second = json.load(fh)
            self.assertEqual(after_second["episode"], 8)

    def test_mismatched_params_on_resume_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            self._run(tmp, state, out, episodes=4, episodes_per_run=4)
            with self.assertRaises(ValueError):
                train_main([
                    "--state", state, "--out", out, "--episodes", "4",
                    "--episodes-per-run", "4", "--seed", "6", "--move-cap", "30",
                    "--jobs", "2", "--round-episodes", "4", "--alpha", "0.05",
                ])


class TestInitWeights(unittest.TestCase):
    def test_new_state_starts_from_init_weights_when_alpha_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_ntuple = NTupleValue()
            src_ntuple.weights[0][0] = 3.5
            src_path = os.path.join(tmp, "src.json")
            src_ntuple.save(src_path)

            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            train_main([
                "--state", state, "--out", out, "--episodes", "2",
                "--episodes-per-run", "2", "--move-cap", "20", "--jobs", "1",
                "--round-episodes", "2", "--alpha", "0.0", "--init-weights", src_path,
            ])
            with open(out, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["weights"][0][0], 3.5)


if __name__ == "__main__":
    unittest.main()
