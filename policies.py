"""
Polityki grające, których używa benchmark.

Wszystkie są deterministyczne przy zadanym seedzie partii — benchmark mierzy,
co polityka umie, a nie jak wypada w trakcie nauki (#8).
"""
import random

from board import Board
from features import FEATURE_NAMES, combo_features, features
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
    końcowa) + w_combo · combo_features(stan combo na końcu)`, przenosząc combo i
    licznik wygaśnięcia przez całą sekwencję zgodnie z `game.apply_placement`
    (`game.py:67-101`). Człon combo (#118) wycenia to, co łańcuch zarobi **za**
    horyzontem — bez niego liść wart był tyle samo przy combo 40 co przy combo 0
    (`docs/combo-w-ocenie.md`). Wagi combo, których w pliku wag nie ma, są zerami,
    więc wektor sześciu wag daje ocenę sprzed #118 co do bitu. Gra pierwszy ruch
    najlepszej znalezionej sekwencji. Nigdy nie woła `generator.next_pieces()` ani nie
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
        + w · features(plansza po niej) + w_combo · combo_features(stan combo po niej))

    czyli oczekiwana wartość po węźle losowym — expectimax z estymatorem Monte
    Carlo zamiast pełnej sumy po 15³ tackach.

    Co ten poziom kupuje: planszę ocenia się przez to, jak radzi sobie z
    **wylosowanymi** tackami, a nie przez statyczny zamiennik `placeable_shapes`.
    Osobnej kary za tackę nie do postawienia **nie ma** — była zaimplementowana i
    zmierzona (0, −50, −200, −500), i nie zmieniła ani jednej decyzji: stan, w
    którym cała losowa tacka nie wchodzi, po opróżnieniu bieżącej tacki po prostu
    nie występuje (0 trafień na 2488 ocen wewnętrznych). Szczegóły i liczby:
    `docs/lookahead.md`.

    Losowanie jest deterministyczne względem `reset(game_seed)`: osobna instancja
    `Generator` z ziarnem wyprowadzonym z seeda partii, nigdy generator gry —
    `act` nie dotyka stanu gry (#58).

    Dobór wartości domyślnych i ich zmierzony koszt: `docs/lookahead.md`.
    """

    name = "lookahead"

    DEFAULT_WEIGHTS = HeuristicPolicy.DEFAULT_WEIGHTS
    DEFAULT_BEAM = TrayPolicy.DEFAULT_BEAM
    # Wartości domyślne wybrane z tabeli pomiarowej w docs/lookahead.md pod twardy
    # limit 1800 s na ramię 600 partii (#92): ramię `lookahead:weights.json` wychodzi
    # na 1316,9 s. Więcej próbek, szerszy `branch` i głębszy drugi poziom zmierzono —
    # wszystkie kosztują czas i żaden nie oddaje go w jakości.
    DEFAULT_SAMPLES = 2
    DEFAULT_BRANCH = 2
    DEFAULT_INNER_BEAM = 1
    DEFAULT_INNER_DEPTH = 1

    def __init__(self, weights=None, beam=None, samples=None, branch=None,
                 inner_beam=None, inner_depth=None, seed=0):
        self.weights = tuple(weights) if weights is not None else self.DEFAULT_WEIGHTS
        self.beam = beam if beam is not None else self.DEFAULT_BEAM
        self.samples = samples if samples is not None else self.DEFAULT_SAMPLES
        self.branch = branch if branch is not None else self.DEFAULT_BRANCH
        self.inner_beam = inner_beam if inner_beam is not None else self.DEFAULT_INNER_BEAM
        self.inner_depth = inner_depth if inner_depth is not None else self.DEFAULT_INNER_DEPTH
        self._seed = seed
        self.last_expanded = 0
        # `None` = wartość liścia z `_weighted_features` (plansza + człon combo,
        # zachowanie niezmienione). Alternatywne źródło (np. sieć N-tuple, #123)
        # wpina się przez podklasę, która nadpisuje ten atrybut funkcją
        # `(board, combo, combo_counter) -> float` — patrz `NTupleLookaheadPolicy`.
        self._leaf_value = None
        self.reset(None)

    def reset(self, game_seed):
        # Własny generator próbek — gra swojego nie oddaje, a wspólny byłby
        # podglądaniem przyszłości zamiast losowania z rozkładu.
        self._sampler = Generator(seed="lookahead:%r:%r" % (self._seed, game_seed))

    def _search(self, board, pieces, combo, combo_counter, beam, root_actions=None, depth=None):
        return _tray_beam_search(
            board, pieces, combo, combo_counter, self.weights, beam,
            root_actions=root_actions, depth=depth, leaf_value=self._leaf_value,
        )

    def act(self, game, actions):
        pieces0 = tuple(game.pieces)
        depth = sum(1 for p in pieces0 if p is not None)
        self.last_expanded = 0
        if depth == 0 or not actions:
            return actions[0]

        frontier, expanded = self._search(
            game.board, pieces0, game.combo, game.combo_counter,
            self.beam, root_actions=actions,
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
                inner, inner_expanded = self._search(
                    state["board"], tray, state["combo"], state["combo_counter"],
                    self.inner_beam, depth=self.inner_depth,
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


class NTupleLookaheadPolicy(LookaheadPolicy):
    """`LookaheadPolicy`, ale wartość liścia liczy sieć N-tuple (`ntuple.py`, #123)
    zamiast `_weighted_features`.

    Reszta — wiązka, drugi poziom nad wylosowaną tacką, próbkowanie — jest
    dokładnie tym, co robi `LookaheadPolicy`; różnica siedzi wyłącznie w
    `_leaf_value`, którym `_search` podmienia funkcję oceny liścia w
    `_tray_beam_search`. Ocena N-tuple jest **alternatywnym, wybieralnym**
    źródłem wartości liścia — `features.py` i `HeuristicPolicy`/`TrayPolicy`/
    `LookaheadPolicy` na wagach ręcznych zostają nietknięte.

    **Liść ocenia wyłącznie planszę, bez członu combo** (decyzja #125). `gain`
    już niesie efekt combo dla ocenianego ruchu, a `V(board)` ma szacować
    przyszłość samej planszy; jedyny pomiar combo w ocenie liścia wyszedł
    ujemnie (#122: −6,6%, przeżycie 95,97 wobec 110,5), więc dosypanie tego
    członu tutaj kopiowałoby zmierzony błąd. Adapter `_ntuple_leaf` dostaje
    jednak **pełną trójkę** `(board, combo, combo_counter)` i dwa ostatnie
    argumenty ignoruje — dosypanie combo później nie wymaga zmiany sygnatury
    haka.
    """

    name = "lookahead-ntuple"

    def __init__(self, ntuple, beam=None, samples=None, branch=None,
                 inner_beam=None, inner_depth=None, seed=0):
        # `weights` klasy bazowej nie jest tu używane (leaf_value je zastępuje),
        # ale `LookaheadPolicy.__init__` go wymaga — wartość jest obojętna.
        super().__init__(
            weights=HeuristicPolicy.DEFAULT_WEIGHTS, beam=beam, samples=samples,
            branch=branch, inner_beam=inner_beam, inner_depth=inner_depth, seed=seed,
        )
        self.ntuple = ntuple
        self._leaf_value = self._ntuple_leaf

    def _ntuple_leaf(self, board, combo, combo_counter):
        """Wartość liścia z sieci N-tuple; `combo`/`combo_counter` świadomie bez wpływu."""
        return self.ntuple.value(board)


def _tray_beam_search(board, pieces, combo, combo_counter, weights, beam,
                      root_actions=None, depth=None, leaf_value=None):
    """Wiązka po sekwencjach postawień z tacki `pieces` na kopii `board`.

    Serce `TrayPolicy` (#58) i obu poziomów `LookaheadPolicy` (#92) — wyniesione
    tutaj, żeby obie polityki liczyły **dokładnie to samo**, łącznie z kolejnością
    kandydatów, od której zależy rozstrzyganie remisów (`list.sort` jest stabilny).

    Zwraca `(wiązka po ostatnim poziomie, liczba kandydatów rozwiniętych łącznie
    przed przycięciem)`. Każdy stan wiązki ma pole `score`.

    - `root_actions` — gotowa lista legalnych akcji na poziom 0 (gra już ją
      policzyła, nie ma po co liczyć jej drugi raz).
    - `depth` — ile poziomów rozwinąć; domyślnie tyle, ile klocków zostało w tacce.
    - `leaf_value` — `None` (domyślnie) liczy wartość liścia przez
      `_weighted_features` (plansza plus człon combo, zachowanie od #118 bez
      zmian). Podanie funkcji `(board, combo, combo_counter) -> float`
      zastępuje ją tym wywołaniem; `weights` jest wtedy ignorowane. Trójka
      argumentów jest **dokładnie** tą, którą dostaje `_weighted_features`, żeby
      każde źródło wartości liścia widziało ten sam stan; adapter, który combo
      nie używa (`NTupleLookaheadPolicy`, #123/#125), po prostu ignoruje dwa
      ostatnie argumenty — decyzja, żeby liść N-tuple oceniał samą planszę, jest
      z #125 i stoi na pomiarze z #122 (człon combo w ocenie liścia wyszedł
      −6,6%).
    """
    value_fn = leaf_value if leaf_value is not None else (
        lambda b, c, cc: _weighted_features(weights, b, c, cc)
    )
    root = {
        "board": board.copy(),
        "pieces": tuple(pieces),
        "combo": combo,
        "combo_counter": combo_counter,
        "gain": 0,
        "first_action": None,
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
                candidates.append(state)
                continue
            for action in legal:
                candidates.append(_expand(state, action))
        expanded += len(candidates)
        for candidate in candidates:
            candidate["score"] = candidate["gain"] + value_fn(
                candidate["board"], candidate["combo"], candidate["combo_counter"],
            )
        candidates.sort(key=lambda c: c["score"], reverse=True)
        frontier = candidates[:beam]

    if levels == 0:
        for candidate in frontier:
            candidate["score"] = candidate["gain"] + value_fn(
                candidate["board"], candidate["combo"], candidate["combo_counter"],
            )
    return frontier, expanded


def _weighted_features(weights, board, combo, combo_counter):
    """Ocena liścia: wagi planszowe razy `features`, plus wagi combo razy `combo_features`.

    Wektor `weights` może być krótszy niż `features.ALL_FEATURE_NAMES` — ogon
    combo jest wtedy pusty i człon w ogóle się nie liczy. Przy zerowych wagach
    combo (tak dopełnia `benchmark.load_tuned_weights`) dochodzi dokładne `0.0`,
    a `x + 0.0 == x` dla każdej skończonej liczby zmiennoprzecinkowej. Oba
    warianty zwracają więc **bit w bit** tę samą liczbę co przed #118 — to jest
    mechanizm, którym `lookahead:weights.json` zostaje ramieniem odniesienia bez
    zmiany ani jednego ruchu.
    """
    total = sum(w * f for w, f in zip(weights, features(board)))
    combo_weights = weights[len(FEATURE_NAMES):]
    if combo_weights:
        total += sum(
            w * f
            for w, f in zip(combo_weights, combo_features(combo, combo_counter))
        )
    return total


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
