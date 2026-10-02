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
        self.progs = []
        self.snapshots = []  # zawartość pomiar.json widziana na starcie kolejnego kawałka
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "out")

    def fake_main(self, max_moves, spec, source, seria=False, prog=None):
        self.progs.append(prog)
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
            ({"okno": "restart_utracil_partie", "end": "okno: restart_utracil_partie"},
             "restart_utracil_partie", "restart_utracil_partie"),  # #318
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
        h = Harness(self, [chunk(0, 3), chunk(3, 3), chunk(6, 1, {"end": "gra nie jest na pierwszym planie"})],
                    counter_reads=[[150_000, 150_000], [1_500_000, 1_500_000]])
        code, p = h.run("--kawalek", "3")
        self.assertEqual(code, 2)
        self.assertEqual(p["przyczyna"], "apka_nie_wraca")
        self.assertEqual(p["licznik_apki"]["wartosc"], 150_000)
        self.assertEqual(len(p["licznik_odrzucone"]), 1)

    def test_kotwica_nie_utyka_na_ciagu_z_s4_partii_1(self):
        # #324: kawałek 4 przyjęty (25 662), kawałek 5 niestabilny (167 289), od 6. odczyty ≥ 10× kotwicy.
        # Ciąg z docs/seria/s4/partia-1/pomiar.json; kawałki 150 postawień jak w serii.
        with open(os.path.join(ROOT, "docs", "seria", "s4", "partia-1", "pomiar.json")) as f:
            pomiar = json.load(f)
        reads = {4: [25_662, 25_662], 5: pomiar["licznik_apki"]["odczyty"]}
        reads.update({r["kawalek"]: r["odczyty"] for r in pomiar["licznik_odrzucone"]})
        self.assertEqual(reads[5][-1], 167_289)
        self.assertFalse(len(set(reads[5][-2:])) == 1)  # niestabilny: kotwica zostaje na 25 662
        kawalki = sorted(reads)
        last = next(k for k in kawalki if reads[k][-1] >= 1_000_000 and reads[k][-1] == reads[k][-2])
        kawalki = [k for k in kawalki if k <= last]
        h = Harness(self, [chunk(150 * i, 150) for i in range(len(kawalki))],
                    counter_reads=[list(reads[k]) for k in kawalki])
        code, p = h.run("--kawalek", "150")
        self.assertEqual(code, 0)
        self.assertEqual(p["zakonczenie"], "cel")
        self.assertEqual(p["licznik_apki"]["wartosc"], reads[last][-1])
        self.assertGreaterEqual(p["licznik_apki"]["wartosc"], 1_000_000)
        self.assertEqual(len(h.calls), len(kawalki))
        # kotwica ruszyła się najpóźniej po kilku kawałkach: odrzucone tylko początek ciągu
        self.assertLessEqual(len(p["licznik_odrzucone"]), 1)

    def test_granica_przyrostu_od_kotwicy(self):
        cc = partia_serii.counter_consistent
        self.assertTrue(cc(None, 5))
        self.assertFalse(cc(25_662, 25_661, 10_000))                          # zgubiona cyfra: maleje
        self.assertTrue(cc(25_662, 265_147, 300))                             # tempo partii, 300 postawień
        self.assertFalse(cc(150_000, 1_500_000, 150))                         # dopisana cyfra zaraz po kotwicy
        self.assertTrue(cc(150_000, 1_500_000, 250))                          # to samo po dłuższej przerwie w odczytach
        self.assertTrue(cc(1_200_000, 1_520_000))                             # < 10× jak dotąd

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


SERIA = os.path.join(ROOT, "docs", "seria")


def log_kawalka(partia, k=None):
    """Wiersze ostatniego (albo k-tego) kawałka partii z docs/seria."""
    import glob
    import re
    pliki = glob.glob(os.path.join(SERIA, partia, "chunk*_moves.jsonl"))
    num = lambda p: int(re.search(r"chunk(\d+)_moves", p).group(1))
    plik = max(pliki, key=num) if k is None else os.path.join(SERIA, partia, f"chunk{k}_moves.jsonl")
    return partia_serii.load_rows(plik)


