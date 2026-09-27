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
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from ntuple import REWARD_SCORE, NTupleValue
from tools.train_ntuple import episode_seed, load_bench_seeds, main as train_main, read_log, run_episode

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

    def test_td_target_uses_reward_of_current_step_not_previous(self):
        """Atrapa dwoch ruchow o znanych gain (#153): cel dla `V(afterstate_1)`
        musi byc `r_2 + V(afterstate_2)`, nie `r_1 + V(afterstate_2)`."""
        ntuple = NTupleValue()
        alpha = 1.0
        idx1 = [0] * len(ntuple.weights)
        idx2 = [1] * len(ntuple.weights)
        script = iter([
            ("action-1", idx1, 3.0),
            ("action-2", idx2, 5.0),
        ])

        class FakeGame:
            def __init__(self, seed):
                self.done = False
                self.score = 0
                self.placements = 0

            def available_actions(self):
                return ["dummy"]

            def step(self, action):
                self.placements += 1

        with mock.patch("tools.train_ntuple.Game", FakeGame), \
                mock.patch("tools.train_ntuple._choose_action", lambda *a, **k: next(script)):
            run_episode(ntuple, seed=1, move_cap=2, alpha=alpha, reward=REWARD_SCORE)

        # Krok 2: target = r_2 + V(idx2) = 5 + 0 = 5; error = 5 - V(idx1) = 5;
        # V(idx1) += alpha*5 = 5. Terminal: target=0; error = 0 - V(idx2) = 0
        # (idx2 nietkniety wczesniej) -> V(idx2) bez zmian. Cel sprzed #153
        # (r_1 + V(idx2) = 3) dalby V(idx1) = 3, nie 5.
        for table in ntuple.weights:
            self.assertAlmostEqual(table[0], 5.0)
            self.assertAlmostEqual(table[1], 0.0)


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
            seeds_a = [entry["seed"] for entry in read_log(state_a)]
            seeds_b = [entry["seed"] for entry in read_log(state_b)]
            self.assertEqual(len(seeds_a), 2)
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


class TestTDTargetStateGuard(unittest.TestCase):
    """Stan `score` sprzed poprawki #153 (bez `params.td_target`) nie wczytuje
    sie do wznowienia — mieszanie starego i nowego celu TD bez sladu jest
    niedopuszczalne. `survival` nie jest dotkniety (r ≡ 1)."""

    @staticmethod
    def _drop_td_target(state_path):
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
        del state["params"]["td_target"]
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    def test_resuming_pre_153_score_state_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            args = ["--state", state, "--out", out, "--episodes", "2", "--seed", "1",
                     "--move-cap", "40", "--reward", "score"]
            train_main(args)
            self._drop_td_target(state)
            with self.assertRaises(ValueError):
                train_main(args)

    def test_resuming_pre_153_survival_state_is_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            args = ["--state", state, "--out", out, "--episodes", "2", "--seed", "1",
                     "--move-cap", "40", "--reward", "survival"]
            train_main(args)
            self._drop_td_target(state)
            train_main(args)  # nie rzuca
            with open(state, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["episode"], 2)


class TestOutputLoadableByNTupleValue(unittest.TestCase):
    def test_out_file_round_trips_through_ntuple_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            train_main(["--state", state, "--out", out, "--episodes", "1", "--seed", "3", "--move-cap", "40"])
            loaded = NTupleValue.load(out)
            with open(state, encoding="utf-8") as fh:
                self.assertEqual(loaded.weights, json.load(fh)["weights"])


class TestDurationAccumulation(unittest.TestCase):
    """`state["duration_s"]` nie gubi przyrostow krotszych niz ~0,05 s (#158,
    odkrycie #149): kazdy poprzedni kod rounowal skumulowana wartosc po kazdym
    odcinku, wiec dodawanie do juz zaokraglonej (czesto z powrotem do 0.0) sumy
    nigdy nie ruszalo sie z miejsca dla krotkich partii."""

    def test_short_episodes_still_accumulate_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            args = ["--state", state, "--out", out, "--episodes", "5",
                     "--episodes-per-run", "5", "--seed", "1", "--move-cap", "40"]
            # 5 odcinkow x (started, elapsed) = 10 odczytow zegara, kazdy odcinek
            # trwa dokladnie 0.01 s — ponizej progu zaokraglenia do 0.1 s, wiec
            # stary kod (round po kazdym dodaniu) zatrzymywalby sume na 0.0.
            ticks = iter(i * 0.01 for i in range(10))
            with mock.patch("tools.train_ntuple.time.time", side_effect=ticks):
                train_main(args)
            with open(state, encoding="utf-8") as fh:
                duration = json.load(fh)["duration_s"]
            self.assertAlmostEqual(duration, 0.05, places=6)


class TestLayoutFlag(unittest.TestCase):
    """`--layout` (#149): domyslnie A, bez zmiany zachowania; AD wybieralny osobno."""

    def test_default_layout_is_a_and_stored_in_state_and_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, out = os.path.join(tmp, "s.json"), os.path.join(tmp, "o.json")
            train_main(["--state", state, "--out", out, "--episodes", "1", "--move-cap", "30"])
            with open(state, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["params"]["layout"], "A")
            self.assertEqual(len(NTupleValue.load(out).weights), 16)

    def test_layout_ad_produces_52_weight_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, out = os.path.join(tmp, "s.json"), os.path.join(tmp, "o.json")
            train_main(["--state", state, "--out", out, "--episodes", "1", "--move-cap", "30",
                        "--layout", "AD"])
            self.assertEqual(len(NTupleValue.load(out).weights), 52)

    def test_changing_layout_on_resume_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, out = os.path.join(tmp, "s.json"), os.path.join(tmp, "o.json")
            base = ["--state", state, "--out", out, "--episodes", "2", "--move-cap", "30"]
            train_main(base)  # domyslnie A
            with self.assertRaises(ValueError):
                train_main(base + ["--layout", "AD"])

    def test_layout_a_run_matches_run_without_layout_flag_bit_for_bit(self):
        # Wynik jawnego "--layout A" musi byc bitowo identyczny z domyslnym
        # zachowaniem sprzed #149 (kryterium akceptacji #149).
        with tempfile.TemporaryDirectory() as tmp:
            state_default = os.path.join(tmp, "default.state.json")
            out_default = os.path.join(tmp, "default.out.json")
            state_explicit = os.path.join(tmp, "explicit.state.json")
            out_explicit = os.path.join(tmp, "explicit.out.json")
            common = ["--episodes", "30", "--episodes-per-run", "30", "--seed", "11", "--move-cap", "60"]
            train_main(["--state", state_default, "--out", out_default] + common)
            train_main(["--state", state_explicit, "--out", out_explicit] + common + ["--layout", "A"])
            with open(state_default, encoding="utf-8") as fh:
                default_weights = json.load(fh)["weights"]
            with open(state_explicit, encoding="utf-8") as fh:
                explicit_weights = json.load(fh)["weights"]
            self.assertEqual(default_weights, explicit_weights)


if __name__ == "__main__":
    unittest.main(verbosity=2)
