"""
Most do oryginału (#18): zrzut ekranu -> stan -> ruch -> przeciągnięcie -> potwierdzenie.

Działa na emulatorze w Actions (ekran 320x640). Stan planszy i trzech klocków
czytany z pikseli, ruch wybiera polityka zachłanna z benchmarku, wykonanie przez
`adb shell input motionevent`. Każdy ruch trafia do bridge-out/moves.jsonl
(stan, trójka, ruch, wynik — wejście z #9 dla dopasowania symulatora).

Geometria zmierzona na zrzutach z sondy #14 — aktualizacja gry może ją zepsuć.
"""
import io
import json
import os
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw

from board import Board
from pieces import Piece
from policies import GreedyPolicy

OUT = "bridge-out"
SCREEN = (320, 640)
BOARD_X, BOARD_Y, CELL = 17, 136, 35.6
TRAY_Y0, TRAY_Y1, TRAY_CELL = 440, 585, 17.8
SCORE_BOX = (60, 70, 260, 130)
EMPTY = np.array([25, 28, 58])
BACKGROUND = np.array([49, 65, 123])
HOLD_Y = 620  # tu trzymamy palec, żeby zmierzyć, gdzie gra rysuje podniesiony klocek


def adb(*args):
    return subprocess.run(["adb", *args], check=True, capture_output=True).stdout


def touch(action, x, y):
    adb("shell", "input", "motionevent", action, str(int(x)), str(int(y)))


def screenshot():
    img = np.asarray(Image.open(io.BytesIO(adb("exec-out", "screencap", "-p"))).convert("RGB"))
    assert img.shape[1::-1] == SCREEN, f"ekran {img.shape[1::-1]}, oczekiwano {SCREEN}"
    return img.astype(int)


def not_background(img):
    return np.abs(img - BACKGROUND).sum(axis=2) > 60


def read_board(img):
    grid = [[0] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            x, y = cell_center(c, r)
            patch = img[int(y) - 5:int(y) + 6, int(x) - 5:int(x) + 6].reshape(-1, 3).mean(axis=0)
            grid[r][c] = int(np.abs(patch - EMPTY).sum() > 60)
    return grid


def read_tray(img):
    """Trzy sloty: (kształt, środek w px) albo None, gdy slot pusty."""
    mask = not_background(img[TRAY_Y0:TRAY_Y1])
    slots = []
    for s in range(3):
        x0, x1 = s * SCREEN[0] // 3, (s + 1) * SCREEN[0] // 3
        ys, xs = np.nonzero(mask[:, x0:x1])
        if len(xs) < 20:
            slots.append(None)
            continue
        top, left = ys.min() + TRAY_Y0, xs.min() + x0
        h = max(1, round((ys.max() - ys.min() + 1) / TRAY_CELL))
        w = max(1, round((xs.max() - xs.min() + 1) / TRAY_CELL))
        step_y = (ys.max() - ys.min() + 1) / h
        step_x = (xs.max() - xs.min() + 1) / w
        shape = [[int(not_background(img[int(top + (i + .5) * step_y):int(top + (i + .5) * step_y) + 1,
                                         int(left + (j + .5) * step_x):int(left + (j + .5) * step_x) + 1])[0, 0])
                  for j in range(w)] for i in range(h)]
        center = (left + (xs.max() - xs.min()) / 2, top + (ys.max() - ys.min()) / 2)
        slots.append((shape, center))
    return slots


def read_score(img):
    """OCR wyniku przez tesseract; None, gdy się nie da."""
    x0, y0, x1, y1 = SCORE_BOX
    crop = img[y0:y1, x0:x1]
    bw = np.where(crop.min(axis=2) > 170, 0, 255).astype(np.uint8)
    path = os.path.join(OUT, "_score.png")
    Image.fromarray(bw).resize(((x1 - x0) * 3, (y1 - y0) * 3)).save(path)
    try:
        text = subprocess.run(["tesseract", path, "stdout", "--psm", "7", "-c",
                               "tessedit_char_whitelist=0123456789"],
                              capture_output=True, text=True).stdout.strip()
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def cell_center(c, r):
    return BOARD_X + (c + .5) * CELL, BOARD_Y + (r + .5) * CELL


def legal_moves(board, pieces):
    return [(i, x, y) for i, p in enumerate(pieces) if p is not None
            for y in range(8) for x in range(8) if board.can_place_piece(p, x, y)]


def simulate(board, piece, x, y):
    after = board.copy()
    after.place_piece(piece, x, y)
    after.clear_lines(*after.check_full_lines())
    return after.grid


def drag(before, slot_center, x, y):
    """Podnosi klocek, mierzy, gdzie gra go rysuje względem palca, i upuszcza na (x, y)."""
    sx, sy = slot_center
    touch("DOWN", sx, sy)
    for k in range(1, 6):
        touch("MOVE", sx, sy + (HOLD_Y - sy) * k / 5)
    time.sleep(0.3)
    held = screenshot()
    lifted = ((np.abs(held - before).sum(axis=2) > 60) & not_background(held)
              & (np.abs(held - EMPTY).sum(axis=2) > 60))
    ys, xs = np.nonzero(lifted)
    if len(xs) == 0:
        touch("UP", sx, HOLD_Y)
        return None, held
    # Lewy górny róg podniesionego klocka względem palca, w px.
    off_x, off_y = xs.min() - sx, ys.min() - HOLD_Y
    tx, ty = cell_center(x, y)
    fx, fy = tx - CELL / 2 - off_x, ty - CELL / 2 - off_y
    for k in range(1, 6):
        touch("MOVE", sx + (fx - sx) * k / 5, HOLD_Y + (fy - HOLD_Y) * k / 5)
    time.sleep(0.2)
    touch("UP", fx, fy)
    return {"lifted_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
            "offset": [float(off_x), float(off_y)], "finger": [float(fx), float(fy)]}, held


def annotate(img, grid, path):
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for r in range(8):
        for c in range(8):
            x, y = cell_center(c, r)
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(0, 255, 0) if grid[r][c] else (255, 0, 255))
    im.save(path)