class TestStopProgu(unittest.TestCase):
    """#347: koniec kawałka tuż po 1 mln wg odczytu HUD po ruchu."""

    def test_s6_p4_kawalek_15_konczy_kilka_ruchow_po_n63(self):
        rows = log_kawalka("s6/partia-4", 15)
        t = bridge.ProgLicznika(1_000_000)
        stop = next(r["n"] for r in rows if t.feed(r["score"]))
        self.assertGreaterEqual(stop, 63)
        self.assertLessEqual(stop, 63 + 5)

    def test_pojedynczy_blad_odczytu_nie_konczy(self):
        rows = log_kawalka("s6/partia-4", 15)
        scores = [r["score"] for r in rows if r["n"] < 40]
        scores[10] = 1_453_192  # jedna zła klatka >= progu
        t = bridge.ProgLicznika(1_000_000)
        self.assertFalse(any(t.feed(x) for x in scores))
        self.assertFalse(any(t.feed(x) for x in (None, 1_000_001, None, 5, 1_000_001, 1_000_002)))

    def test_bridge_main_przerywa_kawalek_wpisem_stop_prog(self):
        tmp = tempfile.mkdtemp()
        img = np.zeros((640, 320, 3), dtype=int)
        slots = [([[1, 1]], (20, 460)), None, None]
        with mock.patch("bridge.OUT", tmp), \
             mock.patch("bridge.settled_state", return_value=(img, EMPTY, slots)), \
             mock.patch("bridge.stable_state", return_value=(img, EMPTY, slots)), \
             mock.patch("bridge.read_score", return_value=1_200_000), \
             mock.patch("bridge.is_splash_screen", return_value=True), \
             mock.patch("bridge.time.sleep"), mock.patch("bridge.annotate"), redirect_stdout(io.StringIO()):
            bridge.main(50, "greedy", seria=True, prog=1_000_000)
        rows = [json.loads(line) for line in open(os.path.join(tmp, "moves.jsonl"))]
        self.assertEqual(len(rows), bridge.PROG_ODCZYTY)
        self.assertEqual(rows[-1]["stop_prog"], 1_000_000)
        self.assertNotIn("end", rows[-1])

    def stop_chunk(self):
        rows = chunk(0, 5)
        rows.append({"n": 5, "t": T0 + 20.0, "policy": "greedy", "score": 1_002_000, "stop_prog": 1_000_000})
        return rows

    def test_potwierdzony_stop_to_cel(self):
        h = Harness(self, [self.stop_chunk()], counter_reads=[[1_003_000, 1_003_000]])
        code, pomiar = h.run()
        self.assertEqual((code, pomiar["zakonczenie"]), (0, "cel"))
        self.assertEqual(len(h.calls), 1)
        self.assertEqual(h.progs, [1_000_000])
        self.assertEqual(pomiar["stop_prog"], [{"kawalek": 1, "n": 5, "licznik": 1_002_000, "potwierdzony": True}])

    def test_niepotwierdzony_stop_gra_dalej_bez_progu_w_moscie(self):
        h = Harness(self, [self.stop_chunk(), chunk(5, 5), chunk(10, 5, {"end": "koniec_partii"})],
                    counter_reads=[[40_000, 41_000], [50_000, 50_000]])
        code, pomiar = h.run()
        self.assertEqual(len(h.calls), 3)
        self.assertEqual(h.progs, [1_000_000, None, 1_000_000])
        self.assertEqual(pomiar["stop_prog"][0]["potwierdzony"], False)
        self.assertEqual(pomiar["zakonczenie"], "przegrana")

    def test_prog_z_argumentu_idzie_do_mostu(self):
        h = Harness(self, [chunk(0, 3, {"end": "koniec_partii"})])
        h.run("--prog", "500")
        self.assertEqual(h.progs, [500])


class TestKoniecPoOknach(unittest.TestCase):
    """#347: petla_bez_postepu/plansza_zawieszona po oknach po grze to przegrana (docs/seria/s4/konce.md)."""

    PRZEGRANE = ["s4/partia-1", "s4/partia-4", "s4/partia-6", "s4/partia-10", "s3/partia-3"]
    PRZERWANIA = ["s3/partia-1", "s5/partia-2", "s6/partia-1", "s6/partia-5"]

    def test_logi_z_materialu(self):
        for p in self.PRZEGRANE:
            with self.subTest(p):
                self.assertTrue(partia_serii.koniec_po_oknach(log_kawalka(p)))
        for p in self.PRZERWANIA:
            with self.subTest(p):
                self.assertFalse(partia_serii.koniec_po_oknach(log_kawalka(p)))

    def test_przegrana_z_przyczyna_i_kodem_1(self):
        win = lambda n, okno, **kw: {"n": n, "t": T0 + n, "board": EMPTY, "tray": [None] * 3, "score": 0,
                                     "okno": okno, **kw}
        tail = [win(5, "brak_ruchu_ponowny_odczyt"), win(5, "reklama_wideo"),
                win(5, "ustawienia_wstecz", end="okno: petla_bez_postepu")]
        h = Harness(self, [chunk(0, 5) + tail])
        code, pomiar = h.run()
        self.assertEqual((code, pomiar["zakonczenie"], pomiar["przyczyna"]), (1, "przegrana", "koniec_po_oknach"))
        self.assertEqual(pomiar["przyczyna_mostu"], "petla_bez_postepu")

    def test_sama_tacka_pusta_zostaje_przerwaniem(self):
        win = lambda n, okno, **kw: {"n": n, "t": T0 + n, "board": EMPTY, "tray": [None] * 3, "score": 0,
                                     "okno": okno, **kw}
        tail = [win(5, "tacka_pusta_przejsciowo"), win(5, "tacka_pusta_przejsciowo", end="okno: petla_bez_postepu")]
        code, pomiar = Harness(self, [chunk(0, 5) + tail]).run()
        self.assertEqual((code, pomiar["zakonczenie"], pomiar["przyczyna"]), (2, "przerwanie", "petla_bez_postepu"))


if __name__ == "__main__":
    unittest.main()
