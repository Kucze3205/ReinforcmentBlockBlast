"""
Testy wyboru polityki w moście (#95): most nie ma prawa grać wyłącznie zachłanną,
a atrapa gry przekazywana do `policy.act` ma nieść wszystkie pola, których
`TrayPolicy` faktycznie czyta (w tym `combo_counter` — jego brak wywala się dopiero
na żywym emulatorze, #95).
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge
from board import Board
from pieces import PIECE_POOL
from policies import GreedyPolicy, TrayPolicy
from scoring import COMBO_COUNTER_BASE

BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])
ONE_BY_ONE = next(p for p in PIECE_POOL if p.shape == [[1]])


def _bridge_game():
    """Ta sama atrapa co `bridge.main`: plansza pusta, tacka z dwoma klockami."""
    board = Board()
    board.grid = [[0] * 8 for _ in range(8)]
    pieces = [BEAM2, ONE_BY_ONE, None]
    game = SimpleNamespace(board=board, pieces=pieces, combo=0, combo_counter=COMBO_COUNTER_BASE)
    moves = bridge.legal_moves(board, pieces)
    return game, moves


class TestBridgeGameStubHasComboCounter(unittest.TestCase):
    def test_stub_carries_fields_tray_policy_reads(self):
        game, moves = _bridge_game()
        self.assertTrue(hasattr(game, "combo_counter"))
        self.assertTrue(hasattr(game, "combo"))
        self.assertTrue(hasattr(game, "board"))
        self.assertTrue(hasattr(game, "pieces"))


class TestBridgeStubPlaysWithTrayPolicy(unittest.TestCase):
    def test_tray_policy_acts_without_attribute_error(self):
        game, moves = _bridge_game()
        policy = TrayPolicy()
        action = policy.act(game, moves)
        self.assertIn(action, moves)


class TestBridgeStubPlaysWithGreedyPolicy(unittest.TestCase):
    def test_greedy_policy_still_acts(self):
        game, moves = _bridge_game()
        policy = GreedyPolicy()
        action = policy.act(game, moves)
        self.assertIn(action, moves)


class TestResolvePolicySpec(unittest.TestCase):
    def test_default_is_greedy(self):
        self.assertEqual(bridge.resolve_policy_spec(["bridge.py", "30"], {}), "greedy")

    def test_env_var_used_when_no_cli_arg(self):
        spec = bridge.resolve_policy_spec(["bridge.py", "30"], {"BRIDGE_POLICY": "tray"})
        self.assertEqual(spec, "tray")

    def test_cli_arg_wins_over_env_var(self):
        spec = bridge.resolve_policy_spec(
            ["bridge.py", "30", "greedy"], {"BRIDGE_POLICY": "tray"}
        )
        self.assertEqual(spec, "greedy")


if __name__ == "__main__":
    unittest.main()
