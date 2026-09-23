"""
Most do oryginału (#18): zrzut ekranu -> stan -> ruch -> przeciągnięcie -> potwierdzenie.

Działa na emulatorze w Actions (ekran 320x640). Stan planszy i trzech klocków
czytany z pikseli, ruch wybiera polityka zachłanna z benchmarku, wykonanie przez
`adb shell input motionevent`. Każdy ruch trafia do bridge-out/moves.jsonl
(stan, trójka, ruch, wynik — wejście z #9 dla dopasowania symulatora).

Most weryfikuje symulator dwiema ścieżkami naraz (#30): plansza po ruchu musi
zgadzać się z przewidywaniem, a przyrost wyniku — z tym, co naliczy `Game`.
Rozbieżność punktowa idzie do logu, a licznik rozbieżności do podsumowania;
regułę „pojedyncza do logu, systematyczna odpala rekalibrację" niesie #20.

Geometria zmierzona na zrzutach z sondy #14 — aktualizacja gry może ją zepsuć.
"""
import io
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

from game import Game, advance
from pieces import Piece, plausible
from policies import GreedyPolicy

OUT = "bridge-out"
PACKAGE = "com.block.juggle"
SCREEN = (320, 640)
BOARD_X, BOARD_Y, CELL = 17, 136, 35.6
TRAY_Y0, TRAY_Y1, TRAY_CELL = 440, 585, 16
SCORE_BOX = (60, 70, 260, 130)
FRAMES = 3
SHOTS = 20  # zrzuty tylko z początku biegu: długi przebieg zrobiłby setki MB artefaktu
BG_GREEN = 80  # kanał zielony tła planszy; ekran końca partii jest fioletowy i ma ~17
REPLAY = (160, 461)  # przycisk ▶ na ekranie „Can you Top that?"
KILL_AT = int(os.environ.get("KILL_AT", "0"))  # celowe zabicie gry po tym ruchu; 0 = nigdy (#32)
DRAG_GAIN = 1.5  # zmierzone: klocek przesuwa się 1,5 px na 1 px palca
LIFT = 80.6  # środek podniesionego klocka jest tyle px nad środkiem klocka na tacce


def adb(*args):
    return subprocess.run(["adb", *args], check=True, capture_output=True).stdout


def touch(action, x, y):
    adb("shell", "input", "motionevent", action, str(int(x)), str(int(y)))


def screenshot():
    img = np.asarray(Image.open(io.BytesIO(adb("exec-out", "screencap", "-p"))).convert("RGB"))
    assert img.shape[1::-1] == SCREEN, f"ekran {img.shape[1::-1]}, oczekiwano {SCREEN}"
    return img.astype(int)


def game_over(img):
    """Ekran końca partii („Can you Top that?") zamiast planszy.

    Gra zostaje na pierwszym planie, więc `in_game()` tego nie widzi, a tacki nie ma
    — bez tego most kończył przebieg na przegranej, marnując resztę budżetu ruchów.
    Rozpoznanie po tle: plansza jest niebieska, ekran końca fioletowy.
    """
    return img[0:40].reshape(-1, 3).mean(axis=0)[1] < BG_GREEN - 30


def next_game(wait=6, tries=3):
    """Czeka na ekran końca partii i zaczyna następną. None, gdy się nie udało.

    Partia kończy się dwojako: ekranem „Can you Top that?" albo naszym odczytem
    „nie ma legalnego ruchu", który wyprzedza ekran o kilka sekund. Oba prowadzą
    tutaj, bo oba znaczą to samo — i oba kończyły przebieg przed czasem, zanim
    most nauczył się grać dalej.
    """
    for _ in range(wait):
        if game_over(stable_state()[0]):
            return restart_game(tries)
        time.sleep(3)
    return None


def restart_game(tries=3):
    """Klika ▶ i czeka na czytelną planszę nowej partii. None, gdy nie wróciła."""
    for _ in range(tries):
        adb("shell", "input", "tap", str(REPLAY[0]), str(REPLAY[1]))
        time.sleep(5)
        state = stable_state()
        if not game_over(state[0]) and all(s is None or plausible(s[0]) for s in state[2]):
            return state
    return None


def in_game():
    return PACKAGE in adb("shell", "dumpsys", "window").decode(errors="replace").split("mCurrentFocus", 1)[-1][:200]


def relaunch(tries=3):
    """Podnosi grę po tym, jak system zabił jej proces (#32). None, gdy nie wróciła.

    Gry nie zabija ona sama, tylko aktualizacja GMS, więc proces wraca zwykłym startem.
    Czy wraca też *partia*, rozstrzyga porównanie planszy w `main` — tutaj tylko czekamy
    na czytelny ekran, bo po zimnym starcie gra potrafi wejść w ekran końca partii.
    """
    for _ in range(tries):
        adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(20)
        if not in_game():
            continue
        state = stable_state()
        if game_over(state[0]):
            return restart_game()
        if all(s is None or plausible(s[0]) for s in state[2]):
            return state
    return None


