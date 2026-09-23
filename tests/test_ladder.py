"""
Drabinka punktów za linię (#33): odczyt B(ℓ) z zalogowanego przebiegu.

Wpisy są syntetyczne, ale kształt jest ten z mostu: plansza z jednym brakiem w
pierwszym rzędzie i jednokomórkowy klocek, który go zamyka — czyszczenie jednej linii.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from analyze_bridge import ladder

BOARD = [[0] + [1] * 7] + [[0] * 8 for _ in range(7)]


def ruch(n, before, after):
    return {"n": n, "partia": 0, "board": BOARD, "tray": [[[1]], None, None],
            "move": {"slot": 0, "x": 0, "y": 0}, "score": before, "score_after": after}


class LadderReading(unittest.TestCase):
    def test_czysty_odczyt_daje_b_po_odjeciu_komorek_i_podzieleniu_przez_combo(self):
        # combo 1: 1 komórka + 1·B, B = 10; combo 2: 1 + 2·B, B = 15
        table, dirty = ladder([ruch(0, 100, 111), ruch(1, 111, 142)])
        self.assertEqual(table[(1, 1)], {10: 1})
        self.assertEqual(table[(1, 2)], {15: 1})
        self.assertEqual(dirty, 0)

    def test_animacja_przerwana_w_polowie_jest_nieczysta(self):
        # combo 2, reszta 25 nie dzieli się przez 2: licznik nie doszedł do końca
        table, dirty = ladder([ruch(0, 100, 111), ruch(1, 111, 137)])
        self.assertNotIn((1, 2), table)
        self.assertEqual(dirty, 1)


if __name__ == "__main__":
    unittest.main()
