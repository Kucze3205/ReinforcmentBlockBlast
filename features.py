"""
Cechy planszy do oceny stanu gry przez `HeuristicPolicy` i `TrayPolicy` (`policies.py`).

Uzasadnienie każdej wagi domyślnej jest w `docs/cechy-planszy.md`, nie tutaj —
ten plik liczy tylko liczby, nie decyduje, ile ważą.

Implementacja liczy na maskach bitowych planszy (bit `y*WIDTH+x`) zamiast
chodzić po `board.grid` osobno w każdej cesze (#88) — wartości identyczne z
poprzednią wersją opartą na zagnieżdżonych listach, tylko szybciej liczone.
`TrayPolicy` woła `features()` raz na każdego rozwijanego kandydata, więc to
gorący punkt przeszukania tacki (`docs/przeszukanie-tacki.md`).
"""
from board import Board
from pieces import PIECE_POOL, PIECE_TYPES

WIDTH = Board.WIDTH
HEIGHT = Board.HEIGHT

FEATURE_NAMES = (
    "occupied_cells",
    "surrounded_empty",
    "empty_regions",
    "largest_empty_rect",
    "near_full_lines",
    "placeable_shapes",
)

FULL_ROW_MASK = (1 << WIDTH) - 1
COL0_MASK = sum(1 << (y * WIDTH) for y in range(HEIGHT))
COL_LAST_MASK = sum(1 << (y * WIDTH + WIDTH - 1) for y in range(HEIGHT))


def features(board):
    """Zwraca krotkę liczb w kolejności `FEATURE_NAMES`, licząc od `board.grid`."""
    rows = [_row_bits(row) for row in board.grid]
    board_bits = 0
    for y, bits in enumerate(rows):
        board_bits |= bits << (y * WIDTH)
    return (
        _occupied_cells(rows),
        _surrounded_empty(rows),
        _empty_regions(rows),
        _largest_empty_rectangle(rows),
        _near_full_lines(rows),
        _placeable_shapes(board_bits),
    )


def _row_bits(row):
    bits = 0
    for x in range(WIDTH):
        if row[x]:
            bits |= 1 << x
    return bits


def _occupied_cells(rows):
    return sum(bin(r).count("1") for r in rows)


def _surrounded_empty(rows):
    """Puste pole, któremu wszystkie 4 sąsiedztwa to zajęte pole albo krawędź planszy."""
    count = 0
    for y, row in enumerate(rows):
        up = rows[y - 1] if y > 0 else FULL_ROW_MASK
        down = rows[y + 1] if y < HEIGHT - 1 else FULL_ROW_MASK
        left = ((row << 1) | 1) & FULL_ROW_MASK
        right = (row >> 1) | (1 << (WIDTH - 1))
        occupied_neighbors = up & down & left & right
        empty = (~row) & FULL_ROW_MASK
        count += bin(occupied_neighbors & empty).count("1")
    return count


def _empty_regions(rows):
    """Liczba spójnych (4-sąsiedztwo) obszarów pustych pól.

    Rozlewanie na masce bitowej całej planszy: z każdego ziarna rozszerza
    granicę o sąsiadów (bitowe przesunięcia), dopóki się nie ustabilizuje —
    liczba iteracji to średnica obszaru, nie liczba jego komórek.
    """
    remaining = 0
    for y, row in enumerate(rows):
        remaining |= ((~row) & FULL_ROW_MASK) << (y * WIDTH)

    regions = 0
    while remaining:
        seed = remaining & (-remaining)
        component = 0
        frontier = seed
        while frontier:
            component |= frontier
            frontier = _neighbor_mask(frontier) & remaining & ~component
        regions += 1
        remaining &= ~component
    return regions


def _neighbor_mask(mask):
    left = (mask & ~COL0_MASK) >> 1
    right = (mask & ~COL_LAST_MASK) << 1
    up = mask >> WIDTH
    down = mask << WIDTH
    return left | right | up | down


def _largest_empty_rectangle(rows):
    """Pole (liczba komórek) największego prostokąta złożonego wyłącznie z pustych pól.

    Dla każdej pary wierszy (y1, y2) maska AND pustych wierszy w tym zakresie
    daje kolumny puste we wszystkich tych wierszach; najdłuższy ciąg jedynek w
    tej masce (tabela `_LONGEST_RUN`) razy wysokość (y2-y1+1) to kandydat na
    pole. Plansza ma tylko `HEIGHT` wierszy, więc O(HEIGHT²) par jest tanie.
    """
    empty_rows = [(~r) & FULL_ROW_MASK for r in rows]
    best = 0
    for y1 in range(HEIGHT):
        running = FULL_ROW_MASK
        for y2 in range(y1, HEIGHT):
            running &= empty_rows[y2]
            if running == 0:
                break
            area = (y2 - y1 + 1) * _LONGEST_RUN[running]
            if area > best:
                best = area
    return best


def _near_full_lines(rows):
    """Liczba wierszy i kolumn, którym brakuje nie więcej niż dwóch pól do pełna."""
    count = 0
    for r in rows:
        if WIDTH - bin(r).count("1") <= 2:
            count += 1
    for x in range(WIDTH):
        col_count = 0
        for r in rows:
            col_count += (r >> x) & 1
        if HEIGHT - col_count <= 2:
            count += 1
    return count


def _placeable_shapes(board_bits):
    """Liczba kanonicznych typów (`pieces.PIECE_TYPES`), z których co najmniej jedna
    orientacja da się jeszcze gdziekolwiek postawić na tej planszy.

    Pozycje każdej orientacji są prekomputowane raz (`_PIECE_MASKS`) jako maski
    bitowe; sprawdzenie kolizji to jedno bitowe AND zamiast przejścia po
    komórkach klocka przez `Board.can_place_piece` dla każdej pozycji.
    """
    count = 0
    for pose_indices in PIECE_TYPES:
        placeable = False
        for idx in pose_indices:
            for mask in _PIECE_MASKS[idx]:
                if board_bits & mask == 0:
                    placeable = True
                    break
            if placeable:
                break
        if placeable:
            count += 1
    return count


def _piece_position_masks(piece):
    shape = piece.shape
    h, w = len(shape), len(shape[0])
    masks = []
    for y in range(HEIGHT - h + 1):
        for x in range(WIDTH - w + 1):
            mask = 0
            for dy, row in enumerate(shape):
                for dx, cell in enumerate(row):
                    if cell:
                        mask |= 1 << ((y + dy) * WIDTH + (x + dx))
            masks.append(mask)
    return masks


def _longest_run_table():
    table = [0] * (1 << WIDTH)
    for mask in range(1 << WIDTH):
        best = cur = 0
        for x in range(WIDTH):
            if (mask >> x) & 1:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        table[mask] = best
    return table


_PIECE_MASKS = [_piece_position_masks(p) for p in PIECE_POOL]
_LONGEST_RUN = _longest_run_table()
