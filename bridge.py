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
GAME_ACTIVITY = "org.cocos2dx.javascript.AppActivity"  # reklama ma własną aktywność w TYM SAMYM pakiecie
AD_CLOSE = (285, 34)  # X na pełnoekranowej reklamie (com.hs.adx.hella.activity.FullScreenActivity)
RATING_CLOSE = (275, 192)  # X w oknie oceny gry, rysowanym nad ekranem końca partii (#35)
SCREEN = (320, 640)
BOARD_X, BOARD_Y, CELL = 17, 136, 35.6
TRAY_Y0, TRAY_Y1, TRAY_CELL = 440, 585, 16
SCORE_BOX = (60, 70, 260, 130)
CONTRAST = 45  # o tyle kolor musi odstawać od tła tej klatki, żeby był klockiem (#34)
FRAMES = 3
SHOTS = 20  # zrzuty tylko z początku biegu: długi przebieg zrobiłby setki MB artefaktu
STUCK = 3   # tyle wpisów bez ruchu z rzędu kończy przebieg: most, który nie gra, nie żyje (#32)
REPLAY = (160, 461)  # przycisk ▶ — wspólny dla obu wariantów ekranu końca, więc i wyróżnik (#32)
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
    """Ekran końca partii, rozpoznany po białym ▶ — czyli po przycisku, w który i tak klikamy.

    Gra zostaje na pierwszym planie, więc `in_game()` tego nie widzi, a tacki nie ma.
    Rozpoznanie po tle nie działa, bo ekran ma **dwa warianty**: fioletowy „Can you Top
    that?" (zielony kanał 17) i niebieski „Your Best is Next" (64), a plansza ma 80 —
    drugiego wariantu nie da się oddzielić od planszy kolorem tła i to on zatrzymywał
    przebiegi 35842812364 i 35852299298. Przycisk jest wspólny i rozdziela je z zapasem:
    w grze to miejsce ma rozrzut kanałów ~80 przy jasności ~90, na ekranie końca 5 przy 232.

    Trzeci warunek — że przycisk odstaje od tła paska — dokłada motyw brązowy (#34):
    jego pusty pasek ma rozrzut 33 przy jasności 173, więc mieści się pod progiem
    ▶ o 3 i 7 jednostek. Motyw jaśniejszy przekroczy oba i każda klatka w grze będzie
    „ekranem końca". W grze to miejsce **jest** tłem paska, na ekranie końca nim nie jest.
    """
    p = img[REPLAY[1], REPLAY[0] - 5:REPLAY[0] + 6].mean(axis=0)
    return (p.max() - p.min() < 30 and p.mean() > 180
            and bool(stands_out(p, bg_color(img[TRAY_Y0:TRAY_Y1]))))


def next_game(wait=6, tries=3):
    """Czeka na ekran końca partii i zaczyna następną. None, gdy się nie udało.

    Partia kończy się dwojako: ekranem „Can you Top that?" albo naszym odczytem
    „nie ma legalnego ruchu", który wyprzedza ekran o kilka sekund. Oba prowadzą
    tutaj, bo oba znaczą to samo — i oba kończyły przebieg przed czasem, zanim
    most nauczył się grać dalej.
    """
    for _ in range(wait):
        if not in_game() and not recover():  # reklama po przegranej przesłania ekran końca
            return None
        if game_over(stable_state()[0]):
            return restart_game(tries)
        time.sleep(3)
    return None


def readable_tray(shapes):
    """Tacka czyta się jak klocki: jest co czytać i **każdy** odczyt mógłby być klockiem.

    Oba warunki są zmierzone, nie założone. Pusta tacka przechodziła „wszystkie
    wiarygodne" pusto, więc martwy ekran uchodził za zdrową partię i most stał na nim
    2 h 50 min (przebieg 35852299298, #32); w 384 ruchach przebiegu 35887593719 pusta
    tacka nie wypadła ani razu, więc odrzucenie jej nic nie kosztuje. „Którykolwiek
    wiarygodny" przepuszczał z kolei okno oceny gry, bo czyta się ono jako trzy bloby,
    z których dwa mieszczą się w 5x5 (#35).
    """
    read = [s for s in shapes if s]
    return bool(read) and all(plausible(s) for s in read)


def playable(state):
    """Ekran, na którym da się zagrać: nie ekran końca i czytelna tacka."""
    return not game_over(state[0]) and readable_tray([s[0] if s else None for s in state[2]])


