"""
Deterministic Piece Generator

Typ kanoniczny losowany wg wag zmierzonych z mostu (#186), POTEM 1/n na
orientację w obrębie typu (R-8, wciąż niezmierzone — patrz
docs/calibration-assumptions.md, Z-6). Trzy klocki losowane niezależnie w
obrębie jednego rzutu tacki.

Poprzedni model (1/15 na typ, referencja z badania #2, bbengine/src/env.h)
był założeniem modelowym autora referencji, nie pomiarem, i pomiar #182
odrzucił jednostajność typów na progu p ≈ 2,8·10⁻⁷² (897 klocków, 299 tacek).
`PIECE_TYPE_WEIGHTS` to liczby wystąpień typów w 978 klockach z 326
zweryfikowanych tacek mostu (`docs/data/z6-pary.json`, ekstrakcja
`tools/z6_pary.py`, wagi policzone `tools/z6_wagi.py`) — metoda i przedziały
ufności w docs/generator-wagi-typow.md.

Świadomość planszy (#217, dopasowanie: docs/z6-model-generatora.md, koszt i
wdrożenie: docs/generator-swiadomy-planszy.md): dopasowanie 693 par
(`docs/data/z6-pary.json`) wybrało model M2-simple — `PIECE_TYPE_WEIGHTS`
BEZ ZMIAN (dopasowane wagi nie biją ich o > 1 SE na teście), plus odrzucanie
„do skutku": jeśli wylosowana tacka nie jest układalna na BIEŻĄCEJ planszy
(`board.tray_playable`), losuj ponownie, do `REJECT_MAX_ATTEMPTS` razy (limit
awaryjny na planszę, na której naprawdę nie ma grywalnej tacki — wtedy i tak
przegrywa).

To jest opt-in, nie zmiana domyślnego zachowania wywołań bez planszy:
`Generator(seed)` i `next_pieces()` bez podania `board` zachowują się
DOKŁADNIE jak przed #217 (ślepe na planszę, bit w bit) — `game.py` i
`policies.py` nie zostały tym biletem dotknięte i dalej tak wywołują
generator. Świadomość planszy aktywuje się dopiero, gdy ktoś poda
`Generator(seed, board=...)` (albo ustawi `generator.board` po fakcie) —
patrz `docs/generator-swiadomy-planszy.md` po uzasadnienie tej granicy.
`legacy=True` wyłącza odrzucanie nawet z podaną planszą (bit w bit jak
przed #217) — do porównań i testów.
"""
import random

from board import tray_playable
from pieces import CANONICAL_TYPES, PIECE_POOL, PIECE_TYPES

# Liczba wystąpień każdego typu kanonicznego w 978 klockach (326 tacek, #182 + #181),
# w kolejności CANONICAL_TYPES/PIECE_TYPES. Wagi względne — nie muszą sumować się do 1,
# `random.Random.choices` normalizuje sam. Źródło i metoda: docs/generator-wagi-typow.md.
PIECE_TYPE_WEIGHTS = [13, 60, 56, 135, 58, 100, 116, 53, 33, 141, 32, 7, 6, 79, 89]

assert len(PIECE_TYPE_WEIGHTS) == len(CANONICAL_TYPES) == len(PIECE_TYPES)

# #217 (docs/z6-model-generatora.md „do skutku"): `k` dopasowanego M2-simple —
# limit CAŁKOWITEJ liczby rzutów tacki (pierwszy + redraw), nie tylko redrawów.
# Na 693 obserwowanych parach dopasowanie zbiegło do górnej granicy poszerzonej
# siatki (`p=1,0`), więc w praktyce oznacza "losuj, aż grywalna" — limit działa
# wyłącznie jako zapora na planszy, na której żadna tacka nie jest układalna.
REJECT_MAX_ATTEMPTS = 1000


