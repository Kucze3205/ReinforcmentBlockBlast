"""
Deterministic Piece Generator

Model doboru tacki dopasowany do 744 tacek z logów mostu (#38, tools/analyze_generator.py):

1. **Wagi typów** — nierówne, 14 wolnych parametrów (WAGI); orientacja w obrębie typu
   losowana równo (R-8).
2. **Powtórzenie** — każdy klocek po pierwszym z prawdopodobieństwem POWTORZENIE
   kopiuje któryś z poprzednich w tacce. Jednostką losowania jest tacka, nie klocek:
   powtórzony typ ma 37% tacek wobec 24% przy niezależnym losowaniu.
3. **Filtr grywalności** — tacka, której trzech klocków nie da się postawić po kolei,
   jest losowana od nowa (#37). Filtr sam tłumaczy zależność doboru od planszy (litość
   przy ciasnocie), więc wag warunkowanych zapełnieniem nie ma: mają gorsze AIC o ~90
   przy 42 parametrach więcej.

Wagi są wagami *przed* filtrem: filtr przesuwa rozkład, który da się zmierzyć w apce.
Mechanizm apki (przelosowanie czy ważenie) jest nierozstrzygnięty — przelosowanie to
prostsza z hipotez, bo nie ma parametru. Założenie modelowe, nie pomiar — patrz
docs/calibration-assumptions.md (Z-6).
"""
import random

from pieces import CANONICAL_TYPES, PIECE_POOL, PIECE_TYPES
from playability import all_fit, to_mask

WAGI = {
    "1x1": 0.018, "beam2": 0.077, "beam3": 0.065, "beam4": 0.113, "beam5": 0.067,
    "square2": 0.065, "rect23": 0.104, "square3": 0.048, "corner3": 0.062,
    "L": 0.143, "corner5": 0.053, "diag2": 0.026, "diag3": 0.007, "S": 0.070, "T": 0.081,
}
POWTORZENIE = 0.09
MAX_PROB = 200

_TYPE_WEIGHTS = [WAGI[name] for name, _ in CANONICAL_TYPES]


class Generator:
    def __init__(self, seed=None):
        self.reset(seed)

    def reset(self, seed=None):
        self.seed = seed
        # R-9: seed był zapisywany, ale nigdy nieużyty. Bez tego benchmark na
        # ustalonych seedach jest niewykonalny.
        self.rng = random.Random(seed)

    def _next_piece(self):
        type_index = self.rng.choices(range(len(PIECE_TYPES)), _TYPE_WEIGHTS)[0]
        return PIECE_POOL[self.rng.choice(PIECE_TYPES[type_index])]

    def _draw_tray(self):
        tray = []
        for _ in range(3):
            if tray and self.rng.random() < POWTORZENIE:
                tray.append(self.rng.choice(tray))
            else:
                tray.append(self._next_piece())
        return tray

    def next_pieces(self, grid=None):
        """Tacka trzech klocków; z planszą `grid` — taka, którą da się w całości postawić, jeśli istnieje."""
        if grid is None:
            return self._draw_tray()
        mask = to_mask(grid)
        for _ in range(MAX_PROB):
            tray = self._draw_tray()
            if all_fit(mask, [p.shape for p in tray]):
                break
        return tray  # po MAX_PROB nieudanych próbach plansza jest za ciasna: gra i tak się kończy
