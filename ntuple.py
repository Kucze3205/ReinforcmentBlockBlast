"""
Ocena N-tuple: suma odczytów z tablic LUT po łatach binarnych planszy (#123).

Alternatywne, wybieralne źródło wartości liścia — wpinane tam, gdzie dziś stoi
`policies._weighted_features(weights, board, combo, combo_counter)`, nie jego
zamiennik. `features.py` i sześć ręcznych cech zostają nietknięte jako punkt
odniesienia. Adapter w `policies.NTupleLookaheadPolicy` dostaje pełną trójkę
`(board, combo, combo_counter)`, ale `value` bierze **samą planszę**: liść
N-tuple świadomie nie ma członu combo (decyzja #125, pomiar #122).

`c = 2`: komórka planszy jest pusta albo zajęta, więc łata o `k` komórkach ma
`2**k` możliwych wzorców — każdy wzorzec to jeden wpis w tablicy wag tej łaty
(LUT, look-up table). Ocena stanu to suma odczytów ze wszystkich łat: funkcja
liniowa względem tych binarnych cech, tak jak `features.py`, tylko z cechami
dobranymi automatycznie (każdy wzorzec na łacie to osobna waga) zamiast sześciu
ręcznie zaprojektowanych.

Liczba **etapów** (`stages`, #203) jest opcjonalna i domyślnie `1` — wtedy plik wag,
wartości i decyzje są bitowo identyczne ze sprzed #203. Przy `stages > 1` każdy etap
ma własny komplet tablic wag tego samego układu łat; etap danej planszy wybiera
`stage_of_bits` z liczby jej **własnych** zajętych komórek i rosnących progów
`thresholds` (`len(thresholds) == stages - 1`) — etap afterstate'u pochodzi z tego
afterstate'u, nie ze stanu, z którego powstał (`docs/research/przeszukanie-z-wyuczona-ocena.md`,
sekcja 1: N-tuple TD po afterstate'ach, „multi-stage” jako jedno z ulepszeń).

Układ łat jest **danymi**, w jednym miejscu (`LAYOUTS`, nazwane warianty), nie
rozsianymi po kodzie: wariant A z `docs/research/budzet-wyuczonej-oceny.md`
(#120) — 8 wierszy + 8 kolumn, każda łata 8 komórek, `16 × 2**8 = 4096` wag —
wariant AD (#149): A plus wariant D (kwadraty 3×3 we wszystkich 36
położeniach), `52` łaty, i wariant ADC (#162): AD plus wariant C (prostokąty
2×3 i 3×2 we wszystkich 84 położeniach), `136` łat. Uzasadnienie wyboru
wariantu A jako domyślnego, i AD/ADC jako kolejnych, jest w `docs/ntuple.md`,
nie tutaj. `NTupleValue.load` przyjmuje plik z każdym układem z `LAYOUTS`;
plik z nieznanym układem się nie wczyta.
"""
import json

import ntuple_native
from board import Board

WIDTH = Board.WIDTH
HEIGHT = Board.HEIGHT


def _row_patch(y):
    return tuple(y * WIDTH + x for x in range(WIDTH))


def _col_patch(x):
    return tuple(y * WIDTH + x for y in range(HEIGHT))


def _square_patch(x, y):
    """Kwadrat 3x3 z lewym-górnym rogiem `(x, y)` jako łata k=9 komórek (wariant D, #120)."""
    return tuple((y + dy) * WIDTH + (x + dx) for dy in range(3) for dx in range(3))


def _rect_patch(x, y, height, width):
    """Prostokąt `height`x`width` z lewym-górnym rogiem `(x, y)` jako łata
    k=`height*width` komórek (wariant C, #162)."""
    return tuple((y + dy) * WIDTH + (x + dx) for dy in range(height) for dx in range(width))


# Wariant A (#120): 8 łat-wierszy + 8 łat-kolumn, k=8 komórek/łatę.
PATCH_LAYOUT = tuple(_row_patch(y) for y in range(HEIGHT)) + tuple(
    _col_patch(x) for x in range(WIDTH)
)
N_PATCHES = len(PATCH_LAYOUT)
PATCH_SIZE = len(PATCH_LAYOUT[0])
TABLE_SIZE = 1 << PATCH_SIZE
N_WEIGHTS = N_PATCHES * TABLE_SIZE

# Wariant D (#120): kwadraty 3x3 we wszystkich położeniach na planszy 8x8,
# k=9 komórek/łatę — (WIDTH-2) * (HEIGHT-2) = 36 położeń lewego-górnego rogu.
LAYOUT_D = tuple(
    _square_patch(x, y) for y in range(HEIGHT - 2) for x in range(WIDTH - 2)
)

