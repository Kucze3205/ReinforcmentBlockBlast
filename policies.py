"""
Polityki grające, których używa benchmark.

Wszystkie są deterministyczne przy zadanym seedzie partii — benchmark mierzy,
co polityka umie, a nie jak wypada w trakcie nauki (#8).
"""
import random

from board import Board
from features import features
from scoring import FULL_CLEAR_BONUS, clear_points, placement_points


class RandomPolicy:
    """Jednostajnie po dostępnych ruchach. Dolna granica odniesienia."""

    name = "random"

    def __init__(self, seed=0):
        self._seed = seed

    def reset(self, game_seed):
        self.rng = random.Random(f"{self._seed}:{game_seed}")

    def act(self, game, actions):
        return self.rng.choice(actions)


class GreedyPolicy:
    """Maksymalizuje punkty z bieżącego postawienia (jeden pół-ruch w przód)."""

    name = "greedy"

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        best, best_gain = actions[0], None
        for action in actions:
            gain = _immediate_gain(game, action)
            if best_gain is None or gain > best_gain:
                best, best_gain = action, gain
        return best


class HeuristicPolicy:
    """Wybiera postawienie po `immediate_gain + w · features(plansza po postawieniu)`.

    Wagi są dobrane ręcznie, na oko (uzasadnienie: `docs/cechy-planszy.md`) — to
    fundament pod przyszłe strojenie, nie rekord.
    """

    name = "heuristic"

    # Kolejność zgodna z features.FEATURE_NAMES.
    DEFAULT_WEIGHTS = (
        -0.5,   # occupied_cells
        -10.0,  # surrounded_empty
        -2.0,   # empty_regions
        1.0,    # largest_empty_rect
        3.0,    # near_full_lines
        0.5,    # placeable_shapes
    )

    def __init__(self, weights=None):
        self.weights = tuple(weights) if weights is not None else self.DEFAULT_WEIGHTS

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        best, best_score = actions[0], None
        for action in actions:
            gain, board = _simulate_placement(game, action)
            score = gain + sum(w * f for w, f in zip(self.weights, features(board)))
            if best_score is None or score > best_score:
                best, best_score = action, score
        return best


class ModelPolicy:
    """Wytrenowana sieć w trybie deterministycznym (ε = 0)."""

    def __init__(self, agent, name):
        self.agent = agent
        self.name = name

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        grid, shapes, numeric, _ = self.agent.get_state(game)
        move = self.agent.get_action((grid, shapes, numeric), epsilon=0.0)
        return tuple(move)


def _simulate_placement(game, action):
    """Postawienie na kopii planszy, bez dotykania stanu gry.

    Zwraca `(przyrost punktów, plansza po postawieniu i ewentualnym czyszczeniu)`.
    """
    idx, x, y = action
    piece = game.pieces[idx]
    board = game.board.copy()
    board.place_piece(piece, x, y)

    gain = placement_points(piece)
    rows, cols = board.check_full_lines()
    lines = len(rows) + len(cols)
    if lines > 0:
        gain += clear_points(game.combo + 1, lines)
        board.clear_lines(rows, cols)
        if not any(any(row) for row in board.grid):
            gain += FULL_CLEAR_BONUS
    return gain, board


def _immediate_gain(game, action):
    """Punkty, które da to postawienie — wg skalibrowanego wzoru, bez zmiany stanu gry."""
    gain, _ = _simulate_placement(game, action)
    return gain