def close_rating(tries=3):
    """Zdejmuje okno oceny gry i wraca do gry. None, gdy nie zeszło.

    „Rating — give us 5 stars" gra rysuje **nad** ekranem końca partii, we własnej
    aktywności planszy, więc `in_game()` go nie widzi, a przygaszony pod nim ▶ (rozrzut
    3 przy jasności 67) każe `game_over()` słusznie zwrócić False. Zostaje jeden objaw:
    tacka czyta się jako bloby okna zamiast klocków — i to on sprowadza nas tutaj. Tak
    stanął przebieg 35887593719 po 384 ruchach (#35).

    Trzecie okno nad planszą i trzecia współrzędna na sztywno: reklama (#32), motyw
    (#34), ocena. Decyzja z #35: łatamy po jednym oknie. Reguła ogólna „znajdź ✕"
    daje się napisać — ✕ reklamy i ✕ oceny to białe bloby o wypełnieniu 0,41–0,44 —
    ale zębatka ustawień w grze ma 0,31, więc rozdziela je dopiero para strojonych
    progów. Taki próg zawiódł już raz i #34 musiało go usunąć.

    Po zejściu okna ekran jest ekranem końca partii, więc dalej prowadzi ta sama droga
    co po przegranej.
    """
    for _ in range(tries):
        adb("shell", "input", "tap", str(RATING_CLOSE[0]), str(RATING_CLOSE[1]))
        time.sleep(3)
        state = stable_state()
        if playable(state):
            return state
        if game_over(state[0]):
            return restart_game()
    return None


def restart_game(tries=3):
    """Klika ▶ i czeka na czytelną planszę nowej partii. None, gdy nie wróciła."""
    for _ in range(tries):
        adb("shell", "input", "tap", str(REPLAY[0]), str(REPLAY[1]))
        time.sleep(5)
        state = stable_state()
        if playable(state):
            return state
    return None


def current_focus():
    """Okno na wierzchu. Przy zatrzymaniu to ono nazywa sprawcę — grę przesłania coś,
    co ma własny pakiet, a bez tej nazwy zostaje zgadywanie (#32)."""
    out = adb("shell", "dumpsys", "window").decode(errors="replace")
    return out.split("mCurrentFocus", 1)[-1][:200].splitlines()[0].strip() if "mCurrentFocus" in out else ""


def in_game():
    """Na wierzchu jest **plansza**, a nie cokolwiek z pakietu gry.

    Sprawdzanie samego pakietu przepuszczało pełnoekranową reklamę, bo ta ma własną
    aktywność w pakiecie gry — i to ona, nie awaria, zatrzymała przebieg 35876461162
    po 135 ruchach, zgłoszona jako „brak legalnego ruchu" (#32).
    """
    return GAME_ACTIVITY in current_focus()


def recover(tries=3):
    """Przywraca planszę: zamyka reklamę albo podnosi zabity proces. True, gdy wróciła.

    Dwie różne przeszkody dają jeden objaw — planszy nie ma — i rozróżnia je nazwa okna
    na wierzchu. Reklamę zamyka X w rogu, a gdy SDK trzyma go gdzie indziej, klawisz
    wstecz; martwy proces wraca zwykłym startem.
    """
    for _ in range(tries):
        if PACKAGE in current_focus():
            adb("shell", "input", "tap", str(AD_CLOSE[0]), str(AD_CLOSE[1]))
            time.sleep(3)
            if not in_game():
                adb("shell", "input", "keyevent", "KEYCODE_BACK")
                time.sleep(3)
        else:
            adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
            time.sleep(20)
        if in_game():
            return True
    return False


def resume_state():
    """Grywalny stan po odzyskaniu planszy: trwająca partia albo nowa po ekranie końca."""
    if not recover():
        return None
    state = stable_state()
    if game_over(state[0]):
        return restart_game()
    return state if playable(state) else None


