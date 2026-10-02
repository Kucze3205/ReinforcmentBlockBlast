"""
Testy dla #335: podgrupy mechanizmu wpisów `"ok": false` w `tools/ok_false.py` (`docs/seria/ok-false.md`), na wpisach
z prawdziwego materiału `docs/seria/s*/partia-*/chunk*_moves.jsonl`. Zrzuty `*_state.png` opisane w dokumencie
potwierdzają mechanizm; testy trzymają tylko to, co da się policzyć z logu.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ok_false

SERIA = os.path.join(ROOT, "docs", "seria")
_cache = {}


def wpisy(partia, chunk):
    """Wpisy `ok: false` z `docs/seria/<partia>/chunk<chunk>_moves.jsonl` (partia np. `s4/partia-1`)."""
    plik = os.path.join(SERIA, partia, f"chunk{chunk}_moves.jsonl")
    if plik not in _cache:
        _cache[plik] = ok_false.wpisy_podgrup(plik)
    return _cache[plik]


def wpis(partia, chunk, n):
    return next(w for w in wpisy(partia, chunk) if w["n"] == n)


class TestPodgrupy(unittest.TestCase):
    def assertPod(self, w, grupa, podgrupa):
        self.assertEqual((w["grupa"], w["podgrupa"]), (grupa, podgrupa))

    def test_napis_pochwaly_czytany_jako_klocek(self):
        # s4/partia-1/kawalek_22/055_state.png: „Perfect!" na wierszu 4 -> pole (4, 3) w odczycie
        w = wpis("s4/partia-1", 22, 54)
        self.assertPod(w, "nadmiar_gdzie_indziej", "napis")
        self.assertEqual(w["pola"], [(4, 3)])
        self.assertTrue(w["dotrwal"])

    def test_napis_zaslania_klocek(self):
        # s5/partia-2/kawalek_4/020_state.png: baner „Combo 39" na wierszu 4 zakrywa klocek (4, 3)
        self.assertPod(wpis("s5/partia-2", 4, 19), "brak_pol", "napis")

    def test_serce_combo(self):
        # s5/partia-8/kawalek_1/049_state.png: różowe serce „Combo 29" na środku planszy
        w = wpis("s5/partia-8", 1, 48)
        self.assertPod(w, "nadmiar_gdzie_indziej", "serce")
        self.assertGreaterEqual(len(w["pola"]), ok_false.SERCE_MIN_POL)

    def test_zakryte_pole_wraca(self):
        # s3/partia-4/kawalek_2: (4, 5) nie zostało odczytane w n=48 (klocek zakryty), a w n=49 jest na ekranie
        self.assertPod(wpis("s3/partia-4", 2, 49), "nadmiar_gdzie_indziej", "zakryte_wraca")

    def test_duch_znika_po_kilku_krokach(self):
        # s1/partia-3/kawalek_54/100_state.png: pól (6, 3), (6, 4) nie ma na ekranie, `expected` je dziedziczył
        w = wpis("s1/partia-3", 54, 99)
        self.assertPod(w, "brak_pol", "dawny_duch")
        self.assertEqual(w["pola"], [(6, 3), (6, 4)])

    def test_plansza_bez_zmian_mimo_przyjetego_ruchu(self):
        # s1/partia-2/kawalek_1/015_state.png: klocek jest na ekranie (kciuk-nagroda), odczyt go nie widzi;
        # tacka następnego wpisu potwierdza, że gra ruch przyjęła
        w = wpis("s1/partia-2", 1, 14)
        self.assertPod(w, "brak_pol", "plansza_bez_zmian")
        self.assertEqual(w["wpis"]["observed"], w["wpis"]["board"])
        self.assertTrue(w["tacka"])

    def test_klocek_niepelny(self):
        # s2/partia-2/kawalek_4/054_state.png: z klocka 2x3 odczytane 4 pola z 6
        self.assertPod(wpis("s2/partia-2", 4, 53), "brak_pol", "klocek_niepelny")

    def test_klocek_spadl_obok_celu(self):
        w = wpis("s3/partia-7", 1, 5)
        self.assertPod(w, "mieszane", "klocek_obok_celu")
        self.assertFalse(w["tacka"], "tacka nie potwierdza ruchu przy klocku obok celu")

    def test_inny_klocek(self):
        self.assertPod(wpis("s1/partia-5", 2, 34), "nadmiar_gdzie_indziej", "inny_klocek")

    def test_pusty_odczyt_to_klatka_przejsciowa(self):
        w = wpis("s1/partia-2", 2, 0)
        self.assertPod(w, "brak_pol", "odczyt_pusty")
        self.assertFalse(w["dotrwal"], "następny odczyt wraca do `expected`")

    def test_niewyjasnione_duze(self):
        # s4/partia-4/kawalek_1/100_state.png: zwykła plansza bez nakładki, 11 pól różnicy bez wzorca
        w = wpis("s4/partia-4", 1, 99)
        self.assertPod(w, "mieszane", "niewyjasnione_duze")
        self.assertGreaterEqual(len(w["pola"]), ok_false.DUZA_ROZNICA)

    def test_duch_baneru_p7_zostaje_w_pierwszej_grupie(self):
        self.assertPod(wpis("s5/partia-7", 9, 38), "duchy_w_czyszczonych", "duchy_w_czyszczonych")

    def test_nazwy_skladaja_sie_z_rodzajow_w_stalej_kolejnosci(self):
        w = wpis("s3/partia-6", 4, 49)
        self.assertPod(w, "mieszane", "baner+napis+dawny_duch")
        czesci = w["podgrupa"].split("+")
        self.assertEqual(czesci, [e for e in ok_false.RODZAJE if e in czesci])

    def test_podgrupy_sumuja_sie_do_ok_false(self):
        for partia, chunk in (("s5/partia-7", 9), ("s1/partia-2", 1), ("s3/partia-4", 2)):
            plik = os.path.join(SERIA, partia, f"chunk{chunk}_moves.jsonl")
            ws = wpisy(partia, chunk)
            cnt = ok_false.przejdz(plik)
            self.assertEqual(len(ws), cnt["ok_false"], plik)
            for g in ok_false.GRUPY:
                self.assertEqual(sum(w["grupa"] == g for w in ws), cnt[g], (plik, g))
            self.assertTrue(all(w["podgrupa"] for w in ws), plik)

    def test_odczyt_bledny(self):
        self.assertEqual(ok_false.odczyt_bledny("napis+dawny_duch"), "tak")
        self.assertEqual(ok_false.odczyt_bledny("plansza_bez_zmian"), "tak")
        self.assertEqual(ok_false.odczyt_bledny("dawny_duch+zakryte_wraca"), "nie")
        self.assertEqual(ok_false.odczyt_bledny("klocek_obok_celu"), "nie")
        self.assertEqual(ok_false.odczyt_bledny("inny_klocek"), "nieznane")
        self.assertEqual(ok_false.odczyt_bledny("niewyjasnione_duze"), "nieznane")

    def test_zrzut_stanu_wskazuje_klatke_po_ruchu(self):
        w = wpis("s5/partia-7", 9, 38)
        self.assertEqual(os.path.relpath(ok_false.zrzut_stanu(w), ROOT),
                         os.path.join("docs", "seria", "s5", "partia-7", "kawalek_9", "039_state.png"))
        self.assertIsNone(ok_false.zrzut_stanu(wpis("s4/partia-1", 22, 54) | {"n": 1000}))


class TestDecyzja(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.polityka = ok_false.zbuduj_polityke()

    def test_p7_duch_zmienia_decyzje_i_odbiera_uklad_tacki(self):
        # kontrola dodatnia: wpis 38 to przyczyna przegranej s5 p.7 — z duchami plansza nie ma układu całej tacki
        d = ok_false.decyzja(wpis("s5/partia-7", 9, 38), self.polityka)
        self.assertTrue(d["rozni"])
        self.assertTrue(d["odczyt_bez_ulozenia_expected_ma"])
        self.assertFalse(d["nielegalny_na_expected"])

    def test_klocek_zakryty_daje_ruch_nielegalny_na_prawdziwej_planszy(self):
        # odczyt bez klocka (plansza_bez_zmian) -> polityka stawia na polu zajętym w `expected`: gra odrzuci ruch
        w = wpis("s1/partia-1", 12, 59)
        self.assertEqual(w["podgrupa"], "plansza_bez_zmian")
        self.assertTrue(ok_false.decyzja(w, self.polityka)["nielegalny_na_expected"])


if __name__ == "__main__":
    unittest.main()
