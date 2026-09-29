import copy
import unittest
from unittest import mock

from game import Game
from pieces import PIECE_POOL
import tools.measure_death_avoidability as mda

P = {p.name: p for p in PIECE_POOL}


def _prev_game():
    """Plansza pelna poza przekatna (zadna linia nie jest pelna), tacka: jedno 1x1.

    Postawienie w (i, i) czyści wiersz i kolumnę i: osiem plansz koncowych."""
    g = Game(seed=1)
    g.board.grid = [[0 if x == y else 1 for x in range(8)] for y in range(8)]
    g.pieces = [P["1x1"], None, None]
    return g


def _final(g, x, y):
    b = g.board.copy()
    b.place_piece(P["1x1"], x, y)
    b.clear_lines(*b.check_full_lines())
    return b.grid


def _death_game(grid, name):
    d = Game(seed=2)
    d.board.grid = [r[:] for r in grid]
    d.pieces = [P[name]] * 3
    return d


VALUES = {0: 1, 1: 5, 2: 0.5, 4: 3}


def _index(grid):
    """Numer i planszy koncowej: jedyny wiersz calkiem pusty (postawienie w (i, i))."""
    return next(i for i, row in enumerate(grid) if not any(row))


def _value(grid):
    return VALUES.get(_index(grid), 0)


class DeathAvoidabilityTest(unittest.TestCase):
    def test_avoidable_one_tray_earlier(self):
        g = _prev_game()
        chosen = _final(g, 1, 1)

        def fake_tray(game, grid):
            # przezywaja tylko plansze 0 i 2
            return [P["1x1"]] * 3 if _index(grid) in (0, 2) else [P["rect23-0"]] * 3

        death = _death_game(chosen, "rect23-0")  # wybrana plansza 1: tacka smierci nieukladalna
        with mock.patch.object(mda, "next_tray_like_game", fake_tray):
            r = mda.analyze_death(g, death, _value)
        self.assertFalse(r["a_solvable"])
        b = r["b"]
        self.assertTrue(b["any_survive"])
        self.assertEqual((b["n_final_boards"], b["n_survive"]), (8, 2))
        self.assertEqual(b["survive_frac"], 0.25)
        self.assertEqual(b["chosen_rank"], 1)
        self.assertEqual(b["best_survivor_rank"], 3)  # plansza 0 (1) za 1 (5) i 4 (3)
        self.assertFalse(b["sampled"])

    def test_unavoidable_one_tray_earlier(self):
        g = _prev_game()
        death = _death_game(_final(g, 1, 1), "rect23-0")
        with mock.patch.object(mda, "next_tray_like_game", lambda game, grid: [P["rect23-0"]] * 3):
            r = mda.analyze_death(g, death, _value)
        self.assertFalse(r["b"]["any_survive"])
        self.assertEqual(r["b"]["n_survive"], 0)
        self.assertIsNone(r["b"]["best_survivor_rank"])

    def test_a_solvable_when_tray_fits(self):
        g = _prev_game()
        death = _death_game(g.board.grid, "1x1")
        r = mda.analyze_death(None, death, _value)
        self.assertTrue(r["a_solvable"])
        self.assertIsNone(r["b"])

    def test_sampling_keeps_chosen(self):
        g = _prev_game()
        b_grid = _final(g, 1, 1)
        death = _death_game(b_grid, "rect23-0")
        with mock.patch.object(mda, "next_tray_like_game", lambda game, grid: [P["1x1"]] * 3):
            r = mda.analyze_death(g, death, _value, sample_limit=3)
        self.assertTrue(r["b"]["sampled"])
        self.assertEqual(r["b"]["n_evaluated"], 3)
        self.assertTrue(r["b"]["chosen_in_set"])

    def test_copy_draws_like_game_and_leaves_original(self):
        game = Game(seed=7)
        snap = copy.deepcopy(game)
        state_before = snap.generator.rng.getstate()
        for _ in range(3):
            game.step(game.available_actions()[0])
        expected = game.pieces
        got = mda.next_tray_like_game(snap, game.board.grid)
        self.assertEqual([p.name for p in got], [p.name for p in expected])
        self.assertEqual(snap.generator.rng.getstate(), state_before)
        self.assertEqual(snap.board.grid, [[0] * 8 for _ in range(8)])


if __name__ == "__main__":
    unittest.main()
