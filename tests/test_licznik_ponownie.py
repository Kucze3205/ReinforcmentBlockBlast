"""Testy dla #324: `tools/licznik_ponownie.py` — ponowna ocena licznika na zapisanych `chunk*_moves.jsonl`."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import licznik_ponownie as L


def partia(*kawalki):
    """Katalog z chunk<k>_moves.jsonl; kawałek = (numer, lista wierszy)."""
    d = tempfile.mkdtemp()
    for k, rows in kawalki:
        with open(os.path.join(d, "chunk%d_moves.jsonl" % k), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    return d


def w(n, score, **extra):
    return dict(n=n, score=score, move=dict(slot=0, x=0, y=0), **extra)


class TestOcen(unittest.TestCase):
    def test_kolejnosc_kawalkow_numeryczna(self):
        d = partia((10, [w(0, 1_100_000), w(1, 1_100_100), w(2, 1_100_200)]), (2, [w(0, 500_000)]))
        a = L.ocen(L.wczytaj(d))
        self.assertEqual(a["przekroczenie"], (10, 0))
        self.assertEqual(a["maksimum"], 1_100_200)

    def test_wymaga_trzech_kolejnych_wpisow(self):
        d = partia((1, [w(0, 1_000_000), w(1, 1_000_050), w(2, 999_000), w(3, 1_000_100), w(4, 1_000_200)]))
        self.assertIsNone(L.ocen(L.wczytaj(d))["przekroczenie"])  # seria przerwana odczytem < progu
        d = partia((1, [w(0, 999_000), w(1, 1_000_000), w(2, None), w(3, 1_000_050), w(4, 1_000_100)]))
        self.assertEqual(L.ocen(L.wczytaj(d))["przekroczenie"], (1, 1))  # null nie przerywa serii

    def test_koniec_partii_przed_przekroczeniem(self):
        d = partia((1, [w(0, 10), dict(n=1, score=None, end="koniec_partii")]),
                   (2, [w(0, 1_000_000), w(1, 1_000_001), w(2, 1_000_002)]))
        a = L.ocen(L.wczytaj(d))
        self.assertTrue(a["koniec_partii_przed"])
        self.assertEqual(a["przekroczenie"], (2, 0))

    def test_bez_odczytow(self):
        d = partia((1, [w(0, None)]))
        a = L.ocen(L.wczytaj(d))
        self.assertIsNone(a["maksimum"])
        self.assertIsNone(a["przekroczenie"])

    def test_s4_partia_1_rozjazd(self):
        d = os.path.join(ROOT, "docs", "seria", "s4", "partia-1")
        a = L.ocen(L.wczytaj(d))
        self.assertEqual(a["przekroczenie"], (18, 71))
        self.assertFalse(a["koniec_partii_przed"])
        self.assertTrue(L.wiersz_tabeli(d, a).endswith("| tak |"))

    def test_s4_partia_8_cel_ukryty_za_przerwaniem(self):
        d = os.path.join(ROOT, "docs", "seria", "s4", "partia-8")
        a = L.ocen(L.wczytaj(d))
        self.assertEqual(a["przekroczenie"], (16, 17))  # HUD na kawalek_16/final.png: 1 077 946
        self.assertFalse(a["koniec_partii_przed"])
        self.assertGreater(a["maksimum"], 3_000_000)  # HUD na kawalek_57/final.png: 3 172 913
        self.assertTrue(L.wiersz_tabeli(d, a).endswith("| tak |"))  # pomiar.json: przerwanie (limit_minut)


if __name__ == "__main__":
    unittest.main()
