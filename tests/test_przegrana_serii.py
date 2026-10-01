"""
Testy dla #292: `tools/przegrana_serii.py` — diagnoza przegranej z serii na zapisanych logach mostu.

Dwa katalogi-fixture z prawdziwych logów końca partii (`bridge/runs/1b1763a/chunk14_moves.jsonl`,
`bridge/runs/4a1796f/chunk2_moves.jsonl`, ucięte na wierszu `koniec_partii`, jak w logu serii) plus
katalogi syntetyczne na pozostałe werdykty. Bez emulatora.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import bridge
import przegrana_serii

RUNS = os.path.join(ROOT, "bridge", "runs")
EMPTY = [[0] * 8 for _ in range(8)]
JUNK = [[1] * 7 for _ in range(9)]  # kształt-śmieć z nakładki ekranu końca


def grid(cells):
    g = [[0] * 8 for _ in range(8)]
    for x, y in cells:
        g[y][x] = 1
    return g


def real_rows(run, name):
    """Wiersze prawdziwego logu do pierwszego `koniec_partii` włącznie (w serii plik kończy się na nim)."""
    rows = []
    with open(os.path.join(RUNS, run, name)) as f:
        for line in f:
            rows.append(json.loads(line))
            if rows[-1].get("koniec_partii"):
                return rows
    raise AssertionError("brak koniec_partii")


def end_row(n, extra=None):
    return {"n": n, "policy": "greedy", "board": grid([(x, y) for x in range(8) for y in range(8)]),
            "tray": [JUNK, JUNK, JUNK], "score": None, "koniec_partii": True, "wynik_koncowy": 100,
            "wynik_koncowy_odczyty": [100, 100], "zrzut_konca": f"{n:03d}_end.png", "nowa_partia": 2,
            "end": "koniec_partii", **(extra or {})}


def move_row(n, board, tray, move, expected, ok=True):
    return {"n": n, "policy": "greedy", "board": board, "tray": tray, "score": 10 * n, "move": move,
            "drag": {"finger": [0, 0]}, "expected": expected, "observed": expected if ok else grid([(0, 0)]),
            "ok": ok, "decision_ms": 0.1}


def make_dir(rows, zakonczenie="przegrana", polityka="greedy"):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "chunk1_moves.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    pomiar = {"polityka": polityka, "zakonczenie": zakonczenie, "kawalki": ["chunk1_moves.jsonl"],
              "wynik_koncowy": 100, "zrzut_konca": "kawalek_1/000_end.png"}
    with open(os.path.join(d, "pomiar.json"), "w") as f:
        json.dump(pomiar, f)
    return d


def run_tool(d, *extra):
    out = os.path.join(d, "wynik.json")
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        code = przegrana_serii.main([d, "--polityka", "greedy", "--out", out, *extra])
    data = None
    if os.path.exists(out):
        with open(out) as f:
            data = json.load(f)
    return code, buf.getvalue(), data


class TestRealLogs(unittest.TestCase):
    def test_1b1763a_chunk14(self):
        """Gra skończyła się w trakcie tacki z 3x3; ostatni ruch ma `observed` z nakładki (ok=false)."""
        d = make_dir(real_rows("1b1763a", "chunk14_moves.jsonl"))
        code, text, res = run_tool(d)
        self.assertEqual(code, 0)
        self.assertIn(res["werdykt"], przegrana_serii.VERDICTS)
        self.assertNotEqual(res["werdykt"], "nieoceniane")
        self.assertIn(f"werdykt: {res['werdykt']}", text)
        self.assertEqual(res["dane"]["ostatnie_n"], 2)
        self.assertEqual(res["dane"]["legalne_ruchy_po_ostatnim"], 0)

    def test_4a1796f_chunk2(self):
        d = make_dir(real_rows("4a1796f", "chunk2_moves.jsonl"))
        code, _, res = run_tool(d)
        self.assertEqual(code, 0)
        self.assertIn(res["werdykt"], przegrana_serii.VERDICTS)
        self.assertEqual(res["dane"]["ostatnie_n"], 11)
        self.assertEqual(res["dane"]["legalne_ruchy_po_ostatnim"], 0)


class TestVerdicts(unittest.TestCase):
    DOMINO = [[1, 1]]

    def test_tacka_nieukladalna(self):
        # plansza prawie pełna: wolne tylko pola (0,0) i (7,7); tacka trzech domin poziomych nie mieści się
        cells = [(x, y) for x in range(8) for y in range(8) if (x, y) not in ((0, 0), (7, 7))]
        board = grid(cells)
        tray = [self.DOMINO, self.DOMINO, self.DOMINO]
        self.assertFalse(przegrana_serii.mtu.tray_playable(board, tray))
        # most ułożył jedno domino wcześniej (logując pierwszą, pełną tacką); nic się nie mieści
        rows = [move_row(0, board, tray, {"slot": 0, "x": 0, "y": 0}, board)]
        rows[0]["ok"] = True
        rows.append(end_row(1))
        # ruch z pełną tacką, po którym zostają dwa domina bez legalnego miejsca -> plansza po ruchu musi być pełna
        # (ruch niemożliwy do wykonania na tej planszy nie jest potrzebny: diagnoza czyta `expected`)
        d = make_dir(rows)
        code, _, res = run_tool(d)
        self.assertEqual(code, 0)
        self.assertEqual(res["werdykt"], "tacka_nieukladalna")

    def test_ok_false_przed_ostatnim_ruchem_to_rozjazd(self):
        cells = [(x, y) for x in range(8) for y in range(8) if (x, y) not in ((0, 0), (7, 7))]
        board = grid(cells)
        tray = [self.DOMINO, self.DOMINO, self.DOMINO]
        rows = [move_row(0, board, tray, {"slot": 0, "x": 0, "y": 0}, board, ok=False),
                move_row(1, board, [None, self.DOMINO, self.DOMINO], {"slot": 1, "x": 0, "y": 0}, board),
                end_row(2)]
        d = make_dir(rows)
        code, _, res = run_tool(d)
        self.assertEqual(code, 0)
        self.assertEqual(res["werdykt"], "rozjazd_mostu")
        self.assertEqual(res["powod"], "ok_false_przed_ostatnim_ruchem")

    def test_koniec_mimo_legalnego_ruchu_to_rozjazd(self):
        board = grid([(x, y) for x in range(8) for y in range(8) if (x, y) not in ((0, 0), (1, 0))])
        tray = [self.DOMINO, self.DOMINO, self.DOMINO]
        # po „ruchu" zostają dwa domina, a wolne pola (0,0),(1,0) wystarczą na jedno
        rows = [move_row(0, board, tray, {"slot": 0, "x": 0, "y": 0}, board), end_row(1)]
        d = make_dir(rows)
        _, _, res = run_tool(d)
        self.assertEqual(res["werdykt"], "rozjazd_mostu")
        self.assertEqual(res["powod"], "koniec_mimo_legalnego_ruchu_wg_odczytu")

    def test_uklad_istnial_polityka_zgodna_to_slepa_plamka(self):
        # tacka układalna (puste pole na planszy), most gra ruch, który wybiera też zachłanna polityka
        board = grid([(x, y) for x in range(8) for y in range(8) if y > 1 or x > 3])
        tray = [self.DOMINO, self.DOMINO, self.DOMINO]
        self.assertTrue(przegrana_serii.mtu.tray_playable(board, tray))
        b, p = przegrana_serii.to_board(board), przegrana_serii.to_pieces(tray)
        policy, _ = przegrana_serii.build_policy("greedy")
        i, x, y = policy.act(bridge.make_game_stub(b, p), bridge.legal_moves(b, p))
        full = grid([(x2, y2) for x2 in range(8) for y2 in range(8)])
        rows = [move_row(0, board, tray, {"slot": i, "x": x, "y": y}, full)]
        rows[0]["tray"] = tray
        rows.append(end_row(1))
        # po ruchu plansza pełna, a zostają dwa domina: legalnych ruchów brak, gra kończy się w trakcie tacki
        d = make_dir(rows)
        _, _, res = run_tool(d)
        self.assertEqual(res["werdykt"], "slepa_plamka")
        self.assertEqual(res["dane"]["roznice_polityki"], {"ostatnia": []})

    def test_inny_ruch_niz_polityka_to_rozjazd(self):
        board = grid([(x, y) for x in range(8) for y in range(8) if y > 1 or x > 3])
        tray = [self.DOMINO, self.DOMINO, self.DOMINO]
        b, p = przegrana_serii.to_board(board), przegrana_serii.to_pieces(tray)
        policy, _ = przegrana_serii.build_policy("greedy")
        i, x, y = policy.act(bridge.make_game_stub(b, p), bridge.legal_moves(b, p))
        other = next(m for m in bridge.legal_moves(b, p) if m != (i, x, y))
        full = grid([(x2, y2) for x2 in range(8) for y2 in range(8)])
        rows = [move_row(0, board, tray, {"slot": other[0], "x": other[1], "y": other[2]}, full), end_row(1)]
        _, _, res = run_tool(make_dir(rows))
        self.assertEqual(res["werdykt"], "rozjazd_mostu")
        self.assertEqual(res["powod"], "polityka_w_symulatorze_gra_inaczej")
        self.assertTrue(res["dane"]["roznice_polityki"]["ostatnia"])


class TestNieoceniane(unittest.TestCase):
    def test_tacka_ulozona_w_calosci_nowa_niezalogowana(self):
        board = grid([(0, 0)])
        tray = [[[1, 1]], [[1, 1]], [[1, 1]]]
        rows = [move_row(0, board, tray, {"slot": 0, "x": 1, "y": 0}, board),
                move_row(1, board, [None, tray[1], tray[2]], {"slot": 1, "x": 1, "y": 1}, board),
                move_row(2, board, [None, None, tray[2]], {"slot": 2, "x": 1, "y": 2}, board, ok=False),
                end_row(3)]
        _, _, res = run_tool(make_dir(rows))
        self.assertEqual(res["werdykt"], "nieoceniane")
        self.assertEqual(res["powod"], "nowa_tacka_niezalogowana")

    def _okno_rows(self, window_board):
        board = grid([(0, 0)])
        tray = [[[1, 1]], [[1, 1]], [[1, 1]]]
        full = grid([(x, y) for x in range(8) for y in range(8) if (x, y) not in ((0, 0), (7, 7))])
        rows = [move_row(0, board, tray, {"slot": 0, "x": 1, "y": 0}, board),
                move_row(1, board, [None, tray[1], tray[2]], {"slot": 1, "x": 1, "y": 1}, board),
                move_row(2, board, [None, None, tray[2]], {"slot": 2, "x": 1, "y": 2}, full)]
        okno = {"n": 3, "policy": "greedy", "board": window_board(full), "tray": tray, "score": 30,
                "okno": "brak_ruchu_ponowny_odczyt"}
        return rows + [okno, end_row(4)], full, tray

    def test_okno_brak_ruchu_ponowny_odczyt_diagnozuje_nowa_tacke(self):
        rows, full, tray = self._okno_rows(lambda f: f)
        _, _, res = run_tool(make_dir(rows))
        self.assertEqual(res["werdykt"], "tacka_nieukladalna")
        self.assertEqual(res["dane"]["tacka_smierci"]["plansza"], full)
        self.assertEqual(res["dane"]["tacka_smierci"]["tacka"], tray)

    def test_okno_z_plansza_niezgodna_z_expected_to_rozjazd(self):
        rows, _, _ = self._okno_rows(lambda f: grid([(0, 0)]))
        _, _, res = run_tool(make_dir(rows))
        self.assertEqual(res["werdykt"], "rozjazd_mostu")
        self.assertEqual(res["powod"], "plansza_z_ponownego_odczytu_niezgodna_z_expected")

    def test_nierozpoznany_ksztalt(self):
        full = grid([(x, y) for x in range(8) for y in range(8)])
        weird = [[1, 1, 1], [1, 0, 1], [1, 1, 1]]
        tray = [weird, [[1, 1]], [[1, 1]]]
        rows = [move_row(0, grid([(0, 0)]), tray, {"slot": 1, "x": 1, "y": 0}, full), end_row(1)]
        code, _, res = run_tool(make_dir(rows))
        self.assertEqual(code, 0)
        self.assertEqual(res["werdykt"], "nieoceniane")
        self.assertEqual(res["powod"], "ksztalt_nierozpoznany")

    def test_brak_ruchow(self):
        _, _, res = run_tool(make_dir([end_row(0)]))
        self.assertEqual(res["werdykt"], "nieoceniane")
        self.assertEqual(res["powod"], "brak_ruchow_z_pelna_tacka")

    def test_nie_przegrana_konczy_komunikatem_i_kodem_0(self):
        d = make_dir([end_row(0)], zakonczenie="cel")
        code, text, res = run_tool(d)
        self.assertEqual(code, 0)
        self.assertIn("cel", text)
        self.assertIsNone(res)

    def test_przed_koncem_ma_pierwszenstwo(self):
        full = grid([(x, y) for x in range(8) for y in range(8)])
        tray = [[[1, 1]], [[1, 1]], [[1, 1]]]
        row = move_row(0, grid([(0, 0)]), tray, {"slot": 0, "x": 1, "y": 0}, grid([(0, 0)]))
        pk = {"board": full, "tray": [None, [[1, 1]], [[1, 1]]]}
        _, _, res = run_tool(make_dir([row, end_row(1, {"przed_koncem": pk})]))
        self.assertEqual(res["dane"]["plansza_po_ostatnim_ruchu"], full)
        self.assertEqual(res["dane"]["legalne_ruchy_po_ostatnim"], 0)


class TestBridgePrzedKoncem(unittest.TestCase):
    def test_wiersz_konca_niesie_plansze_i_tacke_po_ostatnim_ruchu(self):
        from unittest import mock
        import numpy as np
        from PIL import Image
        img = np.asarray(Image.open(os.path.join(RUNS, "0d96333", "120_state.png")).convert("RGB")).astype(int)
        slots = [([[1, 1]], (20, 460)), ([[1]], (100, 460)), None]
        tmp = tempfile.mkdtemp()
        with mock.patch("bridge.OUT", tmp), \
             mock.patch("bridge.settled_state", return_value=(img, EMPTY, slots)), \
             mock.patch("bridge.stable_state", return_value=(img, EMPTY, slots)), \
             mock.patch("bridge.read_score", return_value=100), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, img)), \
             mock.patch("bridge.is_game_over_screen", side_effect=[False, True]), \
             mock.patch("bridge.game_over_score_box", return_value=bridge.GAME_OVER_SCORE_BOX), \
             mock.patch("bridge.stable_score", return_value=(777, [777, 777])), \
             mock.patch("bridge.tap_play") as tap, \
             mock.patch("bridge.annotate"), contextlib.redirect_stdout(io.StringIO()):
            bridge.main(5, "greedy", seria=True)
        tap.assert_not_called()
        with open(os.path.join(tmp, "moves.jsonl")) as f:
            rows = [json.loads(line) for line in f]
        move, end = rows[0], rows[-1]
        slot = move["move"]["slot"]
        self.assertEqual(end["przed_koncem"]["board"], move["expected"])
        self.assertEqual(end["przed_koncem"]["tray"], [None if j == slot else s for j, s in enumerate(move["tray"])])
        # narzędzie bierze ten stan, gdy jest w wierszu
        self.assertEqual(przegrana_serii.state_before_end(end, move), (move["expected"], end["przed_koncem"]["tray"]))


if __name__ == "__main__":
    unittest.main()
