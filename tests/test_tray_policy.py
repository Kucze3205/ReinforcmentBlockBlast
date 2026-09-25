"""
Testy `TrayPolicy` (#58): przeszukanie wyczerpujące bieżącej tacki z wiązką.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import policies
from board import Board
from game import Game
from pieces import PIECE_POOL, PIECE_TYPES
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


_WIDTH = Board.WIDTH
_HEIGHT = Board.HEIGHT


def _pre88_occupied_cells(grid):
    return sum(1 for row in grid for cell in row if cell)


def _pre88_surrounded_empty(grid):
    count = 0
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            if grid[y][x]:
                continue
            up = grid[y - 1][x] if y > 0 else 1
            down = grid[y + 1][x] if y < _HEIGHT - 1 else 1
            left = grid[y][x - 1] if x > 0 else 1
            right = grid[y][x + 1] if x < _WIDTH - 1 else 1
            if up and down and left and right:
                count += 1
    return count


def _pre88_empty_regions(grid):
    seen = [[False] * _WIDTH for _ in range(_HEIGHT)]
    regions = 0
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            if grid[y][x] or seen[y][x]:
                continue
            regions += 1
            stack = [(y, x)]
            seen[y][x] = True
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < _HEIGHT and 0 <= nx < _WIDTH and not grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
    return regions


def _pre88_largest_rect_in_histogram(heights):
    stack = []
    best = 0
    extended = list(heights) + [0]
    for i, h in enumerate(extended):
        while stack and extended[stack[-1]] > h:
            height = extended[stack.pop()]
            width = i if not stack else i - stack[-1] - 1
            best = max(best, height * width)
        stack.append(i)
    return best


def _pre88_largest_empty_rectangle(grid):
    heights = [0] * _WIDTH
    best = 0
    for y in range(_HEIGHT):
        for x in range(_WIDTH):
            heights[x] = 0 if grid[y][x] else heights[x] + 1
        best = max(best, _pre88_largest_rect_in_histogram(heights))
    return best


def _pre88_near_full_lines(grid):
    count = 0
    for y in range(_HEIGHT):
        if _WIDTH - sum(grid[y]) <= 2:
            count += 1
    for x in range(_WIDTH):
        if _HEIGHT - sum(grid[y][x] for y in range(_HEIGHT)) <= 2:
            count += 1
    return count


def _pre88_can_place_anywhere(board, piece):
    shape = piece.shape
    h, w = len(shape), len(shape[0])
    for y in range(_HEIGHT - h + 1):
        for x in range(_WIDTH - w + 1):
            if board.can_place_piece(piece, x, y):
                return True
    return False


def _pre88_placeable_shapes(board):
    count = 0
    for pose_indices in PIECE_TYPES:
        if any(_pre88_can_place_anywhere(board, PIECE_POOL[idx]) for idx in pose_indices):
            count += 1
    return count


def _pre88_features(board):
    """Kopia `features.features()` sprzed #88 (zagnieżdżone listy zamiast masek
    bitowych) — punkt odniesienia testu równoważności decyzji poniżej."""
    grid = board.grid
    return (
        _pre88_occupied_cells(grid),
        _pre88_surrounded_empty(grid),
        _pre88_empty_regions(grid),
        _pre88_largest_empty_rectangle(grid),
        _pre88_near_full_lines(grid),
        _pre88_placeable_shapes(board),
    )


class TestTrayPolicySpeedupPreservesDecisions(unittest.TestCase):
    """#88: `features.py` przyspieszony (maski bitowe zamiast zagnieżdżonych list)
    musi wybierać dokładnie te same akcje co implementacja sprzed zmiany
    (`_pre88_features` powyżej), na obu zestawach wag używanych przez benchmark.
    """

    SEEDS = tuple(range(3001, 3007))  # rozłączne z seedami reszty tego pliku
    MOVE_CAP = 250  # bezpiecznik; śr. przeżycie przy beam=8 to ~90 postawień (#79)

    def _play(self, weights):
        sequences = []
        for seed in self.SEEDS:
            game = Game(seed=seed)
            policy = TrayPolicy(weights=weights)
            policy.reset(seed)
            moves = []
            n = 0
            while not game.done and n < self.MOVE_CAP:
                actions = game.available_actions()
                if not actions:
                    break
                action = policy.act(game, actions)
                moves.append(action)
                game.step(action)
                n += 1
            sequences.append(tuple(moves))
        return tuple(sequences)

    def _assert_same_sequences(self, weights):
        original_features = policies.features
        try:
            policies.features = _pre88_features
            before = self._play(weights)
        finally:
            policies.features = original_features
        after = self._play(weights)
        self.assertEqual(before, after)

    def test_default_weights(self):
        self._assert_same_sequences(None)

    def test_trained_weights_from_weights_json(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "weights.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        self._assert_same_sequences(tuple(data["weights"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