LAYOUT_A = PATCH_LAYOUT
# Wariant AD (#149): A i D razem — wiersze/kolumny (kompletność linii) plus
# kwadraty 3x3 (fragmentacja lokalna, `square3` zabija 54,7% partii wg
# docs/co-zabija-partie.md), 16 + 36 = 52 łaty.
LAYOUT_AD = LAYOUT_A + LAYOUT_D

# Wariant C (#162, docs/research/budzet-wyuczonej-oceny.md sekcja 3): prostokąty
# 2x3 i 3x2 we wszystkich położeniach lewego-górnego rogu na planszy 8x8 —
# 2x3 (2 wiersze, 3 kolumny): (HEIGHT-1) x (WIDTH-2) = 7x6 = 42 położenia;
# 3x2 (3 wiersze, 2 kolumny): (HEIGHT-2) x (WIDTH-1) = 6x7 = 42 położenia;
# razem 84 łaty, k=6 komórek/łatę — `rect23`, drugi zabójca partii po `square3`
# (razem 76,9% partii wg docs/co-zabija-partie.md).
LAYOUT_C = tuple(
    _rect_patch(x, y, 2, 3) for y in range(HEIGHT - 1) for x in range(WIDTH - 2)
) + tuple(
    _rect_patch(x, y, 3, 2) for y in range(HEIGHT - 2) for x in range(WIDTH - 1)
)

# Wariant ADC (#162): AD plus C — 52 + 84 = 136 łat, `22528 + 5376 = 27904` wag.
LAYOUT_ADC = LAYOUT_AD + LAYOUT_C

# Nazwane układy łat — jedyne, które `NTupleValue.load` przyjmuje (#149).
LAYOUTS = {"A": LAYOUT_A, "AD": LAYOUT_AD, "ADC": LAYOUT_ADC}
DEFAULT_LAYOUT = "A"

# Liczba komórek zajętych na planszy 8x8 (0..64) — jednostka progów etapów (#203).
MAX_OCCUPIED = WIDTH * HEIGHT


def board_bits(board):
    """Cała plansza jako jedna liczba 64-bitowa, bit `y*WIDTH+x` — jak `features.py`."""
    bits = 0
    for y, row in enumerate(board.grid):
        row_bits = 0
        for x in range(WIDTH):
            if row[x]:
                row_bits |= 1 << x
        bits |= row_bits << (y * WIDTH)
    return bits


def _patch_index(bits, positions):
    """Wzorzec łaty jako liczba 0..`2**k - 1`: bit `i` odczytu to bit `positions[i]` planszy.

    Referencja bit-po-bicie: `patch_indices` liczy to samo szybciej (#158),
    równoważność jest testowana wprost (`tests/test_ntuple.py`)."""
    idx = 0
    for i, pos in enumerate(positions):
        idx |= ((bits >> pos) & 1) << i
    return idx


ROW_BYTE_SIZE = 1 << WIDTH

_row_tables_cache = {}


def _row_tables(layout):
    """Tablice odczytu po bajtach wierszy dla `layout`, przygotowane raz (#158).

    Dla każdej łaty: lista `(nr_wiersza, tabela)`, gdzie `tabela[bajt_wiersza]`
    to wkład bitów tego wiersza do indeksu łaty, już przesuniętych na właściwą
    pozycję — `patch_indices` sumuje (OR-em) wkłady z wierszy, które łata
    faktycznie dotyka, zamiast odczytywać każdy bit osobno jak `_patch_index`.
    Wynik jest identyczny, bo każdy bit indeksu pochodzi z dokładnie jednego
    wiersza planszy."""
    cached = _row_tables_cache.get(layout)
    if cached is not None:
        return cached
    tables = []
    for positions in layout:
        by_row = {}
        for i, pos in enumerate(positions):
            row, col = divmod(pos, WIDTH)
            by_row.setdefault(row, []).append((col, i))
        row_tables = []
        for row, cols in by_row.items():
            table = [0] * ROW_BYTE_SIZE
            for byte_val in range(ROW_BYTE_SIZE):
                contrib = 0
                for col, i in cols:
                    if (byte_val >> col) & 1:
                        contrib |= 1 << i
                table[byte_val] = contrib
            row_tables.append((row, tuple(table)))
        tables.append(tuple(row_tables))
    result = tuple(tables)
    _row_tables_cache[layout] = result
    return result


def patch_indices(bits, layout=PATCH_LAYOUT):
    """Indeksy wszystkich łat naraz, z jednej maski bitowej planszy.

    Bity są odczytywane po całych bajtach wiersza przez tablice `_row_tables`
    (przygotowane raz na `layout`), nie bit po bicie jak `_patch_index` — ten
    sam wynik, mniej pracy Pythona na ocenę (#158)."""
    row_mask = ROW_BYTE_SIZE - 1
    row_bytes = tuple((bits >> (row * WIDTH)) & row_mask for row in range(HEIGHT))
    result = []
    for row_tables in _row_tables(layout):
        idx = 0
        for row, table in row_tables:
            idx |= table[row_bytes[row]]
        result.append(idx)
    return result


