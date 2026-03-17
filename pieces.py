"""
Block Blast Piece Library
"""

class Piece:
    def __init__(self, shape, name):
        self.shape = shape
        self.name = name
        self.index = None  # Will be set when added to the pool


PIECE_SHAPES = [
    # Tetrominoes
    ([[1, 1, 1, 1]], "I"),
    ([[1, 1], [1, 1]], "O"),
    ([[0, 1, 0], [1, 1, 1]], "T"),
    ([[0, 1, 1], [1, 1, 0]], "S"),
    ([[1, 1, 0], [0, 1, 1]], "Z"),
    ([[1, 0, 0], [1, 1, 1]], "J"),
    ([[0, 0, 1], [1, 1, 1]], "L"),
    # Extra shapes
    ([[1]], "1x1"),
    ([[1, 1]], "1x2"),
    ([[1], [1]], "2x1"),
    ([[1, 1, 1]], "1x3"),
    ([[1], [1], [1]], "3x1"),
    ([[1, 1], [1, 1]], "2x2"),
    ([[1], [1], [1], [1]], "4x1"),
    ([[1, 1, 1], [1, 1, 1], [1, 1, 1]], "3x3"),
    ([[1, 1, 1], [1, 1, 1]], "2x3"),
    ([[1, 1], [1, 1], [1, 1]], "3x2"),
]

def pad_to_4x4_top_right(shape):
    rows = len(shape)
    cols = len(shape[0])
    grid = [[0]*4 for _ in range(4)]
    for r in range(rows):
        for c in range(cols):
            grid[r][c] = shape[r][c]
    return grid

PIECE_SHAPES_4X4 = [
    (pad_to_4x4_top_right(shape), name)
    for shape, name in PIECE_SHAPES
]

PIECE_POOL = [Piece(shape, name) for shape, name in PIECE_SHAPES]
for i, piece in enumerate(PIECE_POOL):
    piece.index = i

