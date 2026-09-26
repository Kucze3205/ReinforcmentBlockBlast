"""
Polityki grające, których używa benchmark.

Wszystkie są deterministyczne przy zadanym seedzie partii — benchmark mierzy,
co polityka umie, a nie jak wypada w trakcie nauki (#8).
"""
import random

from board import Board
from features import features
from generator import Generator
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
    (uzasadnienie szerokości i wartości domyślnej: `docs/przeszukanie-tacki.md`, #79).

    Po każdym `act` atrybut `last_expanded` niesie sumę kandydatów rozwiniętych na
    wszystkich poziomach tej decyzji (przed przycięciem do `beam`) — miarę
    rozgałęzienia sekwencji, używaną przez `tools/measure_tray_cost.py`.
    """

    name = "tray"

    DEFAULT_WEIGHTS = HeuristicPolicy.DEFAULT_WEIGHTS
    # 8: kompromis jakość/czas zmierzony w #79 — patrz docs/przeszukanie-tacki.md.
    DEFAULT_BEAM = 8

    def __init__(self, weights=None, beam=None):
        self.weights = tuple(weights) if weights is not None else self.DEFAULT_WEIGHTS
        self.beam = beam if beam is not None else self.DEFAULT_BEAM
        self.last_expanded = 0

    def reset(self, game_seed):
        pass

    def act(self, game, actions):
        pieces0 = tuple(game.pieces)
        depth = sum(1 for p in pieces0 if p is not None)
        self.last_expanded = 0
        if depth == 0 or not actions:
            return actions[0]

        frontier, expanded = _tray_beam_search(
            game.board, pieces0, game.combo, game.combo_counter,
            self.weights, self.beam, root_actions=actions,
        )
        self.last_expanded = expanded
        best = max(frontier, key=lambda c: c["score"])
        return best["first_action"]


class LookaheadPolicy:
    """`TrayPolicy` plus jeden poziom za bieżącą tacką: węzeł losowy nad następną (#92).

    Poziom pierwszy jest **dokładnie** przeszukaniem `TrayPolicy` (ta sama funkcja
    `_tray_beam_search`, ta sama `beam`): rozwija bieżącą tackę do końca, czyli do
    stanów, w których gra sięgnęłaby po nową tackę (`game.apply_placement`
    odświeża tackę po trzecim postawieniu, `game.py:96-98`). Dokładnie w tym
    miejscu siedzi węzeł losowy.

    Na `branch` najlepszych stanów końcowych — po jednym na **odrębną pierwszą
    akcję**, bo decyzja dotyczy tylko pierwszego ruchu — losuje `samples` tacek z
    `generator.Generator`, czyli z tego samego rozkładu, którego używa gra, i dla
    każdej pary (stan, tacka) robi płytsze przeszukanie (`inner_beam`,
    `inner_depth` poziomów). Wartość kandydata to

        punkty zdobyte po drodze + średnia po próbkach z (punkty z następnej tacki
        + w · features(plansza po niej))

    czyli oczekiwana wartość po węźle losowym — expectimax z estymatorem Monte
    Carlo zamiast pełnej sumy po 15³ tackach.

    Tacka, której **nie da się postawić**, kończy partię (`game._can_place_any`,
    `game.py:103-111`); takie próbki dostają `death_penalty` do wartości. To jest
    główny powód, dla którego ten poziom w ogóle ma coś kupić: pozwala odrzucić
    planszę, która wygląda dobrze w cechach, a jest pułapką na losową tackę.
    Kara jest wyłącznie wewnętrzną wyceną polityki — nagrody `game.step` nie
    dotyka (#92).

    Losowanie jest deterministyczne względem `reset(game_seed)`: osobna instancja
    `Generator` z ziarnem wyprowadzonym z seeda partii, nigdy generator gry —
    `act` nie dotyka stanu gry (#58).

    Dobór wartości domyślnych i ich zmierzony koszt: `docs/lookahead.md`.
    """

    name = "lookahead"

    DEFAULT_WEIGHTS = HeuristicPolicy.DEFAULT_WEIGHTS
    DEFAULT_BEAM = TrayPolicy.DEFAULT_BEAM
    # Wartości domyślne wybrane z tabeli pomiarowej w docs/lookahead.md pod
    # twardy limit 1800 s na ramię 600 partii (#92).
    DEFAULT_SAMPLES = 3
    DEFAULT_BRANCH = 3
    DEFAULT_INNER_BEAM = 1
    DEFAULT_INNER_DEPTH = 1
    DEFAULT_DEATH_PENALTY = -200.0

    def __init__(self, weights=None, beam=None, samples=None, branch=None,
                 inner_beam=None, inner_depth=None, death_penalty=None, seed=0):
        self.weights = tuple(weights) if weights is not None else self.DEFAULT_WEIGHTS
        self.beam = beam if beam is not None else self.DEFAULT_BEAM
        self.samples = samples if samples is not None else self.DEFAULT_SAMPLES
        self.branch = branch if branch is not None else self.DEFAULT_BRANCH
        self.inner_beam = inner_beam if inner_beam is not None else self.DEFAULT_INNER_BEAM
        self.inner_depth = inner_depth if inner_depth is not None else self.DEFAULT_INNER_DEPTH
        self.death_penalty = (
            death_penalty if death_penalty is not None else self.DEFAULT_DEATH_PENALTY
        )
        self._seed = seed
        self.last_expanded = 0
        self.reset(None)

    def reset(self, game_seed):
        # Własny generator próbek — gra swojego nie oddaje, a wspólny byłby
        # podglądaniem przyszłości zamiast losowania z rozkładu.
        self._sampler = Generator(seed="lookahead:%r:%r" % (self._seed, game_seed))

    def act(self, game, actions):
        pieces0 = tuple(game.pieces)
        depth = sum(1 for p in pieces0 if p is not None)
        self.last_expanded = 0
        if depth == 0 or not actions:
            return actions[0]

        frontier, expanded = _tray_beam_search(
            game.board, pieces0, game.combo, game.combo_counter,
            self.weights, self.beam, root_actions=actions,
        )
        self.last_expanded = expanded

        candidates = self._distinct_first_actions(frontier)
        if self.samples <= 0 or len(candidates) < 2:
            return max(frontier, key=lambda c: c["score"])["first_action"]

        trays = [tuple(self._sampler.next_pieces()) for _ in range(self.samples)]
        best_action, best_value = None, None
        for state in candidates:
            total = 0.0
            for tray in trays:
                inner, inner_expanded = _tray_beam_search(
                    state["board"], tray, state["combo"], state["combo_counter"],
                    self.weights, self.inner_beam, depth=self.inner_depth,
                    death_penalty=self.death_penalty,
                )
                self.last_expanded += inner_expanded
                total += max(inner, key=lambda c: c["score"])["score"]
            value = state["gain"] + total / len(trays)
            if best_value is None or value > best_value:
                best_action, best_value = state["first_action"], value
        return best_action

    def _distinct_first_actions(self, frontier):
        """Najlepszy stan końcowy na każdą odrębną pierwszą akcję, do `branch` sztuk.

        Bez tego wiązka potrafi oddać `beam` wariantów **tej samej** pierwszej
        akcji — drugi poziom liczyłby się wtedy po kilka razy dla jednego ruchu
        i nie rozstrzygałby niczego.
        """
        out, seen = [], set()
        for state in sorted(frontier, key=lambda c: c["score"], reverse=True):
            action = state["first_action"]
            if action in seen:
                continue
            seen.add(action)
            out.append(state)
            if len(out) >= self.branch:
                break
        return out


def _tray_beam_search(board, pieces, combo, combo_counter, weights, beam,
                      root_actions=None, depth=None, death_penalty=None):
    """Wiązka po sekwencjach postawień z tacki `pieces` na kopii `board`.

    Serce `TrayPolicy` (#58) i pierwszego poziomu `LookaheadPolicy` (#92) —
    wyniesione tutaj, żeby obie polityki liczyły **dokładnie to samo**, łącznie
    z kolejnością kandydatów, od której zależy rozstrzyganie remisów
    (`list.sort` jest stabilny).

    Zwraca `(wiązka po ostatnim poziomie, liczba kandydatów rozwiniętych łącznie
    przed przycięciem)`. Każdy stan wiązki ma pole `score`.

    - `root_actions` — gotowa lista legalnych akcji na poziom 0 (gra już ją
      policzyła, nie ma po co liczyć jej drugi raz).
    - `depth` — ile poziomów rozwinąć; domyślnie tyle, ile klocków zostało w tacce.
    - `death_penalty` — gdy podane, stan bez legalnego ruchu (a więc koniec
      partii: `game._can_place_any`) dostaje tę karę do `score`. `None` = zachowanie
      `TrayPolicy`, która o śmierci nie wie.
    """
    root = {
        "board": board.copy(),
        "pieces": tuple(pieces),
        "combo": combo,
        "combo_counter": combo_counter,
        "gain": 0,
        "first_action": None,
        "dead": False,
    }
    frontier = [root]
    expanded = 0

    levels = depth if depth is not None else sum(1 for p in root["pieces"] if p is not None)
    for level in range(levels):
        level_actions = root_actions if level == 0 and root_actions is not None else None
        candidates = []
        for state in frontier:
            legal = level_actions if level_actions is not None else _tray_legal_actions(
                state["board"], state["pieces"]
            )
            if not legal:
                if any(p is not None for p in state["pieces"]):
                    state["dead"] = True
                candidates.append(state)
                continue
            for action in legal:
                candidates.append(_expand(state, action))
        expanded += len(candidates)
        _score_all(candidates, weights, death_penalty)
        candidates.sort(key=lambda c: c["score"], reverse=True)
        frontier = candidates[:beam]

    if levels == 0:
        _score_all(frontier, weights, death_penalty)
    return frontier, expanded


def _score_all(candidates, weights, death_penalty):
    if death_penalty is None:
        for candidate in candidates:
            candidate["score"] = candidate["gain"] + _weighted_features(
                weights, candidate["board"]
            )
        return
    for candidate in candidates:
        candidate["score"] = candidate["gain"] + _weighted_features(
            weights, candidate["board"]
        )
        if candidate["dead"]:
            candidate["score"] += death_penalty


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
        "dead": False,
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