def occupied_count(bits):
    """Liczba zajętych komórek planszy (0..64) — jednostka progów etapów (#203)."""
    return bin(bits).count("1")


def stage_of_occupied(occupied, thresholds):
    """Numer etapu (0-indeksowany) dla liczby zajętych komórek i progów rosnących.

    `thresholds[i]` to najmniejsza liczba zajętych komórek etapu `i + 1` — etap
    afterstate'u jest wybierany z jego własnej planszy (#203, sekcja 1 badania
    `docs/research/przeszukanie-z-wyuczona-ocena.md`), nie ze stanu, z którego
    powstał."""
    stage = 0
    for threshold in thresholds:
        if occupied >= threshold:
            stage += 1
    return stage


# Sygnał, na którym wagi się uczyły (#140). `score`: nagroda to `gain` gry, V
# szacuje punkty; `survival`: nagroda 1 za postawienie, V szacuje liczbę
# pozostałych postawień. Plik wag bez pola `reward` (sprzed #140) to `score`.
REWARD_SCORE = "score"
REWARD_SURVIVAL = "survival"
REWARDS = (REWARD_SCORE, REWARD_SURVIVAL)


def zero_weights(layout=PATCH_LAYOUT):
    return [[0.0] * (1 << len(positions)) for positions in layout]


