"""
Deterministic Piece Generator
"""
import random
from pieces import PIECE_POOL

class Generator:
    def __init__(self, seed=None):
        self.seed = seed
        self.rng = random.Random()

    def reset(self, seed=None):
        self.seed = seed
        self.rng = random.Random()

    def next_pieces(self):
        return [self.rng.choice(PIECE_POOL) for _ in range(3)]
    
    def generate_board(self, board, pieces):
        board.grid = [[1 for _ in range(8)] for _ in range(8)]
        for piece in pieces:
            x = self.rng.randint(0, 8 - len(piece.shape[0]))
            y = self.rng.randint(0, 8 - len(piece.shape))
            for dy, row in enumerate(piece.shape):
                for dx, cell in enumerate(row):
                    if cell:
                        board.grid[y + dy][x + dx] = 0
        for y in range(8):
            for x in range(8):
                if self.rng.choice([0, 1, 2]) == 1: #33% chance to clear a cell
                    board.grid[y][x] = 0
        return board