def settled_state():
    """Stan z kilku klatek: animacja tutorialu przesłania pola i tackę tylko chwilowo.

    Pole planszy zajęte, jeśli klocek widać na którejkolwiek klatce. Tacka: najczęstszy odczyt.

    Cena odczytu niezależnego od motywu (#34): duch podpowiedzi i dłoń tutorialu też
    odstają od tła, więc ruch 0 świeżej instalacji czyta 6 pól za dużo. Ruch 0 i tak
    jest rozbieżny — tutorial wymusza własne postawienie — a `grid` bierze się co ruch
    z ekranu na nowo, więc błąd nie przeżywa jednego ruchu.
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


def bg_color(region):
    """Tło obszaru: jego najczęstszy kolor — puste pole na planszy, tło strony na tacce.

    Czytane z każdej klatki od nowa, bo gra zmienia motyw graficzny **w trakcie partii**.
    Stała nie wystarczy: klocek motywu brązowego ma nasycenie 72, a tło motywu
    niebieskiego 74, więc próg, który przepuszcza pierwszy, przepuszcza i drugie (#34).
    """
    q = (region // 8 * 8).reshape(-1, 3)
    vals, counts = np.unique(q, axis=0, return_counts=True)
    return vals[counts.argmax()]


def stands_out(px, bg):
    """Czy kolor odstaje od tła. Jedyny test „to nie jest tło" w całym odczycie ekranu."""
    d = np.asarray(px) - bg
    return (d * d).sum(axis=-1) >= CONTRAST ** 2


def read_board(img):
    bg = bg_color(img[BOARD_Y:int(BOARD_Y + 8 * CELL), BOARD_X:int(BOARD_X + 8 * CELL)])
    grid = [[0] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            x, y = cell_center(c, r)
            patch = img[int(y) - 5:int(y) + 6, int(x) - 5:int(x) + 6].reshape(-1, 3).mean(axis=0)
            grid[r][c] = int(stands_out(patch, bg))
    return grid


def read_tray(img):
    """Trzy sloty: (kształt, środek w px) albo None, gdy slot pusty."""
    strip = img[TRAY_Y0:TRAY_Y1]
    bg = bg_color(strip)
    mask = stands_out(strip, bg)
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
        shape = [[int(stands_out(img[int(top + (i + .5) * step_y), int(left + (j + .5) * step_x)], bg))
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
    ok_streak = best_streak = score_bad = score_blind = games = revivals = idle = 0
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
        elif not readable_tray(shapes):
            entry["end"] = "odczyt tacki niewiarygodny"
        game.board.grid = [row[:] for row in grid]
        game.pieces = [Piece(sh, f"slot{k}", -1) if sh else None for k, sh in enumerate(shapes)]
        moves = legal_moves(game.board, game.pieces)
        if not moves and "end" not in entry:
            entry["end"] = "brak legalnego ruchu wg odczytu"
        if "end" in entry:
            # Zrzut i nazwa okna na wierzchu — zdjęte PRZED próbą ratunku, bo to ona
            # zaciera sprawcę. Bez nich stanie mostu diagnozuje się kolejnym przebiegiem (#32).
            entry["focus"] = current_focus()
            Image.fromarray(img.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_end.png"))
            if entry["end"] == "gra nie jest na pierwszym planie":
                # Proces zabija aktualizacja GMS, nie przegrana, więc pytamy, czy
                # przeżyła *partia*. Plansza zgodna z którymkolwiek stanem sprzed śmierci
                # znaczy, że gra ją odtworzyła — a więc łańcuch 1M z #9 przeżywa awarię,
                # zamiast zaczynać od zera.
                fresh = resume_state()
                entry["wznowienie"] = ("plansza nie wróciła" if fresh is None
                                       else "partia przeżyła" if fresh[1] in refs
                                       else "partia przepadła")
                revivals += fresh is not None
            elif entry["end"] in ("koniec partii", "brak legalnego ruchu wg odczytu"):
                fresh = next_game()
            else:
                # Odczyt, który grą nie jest, znaczy dziś jedno: coś stoi nad planszą.
                # Werdykt liczony jak po zabiciu procesu, bo pytanie jest to samo —
                # czy pod oknem została ta partia, czy trzeba zerować combo (#35).
                fresh = close_rating()
                entry["wznowienie"] = ("okno nie zeszło" if fresh is None
                                       else "partia przeżyła" if fresh[1] in refs
                                       else "partia przepadła")
                revivals += fresh is not None
            print(json.dumps(entry), file=log)
            log.flush()
            print(f"{entry['end']} (partia {games}, ruch {n}) na oknie {entry['focus']}"
                  + (f" -> {entry['wznowienie']}" if "wznowienie" in entry else ""), flush=True)
            if fresh is None:
                break
            idle += 1
            if idle >= STUCK:
                print(f"{STUCK} wpisy bez ruchu z rzędu — przebieg stoi, kończę", flush=True)
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
        idle = 0
        refs = [entry["board"], expected, observed]
        if n + 1 == KILL_AT:
            # Czekanie na aktualizację GMS to loteria (2 przebiegi z 6). Zabicie procesu
            # ręcznie daje tę samą śmierć — „app died, no saved state" — na zawołanie,
            # więc wznowienie da się zmierzyć jednym przebiegiem zamiast serią.
            adb("shell", "am", "force-stop", PACKAGE)
            print(f"celowe zabicie gry po ruchu {n} (#32)", flush=True)
    annotate(img, grid, os.path.join(OUT, "final.png"))
    print(f"rozegranych partii: {games + 1}")
    print(f"odzyskań planszy (okno nad planszą albo zabity proces): {revivals}")
    print(f"najdłuższa seria zgodnych ruchów: {best_streak}")
    print(f"rozbieżności punktowe: {score_bad}, ruchy bez odczytu wyniku: {score_blind}")
    return best_streak


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
