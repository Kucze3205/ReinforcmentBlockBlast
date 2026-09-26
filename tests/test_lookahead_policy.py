"""
Testy `LookaheadPolicy` (#92): węzeł losowy nad następną tacką.

Trzy rzeczy są tu wiążące i nie wolno ich zepsuć przy strojeniu parametrów:
legalność ruchu (#51), nietykalność stanu gry (#58) i determinizm losowania
próbek względem `reset(seed)` — bez tego benchmark na stałych seedach przestaje
cokolwiek znaczyć (#8).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board import Board
from game import Game
from pieces import PIECE_POOL
from policies import LookaheadPolicy, TrayPolicy

ONE_BY_ONE = next(p for p in PIECE_POOL if p.shape == [[1]])
SQUARE3 = next(p for p in PIECE_POOL if p.shape == [[1] * 3] * 3)


def play(policy, seed, move_cap=120):
    """Cała sekwencja akcji jednej partii — porównywalna znak w znak."""
    game = Game(seed=seed)
    policy.reset(seed)
    moves = []
    while not game.done and len(moves) < move_cap:
        actions = game.available_actions()
        if not actions:
            break
        action = policy.act(game, actions)
        moves.append(action)
        game.step(action)
    return tuple(moves)


class TestLookaheadDoesNotMutate(unittest.TestCase):
    """`act` nie wolno ruszyć gry ani pociągnąć jej generatora (#58)."""

    def test_game_state_unchanged_after_act(self):
        policy = LookaheadPolicy()
        for seed in (1, 7, 42):
            game = Game(seed=seed)
            policy.reset(seed)
            before = game.get_state()
            policy.act(game, game.available_actions())
            self.assertEqual(before, game.get_state(), "seed=%r" % (seed,))

    def test_game_generator_not_advanced(self):
        """Próbki idą z własnego generatora polityki, nie z tego, którym gra losuje."""
        game = Game(seed=11)
        policy = LookaheadPolicy()
        policy.reset(11)
        before = game.generator.rng.getstate()
        policy.act(game, game.available_actions())
        self.assertEqual(before, game.generator.rng.getstate())


class TestLookaheadReturnsLegalAction(unittest.TestCase):
    """Kontrakt z #51: wyłącznie ruchy z `available_actions()`, zero nielegalnych."""

    def test_every_action_of_a_whole_game_is_legal(self):
        policy = LookaheadPolicy()
        for seed in (2, 13, 99):
            game = Game(seed=seed)
            policy.reset(seed)
            n = 0
            while not game.done and n < 60:
                actions = game.available_actions()
                if not actions:
                    break
                action = policy.act(game, actions)
                self.assertIn(action, actions, "seed=%r ruch=%d" % (seed, n))
                game.step(action)
                n += 1
            self.assertGreater(n, 0, "seed=%r: partia nie ruszyła" % (seed,))


class TestLookaheadSamplingIsDeterministic(unittest.TestCase):
    """Dwa przebiegi tego samego seeda dają tę samą sekwencję akcji."""

    SEEDS = (4101, 4102, 4103)

    def test_same_seed_same_sequence_same_instance(self):
        policy = LookaheadPolicy()
        for seed in self.SEEDS:
            self.assertEqual(play(policy, seed), play(policy, seed), "seed=%r" % (seed,))

    def test_same_seed_same_sequence_fresh_instance(self):
        for seed in self.SEEDS:
            self.assertEqual(
                play(LookaheadPolicy(), seed),
                play(LookaheadPolicy(), seed),
                "seed=%r" % (seed,),
            )

    def test_interleaved_games_do_not_leak_state(self):
        """Ta sama instancja po innej partii nadal odtwarza sekwencję — `reset` czyści."""
        policy = LookaheadPolicy()
        first = play(policy, self.SEEDS[0])
        play(policy, self.SEEDS[1])
        self.assertEqual(play(policy, self.SEEDS[0]), first)

    def test_different_seeds_draw_different_trays(self):
        """Ziarno próbek zależy od seeda partii — inaczej wszystkie partie
        widziałyby tę samą przyszłość."""
        a = LookaheadPolicy()
        a.reset(1)
        b = LookaheadPolicy()
        b.reset(2)
        self.assertNotEqual(
            [a._sampler.next_pieces() for _ in range(5)],
            [b._sampler.next_pieces() for _ in range(5)],
        )


class TestLookaheadDegeneratesToTray(unittest.TestCase):
    """Bez próbek drugi poziom znika — muszą wyjść decyzje `TrayPolicy`.

    To jest test na to, że pierwszy poziom `LookaheadPolicy` jest naprawdę
    przeszukaniem `TrayPolicy`, a nie jego wariacją: cała różnica siedzi w
    węźle losowym, który tu jest wyłączony.
    """

    def test_samples_zero_matches_tray_policy(self):
        for seed in (4201, 4202, 4203):
            self.assertEqual(
                play(LookaheadPolicy(samples=0), seed),
                play(TrayPolicy(), seed),
                "seed=%r" % (seed,),
            )


class TestLookaheadAvoidsTrapBoard(unittest.TestCase):
    """Plansza-pułapka: nie zabetonować jedynego miejsca na większy klocek.

    Plansza jest zapełniona poza dwoma obszarami: kwadratem 3×3 w lewym górnym
    rogu i rozproszonymi pojedynczymi dziurami. Tacka ma jeden klocek `1x1`.
    Postawienie go w kwadracie 3×3 psuje jedyne miejsce, w które wejdzie coś
    większego niż `1x1`; postawienie w pojedynczej dziurze zostawia kwadrat
    nietknięty. Punktowo oba ruchy są identyczne (1 komórka, zero linii).

    Uczciwie: **`TrayPolicy` wybiera tu tak samo** (sprawdzone), bo cecha
    `placeable_shapes` już to widzi. Ten test jest zaporą na regresję
    `LookaheadPolicy` do ruchów oczywiście złych, a **nie** dowodem, że drugi
    poziom coś kupuje — dowodem na to jest tabela w `docs/lookahead.md`.
    """

    def _game(self):
        game = Game(seed=17)
        game.board.grid = [[1] * Board.WIDTH for _ in range(Board.HEIGHT)]
        for y in range(3):
            for x in range(3):
                game.board.grid[y][x] = 0
        for y, x in ((5, 6), (6, 6), (7, 3)):
            game.board.grid[y][x] = 0
        game.pieces = [ONE_BY_ONE, None, None]
        game.combo = 0
        game.combo_counter = 3
        return game

    def test_square_stays_free(self):
        game = self._game()
        idx, x, y = LookaheadPolicy().act(game, game.available_actions())
        self.assertEqual(idx, 0)
        self.assertFalse(
            x < 3 and y < 3,
            "postawiono 1x1 w kwadracie 3x3 na (%d, %d) — jedyne miejsce na "
            "większy klocek z następnej tacki" % (x, y),
        )

    def test_the_square_really_is_the_only_room_for_a_3x3(self):
        # Sprawdza założenie testu, nie politykę.
        game = self._game()
        spots = [
            (x, y)
            for y in range(Board.HEIGHT - 2)
            for x in range(Board.WIDTH - 2)
            if game.board.can_place_piece(SQUARE3, x, y)
        ]
        self.assertEqual(spots, [(0, 0)])


class TestLookaheadAcceptsWeightsLikeTray(unittest.TestCase):
    """`build_policy` konstruuje ramiona `lookahead:<plik>` przez `weights=`."""

    def test_weights_keyword_is_accepted_and_used(self):
        weights = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        policy = LookaheadPolicy(weights=weights)
        self.assertEqual(policy.weights, weights)
        self.assertNotEqual(LookaheadPolicy().weights, weights)


if __name__ == "__main__":
    unittest.main(verbosity=2)
