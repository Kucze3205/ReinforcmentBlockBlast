"""Testy dla #341: `tools/duchy_serii.py` — decyzje zapadłe na odczycie z duchem. Bez emulatora."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import duchy_serii as ds
import przegrana_serii as ps

P10 = os.path.join(ROOT, "docs", "seria", "s6", "partia-10")
EMPTY = [[0] * 8 for _ in range(8)]
DOT = [[1]]


def grid(cells):
    g = [[0] * 8 for _ in range(8)]
    for r, c in cells:
        g[r][c] = 1
    return g


def row(observed, expected, ok=False):
    return {"n": 1, "observed": observed, "expected": expected, "ok": ok}


class FirstLegal:
    """Polityka-atrapa: pierwszy legalny ruch."""
    def act(self, game, moves):
        return moves[0]


def move(n, board, tray, mv, expected, ok=True):
    return {"n": n, "board": board, "tray": tray, "move": {"slot": mv[0], "x": mv[1], "y": mv[2]},
            "expected": expected, "observed": expected, "ok": ok}


class TestPas(unittest.TestCase):
    def test_roznica_w_wierszach_3_4(self):
        self.assertTrue(ds.w_pasie(row(grid([(4, 2), (3, 1)]), EMPTY)))

    def test_roznica_poza_pasem(self):
        self.assertFalse(ds.w_pasie(row(grid([(4, 2), (6, 1)]), EMPTY)))

    def test_brak_roznicy_nie_jest_w_pasie(self):
        self.assertFalse(ds.w_pasie(row(EMPTY, EMPTY)))

    def test_diff_cells_nadmiar_i_brak(self):
        self.assertEqual(ds.diff_cells(row(grid([(1, 1)]), grid([(2, 2)]))), [(1, 1), (2, 2)])


class TestDecyzje(unittest.TestCase):
    def test_duch_zmienia_ruch_atrapy(self):
        # n=1 ok:true; n=2 ok:false (duch w (5,5) w odczycie); n=3 zapada na planszy z duchem
        t = [DOT, DOT, DOT]
        b0 = grid([])
        e0 = grid([(0, 0)])
        e1 = grid([(0, 0), (0, 1)])
        ghost = grid([(0, 0), (0, 1), (0, 2), (5, 5)])
        m1 = move(1, b0, t, (0, 0, 0), e0)
        m2 = move(2, e0, [None, DOT, DOT], (1, 1, 0), e1, ok=False)
        m3 = move(3, ghost, [None, None, DOT], (2, 3, 0), grid([(0, 0), (0, 1), (0, 2)]))
        m3["board"] = ghost
        # atrapa zagra (2,2,0) na prawdziwej planszy (pierwsze legalne pole (0,2)), most zagrał inaczej
        c, bad = ds.decyzje(FirstLegal(), [m1, m2, m3])
        self.assertEqual((c["ok_false"], c["baza_czysta"], c["inaczej"]), (1, 1, 1))
        self.assertEqual(bad, [])  # pusta plansza: oba ruchy dają układ

    def test_przerwa_w_numeracji_pomija(self):
        t = [DOT, DOT, DOT]
        m1 = move(1, grid([]), t, (0, 0, 0), grid([(0, 0)]))
        m2 = move(2, grid([(0, 0)]), [None, DOT, DOT], (1, 1, 0), grid([(0, 0), (0, 1)]), ok=False)
        m3 = move(9, grid([(0, 0), (0, 1)]), [None, None, DOT], (2, 3, 0), grid([(0, 0), (0, 1), (0, 3)]))
        c, _ = ds.decyzje(FirstLegal(), [m1, m2, m3])
        self.assertEqual(c["baza_czysta"], 0)


@unittest.skipUnless(os.path.exists(os.path.join(P10, "pomiar.json")), "brak materiału s6 p.10")
class TestPartia10(unittest.TestCase):
    def test_jedyna_szkodliwa_decyzja_to_ruch_44(self):
        with open(os.path.join(P10, "pomiar.json"), encoding="utf-8") as f:
            pomiar = json.load(f)
        rows = []
        for name in pomiar["kawalki"]:
            rows.extend(ps.load_rows(os.path.join(P10, name)))
        moves = [r for r in rows if "move" in r and "expected" in r]
        policy, err = ps.build_policy(pomiar["polityka"])
        self.assertIsNotNone(policy, err)
        c, bad = ds.decyzje(policy, moves)
        self.assertEqual([n for _, n in bad], [44])
        self.assertEqual(c["szkodliwe"], 1)
        self.assertEqual(bad[0][0], len(moves) - 1)  # to ostatni ruch w logu


if __name__ == "__main__":
    unittest.main()
