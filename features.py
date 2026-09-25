"""
Cechy planszy do oceny stanu gry przez `HeuristicPolicy` (`policies.py`).

Uzasadnienie każdej wagi domyślnej jest w `docs/cechy-planszy.md`, nie tutaj —
ten plik liczy tylko liczby, nie decyduje, ile ważą.
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


def features(board):
    """Zwraca krotkę liczb w kolejności `FEATURE_NAMES`, licząc od `board.grid`."""
    grid = board.grid
    return (
        _occupied_cells(grid),
        _surrounded_empty(grid),
        _empty_regions(grid),
        _largest_empty_rectangle(grid),
        _near_full_lines(grid),
        _placeable_shapes(board),
    )


def _occupied_cells(grid):
    return sum(1 for row in grid for cell in row if cell)


def _surrounded_empty(grid):
    """Puste pole, któremu wszystkie 4 sąsiedztwa to zajęte pole albo krawędź planszy."""
    count = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x]:
                continue
            up = grid[y - 1][x] if y > 0 else 1
            down = grid[y + 1][x] if y < HEIGHT - 1 else 1
            left = grid[y][x - 1] if x > 0 else 1
            right = grid[y][x + 1] if x < WIDTH - 1 else 1
            if up and down and left and right:
                count += 1
    return count


def _empty_regions(grid):
    """Liczba spójnych (4-sąsiedztwo) obszarów pustych pól."""
    seen = [[False] * WIDTH for _ in range(HEIGHT)]
    regions = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if grid[y][x] or seen[y][x]:
                continue
            regions += 1
            stack = [(y, x)]
            seen[y][x] = True
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < HEIGHT and 0 <= nx < WIDTH and not grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
    return regions


def _largest_empty_rectangle(grid):
    """Pole (liczba komórek) największego prostokąta złożonego wyłącznie z pustych pól."""
    heights = [0] * WIDTH
    best = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            heights[x] = 0 if grid[y][x] else heights[x] + 1
        best = max(best, _largest_rect_in_histogram(heights))
    return best


def _largest_rect_in_histogram(heights):
    stack = []
    best = 0
    extended = list(heights) + [0]
    for i, h in enumerate(extended):
        while stack and extended[stack[-1]] > h:
            height = extended[stack.pop()]
            width = i if not stack else i - stack[-1] - 1
            best = max(best, height * width)
        stack.append(i)
    return best


def _near_full_lines(grid):
    """Liczba wierszy i kolumn, którym brakuje nie więcej niż dwóch pól do pełna."""
    count = 0
    for y in range(HEIGHT):
        if WIDTH - sum(grid[y]) <= 2:
            count += 1
    for x in range(WIDTH):
        if HEIGHT - sum(grid[y][x] for y in range(HEIGHT)) <= 2:
            count += 1
    return count


def _placeable_shapes(board):
    """Liczba kanonicznych typów (`pieces.PIECE_TYPES`), z których co najmniej jedna
    orientacja da się jeszcze gdziekolwiek postawić na tej planszy."""
    count = 0
    for pose_indices in PIECE_TYPES:
        if any(_can_place_anywhere(board, PIECE_POOL[idx]) for idx in pose_indices):
            count += 1
    return count


def _can_place_anywhere(board, piece):
    shape = piece.shape
    h, w = len(shape), len(shape[0])
    for y in range(HEIGHT - h + 1):
        for x in range(WIDTH - w + 1):
            if board.can_place_piece(piece, x, y):
                return True
    return False
