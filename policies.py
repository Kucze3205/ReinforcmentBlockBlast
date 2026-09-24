"""
Polityki grające, których używa benchmark.

Wszystkie są deterministyczne przy zadanym seedzie partii — benchmark mierzy,
co polityka umie, a nie jak wypada w trakcie nauki (#8).
"""
import random

from board import Board
from scoring import clear_points, placement_points


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


def _immediate_gain(game, action):
    """Punkty, które da to postawienie — wg skalibrowanego wzoru, bez zmiany stanu gry."""
    idx, x, y = action
    piece = game.pieces[idx]
    board = game.board.copy()
    board.place_piece(piece, x, y)

    gain = placement_points(piece)
    rows, cols = board.check_full_lines()
    lines = len(rows) + len(cols)
    if lines > 0:
        gain += clear_points(game.combo + lines, lines)
    return gain


class FillPolicy:
    """Zapycha planszę (#37): zamiast punktów maksymalizuje szansę, że ślepo dobrana tacka nie wejdzie.

    Cel to plansza, na której losowa tacka jest niegrywalna w kilku procentach,
    bo dopiero tam da się rozstrzygnąć, czy gra takie tacki tłumi. Ograniczenie:
    reszta bieżącej tacki musi dać się postawić w całości, inaczej polityka
    przegrałaby, zanim gra dobierze następną. Dopiero to ograniczenie odróżnia
    zapychanie od samobójstwa.
    """

    name = "fill"

    def __init__(self, samples=48, whole=True):
        self.whole = whole
        from playability import sample_trays
        self.trays = sample_trays(samples)

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        from playability import all_fit, clear, p_dead, placements, key, to_mask
        mask = to_mask(game.board.grid)
        best, best_score = actions[0], None
        for idx, x, y in actions:
            piece = game.pieces[idx]
            place = sum(1 << (8 * (y + dy) + x + dx)
                        for dy, row in enumerate(piece.shape) for dx, c in enumerate(row) if c)
            after = clear(mask | place)
            rest = [p.shape for i, p in enumerate(game.pieces) if p is not None and i != idx]
            alive = all_fit(after, rest)
            score = (alive, p_dead(after, self.trays, whole=self.whole), bin(after).count("1"))
            if best_score is None or score > best_score:
                best, best_score = (idx, x, y), score
        return best
