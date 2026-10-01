#!/usr/bin/env python3
"""Porównanie odczytu mostu z obrazem (#305). Nic nie naprawia; czyta zrzuty `NNN_state.png` i log ruchów.

    python3 tools/porownanie_odczytu.py KATALOG_KAWALKA PLIK_RUCHOW.jsonl [--od N] [--do N] [--out PLIK.json]

Dla każdego stanu: plansza i tacka z `bridge.read_board`/`bridge.read_tray` na zrzucie vs. odczyt niezależny:
plansza — komórka zajęta, gdy jej łata różni się od najczęstszego koloru pustej komórki (L1 > BOARD_DIST);
tacka — komórka kształtu zajęta, gdy punkt różni się od mediany paska tacki (jak maska `read_tray`, ale
także przy próbkowaniu kształtu, czego `read_tray` nie robi). Różnice to pola i sloty, w których `bridge`
odczytuje inaczej niż obraz.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import bridge
import most_tacki_ukladalne as mtu
from board import Board, tray_playable
from pieces import Piece

BOARD_DIST = 60


def load(path):
    return np.array(Image.open(path).convert("RGB")).astype(int)


def board_independent(img):
    patches = {}
    for r in range(8):
        for c in range(8):
            x, y = bridge.cell_center(c, r)
            patches[r, c] = img[int(y) - 5:int(y) + 6, int(x) - 5:int(x) + 6].reshape(-1, 3).mean(axis=0)
    keys = [tuple((p // 16).astype(int)) for p in patches.values()]
    mode = max(set(keys), key=keys.count)
    empty = np.mean([p for p, k in zip(patches.values(), keys) if k == mode], axis=0)
    return [[int(np.abs(patches[r, c] - empty).sum() > BOARD_DIST) for c in range(8)] for r in range(8)]


def tray_independent(img):
    strip = img[bridge.TRAY_Y0:bridge.TRAY_Y1]
    bg = np.median(strip.reshape(-1, 3), axis=0)
    mask = bridge.is_block(strip) & (np.abs(strip - bg).sum(axis=-1) > bridge.TRAY_BG_DIST)
    out = []
    for s in range(3):
        x0, x1 = s * bridge.SCREEN[0] // 3, (s + 1) * bridge.SCREEN[0] // 3
        ys, xs = np.nonzero(bridge.tray_slot_mask(mask[:, x0:x1]))
        if len(xs) < 20:
            out.append(None)
            continue
        top, left = ys.min(), xs.min()
        h = max(1, round((ys.max() - ys.min() + 1) / bridge.TRAY_CELL))
        w = max(1, round((xs.max() - xs.min() + 1) / bridge.TRAY_CELL))
        sy, sx = (ys.max() - ys.min() + 1) / h, (xs.max() - xs.min() + 1) / w
        out.append([[int(mask[int(top + (i + .5) * sy), int(x0 + left + (j + .5) * sx)]) for j in range(w)]
                    for i in range(h)])
    return out


def compare_state(img, logged_board=None, logged_tray=None):
    bridge_board = bridge.read_board(img)
    bridge_tray = [None if s is None else s[0] for s in bridge.read_tray(img)]
    own_board, own_tray = board_independent(img), tray_independent(img)
    diff_cells = [[r, c] for r in range(8) for c in range(8) if bridge_board[r][c] != own_board[r][c]]
    diff_slots = [i for i in range(3) if bridge_tray[i] != own_tray[i]]
    out = dict(pola_planszy_rozne=diff_cells, sloty_tacki_rozne=diff_slots,
               tacka_mostu=bridge_tray, tacka_obrazu=own_tray)
    if logged_board is not None:
        out["log_zgodny_z_odczytem_mostu"] = logged_board == bridge_board and logged_tray == bridge_tray
    return out


def deal_outcome(img, policy_spec):
    """Rozdanie z obrazu (prawdziwa plansza i tacka): czy istnieje ułożenie całej trójki i czy polityka ją przeżywa.

    Polityka gra kolejno trzy ruchy na planszy z obrazu, z czyszczeniem linii; `przezyla` = położyła wszystkie trzy."""
    grid, tray = board_independent(img), [mtu.trim(s) if s else None for s in tray_independent(img)]
    shapes = [s for s in tray if s]
    out = dict(plansza=grid, tacka=tray, ukladalna=tray_playable(grid, shapes) if len(shapes) == 3 else None)
    policy = bridge.build_policy(policy_spec, {"torch_seed": 0})
    if hasattr(policy, "reset"):
        policy.reset(0)
    board = Board()
    board.grid = [row[:] for row in grid]
    pieces = [Piece(s, f"slot{i}", -1) if s else None for i, s in enumerate(tray)]
    played = []
    while any(pieces):
        moves = bridge.legal_moves(board, pieces)
        if not moves:
            break
        i, x, y = policy.act(bridge.make_game_stub(board, pieces), moves)
        played.append(dict(slot=i, x=x, y=y))
        board.grid = bridge.simulate(board, pieces[i], x, y)
        pieces[i] = None
    out.update(ruchy_polityki=played, przezyla=not any(pieces), plansza_na_koncu=board.grid)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("katalog")
    ap.add_argument("ruchy")
    ap.add_argument("--od", type=int, default=0)
    ap.add_argument("--do", type=int, default=10 ** 9)
    ap.add_argument("--out", default=None)
    ap.add_argument("--rozdanie", type=int, default=None,
                    help="N: rozdanie ze zrzutu NNN_state.png (prawdziwa plansza i tacka) zamiast porównania zakresu")
    ap.add_argument("--polityka", default=None, help="spec polityki dla --rozdanie (domyślnie: bench/record.json)")
    args = ap.parse_args(argv)
    if args.rozdanie is not None:
        import przegrana_serii
        res = deal_outcome(load(os.path.join(args.katalog, f"{args.rozdanie:03d}_state.png")),
                           args.polityka or przegrana_serii.default_policy_spec())
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=1)
                f.write("\n")
        print("tacka:", res["tacka"], "ukladalna:", res["ukladalna"], "przezyla:", res["przezyla"],
              "ruchy:", res["ruchy_polityki"])
        return 0
    logged = {}
    with open(args.ruchy, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "move" in r:
                logged[r["n"]] = r
    result = {}
    for name in sorted(os.listdir(args.katalog)):
        if not name.endswith("_state.png"):
            continue
        n = int(name[:3])
        if not args.od <= n <= args.do:
            continue
        r = logged.get(n)
        c = compare_state(load(os.path.join(args.katalog, name)), r["board"] if r else None,
                          r["tray"] if r else None)
        result[n] = c
        print(n, "pola:", len(c["pola_planszy_rozne"]), "sloty:", c["sloty_tacki_rozne"],
              "log=most:", c.get("log_zgodny_z_odczytem_mostu"))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
