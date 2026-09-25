"""
Polityki grające, których używa benchmark.

Wszystkie są deterministyczne przy zadanym seedzie partii — benchmark mierzy,
co polityka umie, a nie jak wypada w trakcie nauki (#8).
"""
import random

from board import Board
from features import features
from scoring import COMBO_COUNTER_BASE, FULL_CLEAR_BONUS, clear_points, placement_points


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


class TrayPolicy:
    """Przeszukuje wyczerpująco bieżącą tackę (do 3 klocków, bez węzła losowego).

    Dla każdej kolejności postawienia pozostałych klocków tacki i każdej legalnej
    pozycji ocenia sekwencję jako `suma punktów po drodze + w · features(plansza
    końcowa)`, przenosząc combo i licznik wygaśnięcia przez całą sekwencję zgodnie
    z `game.apply_placement` (`game.py:67-101`). Gra pierwszy ruch najlepszej
    znalezionej sekwencji. Nigdy nie woła `generator.next_pieces()` ani nie
    mutuje przekazanej gry — pracuje wyłącznie na kopiach planszy i tacki.

    `beam` ogranicza liczbę stanów trzymanych na każdym poziomie przeszukiwania
    (uzasadnienie szerokości: `docs/przeszukanie-tacki.md`).
    """

    name = "tray"

    DEFAULT_WEIGHTS = HeuristicPolicy.DEFAULT_WEIGHTS
    DEFAULT_BEAM = 8

    def __init__(self, weights=None, beam=None):
        self.weights = tuple(weights) if weights is not None else self.DEFAULT_WEIGHTS
        self.beam = beam if beam is not None else self.DEFAULT_BEAM

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        pieces0 = tuple(game.pieces)
        depth = sum(1 for p in pieces0 if p is not None)
        if depth == 0 or not actions:
            return actions[0]

        root = {
            "board": game.board.copy(),
            "pieces": pieces0,
            "combo": game.combo,
            "combo_counter": game.combo_counter,
            "gain": 0,
            "first_action": None,
        }
        frontier = [root]

        for level in range(depth):
            level_actions = actions if level == 0 else None
            candidates = []
            for state in frontier:
                legal = level_actions if level_actions is not None else _tray_legal_actions(
                    state["board"], state["pieces"]
                )
                if not legal:
                    candidates.append(state)
                    continue
                for action in legal:
                    candidates.append(_expand(state, action))
            for candidate in candidates:
                candidate["score"] = candidate["gain"] + _weighted_features(
                    self.weights, candidate["board"]
                )
            candidates.sort(key=lambda c: c["score"], reverse=True)
            frontier = candidates[: self.beam]

        best = max(frontier, key=lambda c: c["score"])
        return best["first_action"]


def _weighted_features(weights, board):
    return sum(w * f for w, f in zip(weights, features(board)))


def _tray_legal_actions(board, pieces):
    """Legalne `(idx, x, y)` dla nieużytych jeszcze klocków tacki na danej planszy.

    Ten sam wzór co `Game.available_actions` (`game.py:36-45`), ale bez czytania
    stanu gry — działa na przekazanej kopii planszy i tacki.
    """
    actions = []
    for idx, piece in enumerate(pieces):
        if piece is None:
            continue
        for y in range(Board.HEIGHT - len(piece.shape) + 1):
            for x in range(Board.WIDTH - len(piece.shape[0]) + 1):
                if board.can_place_piece(piece, x, y):
                    actions.append((idx, x, y))
    return actions


def _expand(state, action):
    """Jeden krok symulowanej sekwencji: postawienie `action` na kopii stanu `state`.

    Kopiuje wzorzec `Game.apply_placement` (`game.py:67-101`) na kopii planszy i
    tacki, wliczając próg wygaśnięcia combo — bez wołania generatora ani
    dotykania oryginalnej gry.
    """
    idx, x, y = action
    piece = state["pieces"][idx]
    board = state["board"].copy()
    board.place_piece(piece, x, y)

    gained = placement_points(piece)
    rows, cols = board.check_full_lines()
    lines = len(rows) + len(cols)

    pieces = list(state["pieces"])
    pieces[idx] = None
    remaining = sum(1 for p in pieces if p is not None)

    combo, combo_counter = state["combo"], state["combo_counter"]
    if lines > 0:
        combo += 1
        combo_counter = COMBO_COUNTER_BASE + remaining
        gained += clear_points(combo, lines)
    elif combo_counter <= 1:
        combo = 0
        combo_counter = COMBO_COUNTER_BASE
    else:
        combo_counter -= 1

    board.clear_lines(rows, cols)
    if not any(any(row) for row in board.grid):
        gained += FULL_CLEAR_BONUS

    return {
        "board": board,
        "pieces": tuple(pieces),
        "combo": combo,
        "combo_counter": combo_counter,
        "gain": state["gain"] + gained,
        "first_action": state["first_action"] or action,
    }


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
