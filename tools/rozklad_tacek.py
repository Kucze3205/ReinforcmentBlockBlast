#!/usr/bin/env python3
"""Rozkład kształtów w tackach z logów serii (#341). Nic nie naprawia, niczego nie gra na emulatorze.

    python3 tools/rozklad_tacek.py [KATALOG_DOCS_SERII] [--serie s3,s4,s5,s6] [--out PLIK.md]

Dla każdej serii przechodzi po `s*/partia-*/chunk*_moves.jsonl` i z pola `tray` pierwszego wiersza każdej tacki
(`przegrana_serii.split_trays`: nowa tacka = pełna trójka innej pary plansza+tacka) liczy kształty klocków:

  kwadrat_3x3     pełny kwadrat 3x3 (9 pól)
  prostokat_2x3   pełny prostokąt 2x3 albo 3x2 (6 pól)
  kreska_5        1x5 albo 5x1
  duze            klocek z co najmniej 6 polami (w puli to dokładnie kwadrat 3x3 i prostokąty 2x3/3x2; kreska 1x5 i L 3x3 mają 5)

Udział = klocki danego rodzaju / wszystkie klocki; `tacki_z_duzym` = odsetek tacek z co najmniej jednym klockiem
z co najmniej 6 polami; `pola_na_klocek` = średnia liczba pól. Tacki z nierozpoznanym kształtem (poza `PIECE_POOL`)
są pomijane i liczone w `pominiete`.
"""
import argparse
import glob
import json
import math
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import most_tacki_ukladalne as mtu
import przegrana_serii as ps

DOCS_SERII = os.path.join(REPO_ROOT, "docs", "seria")
RODZAJE = ("kwadrat_3x3", "prostokat_2x3", "kreska_5", "duze")


def natural_key(path):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", os.path.basename(path))]


def rodzaje(shape):
    """Przycięty kształt -> zbiór rodzajów (patrz docstring modułu) i liczba pól."""
    t = mtu.trim(shape)
    h, w = len(t), len(t[0])
    pola = sum(map(sum, t))
    out = set()
    pelny = pola == h * w
    if pelny and (h, w) == (3, 3):
        out.add("kwadrat_3x3")
    if pelny and sorted((h, w)) == [2, 3]:
        out.add("prostokat_2x3")
    if pelny and sorted((h, w)) == [1, 5]:
        out.add("kreska_5")
    if pola >= 6:
        out.add("duze")
    return out, pola


def tacki_z_wierszy(rows):
    """Wiersze z ruchem jednej partii -> lista tacek (każda: trzy kształty z pierwszego wiersza tacki)."""
    moves = [r for r in rows if "move" in r and "expected" in r]
    return [t[0]["tray"] for t in ps.split_trays(moves)]


def licz(tacki):
    """Lista tacek (trójki kształtów) -> słownik: liczniki i udziały."""
    known = mtu.known_shapes()
    klocki = {k: 0 for k in RODZAJE}
    n_klockow = n_tacek = z_duzym = pominiete = pola = 0
    for tray in tacki:
        shapes = [mtu.trim(s) if isinstance(s, list) and s and isinstance(s[0], list) else None for s in tray]
        if any(s is None or tuple(map(tuple, s)) not in known for s in shapes):
            pominiete += 1
            continue
        n_tacek += 1
        duze_w_tacce = False
        for s in tray:
            r, p = rodzaje(s)
            for k in r:
                klocki[k] += 1
            n_klockow += 1
            pola += p
            duze_w_tacce |= "duze" in r
        z_duzym += duze_w_tacce
    return {"tacek": n_tacek, "klockow": n_klockow, "pominiete": pominiete,
            "liczniki": klocki,
            "udzial": {k: (klocki[k] / n_klockow if n_klockow else 0.0) for k in RODZAJE},
            "tacki_z_duzym": z_duzym / n_tacek if n_tacek else 0.0,
            "pola_na_klocek": pola / n_klockow if n_klockow else 0.0}


def partie(katalog_serii):
    """Seria -> lista partii, każda to lista tacek (kolejność gry)."""
    out = []
    for d in sorted(glob.glob(os.path.join(katalog_serii, "partia-*")), key=natural_key):
        rows = []
        for f in sorted(glob.glob(os.path.join(d, "chunk*_moves.jsonl")), key=natural_key):
            rows.extend(ps.load_rows(f))
        out.append(tacki_z_wierszy(rows))
    return out


