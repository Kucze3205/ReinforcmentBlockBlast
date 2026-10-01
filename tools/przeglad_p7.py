#!/usr/bin/env python3
"""Przegląd przegranej s5 p.7 (#329). Nic nie naprawia, niczego nie gra na emulatorze.

    python3 tools/przeglad_p7.py KATALOG_PARTII [--losowan N] [--out PLIK.json]

Czyta `chunk9_moves.jsonl` i zrzuty `kawalek_9/` i liczy cztery rzeczy:
  1. odczyt: czym są pola (6,1),(7,1), które most widzi na planszy po ruchu 38 (kolor łaty na `039_state.png`,
     zgodność `observed`/`expected`, plansza z okna po ostatnim ruchu) i co polityka rekordu zagrałaby na planszy
     bez tych pól;
  2. przegląd wyczerpujący tacki z n=38 na planszy sprzed ruchu 38;
  3. przegląd wsteczny n=35-37: ułożenia tacek, po których tacka z n=38 dałaby się ułożyć, z oceną polityki;
  4. częstość: tacki losowane z `generator.Generator` (ślepy na planszę) na planszach z n=35-38 i odsetek tacek
     nieułożonych w całości po pierwszym ruchu polityki rekordu.
"""
import argparse
import json
import os
import sys
from itertools import permutations

import numpy as np
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge
import policies
import przegrana_serii as ps
from board import Board, _tray_can_place, _tray_place_and_clear
from generator import Generator


def rows_of(path):
    return ps.load_rows(path)


def completions(grid, shapes):
    """Wszystkie ułożenia wszystkich `shapes` (w dowolnej kolejności, z czyszczeniem linii między postawieniami):
    lista [(indeks, x, y), ...]. Bez limitu — plansze z końcówki partii są prawie pełne."""
    out = []

    def rec(g, left, path):
        if not left:
            out.append(path)
            return
        for i in left:
            for y in range(8):
                for x in range(8):
                    if _tray_can_place(g, shapes[i], x, y):
                        rec(_tray_place_and_clear(g, shapes[i], x, y), [j for j in left if j != i],
                            path + [(i, x, y)])

    rec(grid, list(range(len(shapes))), [])
    return out


def completable(grid, shapes):
    """Czy da się ułożyć wszystkie `shapes` (dowolna kolejność). Zatrzymuje się na pierwszym ułożeniu."""
    if not shapes:
        return True
    for perm in permutations(range(len(shapes))):
        if _dfs(grid, [shapes[i] for i in perm]):
            return True
    return False


def _dfs(grid, shapes):
    if not shapes:
        return True
    for y in range(8):
        for x in range(8):
            if _tray_can_place(grid, shapes[0], x, y) and _dfs(_tray_place_and_clear(grid, shapes[0], x, y), shapes[1:]):
                return True
    return False


def play(policy, grid, tray):
    """Polityka gra tackę do końca na kopii planszy; -> (lista ruchów, plansza po tacce, czy ułożono całą)."""
    board, pieces, moves = ps.to_board(grid), ps.to_pieces(tray), []
    while any(pieces):
        legal = bridge.legal_moves(board, pieces)
        if not legal:
            return moves, board.grid, False
        i, x, y = policy.act(bridge.make_game_stub(board, pieces), legal)
        board.place_piece(pieces[i], x, y)
        board.clear_lines(*board.check_full_lines())
        pieces[i] = None
        moves.append((i, x, y))
    return moves, board.grid, True


def ascii_board(grid):
    return ["".join("#" if c else "." for c in row) for row in grid]


def odczyt(R, window, policy, img_path):
    r38, r39 = R[38], R[39]
    exp38 = r38["expected"]
    diff_board39 = [(y, x) for y in range(8) for x in range(8) if r39["board"][y][x] != exp38[y][x]]
    img = np.array(Image.open(img_path).convert("RGB")).astype(int)
    patches = {}
    for c in (5, 6, 7):
        x, y = bridge.cell_center(c, 1)
        p = img[int(y) - 5:int(y) + 6, int(x) - 5:int(x) + 6].reshape(-1, 3).mean(axis=0)
        patches[f"(1,{c})"] = {"rgb": [round(float(v)) for v in p], "is_block": bool(bridge.is_block(p))}
    # plansza prawdziwa przed ruchem 39: expected z n=38 (wiersz 1 po czyszczeniu pusty)
    true39 = [row[:] for row in exp38]
    tray39 = r39["tray"]
    pieces = ps.to_pieces(tray39)

    def pick(grid):
        b = ps.to_board(grid)
        return policy.act(bridge.make_game_stub(b, pieces), bridge.legal_moves(b, pieces))

    def s_fits(grid, mv):
        b = ps.to_board(grid)
        b.place_piece(pieces[mv[0]], mv[1], mv[2])
        b.clear_lines(*b.check_full_lines())
        return bridge.legal_moves(b, [None, None, pieces[2]])

    on_ghost, on_true = pick(r39["board"]), pick(true39)
    return {
        "ok_false_n": [n for n in (38, 39) if R[n].get("ok") is False],
        "roznica_observed_expected": {n: [(y, x) for y in range(8) for x in range(8)
                                          if R[n]["expected"][y][x] != R[n]["observed"][y][x]] for n in (38, 39)},
        "roznica_board39_expected38": diff_board39,
        "lata_039_state": patches,
        "okno_po_ostatnim_ruchu_wiersz1": window["board"][1] if window else None,
        "polityka_na_odczycie_z_banerem": list(on_ghost),
        "polityka_na_planszy_bez_pol": list(on_true),
        "ruch_zalogowany_n39": r39["move"],
        "S_po_ruchu_z_banerem_legalne": len(s_fits(true39, on_ghost)),
        "S_po_ruchu_bez_pol_legalne": len(s_fits(true39, on_true)),
    }


