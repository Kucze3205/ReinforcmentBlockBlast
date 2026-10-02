"""Testy dla #341: `tools/przeglad_s6.py` — przegląd wsteczny przegranej z serii. Bez emulatora.

Test na materiale: `docs/seria/s6/partia-10` (p.10, 12 822 pkt): ruch 44 zapadł na planszy z dwoma duchami baneru
„Combo 5" w (4,2),(4,3); na prawdziwej planszy polityka gra inaczej i układa ostatnią tackę.
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import przegrana_serii as ps
import przeglad_s6 as p6

P10 = os.path.join(ROOT, "docs", "seria", "s6", "partia-10")
DOT = [[1]]
BAR = [[1, 1, 1]]
SQ3 = [[1, 1, 1]] * 3


def grid(cells):
    g = [[0] * 8 for _ in range(8)]
    for r, c in cells:
        g[r][c] = 1
    return g


def row(n, board, tray, move, expected, ok=True):
    return {"n": n, "board": board, "tray": tray, "move": move, "expected": expected, "observed": expected, "ok": ok}


class TestSeqCompletable(unittest.TestCase):
    def test_pusta_plansza_miesci_wszystko(self):
        self.assertIs(p6.seq_completable(grid([]), [[SQ3, SQ3, BAR]]), True)

    def test_brak_miejsca(self):
        full_but_two = grid([(r, c) for r in range(8) for c in range(8) if (r, c) not in {(0, 0), (0, 1)}])
        self.assertIs(p6.seq_completable(full_but_two, [[BAR]]), False)
        self.assertIs(p6.seq_completable(full_but_two, [[SQ3]]), False)

    def test_czyszczenie_linii_zwalnia_miejsce(self):
        # wiersz 0 pełny poza (0,0): kropka go czyści, więc potem (0,0) i reszta wiersza są wolne dla kreski 1x3
        b = grid([(0, c) for c in range(1, 8)])
        self.assertIs(p6.seq_completable(b, [[DOT, BAR]]), True)

    def test_grupy_po_kolei_kropka_przed_kreska(self):
        b = grid([(0, c) for c in range(1, 8)])
        self.assertIs(p6.seq_completable(b, [[DOT], [BAR]]), True)

    def test_pusta_lista_grup_i_puste_grupy(self):
        self.assertIs(p6.seq_completable(grid([]), []), True)
        self.assertIs(p6.seq_completable(grid([]), [[None, None], []]), True)

    def test_budzet_wyczerpany_zwraca_none(self):
        self.assertIsNone(p6.seq_completable(grid([]), [[SQ3, SQ3, SQ3]], budget=1))


class TestTruthBoards(unittest.TestCase):
    def setUp(self):
        self.b0 = grid([(7, 0)])
        self.exp0 = grid([(7, 0), (0, 0)])  # kropka na (0,0)
        self.ghost = grid([(7, 0), (0, 0), (4, 4)])  # odczyt z duchem (4,4)
        self.exp1 = grid([(7, 0), (0, 0), (0, 1)])

    def rows(self, n1=2):
        r0 = row(1, self.b0, [DOT, DOT, None], {"slot": 0, "x": 0, "y": 0}, self.exp0, ok=False)
        r1 = row(n1, self.ghost, [None, DOT, None], {"slot": 1, "x": 1, "y": 0}, self.exp1)
        return [r0, r1]

    def test_prawda_to_symulacja_nie_odczyt(self):
        truth, not_acc = p6.truth_boards(self.rows())
        self.assertEqual(truth[1], self.exp0)
        self.assertNotEqual(truth[1], self.rows()[1]["board"])
        self.assertEqual(not_acc, [False, False])

    def test_przerwa_w_numeracji_bierze_odczyt(self):
        truth, _ = p6.truth_boards(self.rows(n1=7))
        self.assertEqual(truth[1], self.ghost)

    def test_ruch_nieprzyjety_zostawia_plansze(self):
        rows = self.rows()
        rows[1]["tray"] = [DOT, DOT, None]  # slot 0 wciąż pełny: gra ruchu nie przyjęła
        truth, not_acc = p6.truth_boards(rows)
        self.assertEqual(truth[1], self.b0)
        self.assertEqual(not_acc, [False, True])

    def test_kotwica_start_omija_wczesniejsze_wiersze(self):
        truth, _ = p6.truth_boards(self.rows(), start=1)
        self.assertEqual(truth[1], self.ghost)


class TestAccepted(unittest.TestCase):
    def test_slot_pusty_albo_nowa_trojka(self):
        prev = {"tray": [DOT, DOT, None], "move": {"slot": 0, "x": 0, "y": 0}}
        self.assertTrue(p6.accepted(prev, {"tray": [None, DOT, None]}))
        self.assertFalse(p6.accepted(prev, {"tray": [DOT, DOT, None]}))
        last = {"tray": [None, DOT, None], "move": {"slot": 1, "x": 0, "y": 0}}
        self.assertTrue(p6.accepted(last, {"tray": [DOT, BAR, SQ3]}))


@unittest.skipUnless(os.path.exists(os.path.join(P10, "pomiar.json")), "brak materiału s6 p.10")
class TestPartia10(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(P10, "pomiar.json"), encoding="utf-8") as f:
            pomiar = json.load(f)
        rows = []
        for name in pomiar["kawalki"]:
            rows.extend(ps.load_rows(os.path.join(P10, name)))
        cls.moves = p6.last_game_moves(rows)
        policy, err = ps.build_policy(pomiar["polityka"])
        assert policy is not None, err
        cls.res = p6.review(policy, cls.moves, 10, os.path.join(P10, "kawalek_2"))

    def test_ogon_ma_co_najmniej_10_ruchow_z_calych_tacek(self):
        ns = [e["n"] for e in self.res["ruchy"]]
        self.assertGreaterEqual(len(ns), 10)
        self.assertEqual(ns[-1], 44)
        self.assertEqual(self.res["ruchy"][0]["tacka"], -3)

    def test_duchy_w_ruchu_44_to_dwa_pola_baneru(self):
        e = self.res["ruchy"][-1]
        self.assertEqual(sorted(e["board_vs_prawda"]), [(4, 2), (4, 3)])
        self.assertTrue(all(v["is_block"] for v in e["lata"].values()))
        self.assertEqual(e["klasa"], "mieszane")

    def test_wczesniejsze_ruchy_zgodne_i_bez_duchow(self):
        for e in self.res["ruchy"][:-1]:
            self.assertEqual(e["board_vs_prawda"], [], e)
            self.assertTrue(e["zgodne"], e)

    def test_ruch_mostu_nie_ukladal_ostatniej_tacki_ruch_polityki_tak(self):
        e = self.res["ruchy"][-1]
        self.assertFalse(e["zgodne"])
        self.assertIs(e["most_ulozenie"], False)
        self.assertIs(e["polityka_ulozenie"], True)

    def test_kontrfaktyk_polityka_przezywa_zalogowane_tacki(self):
        cf = self.res["kontrfaktyk"]
        self.assertEqual(cf["od_n"], 44)
        self.assertTrue(cf["przezyla_zalogowane_tacki"])

    def test_tabela_md_ma_wiersz_na_ruch(self):
        lines = p6.md_table(self.res).splitlines()
        self.assertEqual(len(lines), 2 + len(self.res["ruchy"]))


if __name__ == "__main__":
    unittest.main()
