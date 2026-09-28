"""
Testy nowych opcji `tools/train_ntuple.py` (#140): sygnał `--reward`, seedy
ewaluacji, `--best-out` tylko przy poprawie, krzywa, przyrostowy log i
wczytanie stanu sprzed #140.

Szybkie: `move_cap` mały, kilka partii.
"""
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import benchmark
from ntuple import NTupleValue
from tools import train_ntuple
from tools.train_ntuple import (
    eval_seeds,
    episode_seed,
    load_bench_seeds,
    log_path,
    main as train_main,
    read_log,
    run_episode,
)

CONFIG_PATH = "bench/config.json"


def _config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestEvalSeeds(unittest.TestCase):
    def test_disjoint_from_fixed_rotated_and_training_seeds(self):
        config = _config()
        forbidden = load_bench_seeds(config)
        seeds = eval_seeds(200, forbidden)
        self.assertEqual(len(set(seeds)), 200)
        self.assertFalse(set(seeds) & forbidden)
        for issue in (1, 127, 140, 999):
            self.assertFalse(set(seeds) & set(benchmark.rotated_seeds(config, issue)), issue)
        training = {episode_seed(s, e, forbidden) for s in (0, 1, 2) for e in range(1, 300)}
        self.assertFalse(set(seeds) & training)
        # Rozlacznosc z rotowanymi dla kazdego issue wynika z przedzialu, nie z proby.
        self.assertTrue(all(s >= 2**31 for s in seeds))

    def test_same_set_regardless_of_training_seed_and_prefix_stable(self):
        forbidden = load_bench_seeds(_config())
        self.assertEqual(eval_seeds(20, forbidden), eval_seeds(20, forbidden))
        self.assertEqual(eval_seeds(20, forbidden), eval_seeds(40, forbidden)[:20])

    def test_forbidden_seed_is_skipped(self):
        natural = eval_seeds(3, set())
        forced = eval_seeds(3, {natural[0]})
        self.assertNotIn(natural[0], forced)


class TestSurvivalReward(unittest.TestCase):
    def test_survival_episode_learns_from_ones_not_gain(self):
        # Ten sam seed, inny sygnal: inne cele TD, wiec inne wagi.
        ntuple = NTupleValue(reward="survival")
        stats = run_episode(ntuple, seed=42, move_cap=40, alpha=0.01, reward="survival")
        self.assertGreater(stats["placements"], 1)
        self.assertTrue(any(any(t) for t in ntuple.weights))
        score_run = NTupleValue()
        run_episode(score_run, seed=42, move_cap=40, alpha=0.01, reward="score")
        self.assertNotEqual(ntuple.weights, score_run.weights)

    def test_eval_does_not_touch_weights(self):
        ntuple = NTupleValue()
        run_episode(ntuple, seed=5, move_cap=40, alpha=0.01)
        before = [list(t) for t in ntuple.weights]
        run_episode(ntuple, seed=6, move_cap=40, alpha=0.01, learn=False)
        self.assertEqual(before, ntuple.weights)


class TestRewardFlag(unittest.TestCase):
    def test_reward_in_state_and_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, out = os.path.join(tmp, "s.json"), os.path.join(tmp, "o.json")
            train_main(["--state", state, "--out", out, "--episodes", "1",
                        "--move-cap", "30", "--reward", "survival"])
            self.assertEqual(_load(state)["params"]["reward"], "survival")
            self.assertEqual(_load(out)["reward"], "survival")
            self.assertEqual(NTupleValue.load(out).reward, "survival")

    def test_changing_reward_on_resume_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, out = os.path.join(tmp, "s.json"), os.path.join(tmp, "o.json")
            base = ["--state", state, "--out", out, "--episodes", "2", "--move-cap", "30"]
            train_main(base + ["--reward", "survival"])
            with self.assertRaises(ValueError):
                train_main(base)  # domyslnie score
            with self.assertRaises(ValueError):
                train_main(base + ["--reward", "score"])


