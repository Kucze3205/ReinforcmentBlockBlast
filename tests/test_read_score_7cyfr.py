"""
Testy dla #290: `bridge.read_score` na zapisanych zrzutach z 01eb4dd (licznik HUD, 6 i 7 cyfr).

Wartości to odczyt wzrokowy ze zrzutu. Pominięte: chunk1/2_final.png (różowy ekran, białe cyfry) i
chunk3_final.png (niebieski ekran) — to nie HUD; chunk14/15 nie mają zrzutu; chunk1–3 nie są w tabeli.
"""
import os
import sys
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge

RUN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bridge", "runs", "01eb4dd")

CHUNKS = {  # chunkN_final.png
    4: 157704, 5: 170276, 6: 202829, 7: 267874, 8: 371248, 9: 513389, 10: 684052, 11: 881444,
    12: 1124408, 13: 1399270, 16: 1887842, 17: 1916865, 18: 1967415,
}
LICZNIKI = {  # klatki z animacji rombu, widoczna wartość
    "seria-proba/licznik_1.png": 1509545,
    "seria-proba2/licznik_1.png": 1547434,
}
STATES_PROBA2 = dict(zip(range(0, 20, 2), (1512468, 1516328, 1520621, 1524648, 1531822, 1532257, 1536264,
                                           1539616, 1543518, 1543916)))
STATES_PROBA = dict(zip(range(0, 50, 4), (1399270, 1407141, 1414148, 1440252, 1444006, 1451518, 1459052,
                                          1466610, 1474615, 1485610, 1493252, 1500924, 1505119)))


def load(rel):
    return np.array(Image.open(os.path.join(RUN, rel)).convert("RGB"))


class ReadScoreTruthTable(unittest.TestCase):
    def check(self, rel, expected):
        self.assertEqual(bridge.read_score(load(rel)), expected, rel)

    def test_chunk_finals(self):
        for n, expected in CHUNKS.items():
            with self.subTest(chunk=n):
                self.check(f"chunk{n}_final.png", expected)

    def test_six_digit_screens(self):
        six = [n for n, v in CHUNKS.items() if v < 1_000_000]
        self.assertGreaterEqual(len(six), 8)
        for n in six:
            self.assertEqual(len(str(bridge.read_score(load(f"chunk{n}_final.png")))), 6)

    def test_seven_digit_under_diamond(self):
        for rel, expected in LICZNIKI.items():
            with self.subTest(rel=rel):
                self.check(rel, expected)

    def test_states_proba2(self):
        for n, expected in STATES_PROBA2.items():
            with self.subTest(n=n):
                self.check(f"seria-proba2/kawalek_1/{n:03d}_state.png", expected)

    def test_states_proba(self):
        for n, expected in STATES_PROBA.items():
            with self.subTest(n=n):
                self.check(f"seria-proba/kawalek_1/{n:03d}_state.png", expected)

    def test_non_hud_screens_give_none(self):
        for n in (1, 2, 3):
            with self.subTest(chunk=n):
                self.assertIsNone(bridge.read_score(load(f"chunk{n}_final.png")))

    def test_blank_screen_gives_none(self):
        self.assertIsNone(bridge.read_score(np.full((640, 320, 3), 255, dtype=np.uint8)))


if __name__ == "__main__":
    unittest.main()
