"""Pomiar #350: czas życia napisu po czyszczeniu linii. Importuje bridge; uruchom z korzenia repo:
python3 bridge/runs/a9fdeb1/napis_czas.py <maks_ruchow> <min_serii>"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, ".")
import bridge as B
from benchmark import build_policy
from board import Board
from pieces import Piece

RUN = "bridge/runs/a9fdeb1"
SPEC = "lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000"
BURST = 6.0
PAUSE = 0.2
JSON = f"{RUN}/napis-czas.json"
TMP = "/tmp/napis"  # wszystkie klatki; do repo trafiają próbki


def merged(a, b):
    return [[max(a[r][c], b[r][c]) for c in range(8)] for r in range(8)]


def analyze(frames, ts, pieces, i, expected, cleared):
    grids = [B.read_board(f) for f in frames]
    trays = [B.read_tray(f) for f in frames]
    last = grids[-1]
    first_eq = next(k for k, g in enumerate(grids) if g == last)  # pierwsza klatka równa ostatniej
    stays = len(grids) - 1  # pierwsza klatka, od której wszystkie następne są równe ostatniej
    while stays > 0 and grids[stays - 1] == last:
        stays -= 1
    st = None
    for k in range(1, len(frames)):
        if B._frame_key(grids[k], trays[k]) == B._frame_key(grids[k - 1], trays[k - 1]):
            st = k
            break
    out = {"t_zniknie_s": ts[first_eq], "t_zniknie_trwale_s": ts[stays], "klatek": len(frames),
           "t_ostatnia_s": ts[-1]}
    roz = [max(B.cell_flatness(f, r, c) for r in B.NAPIS_WIERSZE for c in range(8)) for f in frames]
    out["rozrzut_345"] = roz
    out["max_rozrzut_345"] = max(roz)
    wid = [t for t, v in zip(ts, roz) if v >= B.NAPIS_ROZRZUT]
    out["t_napis_wizualny_s"] = max(wid) if wid else None  # ostatnia klatka z nakładką w wierszach 3-5
    if st is None:
        out["t_stable_s"] = None
        return out
    out["t_stable_s"] = ts[st]
    obs = merged(grids[st], grids[st - 1])
    accepted = B.tray_consumed(pieces, i, trays[st])
    g, duchy = B.drop_banner_ghosts(obs, expected, cleared, accepted)
    g, napis = B.drop_banner_text(frames[st], g, expected, accepted)
    out.update(duchy=[list(p) for p in duchy], napis_pola=[list(p) for p in napis],
               korekta_odpalila=bool(duchy or napis), stable_surowa_eq_ostatnia=obs == last,
               po_korekcji_eq_ostatnia=g == last, po_korekcji_eq_expected=g == expected,
               ostatnia_eq_expected=last == expected)
    return out


def main(max_moves, min_serii):
    os.makedirs(TMP, exist_ok=True)
    policy = build_policy(SPEC, {"torch_seed": 0})
    policy.reset("350")
    res = json.load(open(JSON)) if os.path.exists(JSON) else []
    n = 0
    img, grid, slots = B.stable_state()
    while n < max_moves and sum(1 for r in res if "seria" in r) < min_serii:
        if B.is_game_over_screen(img):
            Image.fromarray(img.astype(np.uint8)).save(f"{RUN}/serie/koniec_{n:03d}.png")
            print("koniec partii", n, flush=True)
            res.append({"zdarzenie": "koniec_partii", "n": n})
            json.dump(res, open(JSON, "w"))
            B.tap_play()
            img, grid, slots = B.stable_state()
            continue
        board = Board()
        board.grid = [r[:] for r in grid]
        pieces = [Piece(s[0], f"slot{i}", -1) if s else None for i, s in enumerate(slots)]
        moves = B.legal_moves(board, pieces)
        if not moves:
            for _ in range(4):
                time.sleep(1)
                img, grid, slots = B.stable_state()
                board.grid = [r[:] for r in grid]
                pieces = [Piece(s[0], f"slot{i}", -1) if s else None for i, s in enumerate(slots)]
                moves = B.legal_moves(board, pieces)
                if moves:
                    break
            if not moves:
                Image.fromarray(img.astype(np.uint8)).save(f"{RUN}/serie/nieznane_{n:03d}.png")
                print("brak ruchu / nieznane okno", n, flush=True)
                res.append({"zdarzenie": "brak_ruchu", "n": n})
                break
        game = B.make_game_stub(board, pieces)
        i, x, y = policy.act(game, moves)
        expected = B.simulate(board, pieces[i], x, y)
        cleared = B.cleared_cells(board, pieces[i], x, y)
        info, aim = B.drag(slots[i][1], pieces[i], x, y)
        t_up = time.perf_counter()
        if cleared:
            frames, ts = [], []
            while time.perf_counter() - t_up <= BURST:
                t_cap = time.perf_counter()
                frames.append(B.screenshot())
                ts.append(round(((t_cap - t_up) + (time.perf_counter() - t_up)) / 2, 3))
                time.sleep(max(0, PAUSE - (time.perf_counter() - t_cap)))
            out = analyze(frames, ts, pieces, i, expected, cleared)
            out.update(n=n, linie=len(cleared), ruch=[i, x, y], t_klatek=ts, seria=len(res))
            d = f"{TMP}/s{len(res):03d}"
            os.makedirs(d, exist_ok=True)
            for k, f in enumerate(frames):
                Image.fromarray(f.astype(np.uint8)).save(f"{d}/{k:02d}.png")
            res.append(out)
            print(len(res), {k: out.get(k) for k in ("t_zniknie_s", "t_stable_s", "korekta_odpalila", "max_rozrzut_345", "linie")}, flush=True)
            json.dump(res, open(JSON, "w"))
        img, grid, slots = B.stable_state()
        n += 1
    json.dump(res, open(JSON, "w"))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
