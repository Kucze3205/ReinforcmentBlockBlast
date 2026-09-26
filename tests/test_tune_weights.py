"""
Testy `tools/tune_weights.py` (#59, #77): rozłączność seedów, format
`weights.json`, `build_policy` i aktualizacji CEM. Szybkie (limity czasu w
sekundach) — pełny przebieg strojenia jest osobnym, ręcznym uruchomieniem
udokumentowanym w `docs/strojenie-wag.md`.

`TrayPolicy` sama w sobie (przeszukanie tacki, brak mutacji gry, kolejność
klocków ma znaczenie) ma dedykowane testy w `tests/test_tray_policy.py` —
tu sprawdzamy tylko, że `build_policy("tray", ...)` faktycznie jej używa.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from features import FEATURE_NAMES
from policies import HeuristicPolicy, LookaheadPolicy, TrayPolicy
from tools.tune_weights import (
    build_policy,
    evaluate_candidate,
    generation_rng,
    load_init_weights,
    main as tune_main,
    run_generation,
    training_seeds,
    update_distribution,
)


class TestTrainingSeeds(unittest.TestCase):
    def test_disjoint_from_forbidden_set(self):
        forbidden = list(range(1, 51))
        seeds = training_seeds(20, forbidden, salt=1)
        self.assertEqual(len(seeds), 20)
        self.assertEqual(len(set(seeds)), 20)
        self.assertFalse(set(seeds) & set(forbidden))

    def test_deterministic_for_same_salt(self):
        forbidden = [1259289227, 1358106528]
        a = training_seeds(10, forbidden, salt=7)
        b = training_seeds(10, forbidden, salt=7)
        self.assertEqual(a, b)

    def test_different_salts_differ(self):
        forbidden = []
        a = training_seeds(10, forbidden, salt=1)
        b = training_seeds(10, forbidden, salt=2)
        self.assertNotEqual(a, b)

    def test_disjoint_from_real_bench_seeds_file(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "bench", "seeds_fixed.json"), encoding="utf-8") as fh:
            bench_seeds = json.load(fh)
        seeds = training_seeds(30, bench_seeds, salt=0)
        self.assertFalse(set(seeds) & set(bench_seeds))


class TestUpdateDistribution(unittest.TestCase):
    def test_mean_matches_elite_average(self):
        elite = [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]
        mean, std = update_distribution(elite)
        self.assertAlmostEqual(mean[0], 2.0)
        self.assertAlmostEqual(mean[1], 4.0)
        self.assertGreater(std[0], 0)

    def test_std_has_floor_for_identical_elite(self):
        elite = [(1.0, 1.0), (1.0, 1.0)]
        _mean, std = update_distribution(elite)
        self.assertGreaterEqual(std[0], 0.05)


class TestBuildPolicy(unittest.TestCase):
    def test_heuristic_uses_heuristic_policy_with_given_weights(self):
        weights = tuple(2.0 for _ in FEATURE_NAMES)
        policy = build_policy("heuristic", weights)
        self.assertIsInstance(policy, HeuristicPolicy)
        self.assertEqual(policy.weights, weights)

    def test_tray_uses_policies_tray_policy_with_given_weights(self):
        weights = tuple(1.5 for _ in FEATURE_NAMES)
        policy = build_policy("tray", weights)
        self.assertIsInstance(policy, TrayPolicy)
        self.assertEqual(policy.weights, weights)

    def test_lookahead_uses_lookahead_policy_with_default_params_from_92(self):
        weights = tuple(0.5 for _ in FEATURE_NAMES)
        policy = build_policy("lookahead", weights)
        self.assertIsInstance(policy, LookaheadPolicy)
        self.assertEqual(policy.weights, weights)
        # Kandydat ma być oceniany dokładnie tą konfiguracją, którą mierzy
        # benchmark (`lookahead:<plik>` → `LookaheadPolicy(weights=...)`), #104.
        self.assertEqual(policy.beam, LookaheadPolicy.DEFAULT_BEAM)
        self.assertEqual(policy.samples, LookaheadPolicy.DEFAULT_SAMPLES)
        self.assertEqual(policy.branch, LookaheadPolicy.DEFAULT_BRANCH)
        self.assertEqual(policy.inner_beam, LookaheadPolicy.DEFAULT_INNER_BEAM)
        self.assertEqual(policy.inner_depth, LookaheadPolicy.DEFAULT_INNER_DEPTH)

    def test_unknown_policy_raises(self):
        with self.assertRaises(ValueError):
            build_policy("nope", HeuristicPolicy.DEFAULT_WEIGHTS)


class TestEvaluateCandidate(unittest.TestCase):
    def test_heuristic_matches_default_weights_policy(self):
        seeds = [111, 222]
        score = evaluate_candidate("heuristic", HeuristicPolicy.DEFAULT_WEIGHTS, seeds, move_cap=50)
        self.assertIsInstance(score, (int, float))

    def test_tray_policy_evaluates_via_policies_tray_policy(self):
        seeds = [111, 222]
        score = evaluate_candidate("tray", TrayPolicy.DEFAULT_WEIGHTS, seeds, move_cap=50)
        self.assertIsInstance(score, (int, float))


class TestMainProducesWeightsFile(unittest.TestCase):
    def test_writes_weights_json_with_expected_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "weights.json")
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cwd = os.getcwd()
            os.chdir(root)
            try:
                tune_main([
                    "--policy", "heuristic",
                    "--minutes", "0.02",
                    "--games-per-candidate", "2",
                    "--population", "2",
                    "--elite", "1",
                    "--seed", "5",
                    "--out", out_path,
                ])
            finally:
                os.chdir(cwd)
            with open(out_path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["policy"], "heuristic")
            self.assertEqual(record["feature_names"], list(FEATURE_NAMES))
            self.assertEqual(len(record["weights"]), len(FEATURE_NAMES))
            self.assertIn("log", record)


class TestGenerationRng(unittest.TestCase):
    def test_same_generation_same_population(self):
        self.assertEqual(generation_rng(104, 3).random(), generation_rng(104, 3).random())

    def test_different_generations_differ(self):
        self.assertNotEqual(generation_rng(104, 3).random(), generation_rng(104, 4).random())


class TestLoadInitWeights(unittest.TestCase):
    def test_reads_weights_key_of_weights_json_format(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        weights = load_init_weights(os.path.join(root, "weights.json"))
        self.assertEqual(len(weights), len(FEATURE_NAMES))

    def test_rejects_wrong_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"weights": [1.0, 2.0]}, fh)
            with self.assertRaises(ValueError):
                load_init_weights(path)


class TestRunGeneration(unittest.TestCase):
    def test_elite_is_top_scorers_and_evaluated_keeps_order(self):
        result = run_generation(
            "heuristic", HeuristicPolicy.DEFAULT_WEIGHTS,
            tuple(1.0 for _ in FEATURE_NAMES), 3, 2, [111, 222], 20,
            generation_rng(1, 1), iteration=1,
        )
        self.assertEqual(len(result["evaluated"]), 3)
        self.assertEqual(len(result["elite"]), 2)
        scores = [s for _, s in result["evaluated"]]
        self.assertEqual([s for _, s in result["elite"]], sorted(scores, reverse=True)[:2])
        self.assertEqual(result["entry"]["iteration"], 1)


class TestGenerationalRunIsResumable(unittest.TestCase):
    """Przebieg przerwany po pokoleniu i wznowiony musi dać to samo, co nieprzerwany.

    To jest sedno #104: pełny przebieg `lookahead` idzie w godzinach, więc jedyny
    sposób, żeby przeżył śmierć runnera, to zapis stanu po każdym pokoleniu —
    a zapis jest wart tyle, ile wierność wznowienia."""

    def _config(self, tmp):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({
                "n_seeds": 300,
                "move_cap": 25,
                "fixed_seed_file": os.path.join(root, "bench", "seeds_fixed.json"),
            }, fh)
        return path

    def _args(self, tmp, tag, config):
        return [
            "--policy", "heuristic",
            "--games-per-candidate", "2",
            "--population", "3",
            "--elite", "2",
            "--seed", "5",
            "--generations", "2",
            "--config", config,
            "--state", os.path.join(tmp, tag + ".state.json"),
            "--out", os.path.join(tmp, tag + ".weights.json"),
        ]

    def test_two_calls_match_one_call_and_state_advances(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(tmp)

            whole = self._args(tmp, "whole", config)
            tune_main(whole + ["--generations-per-run", "2"])

            split = self._args(tmp, "split", config)
            tune_main(split)
            with open(os.path.join(tmp, "split.state.json"), encoding="utf-8") as fh:
                halfway = json.load(fh)
            self.assertEqual(halfway["generation"], 1)
            self.assertEqual(len(halfway["log"]), 1)
            self.assertEqual(len(halfway["elite"]), 2)
            tune_main(split)

            with open(os.path.join(tmp, "whole.state.json"), encoding="utf-8") as fh:
                a = json.load(fh)
            with open(os.path.join(tmp, "split.state.json"), encoding="utf-8") as fh:
                b = json.load(fh)
            self.assertEqual(a["generation"], 2)
            self.assertEqual(b["generation"], 2)
            self.assertEqual(a["best_weights"], b["best_weights"])
            self.assertEqual(a["best_score"], b["best_score"])
            self.assertEqual(a["mean"], b["mean"])
            self.assertEqual(a["std"], b["std"])
            self.assertEqual(a["elite"], b["elite"])
            self.assertEqual(
                [e["mean_score"] for e in a["log"]], [e["mean_score"] for e in b["log"]]
            )

    def test_finished_run_does_not_advance_further(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self._args(tmp, "done", self._config(tmp))
            tune_main(args + ["--generations-per-run", "2"])
            tune_main(args)
            with open(os.path.join(tmp, "done.state.json"), encoding="utf-8") as fh:
                state = json.load(fh)
            self.assertEqual(state["generation"], 2)
            self.assertEqual(len(state["log"]), 2)

    def test_resume_with_mismatched_params_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config(tmp)
            args = self._args(tmp, "clash", config)
            tune_main(args)
            clash = list(args)
            clash[clash.index("--population") + 1] = "4"
            with self.assertRaises(ValueError):
                tune_main(clash)

    def test_out_file_is_loadable_by_benchmark_build_policy(self):
        from benchmark import build_policy as bench_build_policy

        with tempfile.TemporaryDirectory() as tmp:
            args = self._args(tmp, "load", self._config(tmp))
            tune_main(args + ["--generations-per-run", "2"])
            out = os.path.join(tmp, "load.weights.json")
            policy = bench_build_policy("lookahead:" + out, {"torch_seed": 0})
            self.assertEqual(policy.name, "lookahead")
            self.assertEqual(len(policy.weights), len(FEATURE_NAMES))
            with open(out, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["feature_names"], list(FEATURE_NAMES))
            self.assertEqual(record["iterations"], 2)
            self.assertEqual(len(record["log"]), 2)

    def test_init_weights_file_sets_distribution_centre(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            args = self._args(tmp, "init", self._config(tmp))
            tune_main(args + ["--init-weights-file", os.path.join(root, "weights.json")])
            with open(os.path.join(tmp, "init.state.json"), encoding="utf-8") as fh:
                state = json.load(fh)
            self.assertEqual(state["init_weights"], list(load_init_weights(
                os.path.join(root, "weights.json"))))


class TestDefaultRunIsUnchanged(unittest.TestCase):
    """Bez `--state` i bez `--init-weights-file` narzędzie robi to, co przed #104."""

    def test_no_state_file_written_and_record_has_legacy_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "weights.json")
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cwd = os.getcwd()
            os.chdir(root)
            try:
                tune_main([
                    "--policy", "tray", "--minutes", "0.02", "--games-per-candidate", "1",
                    "--population", "2", "--elite", "1", "--seed", "5", "--out", out_path,
                ])
            finally:
                os.chdir(cwd)
            self.assertEqual(os.listdir(tmp), ["weights.json"])
            with open(out_path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["policy"], "tray")
            self.assertEqual(record["init_weights"], list(HeuristicPolicy.DEFAULT_WEIGHTS))
            self.assertEqual(record["params"]["minutes"], 0.02)


if __name__ == "__main__":
    unittest.main(verbosity=2)
