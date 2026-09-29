"""
Block Blast Board Logic
"""
from itertools import permutations

TRAY_PLAYABLE_NODE_BUDGET = 20000


class Board:
    WIDTH = 8
    HEIGHT = 8

    def __init__(self):
        self.grid = [[0 for _ in range(Board.WIDTH)] for _ in range(Board.HEIGHT)]

    def reset(self):
        self.grid = [[0 for _ in range(Board.WIDTH)] for _ in range(Board.HEIGHT)]

    def place_piece(self, piece, x, y):
        if piece is None:
            return False
        if not self.can_place_piece(piece, x, y):
            return False
        
        for dy, row in enumerate(piece.shape):
            for dx, cell in enumerate(row):
                if cell:
                    self.grid[y + dy][x + dx] = 1
        return True
    
    def can_place_piece(self, piece, x, y):
        if piece is None:
            return False
        for dy, row in enumerate(piece.shape):
            for dx, cell in enumerate(row):
                if cell:
                    bx, by = x + dx, y + dy
                    if not (0 <= bx < Board.WIDTH and 0 <= by < Board.HEIGHT):
                        return False
                    if self.grid[by][bx]:
                        return False
        return True

    def check_full_lines(self):
        full_rows = [i for i, row in enumerate(self.grid) if all(row)]
        full_cols = [j for j in range(Board.WIDTH) if all(self.grid[i][j] for i in range(Board.HEIGHT))]
        return full_rows, full_cols

    def clear_lines(self, rows, cols):
        for r in rows:
            self.grid[r] = [0] * Board.WIDTH
        for c in cols:
            for r in range(Board.HEIGHT):
                self.grid[r][c] = 0

    def copy(self):
        new_board = Board()
        new_board.grid = [row[:] for row in self.grid]
        return new_board


# ---------------------------------------------------------------------------
# Grywalność tacki (3 kształty) na surowej siatce (`grid`, lista list), z
# czyszczeniem pełnych linii między postawieniami -- przeniesione z
# `tools/z6_testy.py` (#211/#217) do wspólnego modułu bez zależności na
# `generator.py`, żeby `generator.py` mógł to importować bez cyklu importu
# (z6_testy importuje `Generator`). Jedyne miejsce prawdy tej definicji.
# ---------------------------------------------------------------------------


def _tray_can_place(grid, shape, x, y):
    for dy, row in enumerate(shape):
        for dx, cell in enumerate(row):
            if cell:
                bx, by = x + dx, y + dy
                if not (0 <= bx < Board.WIDTH and 0 <= by < Board.HEIGHT):
                    return False
                if grid[by][bx]:
                    return False
    return True


def _tray_place_and_clear(grid, shape, x, y):
    new_grid = [row[:] for row in grid]
    for dy, row in enumerate(shape):
        for dx, cell in enumerate(row):
            if cell:
                new_grid[y + dy][x + dx] = 1
    full_rows = [i for i, row in enumerate(new_grid) if all(row)]
    full_cols = [c for c in range(Board.WIDTH) if all(new_grid[r][c] for r in range(Board.HEIGHT))]
    for r in full_rows:
        new_grid[r] = [0] * Board.WIDTH
    for c in full_cols:
        for r in range(Board.HEIGHT):
            new_grid[r][c] = 0
    return new_grid


def _tray_dfs_playable(grid, shapes, idx, budget):
    if idx == len(shapes):
        return True, budget
    shape = shapes[idx]
    for y in range(Board.HEIGHT):
        for x in range(Board.WIDTH):
            if budget <= 0:
                return None, budget
            budget -= 1
            if _tray_can_place(grid, shape, x, y):
                new_grid = _tray_place_and_clear(grid, shape, x, y)
                result, budget = _tray_dfs_playable(new_grid, shapes, idx + 1, budget)
                if result:
                    return True, budget
                if result is None:
                    return None, budget
    return False, budget


def tray_playable(grid, shapes, node_budget=TRAY_PLAYABLE_NODE_BUDGET):
    """Czy da się postawić wszystkie 3 kształty w JAKIEJŚ kolejności, z
    czyszczeniem pełnych linii między postawieniami (stąd kolejność ma
    znaczenie). Zwraca True/False, albo None gdy `node_budget` (łączny, przez
    wszystkie 6 permutacji) się wyczerpał zanim padło rozstrzygnięcie."""
    budget = node_budget
    for perm in permutations(range(3)):
        ordered = [shapes[i] for i in perm]
        result, budget = _tray_dfs_playable(grid, ordered, 0, budget)
        if result:
            return True
        if result is None:
            return None
    return False