class TestBestOut(unittest.TestCase):
    def _run(self, tmp, scores, episodes, extra=()):
        state, out = os.path.join(tmp, "s.json"), os.path.join(tmp, "o.json")
        best = os.path.join(tmp, "best.json")
        results = iter(scores)
        best_writes = []
        real_write = train_ntuple.write_json

        def fake_evaluate(ntuple, seeds, move_cap, reward):
            return {"sredni_wynik": next(results), "srednie_przezycie": 1.0, "n_partii": len(seeds)}

        def spy_write(path, data, indent=2):
            if path == best:
                best_writes.append(data["ewaluacja"]["odcinki"])
            return real_write(path, data, indent)

        with mock.patch.object(train_ntuple, "evaluate", fake_evaluate), \
                mock.patch.object(train_ntuple, "write_json", spy_write):
            train_main(["--state", state, "--out", out, "--episodes", str(episodes),
                        "--episodes-per-run", str(episodes), "--move-cap", "30",
                        "--eval-every", "1", "--eval-episodes", "2", "--best-out", best]
                       + list(extra))
        return state, best, best_writes

    def test_written_only_on_improvement(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, best, writes = self._run(tmp, [10.0, 5.0, 10.0, 20.0], 4)
            self.assertEqual(writes, [1, 4])
            self.assertEqual(_load(best)["ewaluacja"]["sredni_wynik"], 20.0)
            ev = _load(state)["eval"]
            self.assertEqual([p["odcinki"] for p in ev["points"]], [1, 2, 3, 4])
            self.assertEqual(ev["best"]["odcinki"], 4)
            NTupleValue.load(best)  # plik best-out jest plikiem wag

    def test_best_weights_are_the_weights_at_best_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, best, _ = self._run(tmp, [30.0, 5.0], 2)
            # Po odcinku 2 wagi sie zmienily, best-out trzyma te z odcinka 1.
            self.assertNotEqual(_load(best)["weights"], _load(state)["weights"])

    def test_eval_every_requires_best_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                train_main(["--state", os.path.join(tmp, "s.json"), "--episodes", "1",
                            "--eval-every", "1"])

    def test_changing_eval_episodes_on_resume_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "s.json")
            best = os.path.join(tmp, "b.json")
            base = ["--state", state, "--out", os.path.join(tmp, "o.json"), "--episodes", "2",
                    "--move-cap", "20", "--eval-every", "1", "--best-out", best]
            train_main(base + ["--eval-episodes", "2"])
            with self.assertRaises(ValueError):
                train_main(base + ["--eval-episodes", "3"])


class TestCurveOut(unittest.TestCase):
    def test_curve_has_windows_and_eval_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            curve = os.path.join(tmp, "c.json")
            train_main(["--state", os.path.join(tmp, "s.json"), "--out", os.path.join(tmp, "o.json"),
                        "--episodes", "4", "--episodes-per-run", "4", "--move-cap", "20",
                        "--eval-every", "2", "--eval-episodes", "2",
                        "--best-out", os.path.join(tmp, "b.json"), "--curve-out", curve])
            data = _load(curve)
            for key in ("opis", "params", "seed", "n_odcinkow_lacznie", "rozmiar_okna", "okna"):
                self.assertIn(key, data)
            self.assertEqual(data["n_odcinkow_lacznie"], 4)
            window = data["okna"][0]
            for key in ("od_odcinka", "do_odcinka", "n_odcinkow", "sredni_wynik", "srednie_przezycie"):
                self.assertIn(key, window)
            self.assertEqual((window["od_odcinka"], window["do_odcinka"], window["n_odcinkow"]), (1, 4, 4))
            log = read_log(os.path.join(tmp, "s.json"))
            self.assertAlmostEqual(window["sredni_wynik"], round(sum(e["score"] for e in log) / 4, 2))
            self.assertEqual([p["odcinki"] for p in data["ewaluacja"]["punkty"]], [2, 4])


