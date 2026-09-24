"""
Grywalność tacki na bitboardzie (#37): czy da się ją rozegrać na danej planszy.

Dwa poziomy, bo nie wiadomo, którego pilnuje gra:

* **żywa** — którykolwiek klocek mieści się od razu. Zaprzeczenie to koniec partii
  w chwili dobrania tacki; tę gwarancję daje każda gra z regułą „brak ruchu = koniec".
* **cała** — istnieje kolejność i miejsca, w których wchodzą wszystkie trzy klocki
  (z czyszczeniem linii po drodze). Silniejsza gwarancja: klony przeglądarkowe,
  które chciały być grywalne, sprawdzały właśnie to.

Plansza to 64-bitowa maska, bit `8*r + c`. Wynik nie zależy od combo ani punktów.
"""
import random
from functools import lru_cache
from itertools import permutations

from generator import Generator

FULL = (1 << 64) - 1
ROWS = [0xFF << (8 * r) for r in range(8)]
COLS = [sum(1 << (8 * r + c) for r in range(8)) for c in range(8)]


def to_mask(grid):
    return sum(1 << (8 * r + c) for r in range(8) for c in range(8) if grid[r][c])


def to_grid(mask):
    return [[(mask >> (8 * r + c)) & 1 for c in range(8)] for r in range(8)]


@lru_cache(maxsize=None)
def placements(shape):
    """Maski wszystkich miejsc, w które mieści się kształt (krotka krotek, dla cache'u)."""
    h, w = len(shape), len(shape[0])
    cells = [(dy, dx) for dy in range(h) for dx in range(w) if shape[dy][dx]]
    return tuple(sum(1 << (8 * (y + dy) + x + dx) for dy, dx in cells)
                 for y in range(9 - h) for x in range(9 - w))


def key(shape):
    return tuple(tuple(row) for row in shape)


def clear(mask):
    """Zdejmuje pełne wiersze i kolumny naraz, jak gra."""
    kill = 0
    for line in ROWS + COLS:
        if mask & line == line:
            kill |= line
    return mask & ~kill


def any_fits(mask, shapes):
    return any(mask & p == 0 for s in shapes if s for p in placements(key(s)))


def all_fit(mask, shapes):
    """Czy wszystkie niepuste klocki dają się postawić po kolei (dowolna kolejność)."""
    shapes = [key(s) for s in shapes if s]

    def rec(m, rest):
        if not rest:
            return True
        seen = set()
        for i, s in enumerate(rest):
            if s in seen:
                continue
            seen.add(s)
            others = rest[:i] + rest[i + 1:]
            for p in placements(s):
                if m & p == 0 and rec(clear(m | p), others):
                    return True
        return False

    return rec(mask, shapes)


def sample_trays(n, seed=0):
    """Stała próbka ślepych tacek z generatora symulatora: wspólna dla wszystkich ocen."""
    gen = Generator(seed)
    return [[p.shape for p in gen.next_pieces()] for _ in range(n)]


def p_dead(mask, trays, whole=False):
    """Frakcja tacek z próbki, które na tej planszy są niegrywalne przy ślepym losowaniu."""
    check = all_fit if whole else any_fits
    return sum(not check(mask, t) for t in trays) / len(trays)
