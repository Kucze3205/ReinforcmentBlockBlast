"""
Block Blast Game Engine
"""
from ui import UI, COLORS, SCREEN_WIDTH, SCREEN_HEIGHT
from board import Board
from generator import Generator
import pygame
import sys
import time
from scoring import placement_points, simultaneous_clear_points, streak_bonus

class Game:
    def __init__(self, seed=None):
        self.board = Board()
        self.generator = Generator(seed)
        self.ui = UI()
        self.score = 0
        self.streak = 0
        self.round_placement = 0
        self.pieces = self.generator.next_pieces()
        self.done = False
        self.last_lines_cleared = 0

        self.refresh_ui()

    def reset(self, seed=None):
        self.generator.reset(seed)
        self.board.reset()
        self.score = 0
        self.streak = 0
        self.round_placement = 0
        self.pieces = self.generator.next_pieces()
        self.done = False
        self.last_lines_cleared = 0

        self.refresh_ui()

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
    
    def refresh_ui(self):
        self.ui.screen.fill(COLORS['bg'])
        self.ui.draw_grid(self.board.grid)
        self.ui.draw_panel(self.pieces)
        self.ui.draw_info(self.score, self.streak, self.round_placement + 1)
        pygame.display.flip()
        pygame.event.pump()
    


    def step(self, action):

        message = "successful placement"
        if self.done:
            message = {"game_over": True}
            return self.get_state(), self.score, True, message
        idx, x, y = action
        piece = self.pieces[idx]
        if not self.board.place_piece(piece, x, y):
            message = {"wrong_placement": True}
            self.done = True
            return self.get_state(), self.score, self.done, message
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

        #self.ui.clock.tick(1)
        self.ui.screen.fill(COLORS['bg'])
        self.ui.draw_grid(self.board.grid)
        self.ui.draw_panel(self.pieces)
        self.ui.draw_info(self.score, self.streak, self.round_placement + 1)
        pygame.display.flip()

        return self.get_state(), self.score, self.done, message

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
            "pieces": [self.pieces[0], self.pieces[1], self.pieces[2]],
            "score": self.score,
            "streak": self.streak,
            "placement_in_round": self.round_placement + 1
        }