def settled_state():
    """Stan z kilku klatek: animacja tutorialu przesłania pola i tackę tylko chwilowo.

    Pole planszy zajęte, jeśli klocek widać na którejkolwiek klatce (duch podpowiedzi
    nigdy nie przechodzi is_block). Tacka: najczęstszy odczyt.
    """
    frames = []
    for _ in range(FRAMES):
        frames.append(screenshot())
        time.sleep(0.25)
    grids = [read_board(f) for f in frames]
    grid = [[max(g[r][c] for g in grids) for c in range(8)] for r in range(8)]
    trays = [read_tray(f) for f in frames]
    keys = [json.dumps([s[0] if s else None for s in t]) for t in trays]
    tray = trays[max(range(FRAMES), key=keys.count)]
    return frames[-1], grid, tray


def stable_state(tries=6):
    """Czeka, aż dwa kolejne odczyty będą identyczne: plansza, tacka i wynik.

    Wynik wchodzi do warunku, bo licznik w grze **dolicza się animacją** po dużym
    czyszczeniu. Odczyt zrobiony za wcześnie pokazuje stan w połowie naliczania i
    porównanie z symulatorem wypada fałszywie na czerwono — tak wyglądały obie
    rozbieżności z przebiegu 35610307974 (#30).
    """
    prev = None
    for _ in range(tries):
        img, grid, tray = settled_state()
        score = read_score(img)
        key = json.dumps([grid, [s[0] if s else None for s in tray], score])
        if key == prev:
            break
        prev = key
    return img, grid, tray, score


def is_block(img):
    """Kolor klocka: nasycony i jasny. Tło, puste pola, duch podpowiedzi i dłoń tutorialu nie przechodzą."""
    return ((img.max(axis=-1) - img.min(axis=-1)) >= 100) & (img.max(axis=-1) >= 150)