class Generator:
    def __init__(self, seed=None, board=None, legacy=False):
        self.board = board
        self.legacy = legacy
        self.reset(seed)

    def reset(self, seed=None):
        self.seed = seed
        # R-9: seed był zapisywany, ale nigdy nieużyty. Bez tego benchmark na
        # ustalonych seedach jest niewykonalny.
        self.rng = random.Random(seed)

    def _next_piece(self):
        pose_indices = self.rng.choices(PIECE_TYPES, weights=PIECE_TYPE_WEIGHTS, k=1)[0]
        return PIECE_POOL[self.rng.choice(pose_indices)]

    def _draw_tray(self):
        return [self._next_piece() for _ in range(3)]

    def next_pieces(self):
        pieces = self._draw_tray()
        if self.board is None or self.legacy:
            return pieces
        for _ in range(1, REJECT_MAX_ATTEMPTS):
            # `tray_playable` zwraca None, gdy budżet węzłów DFS się wyczerpał
            # bez rozstrzygnięcia (board.TRAY_PLAYABLE_NODE_BUDGET) — brak
            # rozstrzygnięcia nie jest dowodem grywalności, więc traktowany
            # jak False (redraw); `None` jest fałszywe w Pythonie, więc `not`
            # obsługuje to bez osobnej gałęzi.
            if tray_playable(self.board.grid, [p.shape for p in pieces]):
                return pieces
            pieces = self._draw_tray()
        return pieces


# ---------------------------------------------------------------------------
# #217: wpięcie świadomości planszy w `Game` BEZ dotykania `game.py` (poza
# budżetem tego biletu — patrz `## Kryteria akceptacji` #217). `Game.__init__`
# tworzy `Generator(seed)` bez planszy; poniższe funkcje ustawiają
# `generator.board` PO fakcie, z zewnątrz — `next_pieces()` czyta `self.board`
# przy KAŻDYM wywołaniu, nie tylko przy konstrukcji, więc wystarczy zrobić to
# raz zaraz po `Game(...)`, żeby WSZYSTKIE kolejne odświeżenia tacki
# (`game.apply_placement`, niedotknięte) już były świadome planszy. Do użytku
# w narzędziach pomiarowych/treningowych (`tools/measure_ntuple_search_grid.py`,
# `tools/train_ntuple.py --board-aware-generator`) — nigdy w kodzie produkcyjnym
# `game.py`/`policies.py`, które ten bilet zostawia nietknięte.
# ---------------------------------------------------------------------------


def attach_to_game(game):
    """Wpina świadomość planszy w JUŻ skonstruowaną `game.Game` (ten sam obiekt
    `game.board`, mutowany w miejscu przez resztę partii — nieinwazyjne tak
    samo jak `Game.set_board`, #168). Pierwsza tacka partii jest już wylosowana
    ślepo wewnątrz `Game.__init__`/`reset` (plansza wtedy pusta, i tak prawie
    zawsze grywalna) — to nie problem, bo świadomość dotyczy KOLEJNYCH odświeżeń."""
    game.generator.board = game.board
    return game


def patch_game_for_board_awareness():
    """Monkeypatch `Game.__init__`, żeby KAŻDA odtąd skonstruowana `Game` miała
    generator wpięty przez `attach_to_game` automatycznie — dla wywołujących,
    którzy (jak `tools/train_ntuple.py:run_episode`) sami konstruują `Game`
    wewnątrz pętli, bez okazji wywołać `attach_to_game` po fakcie. Nie dotyka
    `game.py`. Import `Game` leniwy (wewnątrz funkcji): `game.py` importuje
    `generator.Generator` na poziomie modułu, więc import odwrotny na poziomie
    modułu byłby cyklem."""
    from game import Game

    if getattr(Game.__init__, "_z6_217_board_aware_patch", False):
        return

    original_init = Game.__init__

    def patched_init(self, seed=None):
        original_init(self, seed)
        attach_to_game(self)

    patched_init._z6_217_board_aware_patch = True
    Game.__init__ = patched_init
