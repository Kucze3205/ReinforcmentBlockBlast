"""
Testy dla #305: `tools/porownanie_odczytu.py` na zrzutach s2 (skórka drewniana). Bez emulatora.

Usterka z #305 (`bridge.read_tray` czytał S/Z/T/L jako prostokąty na skórce drewnianej) naprawiona w #307.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import porownanie_odczytu as po

STATE_087 = os.path.join(ROOT, "docs", "seria", "s2", "partia-3", "kawalek_3", "087_state.png")


@unittest.skipUnless(os.path.exists(STATE_087), "brak zrzutu s2")
class PorownanieOdczytuTest(unittest.TestCase):
    def setUp(self):
        self.cmp = po.compare_state(po.load(STATE_087))

    def test_plansza_zgodna_z_obrazem(self):
        self.assertEqual(self.cmp["pola_planszy_rozne"], [])

    def test_obraz_ma_z_i_s(self):
        self.assertEqual(self.cmp["tacka_obrazu"][1], [[1, 1, 0], [0, 1, 1]])
        self.assertEqual(self.cmp["tacka_obrazu"][2], [[0, 1, 1], [1, 1, 0]])

    def test_most_czyta_z_i_s_poprawnie(self):
        self.assertEqual(self.cmp["tacka_mostu"][1], [[1, 1, 0], [0, 1, 1]])
        self.assertEqual(self.cmp["tacka_mostu"][2], [[0, 1, 1], [1, 1, 0]])
        self.assertEqual(self.cmp["sloty_tacki_rozne"], [])


if __name__ == "__main__":
    unittest.main()
