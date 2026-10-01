import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import tempo_licznika as T

PUSTA = [[0] * 8 for _ in range(8)]


def wiersz(n, score, t, czysci=False):
    """Wiersz jsonl: klocek 1x1; `czysci` = plansza po ruchu pusta mimo klocka."""
    plansza = [r[:] for r in PUSTA]
    plansza[0][0] = 1
    po = [r[:] for r in PUSTA]
    if not czysci:
        po[0][0] = po[0][1] = 1
    return {"n": n, "board": plansza, "tray": [[[1]], None, None], "score": score,
            "move": {"slot": 0, "x": 1, "y": 0}, "observed": po, "ok": True, "t": 1000.0 + t}


def zapisz(katalog, numer, wiersze):
    with open(os.path.join(katalog, "chunk%d_moves.jsonl" % numer), "w") as f:
        for w in wiersze:
            f.write(json.dumps(w) + "\n")


class TempoLicznika(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_tempo_i_przekroczenie(self):
        zapisz(self.dir, 1, [wiersz(0, 900000, 0), wiersz(1, 950000, 60), wiersz(2, 990000, 120)])
        zapisz(self.dir, 2, [wiersz(0, 1050000, 180), wiersz(1, 1100000, 240)])
        a = T.analizuj(T.wczytaj(self.dir))
        self.assertEqual(a["postawienia"], 5)
        self.assertAlmostEqual(a["minuty"], 4.0)
        self.assertEqual(a["licznik"], 1100000)
        self.assertEqual(a["po_kawalkach"], [990000, 1100000])
        self.assertEqual(a["przekroczenie"][0], 4)
        self.assertAlmostEqual(a["przekroczenie"][1], 3.0)
        self.assertAlmostEqual(a["na_minute"], 1.25)
        self.assertTrue(T.dojdzie_do_progu(a))

    def test_odczyt_cofajacy_sie_i_skok_odrzucone(self):
        zapisz(self.dir, 1, [wiersz(0, 950000, 0), wiersz(1, 50000, 10),  # 7 cyfr -> 5 cyfr
                             wiersz(2, 960000, 20), wiersz(3, 5960000, 30),  # skok o 5 mln
                             wiersz(4, 970000, 40)])
        a = T.analizuj(T.wczytaj(self.dir))
        self.assertEqual(a["odrzucone"], [(2, 50000), (4, 5960000)])
        self.assertEqual(a["licznik"], 970000)
        self.assertIsNone(a["przekroczenie"])
        self.assertFalse(T.dojdzie_do_progu(a))

    def test_brak_odczytow_licznika(self):
        zapisz(self.dir, 1, [wiersz(0, None, 0), wiersz(1, None, 30)])
        a = T.analizuj(T.wczytaj(self.dir))
        self.assertIsNone(a["licznik"])
        self.assertEqual(a["postawienia"], 2)
        self.assertIsNone(T.dojdzie_do_progu(a))

    def test_ponowiona_proba_nie_liczy_sie_podwojnie(self):
        zapisz(self.dir, 1, [wiersz(0, 0, 0), wiersz(1, 0, 10), wiersz(1, 20, 20), wiersz(2, 40, 30)])
        self.assertEqual(T.analizuj(T.wczytaj(self.dir))["postawienia"], 3)

    def test_lancuchy_czyszczen(self):
        c, b = True, False
        zapisz(self.dir, 1, [wiersz(i, i, i, czysci=x) for i, x in enumerate([c, c, b, c, b, c, c, c])])
        self.assertEqual(T.lancuchy(T.wczytaj(self.dir)), [2, 1, 3])

    def test_kolejnosc_kawalkow_numeryczna(self):
        zapisz(self.dir, 2, [wiersz(0, 200, 100)])
        zapisz(self.dir, 10, [wiersz(0, 300, 200)])
        zapisz(self.dir, 1, [wiersz(0, 100, 0)])
        a = T.analizuj(T.wczytaj(self.dir))
        self.assertEqual(a["licznik"], 300)
        self.assertEqual(a["odrzucone"], [])


if __name__ == "__main__":
    unittest.main()
