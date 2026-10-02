"""Testy dla #341: `tools/rozklad_tacek.py` — udział kształtów w tackach z logów serii. Bez emulatora."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import rozklad_tacek as rt

SQ3 = [[1, 1, 1]] * 3
R23 = [[1, 1, 1], [1, 1, 1]]
R32 = [[1, 1], [1, 1], [1, 1]]
LINE5 = [[1, 1, 1, 1, 1]]
LINE5V = [[1]] * 5
DOT = [[1]]
S = [[0, 1, 1], [1, 1, 0]]
L3 = [[1, 0, 0], [1, 0, 0], [1, 1, 1]]
PADDED_DOT = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]  # logi trzymają kształty z zerowym dopełnieniem

EMPTY = [[0] * 8 for _ in range(8)]


def move_row(n, tray, slot=0):
    board = [row[:] for row in EMPTY]
    board[0][0] = n % 2  # inna plansza = inna para plansza+tacka
    return {"n": n, "board": board, "tray": tray, "move": {"slot": slot, "x": 0, "y": 0}, "expected": EMPTY,
            "observed": EMPTY, "ok": True}


class TestRodzaje(unittest.TestCase):
    def test_kwadrat(self):
        self.assertEqual(rt.rodzaje(SQ3), ({"kwadrat_3x3", "duze"}, 9))

    def test_prostokat_w_obu_orientacjach(self):
        self.assertEqual(rt.rodzaje(R23), ({"prostokat_2x3", "duze"}, 6))
        self.assertEqual(rt.rodzaje(R32), ({"prostokat_2x3", "duze"}, 6))

    def test_kreska_w_obu_orientacjach_ma_piec_pol_wiec_nie_jest_duza(self):
        self.assertEqual(rt.rodzaje(LINE5), ({"kreska_5"}, 5))
        self.assertEqual(rt.rodzaje(LINE5V), ({"kreska_5"}, 5))

    def test_ksztalt_z_dopelnieniem_jest_przycinany(self):
        self.assertEqual(rt.rodzaje(PADDED_DOT), (set(), 1))

    def test_L_3x3_ma_piec_pol_wiec_nie_jest_ani_kwadratem_ani_duze(self):
        self.assertEqual(rt.rodzaje(L3), (set(), 5))


class TestLicz(unittest.TestCase):
    def test_udzialy_i_srednia(self):
        w = rt.licz([[SQ3, DOT, DOT], [R32, S, LINE5]])
        self.assertEqual(w["tacek"], 2)
        self.assertEqual(w["klockow"], 6)
        self.assertEqual(w["liczniki"], {"kwadrat_3x3": 1, "prostokat_2x3": 1, "kreska_5": 1, "duze": 2})
        self.assertAlmostEqual(w["udzial"]["kwadrat_3x3"], 1 / 6)
        self.assertAlmostEqual(w["tacki_z_duzym"], 1.0)
        self.assertAlmostEqual(w["pola_na_klocek"], (9 + 1 + 1 + 6 + 4 + 5) / 6)

    def test_tacka_z_duzym_liczy_tacke_raz(self):
        w = rt.licz([[SQ3, SQ3, DOT], [DOT, DOT, DOT]])
        self.assertAlmostEqual(w["tacki_z_duzym"], 0.5)

    def test_nierozpoznany_ksztalt_pomija_tacke(self):
        w = rt.licz([[SQ3, DOT, [[1] * 7] * 9], [DOT, DOT, DOT]])
        self.assertEqual((w["tacek"], w["pominiete"], w["klockow"]), (1, 1, 3))

    def test_pusta_lista(self):
        w = rt.licz([])
        self.assertEqual((w["tacek"], w["klockow"], w["pola_na_klocek"]), (0, 0, 0.0))


class TestTackiZWierszy(unittest.TestCase):
    def test_nowa_tacka_tylko_przy_pelnej_trojce_innej_pary(self):
        t1, t2 = [SQ3, DOT, DOT], [R32, S, LINE5]
        rows = [move_row(1, t1), move_row(2, [None, DOT, DOT], 1), move_row(3, [None, None, DOT], 2),
                move_row(4, t2), move_row(5, t2)]
        rows[4]["board"] = rows[3]["board"]  # ponowienie po nieudanym ruchu: ta sama para plansza+tacka
        self.assertEqual(rt.tacki_z_wierszy(rows), [t1, t2])

    def test_wiersze_bez_ruchu_sa_pomijane(self):
        rows = [{"n": 1, "okno": "tacka_pusta_przejsciowo", "tray": [SQ3, DOT, DOT]}, move_row(2, [SQ3, DOT, DOT])]
        self.assertEqual(len(rt.tacki_z_wierszy(rows)), 1)


class TestPrefiks(unittest.TestCase):
    def test_bierze_poczatek_tylko_dlugich_partii(self):
        a, b, c = [SQ3, DOT, DOT], [DOT, DOT, DOT], [R32, DOT, DOT]
        tr, k = rt.prefiks([[a, b, c], [a], [b, c]], 2)
        self.assertEqual((tr, k), ([a, b, b, c], 2))


class TestZ(unittest.TestCase):
    def test_rowne_odsetki(self):
        z, p = rt.z_dwumianowy(10, 100, 100, 1000)
        self.assertAlmostEqual(z, 0.0)
        self.assertAlmostEqual(p, 0.5)

    def test_wiekszy_odsetek_daje_male_p(self):
        z, p = rt.z_dwumianowy(30, 100, 100, 1000)
        self.assertGreater(z, 4)
        self.assertLess(p, 1e-4)

    def test_puste_proby(self):
        self.assertEqual(rt.z_dwumianowy(0, 0, 1, 10), (0.0, 1.0))


class TestSeria(unittest.TestCase):
    def test_katalog_serii_z_dwiema_partiami(self):
        with tempfile.TemporaryDirectory() as d:
            for k, tray in ((1, [SQ3, DOT, DOT]), (2, [R32, S, LINE5])):
                pd = os.path.join(d, "partia-%d" % k)
                os.makedirs(pd)
                with open(os.path.join(pd, "chunk1_moves.jsonl"), "w") as f:
                    f.write(json.dumps(move_row(1, tray)) + "\n")
            self.assertEqual(rt.seria(d), [[SQ3, DOT, DOT], [R32, S, LINE5]])
            self.assertEqual([len(p) for p in rt.partie(d)], [1, 1])

    def test_kolejnosc_kawalkow_naturalna(self):
        with tempfile.TemporaryDirectory() as d:
            pd = os.path.join(d, "partia-1")
            os.makedirs(pd)
            for k, tray in ((2, [SQ3, DOT, DOT]), (10, [R32, S, LINE5])):
                with open(os.path.join(pd, "chunk%d_moves.jsonl" % k), "w") as f:
                    f.write(json.dumps(move_row(k, tray)) + "\n")
            self.assertEqual(rt.seria(d), [[SQ3, DOT, DOT], [R32, S, LINE5]])


class TestTabela(unittest.TestCase):
    def test_wiersz_na_serie(self):
        t = rt.tabela({"sX": rt.licz([[SQ3, DOT, DOT]])})
        self.assertEqual(len(t.splitlines()), 3)
        self.assertIn("| sX | 1 | 3 | 33.3% |", t)


if __name__ == "__main__":
    unittest.main()