class NTupleValue:
    """Ocena stanu jako suma odczytów z tablic LUT po łatach danego układu (domyślnie `A`).

    Wagi same-zera dają ocenę 0 na każdej planszy (odczyt z tabeli zainicjalizowanej
    zerami), zgodnie z kryterium akceptacji #123.
    """

    def __init__(self, weights=None, reward=REWARD_SCORE, layout=None, native=None,
                 stages=1, thresholds=()):
        if reward not in REWARDS:
            raise ValueError("nieznany sygnal nagrody %r (dozwolone: %s)" % (reward, ", ".join(REWARDS)))
        self.reward = reward
        self.layout = layout if layout is not None else LAYOUTS[DEFAULT_LAYOUT]
        if stages < 1:
            raise ValueError("liczba etapow musi byc >= 1 (jest %r)" % (stages,))
        thresholds = tuple(thresholds)
        if len(thresholds) != stages - 1:
            raise ValueError(
                "liczba progow (%d) musi byc o jeden mniejsza niz liczba etapow (%d)"
                % (len(thresholds), stages)
            )
        for a, b in zip(thresholds, thresholds[1:]):
            if not a < b:
                raise ValueError("progi etapow musza scisle rosnac: %r" % (thresholds,))
        if thresholds and not (0 < thresholds[0] and thresholds[-1] < MAX_OCCUPIED):
            raise ValueError(
                "progi etapow musza miescic sie w (0, %d): %r" % (MAX_OCCUPIED, thresholds)
            )
        self.stages = stages
        self.thresholds = thresholds
        # 1 etap (domyslnie): `self._stage_weights == [tablice_wag]`, dokladnie
        # jak dawne `self._weights` — plik jednoetapowy wczytuje sie i liczy
        # bitowo tak samo jak przed #203 (kryterium akceptacji #203).
        if stages == 1:
            self._stage_weights = [weights if weights is not None else zero_weights(self.layout)]
        else:
            self._stage_weights = weights if weights is not None else \
                [zero_weights(self.layout) for _ in range(stages)]
        if len(self._stage_weights) != stages:
            raise ValueError(
                "liczba zestawow wag (%d) nie zgadza sie z liczba etapow (%d)"
                % (len(self._stage_weights), stages)
            )
        for stage_weights in self._stage_weights:
            if len(stage_weights) != len(self.layout):
                raise ValueError(
                    "liczba tablic wag (%d) nie zgadza sie z liczba lat (%d)"
                    % (len(stage_weights), len(self.layout))
                )
            for table, positions in zip(stage_weights, self.layout):
                if len(table) != (1 << len(positions)):
                    raise ValueError(
                        "tablica wag o dlugosci %d nie zgadza sie z lata k=%d (2**k=%d)"
                        % (len(table), len(positions), 1 << len(positions))
                    )
        # Rdzeń natywny (#184): `None` = według `NTUPLE_NATIVE` i dostępności
        # kompilatora, `False` = zawsze czysty Python. Wagi rdzeń trzyma w
        # buforze C; `weights` oddaje listy zsynchronizowane z nim.
        self._core = None
        self._core_newer = False   # bufor C zmieniony po ostatnim `pull`
        self._lists_touched = False  # listy wydane na zewnątrz — mogły się zmienić
        if native is None:
            native = ntuple_native.enabled()
        if native and WIDTH == ntuple_native.BOARD_SIZE and HEIGHT == ntuple_native.BOARD_SIZE \
                and ntuple_native.available():
            core = ntuple_native.Core(self.layout, self._stage_weights, self.thresholds)
            if core.push(self._stage_weights):
                self._core = core

    def _sync_from_core(self):
        if self._core is not None:
            if self._core_newer:
                self._core.pull(self._stage_weights)
                self._core_newer = False
            self._lists_touched = True

    def stage_of_bits(self, bits):
        """Etap afterstate'u `bits` (0-indeksowany), wybrany z jego wlasnej planszy
        wedlug liczby zajetych komorek (#203). Zawsze `0` dla jednego etapu."""
        if self.stages == 1:
            return 0
        return stage_of_occupied(occupied_count(bits), self.thresholds)

    def stage(self, board):
        return self.stage_of_bits(board_bits(board))

    @property
    def weights(self):
        """Tablice wag jednego etapu (lista list float), albo — przy kilku etapach
        — lista takich list, po jednej na etap. Z rdzeniem: najpierw dociągnięte z
        bufora C, a przy następnej operacji rdzenia wepchnięte z powrotem — tak
        zmiana wagi z zewnątrz (`weights[p][i] = ...`) jest widoczna jak dotąd."""
        self._sync_from_core()
        if self.stages == 1:
            return self._stage_weights[0]
        return self._stage_weights

    @weights.setter
    def weights(self, value):
        self._stage_weights = [value] if self.stages == 1 else value
        self._core_newer = False
        self._lists_touched = True

    @property
    def native(self):
        """Rdzeń gotowy do użycia albo `None` (czysty Python)."""
        core = self._core
        if core is not None and self._lists_touched:
            self._lists_touched = False
            if not core.push(self._stage_weights):
                # Listy przestały pasować do rdzenia (np. waga int) — dalej Python.
                self._core = core = None
        return core

    def indices(self, board):
        return patch_indices(board_bits(board), self.layout)

    def value(self, board):
        core = self.native
        bits = board_bits(board)
        if core is not None:
            return core.value_bits(bits)
        return self.value_from_indices(patch_indices(bits, self.layout), self.stage_of_bits(bits))

    def value_from_indices(self, indices, stage=0):
        core = self.native
        if core is not None:
            if not isinstance(indices, core.IdxArray):
                indices = list(indices)
            idx = core.as_idx(indices)
            if idx is not None:
                return core.value_idx(idx, stage)
        self._sync_from_core()
        return sum(table[i] for table, i in zip(self._stage_weights[stage], indices))

    def update(self, indices, delta, stage=0):
        """TD(0): dopisuje `delta` do każdej aktywnej wagi etapu `stage`.

        Gradient wartości względem wagi aktywnego wzorca danej łaty jest 1 (odczyt
        z tabeli), a względem wszystkich innych wpisów tej łaty jest 0 — stąd
        aktualizacja dotyka wyłącznie jednej wagi na łatę, nie całej tabeli.
        """
        core = self.native
        if core is not None and type(delta) in (float, int):
            if not isinstance(indices, core.IdxArray):
                indices = list(indices)
            idx = core.as_idx(indices)
            if idx is not None:
                core.update(idx, delta, stage)
                self._core_newer = True
                return
        self._sync_from_core()
        for table, i in zip(self._stage_weights[stage], indices):
            table[i] += delta

    def to_dict(self):
        self._sync_from_core()
        data = {
            "reward": self.reward,
            "patch_layout": [list(p) for p in self.layout],
        }
        if self.stages > 1:
            data["stages"] = self.stages
            data["thresholds"] = list(self.thresholds)
            data["weights"] = self._stage_weights
        else:
            data["weights"] = self._stage_weights[0]
        return data

    def save(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path, native=None):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        layout = tuple(tuple(p) for p in data["patch_layout"])
        if layout not in LAYOUTS.values():
            raise ValueError(
                "plik %s ma uklad lat, ktory nie jest zadnym z nazwanych "
                "wariantow ntuple.LAYOUTS (%s) — #149: load przyjmuje kazdy "
                "znany uklad, nie jeden ustalony" % (path, ", ".join(sorted(LAYOUTS)))
            )
        stages = data.get("stages", 1)
        thresholds = tuple(data.get("thresholds", ()))
        if stages > 1:
            weights = [[list(t) for t in stage_weights] for stage_weights in data["weights"]]
        else:
            weights = [list(t) for t in data["weights"]]
        return cls(
            weights=weights,
            reward=data.get("reward", REWARD_SCORE),
            layout=layout,
            native=native,
            stages=stages,
            thresholds=thresholds,
        )
