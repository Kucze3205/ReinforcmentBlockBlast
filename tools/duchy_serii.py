#!/usr/bin/env python3
"""Decyzje zapadłe na odczycie z duchem (#341). Nic nie naprawia, niczego nie gra na emulatorze.

    python3 tools/duchy_serii.py [KATALOG_DOCS_SERII] [--serie s3,s4,s5,s6] [--polityka SPEC] [--out PLIK.md]

Dla każdego wpisu z ruchem, którego poprzednik miał `"ok": false`, a przed nim stał wpis z `ok: true` (baza
czysta: plansza sprzed poprzednika była odczytana dobrze) i który gra przyjęła (`przeglad_s6.accepted`), bierzemy
planszę prawdziwą = `expected` poprzednika i pytamy politykę, co zagrałaby zamiast mostu:

  inaczej    ruch polityki na prawdziwej planszy różni się od ruchu mostu (most zdecydował na `board` z odczytu);
  szkodliwe  ruch polityki pozwala dołożyć resztę tej tacki, ruch mostu nie (po nim gra jest przegrana
             najpóźniej przy tej tacce); liczone przeglądem wyczerpującym `przeglad_s6.seq_completable`;
  pas_3_4    wpisy `ok: false` (wszystkie, z ruchem), w których WSZYSTKIE pola różnicy `observed` wobec `expected`
             leżą w wierszach 3–4 (środek planszy, gdzie wisi baner).

Dla szkodliwych podaje partię, `n` i miejsce w logu (ile ruchów do końca pliku) oraz `zakonczenie` z `pomiar.json`.
Jako polityka domyślna służy ta z `pomiar.json` pierwszej partii ostatniej serii na liście.
"""
import argparse
import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge
import przegrana_serii as ps
import przeglad_s6 as p6

DOCS_SERII = os.path.join(REPO_ROOT, "docs", "seria")
PAS = (3, 4)


def diff_cells(row):
    return [(y, x) for y in range(8) for x in range(8) if row["observed"][y][x] != row["expected"][y][x]]


def w_pasie(row, pas=PAS):
    """Czy `ok: false` ma różnicę wyłącznie w wierszach `pas`."""
    d = diff_cells(row)
    return bool(d) and all(y in pas for y, _ in d)


def decyzje(policy, moves):
    """Wpisy z ruchem jednej partii -> (liczniki, lista szkodliwych: (indeks ruchu, n))."""
    c = dict(ruchow=len(moves), ok_false=0, pas_3_4=0, baza_czysta=0, inaczej=0, szkodliwe=0, nieoceniane=0,
             ruch_mostu_nielegalny=0)
    szkodliwe = []
    for r in moves:
        if r.get("ok") is False and "observed" in r:
            c["ok_false"] += 1
            c["pas_3_4"] += w_pasie(r)
    for j in range(2, len(moves)):
        pp, prev, cur = moves[j - 2], moves[j - 1], moves[j]
        if prev.get("ok") is not False or cur["n"] != prev["n"] + 1:
            continue
        if pp.get("ok") is not True or prev["n"] != pp["n"] + 1 or not p6.accepted(prev, cur):
            continue
        c["baza_czysta"] += 1
        truth = prev["expected"]
        b = ps.to_board(truth)
        pieces = ps.to_pieces(cur["tray"])
        legal = bridge.legal_moves(b, pieces)
        if not legal:
            continue
        mv = tuple(policy.act(bridge.make_game_stub(b, pieces), legal))
        mine = (cur["move"]["slot"], cur["move"]["x"], cur["move"]["y"])
        if mv == mine:
            continue
        c["inaczej"] += 1
        if mine not in legal:
            c["ruch_mostu_nielegalny"] += 1
            continue
        acts = p6.actions_review(truth, cur, [])
        a, m = acts.get(mv), acts.get(mine)
        if a is None or m is None:
            c["nieoceniane"] += 1
        elif a and not m:
            c["szkodliwe"] += 1
            szkodliwe.append((j, cur["n"]))
    return c, szkodliwe


def partie_serii(katalog_serii):
    """-> lista (nazwa partii, katalog, wpisy z ruchem)."""
    out = []
    for d in sorted(glob.glob(os.path.join(katalog_serii, "partia-*")), key=p6.natural_key):
        rows = []
        for f in sorted(glob.glob(os.path.join(d, "chunk*_moves.jsonl")), key=p6.natural_key):
            rows.extend(ps.load_rows(f))
        out.append((os.path.basename(d), d, [r for r in rows if "move" in r and "expected" in r]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog", nargs="?", default=DOCS_SERII)
    ap.add_argument("--serie", default="s3,s4,s5,s6")
    ap.add_argument("--polityka", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    serie = args.serie.split(",")
    spec = args.polityka
    if spec is None:
        with open(os.path.join(args.katalog, serie[-1], "partia-1", "pomiar.json"), encoding="utf-8") as f:
            spec = json.load(f).get("polityka") or ps.default_policy_spec()
    policy, err = ps.build_policy(spec)
    if policy is None:
        print("polityka niedostępna:", err, file=sys.stderr)
        return 1

    lines = ["| seria | ruchów | ok:false | w wierszach 3–4 | baza czysta | inaczej | szkodliwe | nieoceniane | szkodliwe /1000 ruchów |",
             "|---|---|---|---|---|---|---|---|---|"]
    details = []
    for s in serie:
        tot = None
        for nazwa, d, moves in partie_serii(os.path.join(args.katalog, s)):
            c, bad = decyzje(policy, moves)
            tot = c if tot is None else {k: tot[k] + c[k] for k in tot}
            if bad:
                with open(os.path.join(d, "pomiar.json"), encoding="utf-8") as f:
                    zak = json.load(f)
                for j, n in bad:
                    details.append(f"{s} {nazwa}: ruch n={n}, {len(moves) - 1 - j} ruchów przed końcem logu, "
                                   f"zakonczenie={zak.get('zakonczenie')} ({zak.get('przyczyna')})")
        if tot:
            lines.append(f"| {s} | {tot['ruchow']} | {tot['ok_false']} | {tot['pas_3_4']} | {tot['baza_czysta']} | "
                         f"{tot['inaczej']} | {tot['szkodliwe']} | {tot['nieoceniane']} | "
                         f"{1000 * tot['szkodliwe'] / tot['ruchow']:.2f} |")
    text = "\n".join(lines) + "\n\nSzkodliwe decyzje:\n" + "\n".join("- " + d for d in details)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
