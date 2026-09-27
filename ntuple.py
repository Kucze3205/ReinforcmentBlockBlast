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

Układ łat jest **danymi**, w jednym miejscu (`LAYOUTS`, nazwane warianty), nie
rozsianymi po kodzie: wariant A z `docs/research/budzet-wyuczonej-oceny.md`
(#120) — 8 wierszy + 8 kolumn, każda łata 8 komórek, `16 × 2**8 = 4096` wag —
i wariant AD (#149): A plus wariant D (kwadraty 3×3 we wszystkich 36
położeniach), `52` łaty. Uzasadnienie wyboru wariantu A jako domyślnego, i AD
jako drugiego, jest w `docs/ntuple.md`, nie tutaj. `NTupleValue.load` przyjmuje
plik z każdym układem z `LAYOUTS`; plik z nieznanym układem się nie wczyta.
"""
import json

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

# Nazwane układy łat — jedyne, które `NTupleValue.load` przyjmuje (#149).
LAYOUTS = {"A": LAYOUT_A, "AD": LAYOUT_AD}
DEFAULT_LAYOUT = "A"


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
    """Wzorzec łaty jako liczba 0..`2**k - 1`: bit `i` odczytu to bit `positions[i]` planszy."""
    idx = 0
    for i, pos in enumerate(positions):
        idx |= ((bits >> pos) & 1) << i
    return idx


def patch_indices(bits, layout=PATCH_LAYOUT):
    """Indeksy wszystkich łat naraz, z jednej maski bitowej planszy."""
    return [_patch_index(bits, positions) for positions in layout]


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

    def __init__(self, weights=None, reward=REWARD_SCORE, layout=None):
        if reward not in REWARDS:
            raise ValueError("nieznany sygnal nagrody %r (dozwolone: %s)" % (reward, ", ".join(REWARDS)))
        self.reward = reward
        self.layout = layout if layout is not None else LAYOUTS[DEFAULT_LAYOUT]
        self.weights = weights if weights is not None else zero_weights(self.layout)
        if len(self.weights) != len(self.layout):
            raise ValueError(
                "liczba tablic wag (%d) nie zgadza sie z liczba lat (%d)"
                % (len(self.weights), len(self.layout))
            )
        for table, positions in zip(self.weights, self.layout):
            if len(table) != (1 << len(positions)):
                raise ValueError(
                    "tablica wag o dlugosci %d nie zgadza sie z lata k=%d (2**k=%d)"
                    % (len(table), len(positions), 1 << len(positions))
                )

    def indices(self, board):
        return patch_indices(board_bits(board), self.layout)

    def value(self, board):
        return self.value_from_indices(self.indices(board))

    def value_from_indices(self, indices):
        return sum(table[i] for table, i in zip(self.weights, indices))

    def update(self, indices, delta):
        """TD(0): dopisuje `delta` do każdej aktywnej wagi.

        Gradient wartości względem wagi aktywnego wzorca danej łaty jest 1 (odczyt
        z tabeli), a względem wszystkich innych wpisów tej łaty jest 0 — stąd
        aktualizacja dotyka wyłącznie jednej wagi na łatę, nie całej tabeli.
        """
        for table, i in zip(self.weights, indices):
            table[i] += delta

    def to_dict(self):
        return {
            "reward": self.reward,
            "patch_layout": [list(p) for p in self.layout],
            "weights": self.weights,
        }

    def save(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        layout = tuple(tuple(p) for p in data["patch_layout"])
        if layout not in LAYOUTS.values():
            raise ValueError(
                "plik %s ma uklad lat, ktory nie jest zadnym z nazwanych "
                "wariantow ntuple.LAYOUTS (%s) — #149: load przyjmuje kazdy "
                "znany uklad, nie jeden ustalony" % (path, ", ".join(sorted(LAYOUTS)))
            )
        return cls(
            weights=[list(t) for t in data["weights"]],
            reward=data.get("reward", REWARD_SCORE),
            layout=layout,
        )
