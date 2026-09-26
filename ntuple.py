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

Układ łat jest **danymi**, w jednym miejscu (`PATCH_LAYOUT`), nie rozsianymi po
kodzie: wariant A z `docs/research/budzet-wyuczonej-oceny.md` (#120) — 8 wierszy
+ 8 kolumn, każda łata 8 komórek, `16 × 2**8 = 4096` wag. Uzasadnienie wyboru
tego wariantu spośród czterech zmierzonych tam (A: 4096, B: 784, C: 5376,
D: 18432 wag) jest w `docs/ntuple.md`, nie tutaj.
"""
import json

from board import Board

WIDTH = Board.WIDTH
HEIGHT = Board.HEIGHT


def _row_patch(y):
    return tuple(y * WIDTH + x for x in range(WIDTH))


def _col_patch(x):
    return tuple(y * WIDTH + x for y in range(HEIGHT))


# Wariant A (#120): 8 łat-wierszy + 8 łat-kolumn, k=8 komórek/łatę.
PATCH_LAYOUT = tuple(_row_patch(y) for y in range(HEIGHT)) + tuple(
    _col_patch(x) for x in range(WIDTH)
)
N_PATCHES = len(PATCH_LAYOUT)
PATCH_SIZE = len(PATCH_LAYOUT[0])
TABLE_SIZE = 1 << PATCH_SIZE
N_WEIGHTS = N_PATCHES * TABLE_SIZE


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


def zero_weights(layout=PATCH_LAYOUT):
    return [[0.0] * (1 << len(positions)) for positions in layout]


class NTupleValue:
    """Ocena stanu jako suma odczytów z tablic LUT po łatach `PATCH_LAYOUT`.

    Wagi same-zera dają ocenę 0 na każdej planszy (odczyt z tabeli zainicjalizowanej
    zerami), zgodnie z kryterium akceptacji #123.
    """

    layout = PATCH_LAYOUT

    def __init__(self, weights=None):
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
        if layout != cls.layout:
            raise ValueError(
                "plik %s ma inny uklad lat niz ntuple.PATCH_LAYOUT (#123: uklad "
                "lat jest jednym, ustalonym wariantem, plik z innym nie da sie "
                "wczytac)" % path
            )
        return cls(weights=[list(t) for t in data["weights"]])
