#!/usr/bin/env python3
"""Ponowna ocena licznika apki na zapisanym materiale partii (#324): czyta `chunk*_moves.jsonl`.

Dla każdej partii wypisuje maksimum pola `score` (HUD), pierwszy kawałek i `n`, w którym licznik >= PROG utrzymał
się przez >= MIN_WPISOW kolejnych wpisów z odczytem, oraz czy przed tym wpisem był wiersz `koniec_partii`.
Klasyfikacji z `pomiar.json` nie zmienia. Użycie: tools/licznik_ponownie.py KATALOG_PARTII [...]
"""
import argparse
import glob
import json
import os
import re

PROG = 1_000_000
MIN_WPISOW = 3  # kolejnych wpisów z odczytem >= PROG


def _numer_kawalka(sciezka):
    return int(re.search(r"chunk(\d+)_moves", sciezka).group(1))


def wczytaj(katalog):
    """Wiersze partii w kolejności kawałków (numerycznie); każdy dostaje `kawalek`."""
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


def ocen(wiersze, prog=PROG, min_wpisow=MIN_WPISOW):
    """Słownik: maksimum, pierwsze przekroczenie (kawalek, n) utrzymane >= min_wpisow wpisów, koniec_partii przed nim.

    Wpisy bez `score` (null albo brak pola) nie przerywają ani nie liczą się do serii; wiersz z odczytem < prog
    przerywa serię. `koniec_partii_przed` = wiersz z `end: koniec_partii` stoi przed pierwszym wpisem serii."""
    odczyty = [w for w in wiersze if w.get("score") is not None]
    maks = max((w["score"] for w in odczyty), default=None)
    seria, start = 0, None
    for w in odczyty:
        if w["score"] >= prog:
            if seria == 0:
                start = w
            seria += 1
            if seria >= min_wpisow:
                break
        else:
            seria, start = 0, None
    przekroczenie = None
    koniec_przed = None
    if seria >= min_wpisow:
        przekroczenie = (start["kawalek"], start["n"])
        idx = next(i for i, w in enumerate(wiersze) if w is start)
        koniec_przed = any(w.get("end") == "koniec_partii" for w in wiersze[:idx])
    koniec_gdziekolwiek = any(w.get("end") == "koniec_partii" for w in wiersze)
    return {"wpisy": len(wiersze), "odczyty": len(odczyty), "maksimum": maks, "przekroczenie": przekroczenie,
            "koniec_partii_przed": koniec_przed, "koniec_partii": koniec_gdziekolwiek}


def wypisz(katalog, a):
    print(katalog)
    if not a["wpisy"]:
        print("  brak chunk*_moves.jsonl")
        return
    print(f"  maksimum licznika: {a['maksimum'] if a['maksimum'] is not None else 'brak odczytów'}"
          f" (odczytów {a['odczyty']} z {a['wpisy']} wpisów)")
    if a["przekroczenie"]:
        k, n = a["przekroczenie"]
        print(f"  >= {PROG} utrzymany przez >= {MIN_WPISOW} wpisy od: kawałek {k}, n {n}")
        print(f"  koniec_partii przed tym wpisem: {'tak' if a['koniec_partii_przed'] else 'nie'}")
    else:
        print(f"  >= {PROG} przez >= {MIN_WPISOW} kolejne wpisy: nie")
    print(f"  koniec_partii w materiale: {'tak' if a['koniec_partii'] else 'nie'}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("katalogi", nargs="+", help="katalogi partii z chunk*_moves.jsonl")
    args = p.parse_args(argv)
    for k in args.katalogi:
        wypisz(k, ocen(wczytaj(k)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
