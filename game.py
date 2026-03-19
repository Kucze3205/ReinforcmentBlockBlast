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
                    if temp_board.can_place_piece(piece, x, y):
                        actions.append((idx, x, y))
        return actions
    
    def refresh_ui(self):
        self.ui.screen.fill(COLORS['bg'])
        self.ui.draw_grid(self.board.grid)
        self.ui.draw_panel(self.pieces)
        self.ui.draw_info(self.score, self.streak, self.round_placement + 1)
        self.ui.draw_buttons()
        pygame.display.flip()
        pygame.event.pump()
    


    def step(self, action):

        idx, x, y = action
        piece = self.pieces[idx]
        this_round_score = 0
        reward = 0

        if not self.board.place_piece(piece, x, y):
            self.done = True
            return -10, self.score, self.done, "wrong_placement"
        
        # Calculate reward: 
        # Base points for placement (+1 for each cell)
        this_round_score = placement_points(piece)
        
        # bonus point for simultaneous clears (k^2 * 10)
        rows, cols = self.board.check_full_lines()
        k = len(rows) + len(cols)

        if(k > 0):
            this_round_score += simultaneous_clear_points(k)
            reward += simultaneous_clear_points(k)

        self.last_lines_cleared += k
        self.board.clear_lines(rows, cols)

        # BONUS: sprawdź czy plansza jest całkowicie pusta po ruchu
        if all(all(cell == 0 for cell in row) for row in self.board.grid):
            this_round_score += 100  # bonus za wyczyszczenie całej planszy
            reward += 1000

        self.pieces[idx] = None

        self.round_placement += 1
        if self.round_placement == 3:
            if self.last_lines_cleared > 0:
                self.streak += 1
            else:
                self.streak = 0

            # Bonus points for streaks (s^2 * 5)    
            this_round_score += streak_bonus(self.streak)
            reward += streak_bonus(self.streak)

            self.pieces = self.generator.next_pieces()

            self.round_placement = 0
            self.last_lines_cleared = 0

        self.score += this_round_score
        
        #check if there is no place left for any piece, if so - end the game
        if not self._can_place_any():
            self.refresh_ui()
            return -10, self.score, True, "game_over"

        #self.ui.clock.tick(1)
        self.refresh_ui()

        return reward, self.score, self.done, "successful placement"

    def _can_place_any(self):
        for  idx, piece in enumerate(self.pieces):
            if piece is None:
                continue
            for y in range(Board.HEIGHT - len(piece.shape) + 1):
                for x in range(Board.WIDTH - len(piece.shape[0]) + 1):
                    temp_board = self.board.copy()
                    if temp_board.can_place_piece(piece, x, y):
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
