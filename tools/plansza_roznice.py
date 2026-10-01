#!/usr/bin/env python3
"""Tabela klatek z różnicą planszy most vs odczyt niezależny (#315). Nic nie naprawia.

    python3 tools/plansza_roznice.py [--out PLIK.md]

Przechodzi po wszystkich `docs/seria/s*/partia-*/kawalek_K/NNN_state.png`, porównuje `bridge.read_board` z
`porownanie_odczytu.board_independent` i dla klatek z różnicą dopisuje: czy w logu jest ruch, `ok` z logu, czy
ruch przyjęła gra (następny wpis ma o jeden klocek mniej w slocie ruchu albo nową tackę) oraz ciągłość planszy
(plansza z klatki n == `expected` z wpisu n-1). Werdykty „kto ma rację” i kategorie zostały rozstrzygnięte
wzrokowo na zrzutach i siedzą w słownikach niżej (przedstawiciele grup opisani w dokumencie).
"""
import argparse
import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import bridge
import porownanie_odczytu as po

KAT_NAPIS = "napis (Combo / pochwała / +N) nad polami"
KAT_NAPIS_WYBUCH = "napis + błysk wybuchu w komórce"
KAT_WYBUCH = "błysk wybuchu / iskry w komórce"
KAT_KCIUK = "ikony kciuka na polach"
KAT_DLON = "dłoń / duch podpowiedzi samouczka"
KAT_CZYSZCZENIE = "animacja czyszczenia wiersza"
KAT_SERCE = "serce (efekt pełnoekranowy)"
KAT_ODWROT = "odczyt niezależny odwrócony (ponad 32 pola zajęte)"
KAT_START = "ekran startowy, nie plansza"
KAT_REKLAMA = "reklama wideo, nie plansza"
KAT_KONIEC = "ekran końca partii, nie plansza"