def read_board(img):
    grid = [[0] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            x, y = cell_center(c, r)
            patch = img[int(y) - 5:int(y) + 6, int(x) - 5:int(x) + 6].reshape(-1, 3).mean(axis=0)
            grid[r][c] = int(is_block(patch))
    return grid


def read_tray(img):
    """Trzy sloty: (kształt, środek w px) albo None, gdy slot pusty."""
    mask = is_block(img[TRAY_Y0:TRAY_Y1])
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
        shape = [[int(is_block(img[int(top + (i + .5) * step_y), int(left + (j + .5) * step_x)]))
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
        run = subprocess.run(["tesseract", path, "stdout", "--psm", "7", "-c",
                              "tessedit_char_whitelist=0123456789"], capture_output=True, text=True)
        text = run.stdout.strip()
        if not text:
            print("OCR:", run.stderr.strip()[:200], flush=True)
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def cell_center(c, r):
    return BOARD_X + (c + .5) * CELL, BOARD_Y + (r + .5) * CELL


def legal_moves(board, pieces):
    return [(i, x, y) for i, p in enumerate(pieces) if p is not None
            for y in range(8) for x in range(8) if board.can_place_piece(p, x, y)]


def glide(frm, to, steps=10):
    for k in range(1, steps + 1):
        touch("MOVE", frm[0] + (to[0] - frm[0]) * k / steps, frm[1] + (to[1] - frm[1]) * k / steps)


def drag(slot_center, piece, x, y):
    """Przeciąga klocek ze slotu tak, żeby jego lewy górny róg trafił w pole (x, y).

    Model zmierzony na emulatorze: po podniesieniu środek klocka jest LIFT px nad palcem,
    a potem klocek przesuwa się DRAG_GAIN razy szybciej niż palec.
    Pomiar w trakcie ciągnięcia odpada: nad trafionym celem gra podświetla linie do
    wyczyszczenia w kolorze klocka.
    """
    sx, sy = slot_center
    h, w = len(piece.shape), len(piece.shape[0])
    cx, cy = BOARD_X + (x + w / 2) * CELL, BOARD_Y + (y + h / 2) * CELL
    fx = sx + (cx - sx) / DRAG_GAIN
    fy = sy + (cy - (sy - LIFT)) / DRAG_GAIN
    touch("DOWN", sx, sy)
    glide((sx, sy), (fx, fy))
    time.sleep(0.5)  # klocek dogania palec z opóźnieniem
    aim = screenshot()
    touch("UP", fx, fy)
    return {"finger": [round(fx, 1), round(fy, 1)]}, aim


def annotate(img, grid, path):
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    for r in range(8):
        for c in range(8):
            x, y = cell_center(c, r)
            d.ellipse([x - 16, y - 16, x - 8, y - 8], fill=(0, 255, 0) if grid[r][c] else (255, 0, 255))
    im.save(path)


def main(max_moves):
    os.makedirs(OUT, exist_ok=True)
    policy = GreedyPolicy()
    log = open(os.path.join(OUT, "moves.jsonl"), "w")
    game = Game()  # niesie combo i licznik wygaśnięcia między ruchami; planszę i tackę bierze z ekranu
    img, grid, slots, score = stable_state()
    refs = [grid]  # plansze, po których poznamy, że partia przeżyła zabicie procesu (#32)
    ok_streak = best_streak = score_bad = score_blind = games = revivals = 0
    for n in range(max_moves):
        if n < SHOTS:
            Image.fromarray(img.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_state.png"))
            annotate(img, grid, os.path.join(OUT, f"{n:03d}_read.png"))
        shapes = [s[0] if s else None for s in slots]
        entry = {"n": n, "partia": games, "board": grid, "tray": shapes, "score": score}
        if not in_game():
            entry["end"] = "gra nie jest na pierwszym planie"
        elif game_over(img):
            entry["end"] = "koniec partii"
        elif any(sh is not None and not plausible(sh) for sh in shapes):
            entry["end"] = "odczyt tacki niewiarygodny"
        game.board.grid = [row[:] for row in grid]
        game.pieces = [Piece(sh, f"slot{k}", -1) if sh else None for k, sh in enumerate(shapes)]
        moves = legal_moves(game.board, game.pieces)
        if not moves and "end" not in entry:
            entry["end"] = "brak legalnego ruchu wg odczytu"
        if "end" in entry:
            if entry["end"] == "gra nie jest na pierwszym planie":
                # Jedyny koniec, po którym pytamy, czy przeżyła *partia*: proces zabija
                # aktualizacja GMS, nie przegrana. Plansza zgodna z którymkolwiek stanem
                # sprzed śmierci znaczy, że gra ją odtworzyła — a więc łańcuch 1M z #9
                # przeżywa awarię, zamiast zaczynać od zera.
                fresh = relaunch()
                entry["wznowienie"] = ("gra nie wróciła" if fresh is None
                                       else "partia przeżyła" if fresh[1] in refs
                                       else "partia przepadła")
                revivals += fresh is not None
            elif entry["end"] in ("koniec partii", "brak legalnego ruchu wg odczytu"):
                fresh = next_game()
            else:
                fresh = None
            print(json.dumps(entry), file=log)
            log.flush()
            print(f"{entry['end']} (partia {games}, ruch {n})"
                  + (f" -> {entry['wznowienie']}" if "wznowienie" in entry else ""), flush=True)
            if fresh is None:
                break
            img, grid, slots, score = fresh
            if entry.get("wznowienie") != "partia przeżyła":
                game = Game()  # nowa partia zaczyna z zerowym combo
                games += 1
            refs = [grid]
            continue
        i, x, y = policy.act(game, moves)
        piece = game.pieces[i]
        gain, expected = advance(game, grid, shapes, i, x, y)
        info, aim = drag(slots[i][1], piece, x, y)
        if n < SHOTS:
            Image.fromarray(aim.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_aim.png"))
        img, observed, slots, after = stable_state()
        ok = observed == expected
        grid = observed
        ok_streak = ok_streak + 1 if ok else 0
        best_streak = max(best_streak, ok_streak)
        # Wynik w Block Blaście nigdy nie maleje, więc spadek jest błędem OCR, nie
        # rozbieżnością punktacji. Bez tego filtra przebieg 35609533868 zgłosił przyrost -82.
        if score is None or after is None or after < score:
            score_ok = None
            score_blind += 1
        else:
            score_ok = after - score == gain
            score_bad += not score_ok
        entry.update(move={"slot": i, "x": x, "y": y}, drag=info, expected=expected, observed=observed,
                     ok=ok, combo=game.combo, score_after=after, gain_expected=gain, score_ok=score_ok)
        print(json.dumps(entry), file=log)
        log.flush()
        mark = {True: "OK", False: "ROZBIEŻNOŚĆ", None: "?"}
        print(f"ruch {n}: slot {i} -> ({x},{y}) wynik {score} "
              f"plansza {mark[ok]} punkty {mark[score_ok]} (+{gain})", flush=True)
        score = after
        refs = [entry["board"], expected, observed]
        if n + 1 == KILL_AT:
            # Czekanie na aktualizację GMS to loteria (2 przebiegi z 6). Zabicie procesu
            # ręcznie daje tę samą śmierć — „app died, no saved state" — na zawołanie,
            # więc wznowienie da się zmierzyć jednym przebiegiem zamiast serią.
            adb("shell", "am", "force-stop", PACKAGE)
            print(f"celowe zabicie gry po ruchu {n} (#32)", flush=True)
    annotate(img, grid, os.path.join(OUT, "final.png"))
    print(f"rozegranych partii: {games + 1}")
    print(f"wskrzeszeń gry po zabiciu procesu: {revivals}")
    print(f"najdłuższa seria zgodnych ruchów: {best_streak}")
    print(f"rozbieżności punktowe: {score_bad}, ruchy bez odczytu wyniku: {score_blind}")
    return best_streak


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
