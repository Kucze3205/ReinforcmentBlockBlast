#!/usr/bin/env python3
"""Wynik partii wg naszej trajektorii (nie licznika apki), tylko dla realnych
ruchów n=0..55 (#130) — od n=56 most czytał okno Ustawień gry (patrz Odkrycia
w .session/report.md), nie prawdziwą planszę, więc te "ruchy" są odrzucone."""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, REPO_ROOT)

from board import Board
from pieces import Piece
from scoring import COMBO_COUNTER_BASE, FULL_CLEAR_BONUS, clear_points, placement_points
from tools.analiza_z6 import playable_types

RUN_DIR = os.path.dirname(os.path.abspath(__file__))
REALNY_LIMIT_N = 55  # ostatni ruch przed wejsciem w okno Ustawien (n=56)


def load_moves(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def recompute_score(entries):
    combo = 0
    combo_counter = COMBO_COUNTER_BASE
    score = 0
    per_move = []
    for e in entries:
        if "move" not in e:
            break
        board = Board()
        board.grid = [row[:] for row in e["board"]]
        tray = e["tray"]
        i = e["move"]["slot"]
        shape = tray[i]
        piece = Piece(shape, f"slot{i}", -1)
        x, y = e["move"]["x"], e["move"]["y"]
        assert board.place_piece(piece, x, y), f"ruch {e['n']}: nielegalne postawienie wg odczytu"

        gained = placement_points(piece)
        rows, cols = board.check_full_lines()
        lines = len(rows) + len(cols)
        remaining = sum(1 for j, s in enumerate(tray) if s is not None and j != i)

        if lines > 0:
            combo += 1
            combo_counter = COMBO_COUNTER_BASE + remaining
            gained += clear_points(combo, lines)
        elif combo_counter <= 1:
            combo = 0
            combo_counter = COMBO_COUNTER_BASE
        else:
            combo_counter -= 1

        board.clear_lines(rows, cols)
        if not any(any(row) for row in board.grid):
            gained += FULL_CLEAR_BONUS

        score += gained
        per_move.append({"n": e["n"], "gained": gained, "score": score, "lines": lines, "combo": combo})
    return score, per_move


def count_full_playable_rounds(entries, n_types=15):
    rounds = 0
    full = 0
    seen_at = set()
    for e in entries:
        if "move" not in e:
            continue
        tray = e["tray"]
        remaining_before = sum(1 for s in tray if s is not None)
        if remaining_before == 3 and e["n"] not in seen_at:
            seen_at.add(e["n"])
            rounds += 1
            playable = playable_types(e["board"])
            if len(playable) == n_types:
                full += 1
    return rounds, full


def main():
    entries = load_moves(os.path.join(RUN_DIR, "moves.jsonl"))
    real_entries = [e for e in entries if e.get("n", 10**9) <= REALNY_LIMIT_N]
    n_moves_with_move = sum(1 for e in real_entries if "move" in e)
    score, per_move = recompute_score(real_entries)
    rounds, full = count_full_playable_rounds(real_entries)

    n_spurious = sum(1 for e in entries if "move" in e and e["n"] > REALNY_LIMIT_N)

    result = {
        "run": os.path.basename(RUN_DIR),
        "postawien": n_moves_with_move,
        "wynik_wg_naszej_trajektorii": score,
        "koniec": "limit_ruchow",
        "rund_lacznie": rounds,
        "rund_z_15_grywalnymi": full,
        "ruchy_odrzucone_okno_ustawien": n_spurious,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    with open(os.path.join(RUN_DIR, "analiza.json"), "w") as f:
        json.dump({**result, "per_move": per_move}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
