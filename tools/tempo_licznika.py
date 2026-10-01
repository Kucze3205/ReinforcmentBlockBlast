#!/usr/bin/env python3
"""Tempo licznika apki na materiale partii serii (#309): czyta `chunk*_moves.jsonl`.

Pole `score` = odczyt HUD apki, `t` = czas (s, unix) wiersza, `n` = numer postawienia w kawałku
(0-based, kawałek ma zwykle 150 postawień; ponowione próby powtarzają `n`). Odczyt jest odrzucany, gdy
cofa się względem ostatniego przyjętego albo skacze o więcej niż MAX_SKOK (błąd HUD, np. 6 z 7 cyfr);
odrzucone są liczone osobno. Użycie: tools/tempo_licznika.py KATALOG_PARTII [...]
"""
import argparse
import glob
import json
import os
import re

PROG = 1_000_000
MAX_SKOK = 100_000   # największy zmierzony przyrost między sąsiednimi wierszami: ~17 tys.
START_MIN = 3.0      # minuty startu apki doliczane przy szacunku limitu


def _numer_kawalka(sciezka):
    return int(re.search(r"chunk(\d+)_moves", sciezka).group(1))


def wczytaj(katalog):
    """Wiersze partii w kolejności kawałków; każdy dostaje `kawalek`."""
    pliki = sorted(glob.glob(os.path.join(katalog, "chunk*_moves.jsonl")), key=_numer_kawalka)
    wiersze = []
    for p in pliki:
        with open(p) as f:
            for linia in f:
                if linia.strip():
                    w = json.loads(linia)
                    w["kawalek"] = _numer_kawalka(p)
                    wiersze.append(w)
    return wiersze


def czyszczenie(w):
    """Czy ruch wyczyścił linie (komórek planszy + klocka więcej niż w `observed`); None gdy nie wiadomo."""
    if not w.get("ok") or not w.get("observed") or not w.get("move"):
        return None
    klocek = (w.get("tray") or [None] * 3)[w["move"]["slot"]]
    if not klocek:
        return None
    przed = sum(map(sum, w["board"])) + sum(map(sum, klocek))
    return przed > sum(map(sum, w["observed"]))


def _postawienia(wiersze):
    """Ostatni wiersz każdego (kawałek, n) — próba, po której partia poszła dalej."""
    ostatnie = {}
    for w in wiersze:
        ostatnie[(w["kawalek"], w["n"])] = w
    return [ostatnie[k] for k in sorted(ostatnie)]


def lancuchy(wiersze):
    """Długości serii czyszczeń z rzędu (jedno postawienie = jedno czyszczenie lub nie)."""
    serie, biezaca = [], 0
    for w in _postawienia(wiersze):
        c = czyszczenie(w)
        if c:
            biezaca += 1
        elif c is False:
            if biezaca:
                serie.append(biezaca)
            biezaca = 0
    if biezaca:
        serie.append(biezaca)
    return serie


def analizuj(wiersze):
    """Tempo licznika jednej partii (słownik); None dla pustego materiału."""
    if not wiersze:
        return None
    t0 = wiersze[0]["t"]
    offset, suma = {}, 0
    for k in sorted({w["kawalek"] for w in wiersze}):
        offset[k] = suma
        suma += len({w["n"] for w in wiersze if w["kawalek"] == k})
    minuty = (wiersze[-1]["t"] - t0) / 60

    przyjete, odrzucone, ostatni = [], [], None
    for w in wiersze:
        s = w.get("score")
        if s is None:
            continue
        nr = offset[w["kawalek"]] + w["n"] + 1
        if ostatni is not None and (s < ostatni or s - ostatni > MAX_SKOK):
            odrzucone.append((nr, s))
            continue
        ostatni = s
        przyjete.append((nr, s, (w["t"] - t0) / 60, w["kawalek"]))

    po_kawalkach = []
    for k in sorted(offset):
        wk = [p for p in przyjete if p[3] == k]
        if wk:
            po_kawalkach.append(wk[-1][1])
    prz = next((p for p in przyjete if p[1] >= PROG), None)
    return {
        "postawienia": suma,
        "minuty": minuty,
        "licznik": przyjete[-1][1] if przyjete else None,
        "po_kawalkach": po_kawalkach,
        "na_minute": suma / minuty if minuty else None,
        "odrzucone": odrzucone,
        "przekroczenie": (prz[0], prz[2]) if prz else None,
        "serie": lancuchy(wiersze),
    }


def dojdzie_do_progu(a, limit=340):
    """Czy partia dojdzie do PROG w `limit` min (z START_MIN na start apki); None bez odczytów licznika."""
    if a["licznik"] is None:
        return None
    return bool(a["przekroczenie"]) and a["przekroczenie"][1] + START_MIN <= limit


def main():
    ap = argparse.ArgumentParser(description="Tempo licznika apki na partiach serii")
    ap.add_argument("katalogi", nargs="+")
    for k in ap.parse_args().katalogi:
        a = analizuj(wczytaj(k))
        print("==", k)
        if a is None:
            print("  brak wierszy")
            continue
        print("  postawienia %d  minuty %.1f  postawien/min %.2f" % (a["postawienia"], a["minuty"], a["na_minute"]))
        print("  licznik na końcu %s  odrzucone odczyty %d" % (a["licznik"], len(a["odrzucone"])))
        print("  po kawałkach: %s" % (", ".join(map(str, a["po_kawalkach"]))))
        print("  1 mln:", a["przekroczenie"] or "nie przekroczył")
        if a["serie"]:
            print("  serie czyszczeń: %d, najdłuższa %d" % (len(a["serie"]), max(a["serie"])))


if __name__ == "__main__":
    main()
