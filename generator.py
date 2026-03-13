"""
Deterministic Piece Generator
"""
import random
from pieces import PIECE_POOL

class PieceGenerator:
    def __init__(self, seed=None):
        self.seed = seed
        self.rng = random.Random(seed)

    def reset(self, seed=None):
        self.seed = seed
        self.rng = random.Random(seed)

    def next_pieces(self):
        return [self.rng.choice(PIECE_POOL) for _ in range(3)]
