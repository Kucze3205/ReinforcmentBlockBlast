#!/usr/bin/env python3
"""Klasyfikacja wpisów `"ok": false` z materiału serii (#333). Nic nie naprawia.

    python3 tools/ok_false.py [KATALOG_SERII] [--out PLIK.md]

Przechodzi po `docs/seria/s*/partia-*/chunk*_moves.jsonl` i każdy wpis z ruchem i `"ok": false` wrzuca do jednej grupy
(różnica `observed` vs `expected`, pole po polu):
  - `duchy_w_czyszczonych`: tylko nadmiar (observed=1, expected=0), i to wyłącznie w liniach wyczyszczonych tym ruchem
    (typowo baner „Combo N" czytany jako klocki);
  - `nadmiar_gdzie_indziej`: tylko nadmiar, przynajmniej jedno pole poza liniami wyczyszczonymi tym ruchem;
  - `brak_pol`: tylko brak (observed=0, expected=1);
  - `mieszane`: i nadmiar, i brak.
Osobna kolumna `ruch_nieprzyjety` liczy wpisy, w których `observed` == `board` (plansza się nie ruszyła).
Dla pierwszej grupy liczy, w ilu przypadkach duch dotrwał do decyzji następnego ruchu (kolejny wpis z ruchem w tym samym
pliku ma te pola w `board`) i w ilu przypadkach ruch potwierdza tacka tego następnego wpisu (`tray_consumed`).
"""
import argparse
import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import bridge
from board import Board
from pieces import Piece

GRUPY = ("duchy_w_czyszczonych", "nadmiar_gdzie_indziej", "brak_pol", "mieszane")


def klasyfikuj(r):
    """-> (grupa, nadmiar, brak, czyszczone) dla wpisu z ruchem i `ok: false`."""
    board = Board()
    board.grid = [row[:] for row in r["board"]]
    m = r["move"]
    shape = r["tray"][m["slot"]]
    cleared = bridge.cleared_cells(board, Piece(shape, "slot", -1), m["x"], m["y"])
    exp, obs = r["expected"], r["observed"]
    nadmiar = [(y, x) for y in range(8) for x in range(8) if obs[y][x] and not exp[y][x]]
    brak = [(y, x) for y in range(8) for x in range(8) if exp[y][x] and not obs[y][x]]
    if nadmiar and brak:
        grupa = "mieszane"
    elif brak:
        grupa = "brak_pol"
    elif nadmiar:
        grupa = "duchy_w_czyszczonych" if all(p in cleared for p in nadmiar) else "nadmiar_gdzie_indziej"
    else:  # ok=false bez różnicy pól nie istnieje w logu mostu
        grupa = "mieszane"
    return grupa, nadmiar, brak, cleared


def przejdz(plik):
    """Zlicza grupy w jednym pliku; -> (słownik liczników, lista przypadków pierwszej grupy)."""
    with open(plik, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    ruchy = [r for r in rows if "move" in r and "observed" in r]
    cnt = dict.fromkeys(GRUPY, 0)
    cnt.update(ok_false=0, ruchow=len(ruchy), ruch_nieprzyjety=0, duch_dotrwal=0, tacka_potwierdza=0, bez_nastepnego=0)
    for k, r in enumerate(ruchy):
        if r.get("ok") is not False:
            continue
        cnt["ok_false"] += 1
        cnt["ruch_nieprzyjety"] += r["observed"] == r["board"]
        grupa, nadmiar, _, _ = klasyfikuj(r)
        cnt[grupa] += 1
        if grupa != "duchy_w_czyszczonych":
            continue
        if k + 1 >= len(ruchy):
            cnt["bez_nastepnego"] += 1
            continue
        nast = ruchy[k + 1]
        if all(nast["board"][y][x] for y, x in nadmiar):
            cnt["duch_dotrwal"] += 1
        pieces = [Piece(s, "slot", -1) if s else None for s in r["tray"]]
        if bridge.tray_consumed(pieces, r["move"]["slot"], [(s,) if s else None for s in nast["tray"]]):
            cnt["tacka_potwierdza"] += 1
    return cnt


def zbierz(katalog):
    """-> {seria: liczniki} dla `katalog/s*/partia-*/chunk*_moves.jsonl`."""
    out = {}
    for seria in sorted(d for d in os.listdir(katalog) if d.startswith("s") and d[1:].isdigit()):
        razem = None
        for plik in sorted(glob.glob(os.path.join(katalog, seria, "partia-*", "chunk*_moves.jsonl"))):
            c = przejdz(plik)
            razem = c if razem is None else {k: razem[k] + c[k] for k in razem}
        if razem is not None:
            out[seria] = razem
    return out


def tabela(wyniki):
    kol = ("ruchow", "ok_false") + GRUPY + ("ruch_nieprzyjety",) + ("duch_dotrwal", "tacka_potwierdza", "bez_nastepnego")
    suma = {k: sum(w[k] for w in wyniki.values()) for k in kol}
    linie = ["| seria | " + " | ".join(kol) + " |", "|---|" + "---|" * len(kol)]
    for seria, w in list(wyniki.items()) + [("**suma**", suma)]:
        linie.append(f"| {seria} | " + " | ".join(str(w[k]) for k in kol) + " |")
    return "\n".join(linie), suma


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog", nargs="?", default=os.path.join(REPO_ROOT, "docs", "seria"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    tekst, _ = tabela(zbierz(args.katalog))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(tekst + "\n")
    print(tekst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
