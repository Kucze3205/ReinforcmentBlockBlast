"""Testy dla #343: dwa przerwania s6 bezpiecznikiem `petla_bez_postepu` na grywalnej planszy.

p.1 (`partia-1/kawalek_6/final.png`): żółte i czerwone klocki zwykłej planszy spełniały progi `is_trophy_overlay_screen`.
p.5 (`partia-5/kawalek_3/final.png`): fioletowy klocek 2x3 drewnianej skórki miał rozpiętość kanałów 84-89 (< 100),
więc `read_tray` czytał tackę jako pustą. Zrzuty idą jako `int`, jak po `screenshot()` żywego mostu.
"""
import os
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bridge

S6 = os.path.join(ROOT, "docs", "seria", "s6")
S1_TROPHY = os.path.join(ROOT, "docs", "seria", "s1", "partia-10", "kawalek_1", "048_state.png")


def zrzut(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(int)


class PrzerwaniaS6(unittest.TestCase):
    def test_p1_zwykla_plansza_to_nie_nakladka(self):
        for nazwa in ("final.png", "041_state.png", "040_aim.png"):
            with self.subTest(nazwa):
                self.assertFalse(bridge.is_trophy_overlay_screen(zrzut(os.path.join(S6, "partia-1", "kawalek_6", nazwa))))

    def test_p1_tacka_zostaje_odczytana(self):
        tray = bridge.read_tray(zrzut(os.path.join(S6, "partia-1", "kawalek_6", "final.png")))
        self.assertEqual([t[0] if t else None for t in tray], [[[1], [1], [1], [1]], [[1, 0], [1, 1], [0, 1]], None])

    def test_prawdziwa_nakladka_nadal_wykryta(self):
        self.assertTrue(bridge.is_trophy_overlay_screen(zrzut(S1_TROPHY)))

    def test_p5_fioletowy_klocek_2x3_w_tacce(self):
        for nazwa in ("final.png", "106_state.png"):
            with self.subTest(nazwa):
                tray = bridge.read_tray(zrzut(os.path.join(S6, "partia-5", "kawalek_3", nazwa)))
                self.assertEqual([t[0] if t else None for t in tray], [None, None, [[1, 1, 1], [1, 1, 1]]])


if __name__ == "__main__":
    unittest.main()