class TestIncrementalSave(unittest.TestCase):
    def test_state_has_no_log_and_log_is_appended(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "s.json")
            args = ["--state", state, "--out", os.path.join(tmp, "o.json"), "--episodes", "5",
                    "--episodes-per-run", "3", "--move-cap", "20", "--save-every", "2"]
            train_main(args)
            train_main(args)
            self.assertNotIn("log", _load(state))
            self.assertEqual([e["episode"] for e in read_log(state)], [1, 2, 3, 4, 5])

    def test_log_beyond_saved_state_is_truncated_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "s.json")
            args = ["--state", state, "--out", os.path.join(tmp, "o.json"), "--episodes", "3",
                    "--move-cap", "20"]
            train_main(args)
            # Symulacja smierci sesji po dopisaniu logu, przed zapisem stanu.
            with open(log_path(state), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"episode": 2, "seed": -1}) + "\n")
            train_main(args)
            self.assertEqual([e["episode"] for e in read_log(state)], [1, 2])
            self.assertNotEqual(read_log(state)[1]["seed"], -1)

    def test_save_every_resume_matches_continuous(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = os.path.join(tmp, "a.json"), os.path.join(tmp, "b.json")
            common = ["--episodes", "4", "--move-cap", "20", "--seed", "3", "--save-every", "3"]
            train_main(["--state", a, "--out", os.path.join(tmp, "ao.json"),
                        "--episodes-per-run", "4"] + common)
            for _ in range(2):
                train_main(["--state", b, "--out", os.path.join(tmp, "bo.json"),
                            "--episodes-per-run", "2"] + common)
            self.assertEqual(_load(a)["weights"], _load(b)["weights"])
            self.assertEqual([e["seed"] for e in read_log(a)], [e["seed"] for e in read_log(b)])


class TestOldStateFormat(unittest.TestCase):
    def _old_state(self, tmp):
        """Stan w formacie sprzed #140: log w srodku, bez pola `reward`."""
        state = os.path.join(tmp, "s.json")
        out = os.path.join(tmp, "o.json")
        train_main(["--state", state, "--out", out, "--episodes", "2", "--episodes-per-run", "2",
                    "--move-cap", "20", "--seed", "4"])
        data = _load(state)
        log = read_log(state)
        os.remove(log_path(state))
        for key in ("format", "log_bytes", "windows", "eval"):
            data.pop(key)
        data["params"].pop("reward")
        data["log"] = log
        with open(state, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return state, out, log

    def test_old_state_resumes_as_score_and_migrates_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, out, log = self._old_state(tmp)
            train_main(["--state", state, "--out", out, "--episodes", "3",
                        "--move-cap", "20", "--seed", "4"])
            data = _load(state)
            self.assertEqual(data["params"]["reward"], "score")
            self.assertNotIn("log", data)
            self.assertEqual(read_log(state)[:2], log)
            self.assertEqual(len(read_log(state)), 3)
            self.assertEqual(data["windows"][0]["n_odcinkow"], 3)

    def test_old_state_rejects_survival(self):
        with tempfile.TemporaryDirectory() as tmp:
            state, out, _ = self._old_state(tmp)
            with self.assertRaises(ValueError):
                train_main(["--state", state, "--out", out, "--episodes", "3",
                            "--move-cap", "20", "--seed", "4", "--reward", "survival"])


class TestLogRotation(unittest.TestCase):
    """Rotacja logu na pliki-bloki (#187): zaden plik logu nie rosnie bez
    granic przy milionie odcinkow. `BLOCK_EPISODES` jest tu zamockowane na
    male wartosci, zeby przetestowac granice bloku bez uruchamiania miliona
    odcinkow."""

    def test_log_splits_into_block_files_and_read_log_concatenates_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "s.json")
            out = os.path.join(tmp, "o.json")
            with mock.patch.object(train_ntuple, "BLOCK_EPISODES", 2):
                train_main(["--state", state, "--out", out, "--episodes", "5",
                            "--episodes-per-run", "5", "--move-cap", "20"])
            base = os.path.join(tmp, "s")
            self.assertTrue(os.path.exists(base + ".log.jsonl"))  # blok 0: odcinki 1-2
            self.assertTrue(os.path.exists(base + ".log.0001.jsonl"))  # odcinki 3-4
            self.assertTrue(os.path.exists(base + ".log.0002.jsonl"))  # odcinek 5
            with open(base + ".log.jsonl", encoding="utf-8") as fh:
                self.assertEqual(len(fh.readlines()), 2)
            with open(base + ".log.0001.jsonl", encoding="utf-8") as fh:
                self.assertEqual(len(fh.readlines()), 2)
            with open(base + ".log.0002.jsonl", encoding="utf-8") as fh:
                self.assertEqual(len(fh.readlines()), 1)
            self.assertEqual([e["episode"] for e in read_log(state)], [1, 2, 3, 4, 5])

    def test_no_single_block_file_exceeds_size_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "s.json")
            out = os.path.join(tmp, "o.json")
            with mock.patch.object(train_ntuple, "BLOCK_EPISODES", 3):
                train_main(["--state", state, "--out", out, "--episodes", "10",
                            "--episodes-per-run", "10", "--move-cap", "20"])
            base = os.path.join(tmp, "s")
            paths = [base + ".log.jsonl"] + sorted(glob.glob(base + ".log.*.jsonl"))
            self.assertGreater(len(paths), 1)
            # 3 wpisy/blok x max 164 B (pomiar realnych logow ADC/survival) < 40 MB.
            for path in paths:
                self.assertLessEqual(os.path.getsize(path), 3 * 164)

    def test_resuming_across_a_block_boundary_matches_continuous_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_a = os.path.join(tmp, "a.json")
            out_a = os.path.join(tmp, "ao.json")
            state_b = os.path.join(tmp, "b.json")
            out_b = os.path.join(tmp, "bo.json")
            with mock.patch.object(train_ntuple, "BLOCK_EPISODES", 2):
                train_main(["--state", state_a, "--out", out_a, "--episodes", "5",
                            "--episodes-per-run", "5", "--seed", "7", "--move-cap", "20"])
                for _ in range(5):
                    train_main(["--state", state_b, "--out", out_b, "--episodes", "5",
                                "--seed", "7", "--move-cap", "20"])
            self.assertEqual(_load(state_a)["weights"], _load(state_b)["weights"])
            self.assertEqual([e["seed"] for e in read_log(state_a)], [e["seed"] for e in read_log(state_b)])

    def test_weights_are_bit_identical_regardless_of_block_size(self):
        """Rozmiar bloku logu to szczegol zapisu na dysk — nie moze zmienic
        wag ani celu TD (kryterium akceptacji #187)."""
        with tempfile.TemporaryDirectory() as tmp:
            state_small = os.path.join(tmp, "small.json")
            out_small = os.path.join(tmp, "small.o.json")
            state_big = os.path.join(tmp, "big.json")
            out_big = os.path.join(tmp, "big.o.json")
            common = ["--episodes", "6", "--episodes-per-run", "6", "--seed", "13",
                      "--move-cap", "30", "--reward", "survival", "--layout", "ADC"]
            with mock.patch.object(train_ntuple, "BLOCK_EPISODES", 2):
                train_main(["--state", state_small, "--out", out_small] + common)
            train_main(["--state", state_big, "--out", out_big] + common)  # BLOCK_EPISODES domyslne
            self.assertEqual(_load(state_small)["weights"], _load(state_big)["weights"])
            with open(out_small, "rb") as fh_small, open(out_big, "rb") as fh_big:
                self.assertEqual(
                    hashlib.sha256(fh_small.read()).hexdigest(),
                    hashlib.sha256(fh_big.read()).hexdigest(),
                )

    def test_orphaned_block_logs_are_removed_when_state_restarts(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "s.json")
            out = os.path.join(tmp, "o.json")
            with mock.patch.object(train_ntuple, "BLOCK_EPISODES", 2):
                train_main(["--state", state, "--out", out, "--episodes", "5",
                            "--episodes-per-run", "5", "--move-cap", "20"])
                os.remove(state)  # stan usuniety, logi osierocone
                train_main(["--state", state, "--out", out, "--episodes", "1",
                            "--episodes-per-run", "1", "--move-cap", "20"])
            self.assertEqual([e["episode"] for e in read_log(state)], [1])