# Klatki (seria/partia/kawałek/n), w których most odczytał planszę źle wg ciągłości z `expected` n-1 i zrzutu.
# `brak` = pola z prawdziwym klockiem, które most czyta jako puste; `duch` = pola puste, które most czyta jako zajęte.
MOST_ZLE = {
    "s1/10/1/40": dict(kat=KAT_NAPIS, kto="niezależny (+ oba w 2 polach)", brak=[(3, 3)], duch=[(4, 2), (4, 4)]),
    "s1/2/1/15": dict(kat=KAT_KCIUK, kto="niezależny", brak=[(5, 0), (5, 1), (5, 2), (6, 0), (7, 0)], duch=[]),
    "s1/2/1/100": dict(kat=KAT_KCIUK, kto="niezależny", brak=[(0, 7), (1, 7), (2, 7), (3, 7)], duch=[]),
    "s1/6/1/45": dict(kat=KAT_KCIUK, kto="niezależny",
                      brak=[(r, c) for r in range(3) for c in range(3)], duch=[]),
    "s1/6/1/110": dict(kat=KAT_NAPIS, kto="niezależny", brak=[(4, 3)], duch=[]),
    "s1/8/1/15": dict(kat=KAT_NAPIS, kto="niezależny (+ oba w 2 polach)", brak=[(4, 3), (4, 4)], duch=[(4, 1), (4, 2)]),
    "s1/9/1/15": dict(kat=KAT_KCIUK, kto="niezależny", brak=[(5, 3), (5, 4), (6, 3), (7, 3)], duch=[]),
    "s1/1/9/100": dict(kat=KAT_NAPIS, kto="most w polach spornych; oba źle w 2 polach", brak=[], duch=[(1, 6), (1, 7)]),
    "s1/5/2/10": dict(kat=KAT_SERCE, kto="oba źle", brak=[],
                      duch=[(2, 2), (2, 3), (2, 4), (2, 5), (3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (5, 3)]),
    "s1/5/2/120": dict(kat=KAT_NAPIS, kto="most w polach spornych; oba źle w 2 polach", brak=[], duch=[(5, 5), (5, 6)]),
    "s1/7/1/15": dict(kat=KAT_KCIUK, kto="oba źle", brak=[], duch=[(4, 2), (5, 2)]),
}

# Pozostałe klatki z ruchem: kategoria wg indeksu na arkuszach podglądu (zob. dokument); kto = most.
KAT_WG_KLATKI = {
    KAT_NAPIS_WYBUCH: ["s1/1/23/100", "s1/1/27/50", "s1/1/30/50", "s1/1/38/50", "s1/1/40/100", "s1/1/49/50",
                       "s1/1/50/100", "s1/1/53/50", "s1/3/13/100", "s1/3/27/100", "s1/3/54/50"],
    KAT_WYBUCH: ["s1/1/28/50", "s1/1/32/100", "s1/1/41/50", "s1/1/47/50", "s1/3/12/100", "s1/3/15/100",
                 "s1/3/3/100", "s1/3/45/50"],
    KAT_KCIUK: ["s1/5/1/0x", "s1/5/2/50x", "s1/5/1/35x", "s1/5/2/30", "s1/5/1/35", "s1/5/3/95x", "s1/6/1/40"],
    KAT_DLON: ["s1/10/1/0", "s1/2/1/0", "s1/4/1/0", "s1/5/1/0", "s1/6/1/0", "s1/7/1/0", "s1/8/1/0", "s1/9/1/0",
               "s3/7/1/0"],
    KAT_CZYSZCZENIE: ["s1/5/1/15"],
}
KAT_WG_KLATKI[KAT_KCIUK] = ["s1/5/2/30", "s1/5/1/35", "s1/6/1/40", "s1/8/2/45x"]
KAT_WG_KLATKI[KAT_KCIUK] = [k for k in KAT_WG_KLATKI[KAT_KCIUK] if not k.endswith("x")]

SPLASH = {"s2/1/2/58", "s2/10/2/60", "s2/3/3/92", "s2/4/2/46", "s2/9/2/63"}


def load_log(part, kawalek):
    recs = {}
    with open(os.path.join(part, f"chunk{kawalek}_moves.jsonl"), encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            recs[r.get("n")] = r
    return recs


def n_pieces(tray):
    return sum(1 for s in tray if s)


def accepted(a, b):
    """Czy gra przyjęła ruch z wpisu a: wpis b (n+1) ma o jeden klocek mniej, w slocie ruchu pusto, albo nową tackę."""
    if a.get("ok") is True:
        return True
    if b is None or "tray" not in b:
        return None
    ca, cb = n_pieces(a["tray"]), n_pieces(b["tray"])
    if cb == ca - 1:
        return b["tray"][a["move"]["slot"]] is None
    return ca == 1 and cb == 3


def scan():
    rows = []
    for png in sorted(glob.glob(os.path.join(REPO_ROOT, "docs/seria/s*/partia-*/kawalek_*/*_state.png"))):
        d = os.path.dirname(png)
        kawalek = int(d.rsplit("_", 1)[1])
        part = os.path.dirname(d)
        n = int(os.path.basename(png)[:3])
        seria = os.path.relpath(part, os.path.join(REPO_ROOT, "docs/seria")).split(os.sep)
        partia = seria[1].split("-")[1]
        key = f"{seria[0]}/{partia}/{kawalek}/{n}"
        img = po.load(png)
        mine, own = bridge.read_board(img), po.board_independent(img)
        diff = [(r, c) for r in range(8) for c in range(8) if mine[r][c] != own[r][c]]
        if not diff:
            continue
        recs = load_log(part, kawalek)
        rec, prev, nxt = recs.get(n), recs.get(n - 1), recs.get(n + 1)
        has_move = bool(rec and "move" in rec)
        cont = None
        if rec and prev and "expected" in prev:
            cont = rec["board"] == prev["expected"]
        move_cells = []
        if has_move:
            shape = rec["tray"][rec["move"]["slot"]]
            move_cells = [(rec["move"]["y"] + i, rec["move"]["x"] + j)
                          for i, row in enumerate(shape) for j, v in enumerate(row) if v]
        rows.append(dict(key=key, seria=seria[0], partia=partia, kawalek=kawalek, n=n, diff=diff, has_move=has_move,
                         ok=rec.get("ok") if rec else None, accepted=accepted(rec, nxt) if has_move else None,
                         cont=cont, move_cells=move_cells, bridge_n=sum(map(sum, mine)), own_n=sum(map(sum, own)),
                         end=rec.get("end") if rec else None))
    return rows


def verdict(r, kat_idx):
    k = r["key"]
    if k in MOST_ZLE:
        v = MOST_ZLE[k]
        return v["kto"], v["kat"]
    if len(r["diff"]) == 64 and r["has_move"]:
        return "most", KAT_ODWROT
    if k in SPLASH:
        return "oba (to nie plansza)", KAT_START
    if k == "s2/2/4/61":
        return "oba (to nie plansza)", KAT_REKLAMA
    if k == "s1/10/1/48":
        return "oba (to nie plansza)", KAT_KONIEC
    if k == "s1/5/4/48":
        return "niezależny (duch w polu (4,5))", KAT_NAPIS
    return "most", kat_idx.get(k, KAT_NAPIS)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="plik na tabelę markdown (domyślnie: stdout)")
    args = ap.parse_args(argv)
    kat_idx = {k: kat for kat, ks in KAT_WG_KLATKI.items() for k in ks}
    rows = scan()
    lines = ["| seria | partia | kawałek | n | różnych pól | kto ma rację | kategoria | ruch | ok (log) | gra przyjęła ruch "
             "| most źle i ruch |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    n_most_zle_ruch = 0
    for r in rows:
        kto, kat = verdict(r, kat_idx)
        zle = r["key"] in MOST_ZLE and r["has_move"]
        n_most_zle_ruch += zle
        if zle:
            brak = set(MOST_ZLE[r["key"]]["brak"])
            print(r["key"], "ruch na polach pominiętych przez most:", sorted(brak & set(r["move_cells"])) or "brak",
                  "| przyjęty:", r["accepted"])
        acc = {True: "tak", False: "nie", None: "?"}[r["accepted"]] if r["has_move"] else "-"
        lines.append(f"| {r['seria']} | {r['partia']} | {r['kawalek']} | {r['n']} | {len(r['diff'])} | {kto} | {kat} "
                     f"| {'tak' if r['has_move'] else 'nie'} | {r['ok'] if r['has_move'] else '-'} | {acc} "
                     f"| {'**tak**' if zle else 'nie'} |")
    text = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    print(len(rows), "klatek z różnicą;", sum(r["has_move"] for r in rows), "z ruchem;", n_most_zle_ruch,
          "z błędem mostu i ruchem")
    return 0


if __name__ == "__main__":
    sys.exit(main())
