"""
Block Blast Engine Test Suite

Testy pilnują kalibracji pod wzór referencyjny z badania #2. Każdy test, który
sprawdza liczbę, jest przywiązany do konkretnej rozbieżności (R-1..R-10), żeby
regresja wskazywała, co dokładnie się rozjechało.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from generator import Generator
from pieces import Piece, CANONICAL_TYPES, EXPECTED_POSES, PIECE_POOL, PIECE_TYPES, plausible
from scoring import clear_points, combo_unit, line_bonus, placement_points

ONE_BY_ONE = PIECE_POOL[0]


def row_full_except(game, x, filler=False):
    """Plansza z wierszem 0 pełnym poza kolumną x — jedno postawienie czyści jedną linię.

    `filler` zostawia komórkę poza wierszem 0, żeby plansza nie zrobiła się pusta
    i nie doliczył się bonus za pełne czyszczenie (osobny test).
    """
    game.board.grid = [[0] * 8 for _ in range(8)]
    for col in range(8):
        game.board.grid[0][col] = 1
    game.board.grid[0][x] = 0
    if filler:
        game.board.grid[7][0] = 1


def place_1x1(game, x, y):
    game.pieces = [ONE_BY_ONE, None, None]
    game.round_placement = 2  # kolejne postawienie domyka tackę
    game.board.place_piece(ONE_BY_ONE, x, y)
    return game.apply_placement(0)


class TestScoringFormula(unittest.TestCase):
    """R-1: bonus bazowy to 10*l*(l-1), a nie 10*k^2."""

    def test_placement_points_are_cell_count(self):
        for piece in PIECE_POOL:
            cells = sum(sum(row) for row in piece.shape)
            self.assertEqual(placement_points(piece), cells)

    def test_line_bonus_matches_reference(self):
        self.assertEqual(line_bonus(0), 0)
        self.assertEqual(line_bonus(1), 10)
        self.assertEqual(line_bonus(2), 20)
        self.assertEqual(line_bonus(3), 60)

    def test_five_and_six_lines_give_the_two_repeated_numbers(self):
        # 200 i 300 to jedyne dwie liczby, które poradniki powtarzają niezależnie.
        self.assertEqual(line_bonus(5), 200)
        self.assertEqual(line_bonus(6), 300)

    def test_combo_multiplies_the_bonus(self):
        # R-2: combo jest mnożnikiem całego bonusu, nie dodatkiem.
        self.assertEqual(clear_points(1, 2), 20)
        self.assertEqual(clear_points(3, 2), 60)
        self.assertEqual(clear_points(0, 2), 0)

    def test_ladder_has_three_steps_and_no_fourth(self):
        # #33: 10 (combo 1-5), 15 (6-10), 20 od 11 - trzyma do combo 39 zmierzonego w apce.
        self.assertEqual([combo_unit(c) for c in (1, 5, 6, 10, 11, 16, 17, 39, 100)],
                         [10, 10, 15, 15, 20, 20, 20, 20, 20])
        self.assertEqual(clear_points(30, 1), 30 * 20)     # przebieg 35879525460, ruch 126
        self.assertEqual(clear_points(21, 2), 21 * 40)     # ruch 111: 843 = 3 komorki + 840
        self.assertEqual(clear_points(4, 4), 4 * 10 * 12)  # cztery linie od combo 0: 480


class TestComboMechanics(unittest.TestCase):
    def setUp(self):
        self.game = Game(seed=42)

    def test_combo_rises_per_placement_not_per_tray(self):
        # R-3: combo aktualizuje się po każdym postawieniu.
        row_full_except(self.game, 7, filler=True)
        gained = place_1x1(self.game, 7, 0)
        self.assertEqual(self.game.combo, 1)
        self.assertEqual(gained, 1 + 1 * 10)

        row_full_except(self.game, 7, filler=True)
        gained = place_1x1(self.game, 7, 0)
        self.assertEqual(self.game.combo, 2)
        self.assertEqual(gained, 1 + 2 * 10)

    def test_combo_rises_by_lines_cleared_not_by_one(self):
        # #33: dwie linie w jednym ruchu to +2 combo (zmierzone w apce: 46 -> 66 przy ruchu 131).
        game = self.game
        game.board.grid = [[0] * 8 for _ in range(8)]
        for col in range(1, 8):
            game.board.grid[0][col] = 1
            game.board.grid[1][col] = 1
        game.board.grid[7][7] = 1  # filler: plansza nie moze zostac pusta
        game.pieces = [Piece([[1], [1]], "v2", 0), None, None]
        game.round_placement = 2
        game.board.place_piece(game.pieces[0], 0, 0)
        gained = game.apply_placement(0)
        self.assertEqual(game.combo, 2)
        self.assertEqual(gained, 2 + 2 * 20)

    def test_combo_survives_two_placements_then_dies(self):
        # R-4: combo wygasa przez licznik, nie natychmiast.
        row_full_except(self.game, 7, filler=True)
        place_1x1(self.game, 7, 0)
        self.assertEqual(self.game.combo, 1)

        for placement in range(2):
            place_1x1(self.game, placement, 5)
            self.assertEqual(self.game.combo, 1, "combo zginęło za wcześnie")

        place_1x1(self.game, 2, 5)
        self.assertEqual(self.game.combo, 0, "combo powinno zginąć przy trzecim postawieniu")

    def test_full_clear_bez_bonusu(self):
        # Z-4 zmierzone na oryginale (#30): za opróżnienie planszy nie ma nic.
        # Źródła referencyjne dawały 300, więc test pilnuje, by bonus nie wrócił.
        row_full_except(self.game, 7)
        gained = place_1x1(self.game, 7, 0)
        # 1 komórka + combo 1 x B(1), i nic za pustą planszę
        self.assertEqual(gained, 1 + 10)


class TestScoreAccumulates(unittest.TestCase):
    """Warunek wstępny #8 nr 1: bez tego benchmark nie ma czego czytać."""

    def test_score_is_cumulative(self):
        game = Game(seed=7)
        running = 0
        for _ in range(10):
            actions = game.available_actions()
            if not actions or game.done:
                break
            gained, score, _, _ = game.step(actions[0])
            running += gained
            self.assertEqual(score, running)
        self.assertGreater(game.score, 10)

    def test_placements_count_survival(self):
        game = Game(seed=7)
        moves = 0
        while not game.done:
            actions = game.available_actions()
            if not actions:
                break
            game.step(actions[0])
            moves += 1
        self.assertEqual(game.placements, moves)


