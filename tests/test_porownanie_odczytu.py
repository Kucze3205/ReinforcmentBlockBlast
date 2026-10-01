"""
Testy dla #305: `tools/porownanie_odczytu.py` na zrzutach s2 (skórka drewniana). Bez emulatora.

Test dokumentuje zmierzoną usterkę, nie wymaganie: `bridge.read_tray` czyta kształty niebędące prostokątem jako
pełne prostokąty (tło paska tacki (173,89,58) przechodzi `is_block` przy próbkowaniu komórek). Gdy usterka
zostanie naprawiona w `bridge.py`, `test_most_czyta_z_jako_prostokat` ma zacząć padać — wtedy go usuń.
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

    def test_most_czyta_z_jako_prostokat(self):
        self.assertEqual(self.cmp["tacka_mostu"][1], [[1, 1, 1], [1, 1, 1]])
        self.assertEqual(self.cmp["sloty_tacki_rozne"], [1, 2])


if __name__ == "__main__":
    unittest.main()
