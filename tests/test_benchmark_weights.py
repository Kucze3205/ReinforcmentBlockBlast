"""
Testy `benchmark.build_policy` dla ramion strojonych wagami (#80).

`tools/tune_weights.py` zapisuje `weights.json` z kluczem `weights` (lista
liczb w kolejności `features.FEATURE_NAMES`). `build_policy` musi rozpoznać
prefiksy `heuristic:<plik>` i `tray:<plik>` i zbudować politykę z tego samego
formatu, bez wpadania w gałąź wag torcha (#80). Ścieżka bez prefiksu ma
zostać nietknięta — pokrywa to `test_tune_weights.py::...build_policy("tray", ...)`
i istniejące testy modelu torcha; tu tylko dodajemy nowe przypadki.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import ArmUnavailable, build_policy, load_config
from features import ALL_FEATURE_NAMES, FEATURE_NAMES
from policies import HeuristicPolicy, LookaheadPolicy, TrayPolicy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestBuildPolicyTunedWeights(unittest.TestCase):
    def setUp(self):
        self.config = load_config("bench/config.json")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def _write_weights(self, name, weights):
        path = os.path.join(self.tmpdir.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"weights": weights}, fh)
        return path

    def _padding(self):
        """Ogon zer, którym #118 dopełnia plik sprzed dodania wag combo."""
        return (0.0,) * (len(ALL_FEATURE_NAMES) - len(FEATURE_NAMES))

    def test_heuristic_prefix_loads_weights(self):
        weights = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        path = self._write_weights("w.json", weights)
        policy = build_policy("heuristic:" + path, self.config)
        self.assertIsInstance(policy, HeuristicPolicy)
        self.assertEqual(policy.weights, tuple(weights) + self._padding())

    def test_tray_prefix_loads_weights(self):
        weights = [0.0] * len(FEATURE_NAMES)
        path = self._write_weights("w.json", weights)
        policy = build_policy("tray:" + path, self.config)
        self.assertIsInstance(policy, TrayPolicy)
        self.assertEqual(policy.weights, tuple(weights) + self._padding())

    def test_combo_weights_are_loaded_verbatim(self):
        """Pełny wektor (#118) wchodzi bez dopełniania i bez obcinania."""
        weights = [float(i) for i in range(len(ALL_FEATURE_NAMES))]
        path = self._write_weights("w.json", weights)
        policy = build_policy("tray:" + path, self.config)
        self.assertEqual(policy.weights, tuple(weights))

    def test_partial_combo_tail_is_padded_with_zeros(self):
        """Plik z częścią wag combo też wchodzi — brakujące są zerami."""
        weights = [1.0] * (len(FEATURE_NAMES) + 1)
        path = self._write_weights("w.json", weights)
        policy = build_policy("tray:" + path, self.config)
        self.assertEqual(len(policy.weights), len(ALL_FEATURE_NAMES))
        self.assertEqual(policy.weights[len(FEATURE_NAMES) + 1:],
                         (0.0,) * (len(ALL_FEATURE_NAMES) - len(FEATURE_NAMES) - 1))

    def test_too_short_raises_arm_unavailable_with_lengths(self):
        path = self._write_weights("w.json", [1.0, 2.0])
        with self.assertRaises(ArmUnavailable) as ctx:
            build_policy("heuristic:" + path, self.config)
        message = str(ctx.exception)
        self.assertIn(str(len(FEATURE_NAMES)), message)
        self.assertIn("2", message)

    def test_too_long_raises_arm_unavailable_with_lengths(self):
        """Za długi wektor to literówka w pliku, nie nowa cecha — ma wywalić."""
        too_long = len(ALL_FEATURE_NAMES) + 1
        path = self._write_weights("w.json", [1.0] * too_long)
        with self.assertRaises(ArmUnavailable) as ctx:
            build_policy("heuristic:" + path, self.config)
        message = str(ctx.exception)
        self.assertIn(str(len(ALL_FEATURE_NAMES)), message)
        self.assertIn(str(too_long), message)

    def test_missing_file_raises_arm_unavailable_with_name(self):
        missing = os.path.join(self.tmpdir.name, "brak.json")
        with self.assertRaises(ArmUnavailable) as ctx:
            build_policy("tray:" + missing, self.config)
        self.assertIn(missing, str(ctx.exception))


class TestRepoWeightFilesAsLookaheadArms(unittest.TestCase):
    """Oba pliki wag **z repo** budują ramię `lookahead:` (#125).

    Testy wyżej pracują na plikach tymczasowych, więc przechodziłyby nawet
    wtedy, gdyby `weights.json` albo `weights-combo.json` w repo przestały się
    wczytywać. Te dwa pliki są konkretnymi ramionami benchmarku (#118) —
    `weights.json` odniesieniem sprzed combo, `weights-combo.json` ramieniem z
    pełnym wektorem — i wpięcie alternatywnego liścia (#123/#125) nie ma prawa
    ruszyć ani jednej, ani drugiej ścieżki wczytywania.
    """

    def setUp(self):
        self.config = load_config("bench/config.json")

    def test_weights_json_is_six_numbers_padded_with_zero_combo_tail(self):
        with open(os.path.join(ROOT, "weights.json"), encoding="utf-8") as fh:
            stored = tuple(json.load(fh)["weights"])
        self.assertEqual(len(stored), len(FEATURE_NAMES))

        policy = build_policy("lookahead:" + os.path.join(ROOT, "weights.json"), self.config)
        self.assertIsInstance(policy, LookaheadPolicy)
        self.assertEqual(len(policy.weights), len(ALL_FEATURE_NAMES))
        self.assertEqual(policy.weights[:len(FEATURE_NAMES)], stored)
        # Ogon dokładnie zerowy: to on gwarantuje ocenę bit w bit jak przed #118.
        self.assertEqual(policy.weights[len(FEATURE_NAMES):],
                         (0.0,) * (len(ALL_FEATURE_NAMES) - len(FEATURE_NAMES)))

    def test_weights_combo_json_is_nine_numbers_loaded_verbatim(self):
        with open(os.path.join(ROOT, "weights-combo.json"), encoding="utf-8") as fh:
            stored = tuple(json.load(fh)["weights"])
        self.assertEqual(len(stored), len(ALL_FEATURE_NAMES))

        policy = build_policy("lookahead:" + os.path.join(ROOT, "weights-combo.json"),
                              self.config)
        self.assertIsInstance(policy, LookaheadPolicy)
        self.assertEqual(policy.weights, stored)


if __name__ == "__main__":
    unittest.main()
