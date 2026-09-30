"""
Testy dla #283: `tools/partia_serii.py` — trzy zakończenia, kody wyjścia, atomowy checkpoint.

Most (`bridge.main`), zrzut i OCR podmienione — bez emulatora.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import bridge
import partia_serii

EMPTY = [[0] * 8 for _ in range(8)]
T0 = 1_000_000.0


def move_row(n, t, decision=10.0):
    return {"n": n, "t": T0 + t, "board": EMPTY, "tray": [[[1, 1]], None, None], "score": 0,
            "move": {"slot": 0, "x": 0, "y": 0}, "decision_ms": decision}


def chunk(n0, count, end_row=None):
    rows = [move_row(n0 + i, (n0 + i) * 4.0, 10.0 + i) for i in range(count)]
    if end_row:
        rows.append({"n": n0 + count, "t": T0 + (n0 + count) * 4.0, "board": EMPTY,
                     "tray": [[[1, 1]], None, None], "score": 0, **end_row})
    return rows


class Harness:
    """Podstawia `bridge.main` (pisze scenariusz do moves.jsonl) oraz odczyt licznika."""

    def __init__(self, test, chunks, counter_reads=()):
        self.test, self.chunks, self.counter_reads = test, list(chunks), list(counter_reads)
        self.calls = []
        self.snapshots = []  # zawartość pomiar.json widziana na starcie kolejnego kawałka
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "out")

    def fake_main(self, max_moves, spec, source, seria=False):
        self.calls.append((max_moves, spec, seria, bridge.OUT))
        pomiar = os.path.join(self.out, "pomiar.json")
        self.snapshots.append(json.load(open(pomiar)) if os.path.exists(pomiar) else None)
        rows = self.chunks[len(self.calls) - 1]
        with open(os.path.join(bridge.OUT, "moves.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return 0

    def fake_stable_score(self, img, box, tries=6):
        reads = self.counter_reads.pop(0)
        return reads[-1], reads

    def run(self, *extra):
        argv = ["greedy", self.out, *extra]
        buf = io.StringIO()
        with mock.patch("partia_serii.bridge.main", self.fake_main), \
             mock.patch("partia_serii.bridge.screenshot", lambda: np.zeros((640, 320, 3), dtype=int)), \
             mock.patch("partia_serii.bridge.stable_score", self.fake_stable_score), \
             redirect_stdout(buf), redirect_stderr(buf):
            code = partia_serii.main(argv)
        with open(os.path.join(self.out, "pomiar.json")) as f:
            return code, json.load(f)


class TestZakonczenia(unittest.TestCase):
    def test_cel_na_stabilnej_klatce(self):
        h = Harness(self, [chunk(0, 5), chunk(5, 5)], counter_reads=[[900_000, 900_000], [1_000_120, 1_000_120]])
        code, p = h.run("--prog", "1000000", "--kawalek", "5")
        self.assertEqual(code, 0)
        self.assertEqual(p["zakonczenie"], "cel")
        self.assertEqual(p["licznik_apki"]["wartosc"], 1_000_120)
        self.assertTrue(os.path.exists(os.path.join(h.out, p["licznik_apki"]["zrzut"])))
        self.assertEqual(p["postawienia"], 10)
        self.assertEqual(p["kawalki"], ["chunk1_moves.jsonl", "chunk2_moves.jsonl"])
        self.assertEqual([c[:3] for c in h.calls], [(5, "greedy", True)] * 2)
        self.assertIsNotNone(p["wynik_wzor"])
        self.assertIsNotNone(p["postawien_na_minute"])
        self.assertEqual(set(p["decision_ms"]), {"mediana", "p95", "max"})

    def test_licznik_niestabilny_nie_konczy_jako_cel(self):
        # ≥ progu, ale odczyty się różnią — gra idzie dalej; kończy dopiero stabilna klatka
        h = Harness(self, [chunk(0, 3), chunk(3, 3)],
                    counter_reads=[[1_000_500, 1_000_700], [2_000_000, 2_000_000]])
        code, p = h.run("--kawalek", "3")
        self.assertEqual(len(h.calls), 2)
        self.assertEqual(code, 0)
        self.assertEqual(h.snapshots[1]["zakonczenie"], "w_toku")
        self.assertFalse(h.snapshots[1]["licznik_apki"]["stabilny"])

    def test_przegrana_ekran_konca(self):
        end = {"koniec_partii": True, "wynik_koncowy": 4321, "zrzut_konca": "007_end.png", "end": "koniec_partii"}
        h = Harness(self, [chunk(0, 7, end)])
        code, p = h.run("--kawalek", "150")
        self.assertEqual(code, 1)
        self.assertEqual(p["zakonczenie"], "przegrana")
        self.assertEqual(len(p["ostatnie_ruchy"]), 5)
        self.assertEqual([r["n"] for r in p["ostatnie_ruchy"]], [2, 3, 4, 5, 6])
        self.assertEqual(p["ostatnie_ruchy"][0]["board"], EMPTY)
        self.assertTrue(p["zrzut_konca"].endswith("007_end.png"))
        self.assertEqual(p["wynik_koncowy"], 4321)
        self.assertEqual(len(h.calls), 1)

    def test_przerwanie_przyczyny(self):
        cases = [
            ({"okno": "plansza_zawieszona", "end": "okno: plansza_zawieszona"}, "plansza_zawieszona", "plansza_zawieszona"),
            ({"okno": "menu_glowne", "end": "okno: petla_bez_postepu"}, "petla_bez_postepu", "menu_glowne"),
            ({"end": "gra nie jest na pierwszym planie"}, "apka_nie_wraca", None),
            ({"end": "okno: reklama_interstitial"}, "nieznane_okno", "reklama_interstitial"),
        ]
        for end, przyczyna, okno in cases:
            with self.subTest(przyczyna=przyczyna, okno=okno):
                h = Harness(self, [chunk(0, 2, end)])
                code, p = h.run()
                self.assertEqual(code, 2)
                self.assertEqual(p["zakonczenie"], "przerwanie")
                self.assertEqual(p["przyczyna"], przyczyna)
                self.assertEqual(p["okno"], okno)

    def test_przerwanie_limit_minut(self):
        h = Harness(self, [chunk(0, 2)], counter_reads=[[10, 10]])
        times = iter([0, 0, 7200, 7200])
        buf = io.StringIO()
        args = partia_serii.build_parser().parse_args(["greedy", h.out, "--limit-minut", "60"])
        with mock.patch("partia_serii.bridge.main", h.fake_main), \
             mock.patch("partia_serii.bridge.screenshot", lambda: np.zeros((640, 320, 3), dtype=int)), \
             mock.patch("partia_serii.bridge.stable_score", h.fake_stable_score), redirect_stdout(buf):
            code = partia_serii.run(args, now=lambda: next(times))
        self.assertEqual(code, 2)
        with open(os.path.join(h.out, "pomiar.json")) as f:
            p = json.load(f)
        self.assertEqual(p["przyczyna"], "limit_minut")
        self.assertEqual(len(h.calls), 1)

    def test_wyjatek_to_przerwanie(self):
        h = Harness(self, [chunk(0, 2)])
        os.makedirs(h.out)
        buf = io.StringIO()
        with mock.patch("partia_serii.bridge.main", side_effect=RuntimeError("adb padł")), \
             redirect_stdout(buf), redirect_stderr(buf):
            code = partia_serii.main(["greedy", h.out])
        self.assertEqual(code, 2)
        with open(os.path.join(h.out, "pomiar.json")) as f:
            p = json.load(f)
        self.assertEqual(p["zakonczenie"], "przerwanie")
        self.assertIn("adb padł", p["przyczyna"])

    def test_blad_argumentow_kod_3(self):
        buf = io.StringIO()
        with redirect_stderr(buf), self.assertRaises(SystemExit) as cm:
            partia_serii.main(["--prog", "abc"])
        self.assertEqual(cm.exception.code, 3)
        with redirect_stderr(buf):
            self.assertEqual(partia_serii.main(["greedy", "x", "--kawalek", "0"]), 3)


class TestCheckpoint(unittest.TestCase):
    def test_checkpoint_po_kazdym_kawalku_atomowo(self):
        h = Harness(self, [chunk(0, 3), chunk(3, 3), chunk(6, 3)],
                    counter_reads=[[500_000, 500_000], [900_000, 900_000], [2_000_000, 2_000_000]])
        replaced = []
        real = os.replace

        def spy(src, dst):
            replaced.append((src, dst))
            return real(src, dst)

        with mock.patch("partia_serii.os.replace", spy):
            code, p = h.run("--kawalek", "3")
        self.assertEqual(code, 0)
        # przed 2. i 3. kawałkiem pomiar.json już jest, w_toku, z poprzednimi kawałkami
        self.assertEqual(h.snapshots[0], None)
        self.assertEqual(h.snapshots[1]["zakonczenie"], "w_toku")
        self.assertEqual(h.snapshots[1]["kawalki"], ["chunk1_moves.jsonl"])
        self.assertEqual(h.snapshots[2]["kawalki"], ["chunk1_moves.jsonl", "chunk2_moves.jsonl"])
        self.assertEqual(h.snapshots[2]["postawienia"], 6)
        pomiar = os.path.join(h.out, "pomiar.json")
        writes = [(s, d) for s, d in replaced if d == pomiar]
        self.assertEqual(len(writes), 3)  # 2 checkpointy w toku + końcowy
        self.assertTrue(all(s == pomiar + ".tmp" for s, _ in writes))
        self.assertFalse(os.path.exists(pomiar + ".tmp"))


class TestSpojnoscLicznika(unittest.TestCase):
    def test_niespojny_odczyt_to_brak_odczytu(self):
        # 1 519 468 -> 151 946 (zgubiona cyfra): maleje i 10x poniżej; potem 1 520 000 kończy jako cel
        h = Harness(self, [chunk(0, 3), chunk(3, 3), chunk(6, 3)],
                    counter_reads=[[1_200_000, 1_200_000], [150_545, 150_545], [1_520_000, 1_520_000]])
        code, p = h.run("--kawalek", "3", "--prog", "1500000")
        self.assertEqual(code, 0)
        self.assertEqual(len(h.calls), 3)
        self.assertEqual(h.snapshots[2]["licznik_apki"]["wartosc"], 1_200_000)
        self.assertEqual([r["wartosc"] for r in p["licznik_odrzucone"]], [150_545])
        self.assertEqual(p["licznik_apki"]["wartosc"], 1_520_000)

    def test_skok_o_rzad_wielkosci_nie_konczy_jako_cel(self):
        h = Harness(self, [chunk(0, 3), chunk(3, 3)], counter_reads=[[150_000, 150_000], [1_500_000, 1_500_000]])
        code, p = h.run("--kawalek", "3", "--limit-minut", "0.0001")
        self.assertEqual(code, 2)
        self.assertEqual(p["przyczyna"], "limit_minut")
        self.assertEqual(p["licznik_apki"]["wartosc"], 150_000)
        self.assertEqual(len(p["licznik_odrzucone"]), 1)

    def test_zrzut_to_klatka_zaakceptowanego_odczytu(self):
        frames = iter(np.full((640, 320, 3), v, dtype=int) for v in (10, 20))

        def stable(img, box, tries=6):
            bridge.screenshot()  # drugi odczyt robi nowy zrzut
            return 900, [899, 900, 900]

        with mock.patch("partia_serii.bridge.screenshot", lambda: next(frames)), \
             mock.patch("partia_serii.bridge.stable_score", stable):
            value, reads, is_stable, img = partia_serii.read_stable_counter()
        self.assertEqual((value, is_stable), (900, True))
        self.assertEqual(int(img[0, 0, 0]), 20)  # klatka ostatniego odczytu, nie pierwszy zrzut (10)


class TestBridgeSeria(unittest.TestCase):
    def test_koniec_partii_w_serii_nie_stuka_play(self):
        from PIL import Image
        runs = os.path.join(ROOT, "bridge", "runs", "0d96333", "120_state.png")
        img = np.asarray(Image.open(runs).convert("RGB")).astype(int)
        slots = [([[1, 1]], (20, 460)), None, None]
        tmp = tempfile.mkdtemp()
        with mock.patch("bridge.OUT", tmp), \
             mock.patch("bridge.settled_state", return_value=(img, EMPTY, slots)), \
             mock.patch("bridge.read_score", return_value=100), \
             mock.patch("bridge.is_game_over_screen", return_value=True), \
             mock.patch("bridge.game_over_score_box", return_value=bridge.GAME_OVER_SCORE_BOX), \
             mock.patch("bridge.stable_score", return_value=(777, [777, 777])), \
             mock.patch("bridge.tap_play") as tap, \
             mock.patch("bridge.annotate"), redirect_stdout(io.StringIO()):
            bridge.main(5, "greedy", seria=True)
        tap.assert_not_called()
        rows = [json.loads(line) for line in open(os.path.join(tmp, "moves.jsonl"))]
        self.assertEqual(rows[-1]["end"], "koniec_partii")
        self.assertEqual(rows[-1]["wynik_koncowy"], 777)


if __name__ == "__main__":
    unittest.main()
