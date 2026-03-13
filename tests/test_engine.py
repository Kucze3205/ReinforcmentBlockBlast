"""
Block Blast Engine Test Suite
"""
import unittest
from game import Game

class TestBlockBlastEngine(unittest.TestCase):
    def setUp(self):
        self.game = Game(seed=42)
        self.game.reset(seed=42)

    def test_placement_scoring(self):
        state = self.game.get_state()
        piece = state['pieces'][0]
        action = (0, 0, 0)
        _, reward, _, _ = self.game.step(action)
        self.assertEqual(reward, sum(cell for row in piece.shape for cell in row))

    def test_line_clear_scoring(self):
        self.game.board.grid = [[1]*8 for _ in range(8)]
        piece = self.game.pieces[0]
        self.game.pieces[0] = piece
        action = (0, 0, 0)
        _, reward, _, _ = self.game.step(action)
        self.assertTrue(reward >= 10)

    def test_streak_bonus(self):
        self.game.streak = 1
        self.game.round_placement = 2
        self.game.last_lines_cleared = 1
        self.game.pieces = [self.game.pieces[0], None, None]
        action = (0, 0, 0)
        _, reward, _, _ = self.game.step(action)
        self.assertTrue(reward >= 10)

    def test_invalid_placement(self):
        action = (0, 100, 100)
        _, reward, _, info = self.game.step(action)
        self.assertTrue('invalid' in info)

    def test_game_over_detection(self):
        self.game.board.grid = [[1]*8 for _ in range(8)]
        self.game.pieces = [self.game.pieces[0], self.game.pieces[1], self.game.pieces[2]]
        actions = self.game.available_actions()
        self.assertEqual(len(actions), 0)
        self.assertTrue(self.game.done)

    def test_determinism(self):
        g1 = Game(seed=123)
        g2 = Game(seed=123)
        s1 = g1.reset(seed=123)
        s2 = g2.reset(seed=123)
        self.assertEqual([p.name for p in s1['pieces']], [p.name for p in s2['pieces']])

if __name__ == '__main__':
    unittest.main()