def przeglad_38(R, policy):
    r = R[38]
    shapes = [p.shape for p in ps.to_pieces(r["tray"])]
    seqs = completions(r["board"], shapes)
    firsts = sorted({s[0] for s in seqs})
    chosen = (r["move"]["slot"], r["move"]["x"], r["move"]["y"])
    moves, final, done = play(policy, r["board"], r["tray"])
    return {
        "ukladalna": bool(seqs),
        "liczba_ulozen": len(seqs),
        "liczba_pierwszych_ruchow": len(firsts),
        "wybrany_ruch_jest_w_ulozeniu": chosen in firsts,
        "przyklad": [list(m) for m in seqs[0]] if seqs else None,
        "polityka_na_prawdziwej_planszy": {"ruchy": [list(m) for m in moves], "ulozona_w_calosci": done,
                                          "plansza_po": ascii_board(final)},
    }


def retro(R, policy):
    shapes38 = [p.shape for p in ps.to_pieces(R[38]["tray"])]
    out = {}
    for n in (35, 36, 37):
        r = R[n]
        pieces = ps.to_pieces(r["tray"])
        stub = bridge.make_game_stub(ps.to_board(r["board"]), pieces)
        final = policies._tray_complete_search(
            ps.to_board(r["board"]), tuple(pieces), stub.combo, stub.combo_counter,
            policy._ntuple_leaf, policy._path_key, policy._gain_weight)
        chosen_slot = r["move"]["slot"]
        actual = (chosen_slot, r["move"]["x"], r["move"]["y"])
        rows = []
        for st in final:
            rows.append({"score": float(st["score"]), "first": list(st["first_action"]),
                         "plansza": st["board"].grid, "tacka38_ukladalna": completable(st["board"].grid, shapes38)})
        best = rows[0] if rows else None  # posortowane malejąco: wybór polityki
        ok_rows = [x for x in rows if x["tacka38_ukladalna"]]
        out[str(n)] = {
            "wybrany_ruch": list(actual),
            "stanow_koncowych": len(rows),
            "z_ukladalna_tacka38": len(ok_rows),
            "ocena_wybranego_stanu": best["score"] if best else None,
            "plansza_wybranego_ma_ukladalna_tacke38": best["tacka38_ukladalna"] if best else None,
            "najlepszy_alternatywny": ({"score": ok_rows[0]["score"], "pierwszy_ruch": ok_rows[0]["first"],
                                        "miejsce_w_rankingu": rows.index(ok_rows[0]) + 1,
                                        "plansza_po_tacce": ascii_board(ok_rows[0]["plansza"])} if ok_rows else None),
        }
    return out


def czestosc(R, policy, losowan):
    per = max(1, -(-losowan // 4))
    out, total, bad_after_first, bad_start = {}, 0, 0, 0
    for n in (35, 36, 37, 38):
        grid = R[n]["board"]
        gen = Generator(seed=f"przeglad-p7:{n}")
        cnt = {"losowan": 0, "nieukladalne_na_planszy": 0, "nieulozone_po_pierwszym_ruchu": 0}
        for _ in range(per):
            tray = gen.next_pieces()
            shapes = [p.shape for p in tray]
            cnt["losowan"] += 1
            if not completable(grid, shapes):
                cnt["nieukladalne_na_planszy"] += 1
            b = ps.to_board(grid)
            legal = bridge.legal_moves(b, tray)
            if not legal:
                cnt["nieulozone_po_pierwszym_ruchu"] += 1
                continue
            i, x, y = policy.act(bridge.make_game_stub(b, list(tray)), legal)
            b.place_piece(tray[i], x, y)
            b.clear_lines(*b.check_full_lines())
            rest = [tray[j].shape for j in range(3) if j != i]
            if not completable(b.grid, rest):
                cnt["nieulozone_po_pierwszym_ruchu"] += 1
        out[str(n)] = cnt
        total += cnt["losowan"]
        bad_start += cnt["nieukladalne_na_planszy"]
        bad_after_first += cnt["nieulozone_po_pierwszym_ruchu"]
    out["razem"] = {"losowan": total, "nieukladalne_na_planszy": bad_start,
                    "nieulozone_po_pierwszym_ruchu": bad_after_first,
                    "odsetek_nieukladalnych": bad_start / total,
                    "odsetek_nieulozonych_po_pierwszym_ruchu": bad_after_first / total}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog")
    ap.add_argument("--losowan", type=int, default=1200)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    rows = rows_of(os.path.join(args.katalog, "chunk9_moves.jsonl"))
    R = {r["n"]: r for r in rows if "move" in r and r.get("n", 0) >= 34}
    ends = [r for r in rows if r.get("koniec_partii")]
    window = next((r for r in rows if r.get("okno") == "brak_ruchu_ponowny_odczyt"), None)
    policy, err = ps.build_policy(ps.default_policy_spec())
    if policy is None:
        print("polityka niedostępna:", err, file=sys.stderr)
        return 1
    res = {
        "odczyt": odczyt(R, window, policy, os.path.join(args.katalog, "kawalek_9", "039_state.png")),
        "przeglad_n38": przeglad_38(R, policy),
        "wsteczny_n35_37": retro(R, policy),
        "czestosc": czestosc(R, policy, args.losowan),
        "wynik_koncowy": ends[-1].get("wynik_koncowy") if ends else None,
    }
    text = json.dumps(res, indent=1, ensure_ascii=False, default=list)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
