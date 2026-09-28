"""
Testy rdzenia natywnego N-tuple (#184): ścieżka natywna i czysty Python dają
**bitowo** to samo — wartości (`==`, nie przybliżenie), wagi po treningu (sha256),
log treningu i wyniki partii `lookahead-ntuple`.

Bez kompilatora albo z `NTUPLE_NATIVE=0` testy porównujące są pomijane, a
`TestFallback` sprawdza, że kod liczy w czystym Pythonie.
"""
import hashlib
import json
import os
import random
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import ntuple_native
from benchmark import build_policy, play_game
from board import Board
from game import Game
from ntuple import LAYOUTS, NTupleValue, board_bits
from policies import NTupleLookaheadPolicy, _tray_beam_search, _tray_beam_search_native
from tools.train_ntuple import main as train_main, read_log

CONFIG_PATH = "bench/config.json"
ADC_WEIGHTS = "ntuple/survival-adc-70k.json"
NATIVE = ntuple_native.available()


def _random_weights(layout, rng):
    """Wagi o bardzo różnych rzędach wielkości — tam sumowanie kompensacyjne
    `sum()` różni się od zwykłego, więc test widzi zły algorytm sumy."""
    return [
        [rng.choice((1.0, -1.0)) * rng.random() * 10.0 ** rng.randint(-12, 12)
         for _ in range(1 << len(positions))]
        for positions in layout
    ]


def _random_board(rng):
    density = rng.random()
    board = Board()
    board.grid = [[1 if rng.random() < density else 0 for _ in range(Board.WIDTH)]
                  for _ in range(Board.HEIGHT)]
    return board


def _pair(layout, weights):
    native = NTupleValue(weights=[list(t) for t in weights], layout=layout, native=True)
    pure = NTupleValue(weights=[list(t) for t in weights], layout=layout, native=False)
    return native, pure


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@unittest.skipUnless(NATIVE, "rdzen natywny niedostepny (brak kompilatora albo NTUPLE_NATIVE=0)")
class TestValueEquivalence(unittest.TestCase):
    def test_value_on_1000_random_boards_equals_pure_python(self):
        for name in ("A", "AD", "ADC"):
            rng = random.Random("184:" + name)
            native, pure = _pair(LAYOUTS[name], _random_weights(LAYOUTS[name], rng))
            self.assertIsNotNone(native.native)
            self.assertIsNone(pure.native)
            for _ in range(1000):
                board = _random_board(rng)
                self.assertEqual(native.value(board), pure.value(board), name)
                self.assertEqual(native.indices(board), pure.indices(board), name)

    def test_value_on_trained_adc_weights_equals_pure_python(self):
        native = NTupleValue.load(ADC_WEIGHTS, native=True)
        pure = NTupleValue.load(ADC_WEIGHTS, native=False)
        rng = random.Random(1184)
        for _ in range(1000):
            board = _random_board(rng)
            self.assertEqual(native.value(board), pure.value(board))

    def test_updates_leave_identical_weights(self):
        layout = LAYOUTS["AD"]
        rng = random.Random(7)
        native, pure = _pair(layout, _random_weights(layout, rng))
        for _ in range(300):
            board = _random_board(rng)
            delta = rng.uniform(-1.0, 1.0) * 10.0 ** rng.randint(-6, 3)
            native.update(native.native.indices_list(board_bits(board)), delta)
            pure.update(pure.indices(board), delta)
            self.assertEqual(native.value(board), pure.value(board))
        self.assertEqual(native.weights, pure.weights)

    def test_weights_edited_from_outside_are_seen_by_the_core(self):
        native, pure = _pair(LAYOUTS["A"], _random_weights(LAYOUTS["A"], random.Random(3)))
        board = Board()
        board.grid[0] = [1] * Board.WIDTH
        for value in (native, pure):
            value.weights[0][255] = 12.5
        self.assertEqual(native.value(board), pure.value(board))

    def test_integer_weight_falls_back_to_python(self):
        native, pure = _pair(LAYOUTS["A"], _random_weights(LAYOUTS["A"], random.Random(4)))
        for value in (native, pure):
            value.weights[3][17] = 5
        self.assertIsNone(native.native)
        board = _random_board(random.Random(5))
        self.assertEqual(native.value(board), pure.value(board))


