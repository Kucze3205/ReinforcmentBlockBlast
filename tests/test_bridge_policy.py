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

from benchmark import build_policy
import bridge
from board import Board
from pieces import PIECE_POOL
from policies import GreedyPolicy, TrayPolicy
from scoring import COMBO_COUNTER_BASE

BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])
ONE_BY_ONE = next(p for p in PIECE_POOL if p.shape == [[1]])


def _bridge_game():
    """Ta sama atrapa co `bridge.main` — przez `bridge.make_game_stub`, żeby test
    nie mógł się rozjechać z produkcją (#103): plansza pusta, tacka z dwoma klockami."""
    board = Board()
    board.grid = [[0] * 8 for _ in range(8)]
    pieces = [BEAM2, ONE_BY_ONE, None]
    game = bridge.make_game_stub(board, pieces)
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


class TestBridgeStubPlaysWithLookaheadPolicy(unittest.TestCase):
    """#92 dołożyło `LookaheadPolicy`, najlepszą politykę benchmarku — most musi ją
    unieść, zanim zagra nią sesja na emulatorze (#103), tak samo jak dziś unosi
    `TrayPolicy`."""

    def test_lookahead_policy_acts_without_attribute_error(self):
        game, moves = _bridge_game()
        policy = build_policy("lookahead", {"torch_seed": 0})
        policy.reset(0)
        action = policy.act(game, moves)
        self.assertIn(action, moves)

    def test_lookahead_policy_with_tuned_weights_acts_without_attribute_error(self):
        game, moves = _bridge_game()
        policy = build_policy("lookahead:weights.json", {"torch_seed": 0})
        policy.reset(0)
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


class TestPolicySpecSource(unittest.TestCase):
    """Most ma wypisać na stdout, skąd wzięła się nazwa polityki (#103)."""

    def test_default_when_neither_given(self):
        self.assertEqual(bridge.policy_spec_source(["bridge.py", "30"], {}), "domyślna")

    def test_env_var_when_no_cli_arg(self):
        source = bridge.policy_spec_source(["bridge.py", "30"], {"BRIDGE_POLICY": "tray"})
        self.assertEqual(source, "BRIDGE_POLICY")

    def test_cli_arg_wins_over_env_var(self):
        source = bridge.policy_spec_source(
            ["bridge.py", "30", "greedy"], {"BRIDGE_POLICY": "tray"}
        )
        self.assertEqual(source, "argv")


class TestRunId(unittest.TestCase):
    """Wartość dająca odtwarzalność `LookaheadPolicy.reset` między przebiegami (#103)."""

    def test_falls_back_to_local_without_env(self):
        self.assertEqual(bridge.run_id({}), "local")

    def test_uses_github_run_id(self):
        self.assertEqual(bridge.run_id({"GITHUB_RUN_ID": "42"}), "42")

    def test_bridge_run_id_wins_over_github_run_id(self):
        env = {"BRIDGE_RUN_ID": "7", "GITHUB_RUN_ID": "42"}
        self.assertEqual(bridge.run_id(env), "7")


if __name__ == "__main__":
    unittest.main()
