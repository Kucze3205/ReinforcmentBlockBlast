"""Zapora na rekord: `lookahead:weights.json` gra dokładnie to, co grał przed #118.

`bench/record.json` trzyma `lookahead:weights.json` (6171,04 pkt, 110,5
postawienia). To ramię jest jednocześnie odniesieniem każdego następnego
pomiaru — gdyby #118 zmieniło mu choć jeden ruch, rekord przestałby opisywać
politykę, którą nazywa, a wszystkie przyszłe różnice mierzyłyby się od ruchomego
punktu.

Dlatego porównywane są **całe sekwencje ruchów pełnych partii**, nie wyniki:
jedna inna decyzja rozjeżdża resztę partii, a dwie polityki potrafią dać ten sam
wynik zupełnie innymi ruchami. Złote sekwencje z `tests/data/` zapisano na
commicie 1bd38fa, czyli na kodzie sprzed dodania combo do oceny liścia.

Dlaczego test ma prawo przechodzić: `weights.json` ma sześć wag planszowych,
`benchmark.load_tuned_weights` dopełnia ogon combo zerami, a `x + 0.0 == x`.
Test sprawdza, że ten łańcuch rozumowania trzyma się także w praktyce — łącznie
z kolejnością kandydatów, od której zależy rozstrzyganie remisów.

Test jest wolny (~2 min): to jest cena za rekord, nie niedopatrzenie.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import build_policy
from game import Game

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_PATH = os.path.join(ROOT, "tests", "data", "lookahead_weights_moves.json")
MIN_SEEDS = 20


def load_golden():
    with open(GOLDEN_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def play(policy, seed):
    """Partia do końca; zwraca ruchy w zapisie złotego pliku, wynik i przeżycie."""
    game = Game(seed=seed)
    policy.reset(seed)
    moves = []
    while not game.done:
        actions = game.available_actions()
        if not actions:
            break
        action = policy.act(game, actions)
        moves.append("%d,%d,%d" % action)
        game.step(action)
    return moves, game.score, game.placements


class TestLookaheadWeightsJsonMovesUnchanged(unittest.TestCase):
    def setUp(self):
        self.golden = load_golden()

    def test_golden_file_covers_enough_seeds(self):
        """Mniej niż 20 seedów i test przestaje być zaporą — patrz kryteria #118."""
        self.assertEqual(self.golden["spec"], "lookahead:weights.json")
        self.assertGreaterEqual(len(self.golden["games"]), MIN_SEEDS)

    def test_same_moves_on_every_golden_seed(self):
        policy = build_policy(self.golden["spec"], {"torch_seed": 0})
        for game in self.golden["games"]:
            seed = game["seed"]
            moves, score, placements = play(policy, seed)
            # Najpierw liczby — przy rozjeździe mówią, jak bardzo, zanim
            # assertEqual wypisze różnicę dwóch list po kilkaset pozycji.
            self.assertEqual(
                (score, placements), (game["score"], game["placements"]),
                "seed=%r: wynik/przeżycie rozjechały się z zapisem sprzed #118" % (seed,),
            )
            self.assertEqual(
                moves, game["moves"],
                "seed=%r: inna sekwencja ruchów niż przed #118" % (seed,),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
