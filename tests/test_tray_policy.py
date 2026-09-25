"""
Testy `TrayPolicy` (#58): przeszukanie wyczerpujące bieżącej tacki z wiązką.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from pieces import PIECE_POOL
from policies import TrayPolicy

BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])
ONE_BY_ONE = next(p for p in PIECE_POOL if p.shape == [[1]])


class TestTrayPolicyDoesNotMutate(unittest.TestCase):
    """Kryterium: `act` nie woła `generator.next_pieces()` ani nie zmienia gry."""

    def test_game_state_unchanged_after_act(self):
        policy = TrayPolicy()
        for seed in (1, 7, 42):
            game = Game(seed=seed)
            before = game.get_state()
            actions = game.available_actions()
            policy.act(game, actions)
            after = game.get_state()
            self.assertEqual(before, after, "seed=%r" % (seed,))


class TestTrayPolicyReturnsLegalAction(unittest.TestCase):
    def test_action_is_available(self):
        policy = TrayPolicy()
        for seed in (2, 13, 99):
            game = Game(seed=seed)
            actions = game.available_actions()
            action = policy.act(game, actions)
            self.assertIn(action, actions, "seed=%r" % (seed,))


class TestTrayPolicyOrderMatters(unittest.TestCase):
    """Plansza ustawiona ręcznie: kolejność dwóch klocków tacki zmienia wynik.

    Wiersz 0 ma dwie puste komórki obok siebie (kolumny 3 i 4). `beam2` (poziomy
    1x2) postawiony tam jako pierwszy natychmiast czyści wiersz. Jeśli najpierw
    postawi się `1x1` w jedną z tych dwóch komórek, luka zwęża się do jednej
    komórki i `beam2` już nigdzie tego wiersza nie domknie — sekwencja daje
    dużo mniej punktów. `TrayPolicy` musi wybrać pierwszy ruch lepszej sekwencji:
    `beam2` na (3, 0).
    """

    def _game(self):
        game = Game(seed=5)
        game.board.grid = [[0] * 8 for _ in range(8)]
        for col in range(8):
            if col not in (3, 4):
                game.board.grid[0][col] = 1
        game.pieces = [BEAM2, ONE_BY_ONE, None]
        game.combo = 0
        game.combo_counter = 3
        return game

    def test_prefers_placing_beam2_first_to_clear_the_line(self):
        game = self._game()
        actions = game.available_actions()
        action = TrayPolicy().act(game, actions)
        self.assertEqual(action, (0, 3, 0))

    def test_worse_order_really_is_worse(self):
        # Sprawdza samo założenie testu, nie TrayPolicy: 1x1 najpierw blokuje czyszczenie.
        game = self._game()
        game.board.place_piece(ONE_BY_ONE, 3, 0)
        rows, cols = game.board.check_full_lines()
        self.assertEqual((rows, cols), ([], []), "1x1 na (3,0) nie powinien jeszcze czyścić")

        # Wariant beam2-first (na świeżej planszy): czyści od razu.
        game2 = self._game()
        game2.board.place_piece(BEAM2, 3, 0)
        rows2, cols2 = game2.board.check_full_lines()
        self.assertEqual(rows2, [0])
        self.assertEqual(cols2, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