@unittest.skipUnless(NATIVE, "rdzen natywny niedostepny (brak kompilatora albo NTUPLE_NATIVE=0)")
class TestSearchEquivalence(unittest.TestCase):
    """`_tray_beam_search_native` vs `_tray_beam_search` z liściem N-tuple:
    ta sama wiązka (stany, kolejność, pola) i ta sama liczba rozwinięć."""

    def _compare(self, value, board, pieces, combo, counter, beam, root_actions, depth, path_key):
        expected = _tray_beam_search(
            board, pieces, combo, counter, None, beam, root_actions=root_actions, depth=depth,
            leaf_value=lambda b, c, cc: value.value(b), path_key=path_key,
        )
        got = _tray_beam_search_native(
            value.native, board, pieces, combo, counter, beam,
            root_actions=root_actions, depth=depth, path_key=path_key,
        )
        self.assertIsNotNone(got)
        self.assertEqual(got[1], expected[1])
        self.assertEqual(len(got[0]), len(expected[0]))
        for g, e in zip(got[0], expected[0]):
            self.assertEqual(g["board"].grid, e["board"].grid)
            for key in ("pieces", "combo", "combo_counter", "gain", "placed", "first_action", "score"):
                self.assertEqual(g[key], e[key], key)

    def test_random_states_match_python_search(self):
        value = NTupleValue.load(ADC_WEIGHTS, native=True)
        rng = random.Random(84)
        checked = 0
        for n in range(300):
            game = Game(seed=rng.randrange(1, 10**6))
            # Trochę ruchów, żeby plansza, combo i tacka nie były startowe.
            for _ in range(rng.randrange(0, 15)):
                actions = game.available_actions()
                if game.done or not actions:
                    break
                game.step(rng.choice(actions))
            if game.done:
                continue
            root = game.available_actions() if n % 2 else None
            self._compare(
                value, game.board, tuple(game.pieces), game.combo, game.combo_counter,
                rng.choice((1, 2, 8, 30)), root, rng.choice((None, 1, 2, 3, 4)),
                rng.choice(("gain", "placed")),
            )
            checked += 1
        self.assertGreater(checked, 100)

    def test_high_combo_and_no_moves(self):
        value = NTupleValue.load(ADC_WEIGHTS, native=True)
        game = Game(seed=11)
        full = Board()
        full.grid = [[1] * Board.WIDTH for _ in range(Board.HEIGHT)]
        full.grid[0][0] = 0
        for board in (game.board, full):
            for combo, counter in ((0, 3), (7, 1), (40, 5)):
                for path_key in ("gain", "placed"):
                    self._compare(value, board, tuple(game.pieces), combo, counter, 8, None, None, path_key)
                    self._compare(value, board, tuple(game.pieces), combo, counter, 8, [], None, path_key)
                    self._compare(value, board, tuple(game.pieces), combo, counter, 3, None, 0, path_key)

    def test_case_outside_point_tables_falls_back_to_python(self):
        """Plansza z już pełną linią: czyszczenie liczy więcej linii, niż klocek
        może domknąć — rdzeń oddaje `None`, a polityka liczy wiązkę w Pythonie."""
        value = NTupleValue.load(ADC_WEIGHTS, native=True)
        game = Game(seed=12)
        game.board.grid[4] = [1] * Board.WIDTH
        pieces = tuple(game.pieces)
        self.assertIsNone(_tray_beam_search_native(
            value.native, game.board, pieces, 0, 3, 8, path_key="placed"))
        policy = NTupleLookaheadPolicy(value)
        got = policy._search(game.board, pieces, 0, 3, 8)
        expected = _tray_beam_search(
            game.board, pieces, 0, 3, None, 8,
            leaf_value=lambda b, c, cc: value.value(b), path_key="placed",
        )
        self.assertEqual([s["score"] for s in got[0]], [s["score"] for s in expected[0]])
        self.assertEqual(got[1], expected[1])

@unittest.skipUnless(NATIVE, "rdzen natywny niedostepny (brak kompilatora albo NTUPLE_NATIVE=0)")
class TestTrainingEquivalence(unittest.TestCase):
    def _train(self, tmp, tag, native, extra):
        state = os.path.join(tmp, tag + ".state.json")
        out = os.path.join(tmp, tag + ".weights.json")
        env = {} if native else {ntuple_native.ENV_FLAG: "0"}
        with mock.patch.dict(os.environ, env):
            train_main(["--state", state, "--out", out, "--seed", "184"] + extra)
        log = read_log(state)
        for entry in log:
            entry.pop("duration_s")
        return _sha(out), log

    def _check(self, extra):
        with tempfile.TemporaryDirectory() as tmp:
            sha_native, log_native = self._train(tmp, "native", True, extra)
            sha_pure, log_pure = self._train(tmp, "pure", False, extra)
        self.assertEqual(sha_native, sha_pure)
        self.assertEqual(log_native, log_pure)
        self.assertTrue(log_native)

    def test_200_adc_survival_episodes_same_weights_and_log(self):
        self._check([
            "--episodes", "200", "--episodes-per-run", "200", "--reward", "survival", "--layout", "ADC",
        ])

    def test_score_reward_same_weights_and_log(self):
        self._check([
            "--episodes", "30", "--episodes-per-run", "30", "--reward", "score", "--layout", "AD",
        ])


@unittest.skipUnless(NATIVE, "rdzen natywny niedostepny (brak kompilatora albo NTUPLE_NATIVE=0)")
class TestPlayGameEquivalence(unittest.TestCase):
    def test_lookahead_ntuple_games_identical(self):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            config = json.load(fh)
        with open(config["fixed_seed_file"], encoding="utf-8") as fh:
            seeds = json.load(fh)[:3]
        spec = "lookahead-ntuple:" + ADC_WEIGHTS
        native = build_policy(spec, config)
        with mock.patch.dict(os.environ, {ntuple_native.ENV_FLAG: "0"}):
            pure = build_policy(spec, config)
        self.assertIsNotNone(native.ntuple.native)
        self.assertIsNone(pure.ntuple.native)
        for seed in seeds:
            self.assertEqual(
                play_game(native, seed, config["move_cap"]),
                play_game(pure, seed, config["move_cap"]),
                seed,
            )


class TestFallback(unittest.TestCase):
    def test_env_flag_zero_means_pure_python(self):
        with mock.patch.dict(os.environ, {ntuple_native.ENV_FLAG: "0"}):
            self.assertFalse(ntuple_native.available())
            value = NTupleValue(layout=LAYOUTS["AD"])
            policy = NTupleLookaheadPolicy(value)
        self.assertIsNone(value.native)
        game = Game(seed=5)
        self.assertEqual(value.value(game.board), 0.0)
        self.assertIn(policy.act(game, game.available_actions()), game.available_actions())

    def test_explicit_pure_value_has_no_core(self):
        self.assertIsNone(NTupleValue(native=False).native)


if __name__ == "__main__":
    unittest.main()
