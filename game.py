"""
Block Blast Game Engine
"""
from board import Board
from generator import PieceGenerator
from scoring import placement_points, simultaneous_clear_points, streak_bonus

class Game:
    def __init__(self, seed=None):
        self.generator = PieceGenerator(seed)
        self.board = Board()
        self.score = 0
        self.streak = 0
        self.round_placement = 0
        self.pieces = self.generator.next_pieces()
        self.done = False
        self.last_lines_cleared = 0

    def reset(self, seed=None):
        self.generator.reset(seed)
        self.board.reset()
        self.score = 0
        self.streak = 0
        self.round_placement = 0
        self.pieces = self.generator.next_pieces()
        self.done = False
        self.last_lines_cleared = 0
        return self.get_state()

    def available_actions(self):
        actions = []
        for idx, piece in enumerate(self.pieces):
            if piece is None:
                continue
            for y in range(Board.HEIGHT - len(piece.shape) + 1):
                for x in range(Board.WIDTH - len(piece.shape[0]) + 1):
                    temp_board = self.board.copy()
                    if temp_board.place_piece(piece, x, y):
                        actions.append((idx, x, y))
        return actions

    def step(self, action):
        if self.done:
            return self.get_state(), 0, True, {}
        idx, x, y = action
        piece = self.pieces[idx]
        if not self.board.place_piece(piece, x, y):
            return self.get_state(), 0, self.done, {"invalid": True}
        reward = placement_points(piece)
        rows, cols = self.board.check_full_lines()
        k = len(rows) + len(cols)
        reward += simultaneous_clear_points(k)
        self.last_lines_cleared += k
        self.board.clear_lines(rows, cols)
        self.pieces[idx] = None
        self.round_placement += 1
        if self.round_placement == 3:
            if self.last_lines_cleared > 0:
                self.streak += 1
            else:
                self.streak = 0
            reward += streak_bonus(self.streak)
            self.pieces = self.generator.next_pieces()
            self.round_placement = 0
            self.last_lines_cleared = 0
        self.score += reward
        self.done = not self._can_place_any()
        return self.get_state(), reward, self.done, {}

    def _can_place_any(self):
        for idx, piece in enumerate(self.pieces):
            if piece is None:
                continue
            for y in range(Board.HEIGHT - len(piece.shape) + 1):
                for x in range(Board.WIDTH - len(piece.shape[0]) + 1):
                    temp_board = self.board.copy()
                    if temp_board.place_piece(piece, x, y):
                        return True
        return False

    def get_state(self):
        return {
            "board": [row[:] for row in self.board.grid],
            "pieces": [p for p in self.pieces],
            "score": self.score,
            "streak": self.streak,
            "placement_in_round": self.round_placement + 1
        }