def main(max_moves):
    os.makedirs(OUT, exist_ok=True)
    policy = GreedyPolicy()
    log = open(os.path.join(OUT, "moves.jsonl"), "w")
    img = screenshot()
    ok_streak = best_streak = 0
    for n in range(max_moves):
        grid, slots, score = read_board(img), read_tray(img), read_score(img)
        annotate(img, grid, os.path.join(OUT, f"{n:03d}_state.png"))
        board = Board()
        board.grid = [row[:] for row in grid]
        pieces = [Piece(s[0], f"slot{i}", -1) if s else None for i, s in enumerate(slots)]
        moves = legal_moves(board, pieces)
        entry = {"n": n, "board": grid, "tray": [s[0] if s else None for s in slots], "score": score}
        if not moves:
            entry["end"] = "brak legalnego ruchu wg odczytu"
            log.write(json.dumps(entry) + "\n")
            break
        game = SimpleNamespace(board=board, pieces=pieces, combo=0)
        i, x, y = policy.act(game, moves)
        expected = simulate(board, pieces[i], x, y)
        info, held = drag(img, slots[i][1], x, y)
        Image.fromarray(held.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_held.png"))
        time.sleep(1.5)
        img = screenshot()
        observed = read_board(img)
        ok = observed == expected
        ok_streak = ok_streak + 1 if ok else 0
        best_streak = max(best_streak, ok_streak)
        entry.update(move={"slot": i, "x": x, "y": y}, drag=info, expected=expected, observed=observed, ok=ok)
        log.write(json.dumps(entry) + "\n")
        log.flush()
        print(f"ruch {n}: slot {i} -> ({x},{y}) wynik {score} {'OK' if ok else 'ROZBIEŻNOŚĆ'}", flush=True)
    annotate(img, read_board(img), os.path.join(OUT, "final.png"))
    print(f"najdłuższa seria zgodnych ruchów: {best_streak}")
    return best_streak


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
