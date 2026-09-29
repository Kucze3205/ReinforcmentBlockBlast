"""
#186: generator.py losuje typ kanoniczny wg wag zmierzonych z mostu, nie 1/15.
Wagi i metoda: docs/generator-wagi-typow.md, dane: docs/data/z6-pary.json.

#217: generator.py świadomy planszy (opt-in przez `board=`) — model wybrany
w docs/z6-model-generatora.md ("M2-simple": wagi bez zmian, odrzucanie "do
skutku"). Testy niżej: przełącznik `legacy` odtwarza starą sekwencję bit w
bit, i świadomy generator nie zwraca tacki nieukładalnej na planszy, na
której grywalna tacka istnieje.
"""
import math
import os
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board import tray_playable
from game import Game
from generator import Generator, PIECE_TYPE_WEIGHTS, REJECT_MAX_ATTEMPTS
from pieces import CANONICAL_TYPES, PIECE_TYPES
from policies import GreedyPolicy

N_DRAWS = 120000
SEED = 20260928


class TestWeightedTypeSampling(unittest.TestCase):
    def test_frequencies_match_calibrated_weights(self):
        gen = Generator(SEED)
        counts = Counter()
        for _ in range(N_DRAWS):
            counts[gen._next_piece().type_index] += 1

        total_weight = sum(PIECE_TYPE_WEIGHTS)
        for t, (name, _) in enumerate(CANONICAL_TYPES):
            expected_p = PIECE_TYPE_WEIGHTS[t] / total_weight
            expected = expected_p * N_DRAWS
            std = math.sqrt(N_DRAWS * expected_p * (1 - expected_p))
            observed = counts.get(t, 0)
            # 6 odchyleń standardowych: przy 15 typach i jednym uruchomieniu
            # testu szansa fałszywego alarmu jest znikoma, a i tak wykrywa
            # pomyłkę rzędu "1/15 zamiast wagi" (odchylenie o dziesiątki std).
            self.assertLess(
                abs(observed - expected), 6 * std,
                f"typ {name}: obs={observed} exp={expected:.1f} std={std:.1f}",
            )

    def test_orientation_within_type_stays_uniform(self):
        # Orientacja pozostaje 1/n (Cel #186 - zmieniają się tylko wagi typów).
        gen = Generator(SEED)
        pose_counts = Counter()
        for _ in range(N_DRAWS):
            pose_counts[gen._next_piece().index] += 1

        # corner5 (4 poz, waga umiarkowana) - poz powinny być ~równe między sobą.
        type_index = next(i for i, (n, _) in enumerate(CANONICAL_TYPES) if n == "corner5")
        pose_indices = PIECE_TYPES[type_index]
        counts = [pose_counts.get(i, 0) for i in pose_indices]
        mean = sum(counts) / len(counts)
        for c in counts:
            self.assertLess(abs(c - mean) / mean, 0.15)

    def test_same_seed_gives_same_sequence(self):
        a = [gen_piece.name for gen_piece in _draw_many(Generator(7), 5000)]
        b = [gen_piece.name for gen_piece in _draw_many(Generator(7), 5000)]
        self.assertEqual(a, b)


def _draw_many(gen, n):
    return [gen._next_piece() for _ in range(n)]


def _mid_game_board(seed="z6-217-hard-board", n_placements=140):
    """Plansza z prawdziwej partii (GreedyPolicy, deterministyczna) — ta sama
    metoda co próbkowanie plansz w tools/z6_model.py, żeby test opierał się na
    realistycznym stanie, nie na ręcznie sklejonej planszy o niejasnym `pi`."""
    game = Game(seed=seed)
    policy = GreedyPolicy()
    policy.reset(seed)
    while not game.done and game.placements < n_placements:
        actions = game.available_actions()
        if not actions:
            break
        game.step(policy.act(game, actions))
    return game.board


class TestBoardAwareGenerator(unittest.TestCase):
    """#217: `Generator(seed, board=...)` — opt-in, testy budżetowe
    `tests/test_generator_weights.py`/`tests/test_engine.py`."""

    N_SEEDS = 200

    def test_board_none_is_unaffected(self):
        # Zachowanie bez planszy (jak dziś wywołują `game.py`/`policies.py`)
        # ma zostać dokładnie takie samo -- to NIE jest osobna ścieżka kodu,
        # tylko brak `self.board`, ale sprawdzamy jawnie jako zaporę.
        for seed in range(10):
            a = [p.name for p in Generator(seed).next_pieces()]
            b = [p.name for p in Generator(seed, board=None).next_pieces()]
            self.assertEqual(a, b, f"seed={seed}")

    def test_legacy_switch_matches_old_sequence_bit_for_bit(self):
        board = _mid_game_board()
        for seed in range(30):
            blind = [p.name for p in Generator(seed).next_pieces()]
            legacy = [p.name for p in Generator(seed, board=board, legacy=True).next_pieces()]
            self.assertEqual(blind, legacy, f"seed={seed}")

    def test_aware_generator_avoids_unplayable_tray_when_playable_exists(self):
        board = _mid_game_board()
        n_unplayable_blind = 0
        n_unplayable_aware = 0
        for seed in range(self.N_SEEDS):
            blind_pieces = Generator(seed, board=board, legacy=True).next_pieces()
            if not tray_playable(board.grid, [p.shape for p in blind_pieces]):
                n_unplayable_blind += 1

            aware_pieces = Generator(seed, board=board).next_pieces()
            if not tray_playable(board.grid, [p.shape for p in aware_pieces]):
                n_unplayable_aware += 1

        # Zapora na sens testu: jeśli plansza jest tak łatwa, że ślepy generator
        # nigdy nie trafia tacki nieukładalnej, test niczego by nie odróżniał.
        self.assertGreater(n_unplayable_blind, 0, "plansza testowa za łatwa (zero trafień ślepego generatora)")
        self.assertEqual(n_unplayable_aware, 0)

    def test_reject_max_attempts_is_emergency_cap_not_reachable_on_easy_board(self):
        # Plansza pusta: pierwszy rzut jest prawie na pewno grywalny, więc
        # limit REJECT_MAX_ATTEMPTS nie powinien być w praktyce potrzebny --
        # to zapora, nie tryb normalnej pracy.
        empty_board = Game(seed=1).board
        for seed in range(50):
            pieces = Generator(seed, board=empty_board).next_pieces()
            self.assertTrue(tray_playable(empty_board.grid, [p.shape for p in pieces]))
        self.assertGreaterEqual(REJECT_MAX_ATTEMPTS, 1)


if __name__ == "__main__":
    unittest.main()
