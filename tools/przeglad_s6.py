#!/usr/bin/env python3
"""Przegląd wsteczny przegranej z serii (#341), wzór `tools/przeglad_p7.py`, ale dla dowolnej partii z logu.
Nic nie naprawia, niczego nie gra na emulatorze.

    python3 tools/przeglad_s6.py KATALOG_PARTII [--ruchow N] [--out PLIK.json] [--md]

Czyta `pomiar.json` i `chunk*_moves.jsonl` partii (ostatnia gra z logu: od przedostatniego `koniec_partii`) i dla
ostatnich co najmniej N ruchów (dopełnionych do całych tacek) liczy:

  prawda      plansza prawdziwa przed ruchem = `expected` poprzedniego ruchu, gdy gra go przyjęła
              (`bridge.tray_consumed`); inaczej `board` poprzedniego. Różnica `board` (to, co zobaczyła polityka)
              wobec prawdy to duchy odczytu — z nich na zrzucie `NNN_state.png` bierzemy kolor łaty komórki
              i `is_block`.
  ok, klasa   pole `ok` wpisu i grupa `ok_false.klasyfikuj`, liczba pól `duchy` zdjętych przez most.
  polityka    ruch polityki z `--polityka` (domyślnie ta z `pomiar.json`) na PRAWDZIWEJ planszy i tej samej tacce,
              zgodność z ruchem mostu.
  wsteczny    dla każdego legalnego ruchu na prawdziwej planszy: czy po nim reszta bieżącej tacki i wszystkie
              późniejsze zalogowane tacki (z ostatnią włącznie) dają się ułożyć w całości (przegląd wyczerpujący
              z pamięcią stanów, bez limitu głębokości, z budżetem węzłów); ruch mostu i ruch polityki
              na prawdziwej planszy są oceniane tym samym kryterium.
  kontrfaktyk polityka gra od pierwszego ruchu z duchami na prawdziwej planszy do końca zalogowanych tacek.
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge
import most_tacki_ukladalne as mtu
import ok_false
import przegrana_serii as ps
from board import _tray_can_place, _tray_place_and_clear
from pieces import Piece

BUDZET_WEZLOW = 400_000


def natural_key(path):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", os.path.basename(path))]


def last_game_moves(rows):
    """Wiersze z ruchem ostatniej gry w logu (od przedostatniego `koniec_partii`)."""
    ends = [i for i, r in enumerate(rows) if r.get("koniec_partii")]
    start = ends[-2] + 1 if len(ends) > 1 else 0
    stop = ends[-1] if ends else len(rows)
    return [r for r in rows[start:stop] if "move" in r and "expected" in r]


def accepted(prev, cur):
    """Czy gra przyjęła ruch `prev`, sądząc po tacce następnego wpisu (`bridge.tray_consumed`)."""
    pieces = [Piece(s, "slot", -1) if s else None for s in prev["tray"]]
    return bridge.tray_consumed(pieces, prev["move"]["slot"], [(s,) if s else None for s in cur["tray"]])


def truth_boards(moves, start=0):
    """Plansze prawdziwe przed każdym ruchem i flagi `ruch_nieprzyjety` (poprzedniego ruchu).

    Łańcuch od planszy ruchu `start`: prawda przed ruchem j = symulacja ruchu j-1 na prawdzie przed j-1, gdy gra
    ruch przyjęła (`accepted`); inaczej bez zmian. Przed `start` i po przerwie w numeracji `n` (granica kawałka,
    restart) prawdą jest odczytana `board`. Nie bierzemy `expected` mostu, bo ten rośnie z planszy odczytanej,
    więc dziedziczy duchy (`docs/seria/s5/przegrana-p7.md`). Zakłada, że przyjęty klocek wylądował tam, gdzie
    chciał most — rozbieżności z odczytem widać w kolumnie `board≠prawda` wpisów, w których poprzedni ruch
    miał `ok: true`."""
    truth, not_accepted = [], []
    for j, r in enumerate(moves):
        prev = moves[j - 1] if j else None
        if j <= start or r.get("n") != prev.get("n", -2) + 1:
            truth.append(r["board"])
            not_accepted.append(False)
            continue
        acc = accepted(prev, r)
        if acc:
            m = prev["move"]
            piece = Piece(prev["tray"][m["slot"]], "slot", -1)
            truth.append(bridge.simulate(ps.to_board(truth[j - 1]), piece, m["x"], m["y"]))
        else:
            truth.append(truth[j - 1])
        not_accepted.append(not acc)
    return truth, not_accepted


def window_start(moves, n_last):
    """(indeks tacki, indeks ruchu) początku ogona: całe tacki, aż do co najmniej `n_last` ruchów."""
    trays = ps.split_trays(moves)
    first_tray, count = len(trays), 0
    while first_tray > 0 and count < n_last:
        first_tray -= 1
        count += len(trays[first_tray])
    return first_tray, next(j for j, r in enumerate(moves) if r is trays[first_tray][0])


def trim_tray(tray):
    return [mtu.trim(s) if s else None for s in tray]


def seq_completable(grid, groups, budget=BUDZET_WEZLOW):
    """Czy da się ułożyć wszystkie kształty z `groups` (lista grup: każda w dowolnej kolejności, grupy po kolei,
    z czyszczeniem linii między postawieniami). -> True / False / None (budżet węzłów wyczerpany)."""
    groups = [[s for s in g if s] for g in groups if any(g)]
    memo, nodes = {}, [0]

    def rec(g, g_grid, left):
        if not left:
            if g + 1 >= len(groups):
                return True
            return rec(g + 1, g_grid, tuple(range(len(groups[g + 1]))))
        key = (g, bytes(c for row in g_grid for c in row), left)
        if key in memo:
            return memo[key]
        nodes[0] += 1
        if nodes[0] > budget:
            raise OverflowError
        res = False
        for i in left:
            shape = groups[g][i]
            rest = tuple(j for j in left if j != i)
            for y in range(8):
                for x in range(8):
                    if _tray_can_place(g_grid, shape, x, y) and rec(g, _tray_place_and_clear(g_grid, shape, x, y), rest):
                        res = True
                        break
                if res:
                    break
            if res:
                break
        memo[key] = res
        return res

    if not groups:
        return True
    try:
        return rec(0, [row[:] for row in grid], tuple(range(len(groups[0]))))
    except OverflowError:
        return None


def future_groups(trays, t):
    """Kształty (przycięte) pełnych tacek po tacce `t` — te, które gra rozda, jeśli `t` zostanie ułożona."""
    return [trim_tray(tr[0]["tray"]) for tr in trays[t + 1:]]


def actions_review(board_grid, row, later):
    """Legalne ruchy na planszy: -> {akcja: True/False/None} wg `seq_completable` (reszta tacki + `later`)."""
    b = ps.to_board(board_grid)
    pieces = ps.to_pieces(row["tray"])
    out = {}
    for (i, x, y) in bridge.legal_moves(b, pieces):
        after = bridge.simulate(b, pieces[i], x, y)
        rest = [mtu.trim(s) for k, s in enumerate(row["tray"]) if s and k != i]
        out[(i, x, y)] = seq_completable(after, [rest] + later)
    return out


def patch_rgb(img, c, r):
    x, y = bridge.cell_center(c, r)
    p = img[int(y) - 5:int(y) + 6, int(x) - 5:int(x) + 6].reshape(-1, 3).mean(axis=0)
    return [round(float(v)) for v in p], bool(bridge.is_block(p))


def ghost_patches(img_path, cells):
    if not os.path.exists(img_path):
        return None
    img = np.array(Image.open(img_path).convert("RGB")).astype(int)
    return {"(%d,%d)" % (r, c): dict(zip(("rgb", "is_block"), patch_rgb(img, c, r))) for r, c in cells}


def counterfactual(policy, moves, trays, j0, truth):
    """Polityka gra od ruchu `j0` na planszy prawdziwej, na zalogowanych tackach. -> słownik."""
    board = ps.to_board(truth[j0])
    row0 = moves[j0]
    t0 = next(t for t, tr in enumerate(trays) if any(r is row0 for r in tr))
    tray_lists = [row0["tray"]] + [tr[0]["tray"] for tr in trays[t0 + 1:]]
    played = []
    for k, tray in enumerate(tray_lists):
        pieces = ps.to_pieces(tray)
        while any(pieces):
            legal = bridge.legal_moves(board, pieces)
            if not legal:
                return {"od_n": row0["n"], "przezyla_zalogowane_tacki": False, "zgon_w_tacce": t0 + k,
                        "zgon_po_ruchach": len(played), "pozostale_klocki": [p.shape for p in pieces if p]}
            i, x, y = policy.act(bridge.make_game_stub(board, pieces), legal)
            board.place_piece(pieces[i], x, y)
            board.clear_lines(*board.check_full_lines())
            pieces[i] = None
            played.append((i, x, y))
    return {"od_n": row0["n"], "przezyla_zalogowane_tacki": True, "zgon_w_tacce": None, "zgon_po_ruchach": None,
            "ruchy": len(played)}


def review(policy, moves, n_last, state_dir=None):
    trays = ps.split_trays(moves)
    idx = {id(r): j for j, r in enumerate(moves)}
    first_tray, start = window_start(moves, n_last)
    truth, not_accepted = truth_boards(moves, start)
    rows_out = []
    for t in range(first_tray, len(trays)):
        later = future_groups(trays, t)
        for r in trays[t]:
            j = idx[id(r)]
            pr = truth[j]
            mine = (r["move"]["slot"], r["move"]["x"], r["move"]["y"])
            ghosts = [(y, x) for y in range(8) for x in range(8) if r["board"][y][x] != pr[y][x]]
            entry = {"n": r["n"], "tacka": t - len(trays) + 1, "ok": r.get("ok"), "duchy_zdjete": len(r.get("duchy") or []),
                     "klasa": ok_false.klasyfikuj(r)[0] if r.get("ok") is False else None,
                     "poprzedni_nieprzyjety": not_accepted[j], "board_vs_prawda": ghosts, "most": list(mine)}
            if state_dir and ghosts:
                entry["lata"] = ghost_patches(os.path.join(state_dir, "%03d_state.png" % r["n"]), ghosts)
            b = ps.to_board(pr)
            pieces = ps.to_pieces(r["tray"])
            legal = bridge.legal_moves(b, pieces)
            if legal:
                theirs = policy.act(bridge.make_game_stub(b, pieces), legal)
                acts = actions_review(pr, r, later)
                entry.update(polityka_na_prawdzie=list(theirs), zgodne=tuple(theirs) == mine, legalnych=len(acts),
                             ulozenia_po_ruchu=sum(v is True for v in acts.values()),
                             budzet_wyczerpany=sum(v is None for v in acts.values()),
                             most_ulozenie=acts.get(mine), polityka_ulozenie=acts.get(tuple(theirs)))
            else:
                entry.update(polityka_na_prawdzie=None, zgodne=None, legalnych=0)
            rows_out.append(entry)
    first_ghost = next((j for j in range(len(moves)) if truth[j] != moves[j]["board"]
                        and moves[j] in [r for tr in trays[first_tray:] for r in tr]), None)
    cf = counterfactual(policy, moves, trays, first_ghost, truth) if first_ghost is not None else None
    return {"ruchy": rows_out, "kontrfaktyk": cf}


def md_table(res):
    lines = ["| n | tacka | ok | klasa | duchy zdjęte | pola board≠prawda | most | polityka na prawdzie | legalnych | z ułożeniem | most→ułożenie | polityka→ułożenie |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in res["ruchy"]:
        g = e["board_vs_prawda"]
        lines.append("| %s | %d | %s | %s | %d | %s | %s | %s | %s | %s | %s | %s |" % (
            e["n"], e["tacka"], e["ok"], e["klasa"] or "-", e["duchy_zdjete"],
            ("%d: %s" % (len(g), g[:6]) if g else "-").replace("'", ""), tuple(e["most"]),
            tuple(e["polityka_na_prawdzie"]) if e.get("polityka_na_prawdzie") else "-", e.get("legalnych"),
            e.get("ulozenia_po_ruchu", "-"), e.get("most_ulozenie", "-"), e.get("polityka_ulozenie", "-")))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog")
    ap.add_argument("--ruchow", type=int, default=10)
    ap.add_argument("--polityka", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--md", action="store_true")
    args = ap.parse_args(argv)

    with open(os.path.join(args.katalog, "pomiar.json"), encoding="utf-8") as f:
        pomiar = json.load(f)
    rows, last_chunk = [], None
    for name in pomiar.get("kawalki", []):
        path = os.path.join(args.katalog, name)
        if os.path.exists(path):
            rows.extend(ps.load_rows(path))
            last_chunk = int(re.search(r"chunk(\d+)_", name).group(1))
    moves = last_game_moves(rows)
    spec = args.polityka or pomiar.get("polityka") or ps.default_policy_spec()
    policy, err = ps.build_policy(spec)
    if policy is None:
        print("polityka niedostępna:", err, file=sys.stderr)
        return 1
    state_dir = os.path.join(args.katalog, "kawalek_%d" % last_chunk) if last_chunk else None
    res = review(policy, moves, args.ruchow, state_dir)
    res["polityka"] = spec
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1, ensure_ascii=False, default=list)
            f.write("\n")
    print(md_table(res) if args.md else json.dumps(res, indent=1, ensure_ascii=False, default=list))
    if args.md:
        print("\nkontrfaktyk:", json.dumps(res["kontrfaktyk"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