class TestGenerator(unittest.TestCase):
    """Warunek wstępny #8 nr 2: R-9 — seed był ignorowany."""

    def test_same_seed_gives_same_pieces(self):
        a = [p.name for p in Generator(99).next_pieces()]
        b = [p.name for p in Generator(99).next_pieces()]
        self.assertEqual(a, b)

    def test_different_seeds_diverge(self):
        streams = set()
        for seed in range(20):
            gen = Generator(seed)
            streams.add(tuple(p.name for p in gen.next_pieces()))
        self.assertGreater(len(streams), 1)

    def test_whole_game_is_reproducible(self):
        def play(seed):
            game = Game(seed=seed)
            while not game.done:
                actions = game.available_actions()
                if not actions:
                    break
                game.step(actions[0])
            return game.score, game.placements

        self.assertEqual(play(2024), play(2024))


class TestPiecePool(unittest.TestCase):
    """R-6, R-7, R-8: pula i rozkład losowania."""

    def test_pool_has_41_poses(self):
        self.assertEqual(len(PIECE_POOL), EXPECTED_POSES)

    def test_no_duplicate_shapes(self):
        # R-7: "O" i "2x2" były tym samym klockiem, przez co 2x2 wypadał 2x częściej.
        shapes = [tuple(tuple(row) for row in p.shape) for p in PIECE_POOL]
        self.assertEqual(len(shapes), len(set(shapes)))

    def test_orientation_counts_match_reference(self):
        expected = {
            "1x1": 1, "beam2": 2, "beam3": 2, "beam4": 2, "beam5": 2,
            "square2": 1, "rect23": 2, "square3": 1, "corner3": 4,
            "L": 8, "corner5": 4, "diag2": 2, "diag3": 2, "S": 4, "T": 4,
        }
        actual = {
            name: len(PIECE_TYPES[i]) for i, (name, _) in enumerate(CANONICAL_TYPES)
        }
        self.assertEqual(actual, expected)

    def test_sampling_is_uniform_over_types_not_poses(self):
        # R-8: typ 3x3 (1 orientacja) musi wypadać ~8x częściej niż konkretna poza L.
        gen = Generator(1234)
        counts = {}
        for _ in range(20000):
            piece = gen._next_piece()
            counts[piece.name] = counts.get(piece.name, 0) + 1
        square3 = counts.get("square3", 0)
        l_pose = counts.get("L-0", 0)
        self.assertGreater(square3 / max(l_pose, 1), 5.0)


class TestBenchmarkPrerequisites(unittest.TestCase):
    """Warunek wstępny #8 nr 3: agent musi umieć grać deterministycznie."""

    def test_agent_accepts_epsilon_zero(self):
        from agent import Agent

        agent = Agent()
        game = Game(seed=5)
        state = agent.get_state(game)
        agent.get_action(state[:3], epsilon=0.0)
        self.assertEqual(agent.epsilon, 0.0)


class TestOdczytTacki(unittest.TestCase):
    """Filtr wiarygodności odczytu ze slotu tacki (#30).

    Pomiar puli klocków (Z-5) polega na tym, że kształt spoza puli jest wynikiem.
    Filtr, który odrzucałby prawdziwe klocki, ukryłby właśnie ten wynik — a filtr,
    który przepuszcza śmieci, zaleje pomiar kształtami, których gra nigdy nie dała.
    """

    def test_przepuszcza_kazda_poz_z_puli(self):
        for piece in PIECE_POOL:
            self.assertTrue(plausible(piece.shape), f"odrzucony prawdziwy klocek {piece.name}")

    def test_odrzuca_odczyt_launchera(self):
        # Dosłowny odczyt z przebiegu 35610307974, ruch 19: gra zniknęła z pierwszego
        # planu, segmentacja przeczytała pulpit. Bez tego filtra wchodził do puli.
        blob = [[0, 0, 0, 0, 0, 0, 1], [0, 0, 0, 1, 0, 0, 1]]
        self.assertFalse(plausible(blob))


if __name__ == "__main__":
    unittest.main(verbosity=2)
