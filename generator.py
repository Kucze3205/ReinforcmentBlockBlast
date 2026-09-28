"""
Deterministic Piece Generator

Typ kanoniczny losowany wg wag zmierzonych z mostu (#186), POTEM 1/n na
orientację w obrębie typu (R-8, wciąż niezmierzone — patrz
docs/calibration-assumptions.md, Z-6). Trzy klocki losowane niezależnie —
generator jest ślepy na planszę, bez gwarancji grywalności tacki.

Poprzedni model (1/15 na typ, referencja z badania #2, bbengine/src/env.h)
był założeniem modelowym autora referencji, nie pomiarem, i pomiar #182
odrzucił jednostajność typów na progu p ≈ 2,8·10⁻⁷² (897 klocków, 299 tacek).
`PIECE_TYPE_WEIGHTS` to liczby wystąpień typów w 978 klockach z 326
zweryfikowanych tacek mostu (`docs/data/z6-pary.json`, ekstrakcja
`tools/z6_pary.py`, wagi policzone `tools/z6_wagi.py`) — metoda i przedziały
ufności w docs/generator-wagi-typow.md. Świadomość planszy (Z-6 sensu
stricto) pozostaje niezmierzona i nierozstrzygnięta; ta kalibracja zmienia
wyłącznie rozkład brzegowy typów, nie wprowadza zależności od planszy.
"""
import random

from pieces import CANONICAL_TYPES, PIECE_POOL, PIECE_TYPES

# Liczba wystąpień każdego typu kanonicznego w 978 klockach (326 tacek, #182 + #181),
# w kolejności CANONICAL_TYPES/PIECE_TYPES. Wagi względne — nie muszą sumować się do 1,
# `random.Random.choices` normalizuje sam. Źródło i metoda: docs/generator-wagi-typow.md.
PIECE_TYPE_WEIGHTS = [13, 60, 56, 135, 58, 100, 116, 53, 33, 141, 32, 7, 6, 79, 89]

assert len(PIECE_TYPE_WEIGHTS) == len(CANONICAL_TYPES) == len(PIECE_TYPES)


class Generator:
    def __init__(self, seed=None):
        self.reset(seed)

    def reset(self, seed=None):
        self.seed = seed
        # R-9: seed był zapisywany, ale nigdy nieużyty. Bez tego benchmark na
        # ustalonych seedach jest niewykonalny.
        self.rng = random.Random(seed)

    def _next_piece(self):
        pose_indices = self.rng.choices(PIECE_TYPES, weights=PIECE_TYPE_WEIGHTS, k=1)[0]
        return PIECE_POOL[self.rng.choice(pose_indices)]

    def next_pieces(self):
        return [self._next_piece() for _ in range(3)]