class TestResumeFromExistingRepoState(unittest.TestCase):
    """Kryterium akceptacji #187: wznowienie ze stanu sprzed zmiany dziala na
    kopii w katalogu tymczasowym, pliki w `ntuple/` pozostaja nietkniete."""

    STATE_SRC = os.path.join("ntuple", "survival-adc-state.json")

    def test_resume_from_copied_repo_state_leaves_ntuple_dir_untouched(self):
        if not os.path.exists(self.STATE_SRC):
            self.skipTest("ntuple/survival-adc-state.json niedostepny w tym przebiegu")
        with open(self.STATE_SRC, encoding="utf-8") as fh:
            src_state = json.load(fh)
        params = src_state["params"]
        ntuple_dir = "ntuple"

        def _hashes(names):
            hashes = {}
            for name in names:
                with open(os.path.join(ntuple_dir, name), "rb") as fh:
                    hashes[name] = hashlib.sha256(fh.read()).hexdigest()
            return hashes

        before = sorted(os.listdir(ntuple_dir))
        before_hashes = _hashes(before)
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "state.json")
            out = os.path.join(tmp, "out.json")
            best = os.path.join(tmp, "best.json")
            shutil.copy(self.STATE_SRC, state)
            target = src_state["episode"] + 3
            train_main([
                "--state", state, "--out", out,
                "--episodes", str(target), "--episodes-per-run", "3",
                "--seed", str(params["seed"]), "--alpha", str(params["alpha"]),
                "--move-cap", str(params["move_cap"]), "--reward", params["reward"],
                "--layout", params["layout"],
                "--eval-every", str(src_state["eval"]["every"]),
                "--eval-episodes", str(src_state["eval"]["episodes"]),
                "--best-out", best,
            ])
            self.assertEqual(_load(state)["episode"], target)
        after = sorted(os.listdir(ntuple_dir))
        after_hashes = _hashes(after)
        self.assertEqual(before, after)
        self.assertEqual(before_hashes, after_hashes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