def seria(katalog_serii):
    """Wszystkie partie serii -> lista tacek."""
    return [t for p in partie(katalog_serii) for t in p]


def prefiks(lista_partii, n):
    """Pierwsze `n` tacek każdej partii, która ma ich co najmniej `n` -> (lista tacek, liczba partii).
    Udział dużych klocków spada z postępem partii, więc serie złożone z krótkich partii porównujemy po tym samym
    odcinku gry, nie w sumie."""
    dlugie = [p for p in lista_partii if len(p) >= n]
    return [t for p in dlugie for t in p[:n]], len(dlugie)


def z_dwumianowy(k1, n1, k0, n0):
    """Test z dla dwóch proporcji (k1/n1 wobec k0/n0, połączony odsetek); -> (z, p jednostronne: czy k1/n1 większe)."""
    if not (n1 and n0):
        return 0.0, 1.0
    p = (k1 + k0) / (n1 + n0)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n0))
    if se == 0:
        return 0.0, 1.0
    z = (k1 / n1 - k0 / n0) / se
    return z, 0.5 * math.erfc(z / math.sqrt(2))


def odstawanie(wyniki, nazwa):
    """Seria `nazwa` wobec sumy pozostałych: rodzaj -> (odsetek serii, odsetek reszty, z, p)."""
    reszta = [w for n, w in wyniki.items() if n != nazwa]
    n0 = sum(w["klockow"] for w in reszta)
    w1 = wyniki[nazwa]
    out = {}
    for k in RODZAJE:
        k0 = sum(w["liczniki"][k] for w in reszta)
        z, p = z_dwumianowy(w1["liczniki"][k], w1["klockow"], k0, n0)
        out[k] = (w1["udzial"][k], k0 / n0 if n0 else 0.0, z, p)
    return out


def tabela(wyniki):
    """{nazwa serii: wynik `licz`} -> tabela markdown."""
    lines = ["| seria | tacek | klocków | 3×3 | 2×3/3×2 | 1×5/5×1 | ≥6 pól | tacki z ≥6 pól | pól na klocek |",
             "|---|---|---|---|---|---|---|---|---|"]
    for nazwa, w in wyniki.items():
        u = w["udzial"]
        lines.append(f"| {nazwa} | {w['tacek']} | {w['klockow']} | {u['kwadrat_3x3']:.1%} | "
                     f"{u['prostokat_2x3']:.1%} | {u['kreska_5']:.1%} | {u['duze']:.1%} | "
                     f"{w['tacki_z_duzym']:.1%} | {w['pola_na_klocek']:.2f} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog", nargs="?", default=DOCS_SERII)
    ap.add_argument("--serie", default="s3,s4,s5,s6")
    ap.add_argument("--prefiksy", type=lambda v: [int(x) for x in v.split(",") if x], default=[60, 120, 250],
                    help="długości odcinka początku partii do porównania po tym samym postępie gry (puste: brak)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    wyniki, po_partiach = {}, {}
    for nazwa in args.serie.split(","):
        po_partiach[nazwa] = partie(os.path.join(args.katalog, nazwa))
        wyniki[nazwa] = licz([t for p in po_partiach[nazwa] for t in p])
    text = tabela(wyniki)
    for n in args.prefiksy:
        tekst_n = {}
        for nazwa, ps_ in po_partiach.items():
            tr, k = prefiks(ps_, n)
            tekst_n[f"{nazwa} ({k} partii)"] = licz(tr)
        text += f"\n\nPierwsze {n} tacek każdej partii (partie z co najmniej {n} tackami):\n\n" + tabela(tekst_n)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    if len(wyniki) > 1:
        ostatnia = list(wyniki)[-1]
        print(f"\n{ostatnia} wobec reszty (test z dla proporcji, p jednostronne):")
        for k, (u1, u0, z, p) in odstawanie(wyniki, ostatnia).items():
            print(f"  {k}: {u1:.2%} wobec {u0:.2%}, z={z:.2f}, p={p:.2g}")
    for nazwa, w in wyniki.items():
        if w["pominiete"]:
            print(f"uwaga: {nazwa}: pominięto {w['pominiete']} tacek z nierozpoznanym kształtem", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
