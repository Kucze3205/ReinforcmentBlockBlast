"""
Most do oryginału (#18): zrzut ekranu -> stan -> ruch -> przeciągnięcie -> potwierdzenie.

Działa na emulatorze w Actions (ekran 320x640). Stan planszy i trzech klocków
czytany z pikseli, ruch wybiera polityka z benchmarku (domyślnie zachłanna,
wybór przez argv[2]/`BRIDGE_POLICY`, #95), wykonanie przez
`adb shell input motionevent`. Każdy ruch trafia do pliku w `bridge-out/` wybranego przez
`next_moves_path` — `moves.jsonl` przy pierwszym wywołaniu w katalogu, `moves.1.jsonl`,
`moves.2.jsonl`, ... przy kolejnych, żeby jedno wywołanie nigdy nie nadpisało pliku
poprzedniego (#198; dokładne polecenie kopiowania dla verifiera: `docs/most-zapis-ruchow.md`).
Wpis (stan, trójka, ruch, wynik — wejście z #9 dla dopasowania symulatora); wpis
`koniec_partii` niesie też nazwę zrzutu ekranu końca partii (zapisanego przed stuknięciem
"Play") i listę wszystkich odczytów wyniku aż do ich ustabilizowania (#198).

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

from benchmark import build_policy
from board import Board
from pieces import Piece
from scoring import COMBO_COUNTER_BASE

OUT = "bridge-out"
PACKAGE = "com.block.juggle"
SCREEN = (320, 640)
BOARD_X, BOARD_Y, CELL = 17, 136, 35.6
TRAY_Y0, TRAY_Y1, TRAY_CELL = 440, 585, 16
SCORE_BOX = (60, 70, 260, 130)
GAME_OVER_SCORE_BOX = (60, 312, 260, 368)  # wynik na ekranie fioletowym "Can you Top that?" (#169)
GAME_OVER_SCORE_BOX_BLUE = (60, 268, 260, 318)  # wynik na ekranie niebieskim "Your Best is Next" (#173):
# cyfry "20345" na chunk15_after_back.png leżą w wierszach 273-312, wyżej niż na wariancie fioletowym
# (321-361) — GAME_OVER_SCORE_BOX go nie łapie wcale.
GAME_OVER_PURPLE_FRAC = 0.5  # próg dla is_game_over_screen: tło ma 0.92-0.96, reszta ekranów <=0.065
FRAMES = 3
DRAG_GAIN = 1.5  # zmierzone: klocek przesuwa się 1,5 px na 1 px palca
LIFT = 80.6  # środek podniesionego klocka jest tyle px nad środkiem klocka na tacce
AD_CLOSE = (285, 34)  # X reklamy międzyplanszowej, zmierzony na bridge/runs/0d96333/121_end.png (#129)
AD_DARK_FRAC = 0.85  # 121_end.png: 0.95 czarnych pikseli; 120_state.png: 0.0; ekran główny po zabiciu procesu: 0.62
SETTINGS_DARK_FRAC = (0.44, 0.85)  # przedział pikseli ciemniejszych niż 100 (patrz is_settings_screen)
HOME_STATUS_BAR_ROWS = 24  # wysokość paska stanu Androida sprawdzana przez is_home_screen (#169)
HOME_STATUS_BAR_WHITE = 200  # próg jasności kanału uznawanego za piksel paska stanu
HOME_STATUS_BAR_FRAC = 0.02  # próg odsetka: ekran domowy ma 0.076-0.077, gra zawsze 0.0
BRIGHT_AD_MIN_COLORS = 20000  # liczba unikalnych kolorów RGB, patrz is_bright_ad_screen
STATIC_AD_GRAY_TOL = 10  # patrz is_static_ad_screen
STATIC_AD_GRAY_FRAC = 0.98  # próg: reklama statyczna 1.0, następny najwyższy zrzut z bridge/runs/* 0.964
GAME_OVER_BLUE_FRAC = 0.8  # próg wariantu niebieskiego is_game_over_screen: 0.921 na chunk15_after_back.png,
# następny najwyższy zrzut z bridge/runs/* (klocek niebieski na zwykłej planszy) 0.662
RESTART_TRIES = 3
RESTART_WAIT = 20
PLAY_BUTTON = (160, 456)  # przycisk "Play" na obu wariantach ekranu końca partii, zmierzony przez verifiera (#173)
# Dialog wyjścia „Are you sure you want to leave?" (#150/#163): punkty i kolory zmierzone na
# bridge/runs/495cd91/loop2_after_no.png i after_back4.png. Tło dialogu (90,130,230), przycisk
# „No" (8,154,214), przycisk „Yes" (41,170,25) — trójka nie występuje razem na modalu Ustawień
# ani na prawdziwej planszy z tego samego przebiegu.
EXIT_DIALOG_BG = ((160, 300), (90, 130, 230))
EXIT_DIALOG_NO = ((97, 360), (8, 154, 214))
EXIT_DIALOG_YES = ((225, 360), (41, 170, 25))
EXIT_DIALOG_TOL = 20
PROGRESS_SAFEGUARD_TRIES = 6  # K wpisów okienkowych z rzędu bez wykonanego ruchu, #163


def adb(*args):
    return subprocess.run(["adb", *args], check=True, capture_output=True).stdout


def touch(action, x, y):
    adb("shell", "input", "motionevent", action, str(int(x)), str(int(y)))


def screenshot():
    img = np.asarray(Image.open(io.BytesIO(adb("exec-out", "screencap", "-p"))).convert("RGB"))
    assert img.shape[1::-1] == SCREEN, f"ekran {img.shape[1::-1]}, oczekiwano {SCREEN}"
    return img.astype(int)


def in_game():
    return PACKAGE in adb("shell", "dumpsys", "window").decode(errors="replace").split("mCurrentFocus", 1)[-1][:200]


def is_ad_screen(img):
    """Reklama międzyplanszowa: prawie cały ekran czarny (#129).

    `bridge/runs/0d96333/121_end.png` (reklama) ma 0,95 pikseli ciemniejszych niż próg;
    `120_state.png` (zwykła plansza) ma 0,0; ekran główny po zabiciu procesu
    (`bridge/runs/1bd38fa/111_state.png`) ma 0,62 — próg 0,85 łapie tylko reklamę.
    """
    return (img.max(axis=-1) < 30).mean() > AD_DARK_FRAC


def _pixel_close(img, point, color, tol=EXIT_DIALOG_TOL):
    x, y = point
    return bool((np.abs(img[y, x].astype(int) - np.asarray(color)) <= tol).all())


def is_exit_dialog_screen(img):
    """Natywny dialog wyjścia z gry „Are you sure you want to leave?" (#150/#163): otwiera go
    „wstecz" naciśnięte na prawdziwej planszy (bez modalu Ustawień), a `is_settings_screen`
    (próg ciemności) go z tym modalem myli, bo oba przyciemniają tło podobnym stopniem.

    Rozpoznanie po kolorach w stałych punktach zamiast progu jasności: tło dialogu i przyciski
    „No"/„Yes" mają barwy, których nie widać ani na modalu Ustawień, ani na prawdziwej planszy
    (zmierzone na `bridge/runs/495cd91/loop2_after_no.png`, `after_back4.png` — dialog;
    `before_retry.png` — Ustawienia; `loop_after_back.png`, `before_retry2.png` — plansza).
    """
    return (_pixel_close(img, *EXIT_DIALOG_BG)
            and _pixel_close(img, *EXIT_DIALOG_NO)
            and _pixel_close(img, *EXIT_DIALOG_YES))


def is_home_screen(img):
    """Ekran główny Androida (launcher) po padzie apki (#129/#169): pasek stanu systemu
    (zegar, ikony wifi/baterii) w górnych `HOME_STATUS_BAR_ROWS` px, którego gra nigdy nie
    pokazuje (pełny ekran bez UI systemu we wszystkich stanach gry — plansza, modal Ustawień,
    dialog wyjścia, reklamy).

    Zmierzone na `bridge/runs/1402cff/chunk2_001_settings_falsepositive_home.png` (i
    `chunk2_final.png`, `bridge/runs/1bd38fa/111_state.png` — ten sam ekran domowy po innym
    padzie, #129): 7,7% pikseli w tym pasie jest niemal białych (>200 w każdym kanale) —
    tekst/ikony paska stanu. Na wszystkich sprawdzonych zrzutach z gry (plansza, Ustawienia,
    dialog wyjścia, reklama ciemna/jasna — ok. 250 klatek z `bridge/runs/{0d96333,44a8ea2,
    495cd91,1402cff,1bd38fa}`) ten odsetek wynosi 0.
    """
    top = img[:HOME_STATUS_BAR_ROWS]
    return bool((top >= HOME_STATUS_BAR_WHITE).all(axis=-1).mean() > HOME_STATUS_BAR_FRAC)


def is_settings_screen(img):
    """Modal Ustawień (ikona (285,34) trafiona na normalnej planszy zamiast reklamy, #130/#145):
    tło przyciemnione pod białym oknem dialogowym, mniej niż pełnoekranowa reklama.

    `bridge/runs/44a8ea2/p1{a,b,c}_settings.png` (modal otwarty ręcznie w trakcie partii) i
    `p2e_stuck_settings_before.png` (modal, w który trafił most przez pomyłkę `close_ad`) mają
    0,44-0,68 pikseli ciemniejszych niż próg 100; `p1{a,b,c}_before.png`, `p1{a,b,c}_after_back.png`
    i `p2e_stuck_settings_after_back.png` (bez modalu, w tym tuż po „wstecz") mają najwyżej 0,40.
    Górna granica 0,85 wyklucza reklamę międzyplanszową (`0d96333/121_end.png`: 0,96) —
    ciemniejszą niż Ustawienia, bo bez prześwitującej planszy pod spodem.

    Próg samej jasności myli ten modal z dialogiem wyjścia (`bridge/runs/495cd91/loop2_after_no.png`:
    0,77, w przedziale) — dialog wyklucza się jawnie przez `is_exit_dialog_screen` (#163) — i z ciemną
    tapetą ekranu głównego Androida po padzie apki (`chunk2_001_settings_falsepositive_home.png`: 0,44-0,68,
    w przedziale) — wykluczana jawnie przez `is_home_screen` (#169), bo most bił wtedy „wstecz" w launcher
    zamiast wywołać `restart_app`.
    """
    if is_exit_dialog_screen(img) or is_home_screen(img):
        return False
    lo, hi = SETTINGS_DARK_FRAC
    frac = (img.max(axis=-1) < 100).mean()
    return lo < frac < hi


def is_bright_ad_screen(img):
    """Jasna reklama interaktywna (quiz/„Connect Words", #154): za jasna i za ciemna nie jest —
    `is_ad_screen` (próg ciemności) jej nie łapie, a most bez tego odczytuje planszę pod spodem
    jako w pełni zapełnioną i kończy partię błędnym „brak legalnego ruchu" (#145).

    Grafika reklamowa jest fotorealistyczna/gradientowa (dużo odcieni jednego koloru na
    krzywiznach kul, cieniach, gradientach tła), gra ma płaski design z kilkoma stałymi
    kolorami na plansze/UI. Liczba unikalnych kolorów RGB w kadrze rozdziela to bez cienia
    wątpliwości na materiale z `bridge/runs/44a8ea2/`:
    reklamy (`p2_ad_video_before.png`, `p2_ad_video_after_back.png`, `p2_ad_video_after_back2.png`,
    `p2b_ad_before.png`, `p2b_ad_after_back.png`) mają 30 836–68 663 unikalnych kolorów;
    plansza (`p2_after_play.png`, `p2b_after_play.png`, `p1{a,b,c}_before.png`,
    `p1{a,b,c}_after_back.png`) i modal Ustawień (`p1a_settings.png`, `p2e_stuck_settings_before.png`,
    `p2c_real_ad_then_settings_before.png`) mają najwyżej 1155. Próg 20 000 zostawia szeroki margines
    z obu stron (dla porównania ekran główny po zabiciu procesu, `1bd38fa/111_state.png`, ma 13 697).
    """
    flat = img.reshape(-1, 3)
    return len(np.unique(flat, axis=0)) > BRIGHT_AD_MIN_COLORS


def is_game_over_screen(img):
    """Natywny ekran końca partii z przyciskiem Play, dwa warianty (#169, #173): most
    rozpoznawał brak ruchu poprawnie ("brak legalnego ruchu wg odczytu"), ale przez
    przypadek (tło czytane jako plansza pełna), bez odróżnienia od reklamy/Ustawień
    i bez odczytu wyniku końcowego partii — verifier zaczynał nową partię ręcznym stuknięciem.

    Wariant fioletowy „Can you Top that?"/„Beat Your Best Again!": tło to fioletowo-purpurowy
    gradient bez wyjątku, kanał B > R > G z wyraźnym marginesem na każdym pikselu tła
    (tekst/przycisk to osobne, małe obszary). Zmierzone na dwóch niezależnych przebiegach z
    różnym wynikiem i różnym tekstem nagłówka: `bridge/runs/1402cff/
    chunk7_010_gameover_screen.png` („Can you Top that?", wynik 8532) i `bridge/runs/44a8ea2/
    p2_ad_video_closed.png`, `p2_after_tap_score.png` („Can you Top that?"), `p2b_ad_closed_x.png`
    („Beat Your Best Again!") — 0,92-0,96 pikseli spełnia warunek. Na pozostałych ok. 250 zrzutach
    z `bridge/runs/{0d96333,44a8ea2,495cd91,1402cff,1bd38fa}` (plansza, Ustawienia, dialog wyjścia,
    reklamy, ekran domowy) najwyżej 0,065 — próg 0,5 zostawia duży margines z obu stron.

    Wariant niebieski „Your Best is Next" (#173): ten sam test fioletu daje 0,0 na
    `bridge/runs/c1819ed/chunk15_after_back.png` (wynik 20345) — inny gradient tła, kanał
    B > G > R zamiast B > R > G. Zmierzone na tym samym zrzucie: 0,921 pikseli spełnia
    warunek B > G > R z marginesem >=20 na obu różnicach; najwyższy odsetek na pozostałym
    materiale z `bridge/runs/*` (klocki niebieskiej skórki na zwykłej planszy,
    `bridge/runs/1bd38fa/071_aim.png` i podobne) to 0,662 — próg 0,8 zostawia margines.
    """
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    purple = (b > r) & (r > g) & (b - r >= 15) & (r - g >= 15)
    if purple.mean() > GAME_OVER_PURPLE_FRAC:
        return True
    blue = (b > g) & (g > r) & (b - g >= 20) & (g - r >= 20)
    return blue.mean() > GAME_OVER_BLUE_FRAC


def game_over_score_box(img):
    """Który z dwóch warianty końca partii jest na ekranie decyduje, gdzie leży wynik (#173):
    fioletowy ma cyfry niżej (`GAME_OVER_SCORE_BOX`) niż niebieski (`GAME_OVER_SCORE_BOX_BLUE`)."""
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    purple = (b > r) & (r > g) & (b - r >= 15) & (r - g >= 15)
    if purple.mean() > GAME_OVER_PURPLE_FRAC:
        return GAME_OVER_SCORE_BOX
    return GAME_OVER_SCORE_BOX_BLUE


def is_static_ad_screen(img):
    """Reklama statyczna tekstowa (biało-czarna, np. BlackRock, #173): `is_ad_screen` (próg
    ciemności) i `is_bright_ad_screen` (liczba kolorów, myli ją z fotorealistyczną reklamą
    jasną) obie jej nie łapią — most kończył kawałek fałszywym „brak legalnego ruchu wg
    odczytu" (`bridge/runs/c1819ed/chunk15_unknown.png`, 317 unikalnych kolorów, 0,26
    pikseli ciemniejszych niż próg, 0,73 niemal białych).

    Ta reklama jest w praktyce w skali szarości — każdy piksel ma kanały R/G/B w rozpiętości
    poniżej `STATIC_AD_GRAY_TOL`: 100% pikseli na `chunk15_unknown.png`. Żaden inny sprawdzony
    zrzut z `bridge/runs/*` (ok. 770 klatek — plansza, tacka, Ustawienia, dialog wyjścia,
    reklama ciemna/jasna, oba warianty końca partii, ekran domowy) nie przekracza 0,964
    (`bridge/runs/0d96333/121_state.png`, `121_end.png` — reklama ciemna, już łapana przez
    `is_ad_screen`) — próg 0,98 zostawia margines z obu stron i wyklucza zwykłą planszę
    z niebieską skórką (`bridge/runs/c1819ed/chunk15_after_play2.png`: 0,917).
    """
    gray = ((img.max(axis=-1) - img.min(axis=-1)) < STATIC_AD_GRAY_TOL).mean()
    return gray > STATIC_AD_GRAY_FRAC


def board_and_tray_empty(grid, slots):
    """Plansza bez klocków i pusta tacka razem to odczyt podejrzany, nie koniec partii:

    taki stan nie zdarza się w normalnej grze (tacka zawsze niesie klocki, dopóki gra
    trwa), więc zwykle znaczy, że most patrzy na nieznane okno (np. reklamę), nie na
    planszę bez legalnego ruchu (#129).
    """
    return not any(any(row) for row in grid) and all(s is None for s in slots)


def close_ad(tries=3):
    """Zamyka reklamę międzyplanszową znanym X; True, gdy ekran przestał być reklamą."""
    for _ in range(tries):
        touch("DOWN", *AD_CLOSE)
        touch("UP", *AD_CLOSE)
        time.sleep(2)
        if not is_ad_screen(screenshot()):
            return True
    return False


def press_back():
    """KEYCODE_BACK: zamyka modal Ustawień bez ruszania punktu (285,34) reklamy (#150)."""
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)


def close_exit_dialog():
    """Zamyka dialog wyjścia stuknięciem w „No" (#163): `press_back` go nie zamyka — to
    natywny dialog Androida, nie modal Ustawień w webview gry."""
    (x, y), _ = EXIT_DIALOG_NO
    touch("DOWN", x, y)
    touch("UP", x, y)
    time.sleep(2)


def tap_play():
    """Stuka przycisk "Play" na ekranie końca partii (oba warianty, #173): punkt zmierzony
    przez verifiera na żywo, skuteczny dwa razy z rzędu (`chunk9_after_play.png`,
    `chunk15_after_play2.png`)."""
    x, y = PLAY_BUTTON
    touch("DOWN", x, y)
    touch("UP", x, y)
    time.sleep(2)


def restart_app(tries=RESTART_TRIES, wait=RESTART_WAIT):
    """Podnosi zabitą apkę zwykłym startem — bez instalacji i bez ToS, z lokalnego
    autozapisu (#129: logcat 1bd38fa, `app died, no saved state`). True, gdy wróciła."""
    for attempt in range(1, tries + 1):
        print(f"restart {attempt}/{tries}: {PACKAGE}", flush=True)
        adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(wait)
        if in_game():
            return True
    return False


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
    """Czeka, aż dwa kolejne odczyty będą identyczne: czyszczenie linii i licznik wyniku są animowane."""
    prev = None
    for _ in range(tries):
        img, grid, tray = settled_state()
        key = json.dumps([grid, [s[0] if s else None for s in tray]])
        if key == prev:
            break
        prev = key
    return img, grid, tray


def is_block(img):
    """Kolor klocka: nasycony i jasny (próg oryginalny) ALBO wyraźnie zielony (#169).

    Ciemnozielony klocek (`bridge/runs/1402cff/chunk9_stuck_low_saturation_green.png`:
    RGB (74,142,66), (74,146,66), (41,97,41)) ma rozpiętość kanałów 56-80 i szczyt 97-146 —
    poniżej progu oryginalnego (rozpiętość>=100, szczyt>=150) — więc `read_board`/`read_tray`
    czytały pełną tackę jako pustą (kawałki 9-11 z #164, bezpiecznik `petla_bez_postepu`).

    Zwykłe poluzowanie progu nie działa: tło planszy innych skórek leży w tym samym paśmie
    rozpiętości/jasności (np. bordowe tło `bridge/runs/0d96333/120_state.png`: (132,61,74),
    rozpiętość 71, szczyt 132 — 5-8 jednostek od najsłabszego zielonego klocka; różowe tło
    tacki tamże: (255,166,181), rozpiętość 89, szczyt 255 — też w paśmie). Zmierzone tu
    poluzowanie (rozpiętość>=76, szczyt>=140, dopasowane do najsłabszego zielonego) już nie
    łapie tych den, ale każde dalsze poluzowanie (np. rozpiętość>=40, szczyt>=100, jak próbował
    verifier) zaczyna łapać różowe tło tacki — zgodnie z ostrzeżeniem z issue #169: zgadywanie
    ogólnej reguły "znajdź próg" psuje inne skórki.

    Zamiast przesuwać próg, drugi warunek rozpoznaje ten klocek po dominacji zielonego kanału
    (G wyraźnie ponad R i B), której żadne sprawdzone tło nie ma — tła mają dominujący R lub B
    (bordowe, różowe, tan z tacki, brąz planszy z tego samego zielonego motywu:
    `chunk9_stuck_low_saturation_green.png` samo tło planszy to (74,61,58), R dominujące).
    Sprawdzone na wszystkich zrzutach z `bridge/runs/{0d96333,44a8ea2,495cd91,1402cff,1bd38fa}`
    (ok. 250 klatek): żadne realne tło planszy/tacki nie przechodzi obu warunków jednocześnie
    z zachowanym poprzednim odczytem `read_board`/`read_tray` (zweryfikowane 1:1 z zapisanym
    stanem `bridge/runs/0d96333/moves.jsonl` na 25 klatkach).
    """
    mx, mn = img.max(axis=-1), img.min(axis=-1)
    saturated_bright = (mx - mn >= 100) & (mx >= 150)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    dark_green = (g > r) & (g > b) & (g - r >= 40) & (g - b >= 40) & (g >= 90)
    return saturated_bright | dark_green


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


def read_score(img, box=SCORE_BOX):
    """OCR wyniku przez tesseract; None, gdy się nie da.

    `box` domyślnie to HUD w trakcie partii (`SCORE_BOX`); ekran końca partii ma wynik
    w innym miejscu (`GAME_OVER_SCORE_BOX`, #169)."""
    x0, y0, x1, y1 = box
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


def simulate(board, piece, x, y):
    after = board.copy()
    after.place_piece(piece, x, y)
    after.clear_lines(*after.check_full_lines())
    return after.grid


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


def resolve_policy_spec(argv, env):
    """Wiersz poleceń ma pierwszeństwo nad `BRIDGE_POLICY`; domyślnie `greedy` (#95)."""
    if len(argv) > 2:
        return argv[2]
    return env.get("BRIDGE_POLICY", "greedy")


def policy_spec_source(argv, env):
    """Skąd wzięła się nazwa polityki wypisanej przez `resolve_policy_spec` (#103)."""
    if len(argv) > 2:
        return "argv"
    if "BRIDGE_POLICY" in env:
        return "BRIDGE_POLICY"
    return "domyślna"


def run_id(env):
    """Identyfikator przebiegu do `policy.reset` — Actions daje `GITHUB_RUN_ID`,
    lokalnie brak, więc `local` (#103: bez tego losowanie `LookaheadPolicy` nie jest
    odtwarzalne)."""
    return env.get("BRIDGE_RUN_ID") or env.get("GITHUB_RUN_ID") or "local"


def next_moves_path(out_dir):
    """Numeruje plik ruchów tak, że kolejne wywołanie `bridge.py` nigdy nie nadpisze
    poprzedniego (#198): most przy każdym starcie dostawał `moves.jsonl` w trybie `"w"`,
    a gdy verifier nie zdążył skopiować pliku przed kolejnym wywołaniem, trajektoria
    przepadała bez śladu (sesja cb91077, `chunk3_moves.jsonl` z #191). Pierwsze wywołanie
    w danym katalogu dostaje `moves.jsonl`, kolejne `moves.1.jsonl`, `moves.2.jsonl`, ...
    — verifier kopiuje/przenosi plik o najwyższym numerze po każdym wywołaniu (patrz
    `docs/most-zapis-ruchow.md`)."""
    n = 0
    while True:
        path = os.path.join(out_dir, "moves.jsonl" if n == 0 else f"moves.{n}.jsonl")
        if not os.path.exists(path):
            return path
        n += 1


def stable_score(img, box, tries=6):
    """Czyta wynik końca partii, aż dwa kolejne odczyty się zgodzą (limit `tries`, #198):
    licznik bywa jeszcze animowany tuż po wykryciu ekranu końca partii, więc pierwszy
    odczyt bywa błędny (kawałek 12 z #190, `bridge/runs/cb91077/pomiar.json`) i prowadził
    do przedwczesnego stuknięcia "Play" z niecelnym wynikiem w logu. Pierwszy odczyt bierze
    ze zrzutu już zrobionego przez wywołującego (`img`); kolejne robią nowy zrzut. Zwraca
    ostatni odczyt i listę wszystkich odczytów (do logu, żeby niestabilność było widać post
    factum)."""
    reads = [read_score(img, box)]
    while len(reads) < tries and (len(reads) < 2 or reads[-1] != reads[-2]):
        reads.append(read_score(screenshot(), box))
    return reads[-1], reads


def make_game_stub(board, pieces, combo=0):
    """Atrapa gry podawana `policy.act` — jedna wersja dla `bridge.main` i testów (#95, #103).

    Niesie tylko pola, po które sięgają polityki z benchmarku (`combo_counter`
    doszło w #95, gdy jego brak wywalił się dopiero na żywym emulatorze)."""
    return SimpleNamespace(board=board, pieces=pieces, combo=combo, combo_counter=COMBO_COUNTER_BASE)


def main(max_moves, policy_spec="greedy", policy_source="domyślna"):
    os.makedirs(OUT, exist_ok=True)
    policy = build_policy(policy_spec, {"torch_seed": 0})
    print(f"polityka: {policy.name} (źródło: {policy_source})", flush=True)
    if hasattr(policy, "reset"):
        seed = run_id(os.environ)
        policy.reset(seed)
        print(f"reset(seed={seed!r})", flush=True)
    moves_path = next_moves_path(OUT)
    print(f"log ruchów: {moves_path}", flush=True)
    log = open(moves_path, "x")
    img, grid, slots = settled_state()
    ok_streak = best_streak = 0
    n = 0
    window_streak = 0
    game_number = 1

    def windowed_entry(okno):
        """Wpis okienkowy bez ruchu: liczy się do bezpiecznika postępu (#163), a po
        osiągnięciu `PROGRESS_SAFEGUARD_TRIES` z rzędu kończy partię zamiast kręcić się
        bez końca (materiał #159: >130 wpisów `ustawienia_wstecz`/`reklama_interstitial`
        na stałym `n`, bo stary licznik zerował się na każdej nieokienkowej klatce)."""
        nonlocal window_streak
        window_streak += 1
        entry = {"n": n, "policy": policy.name, "board": grid,
                 "tray": [s[0] if s else None for s in slots], "score": score, "okno": okno}
        if window_streak >= PROGRESS_SAFEGUARD_TRIES:
            entry["end"] = "okno: petla_bez_postepu"
        log.write(json.dumps(entry) + "\n")
        log.flush()
        print(f"okno: {okno}" + (f", {entry['end']}" if "end" in entry else ""), flush=True)
        return entry

    while n < max_moves:
        score = read_score(img)
        Image.fromarray(img.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_state.png"))
        annotate(img, grid, os.path.join(OUT, f"{n:03d}_read.png"))
        if is_exit_dialog_screen(img):
            close_exit_dialog()
            entry = windowed_entry("dialog_wyjscia")
            if "end" in entry:
                break
            img, grid, slots = stable_state()
            continue
        if is_settings_screen(img):
            press_back()
            entry = windowed_entry("ustawienia_wstecz")
            if "end" in entry:
                break
            img, grid, slots = stable_state()
            continue
        if is_static_ad_screen(img):
            press_back()
            entry = windowed_entry("reklama_statyczna")
            if "end" in entry:
                break
            img, grid, slots = stable_state()
            continue
        if is_bright_ad_screen(img):
            entry = {"n": n, "policy": policy.name, "board": grid,
                     "tray": [s[0] if s else None for s in slots], "score": score,
                     "end": "okno: reklama_jasna"}
            log.write(json.dumps(entry) + "\n")
            print(entry["end"], flush=True)
            break
        if is_game_over_screen(img):
            end_path = os.path.join(OUT, f"{n:03d}_end.png")
            Image.fromarray(img.astype(np.uint8)).save(end_path)
            final_score, score_reads = stable_score(img, game_over_score_box(img))
            game_number += 1
            window_streak += 1
            entry = {"n": n, "policy": policy.name, "board": grid,
                     "tray": [s[0] if s else None for s in slots], "score": score,
                     "koniec_partii": True, "wynik_koncowy": final_score,
                     "wynik_koncowy_odczyty": score_reads,
                     "zrzut_konca": os.path.basename(end_path), "nowa_partia": game_number}
            if window_streak >= PROGRESS_SAFEGUARD_TRIES:
                entry["end"] = "okno: petla_bez_postepu"
            log.write(json.dumps(entry) + "\n")
            log.flush()
            print(f"koniec_partii, wynik {final_score}, nowa_partia {game_number}"
                  + (f", {entry['end']}" if "end" in entry else ""), flush=True)
            if "end" in entry:
                break
            tap_play()
            img, grid, slots = stable_state()
            continue
        board = Board()
        board.grid = [row[:] for row in grid]
        pieces = [Piece(s[0], f"slot{i}", -1) if s else None for i, s in enumerate(slots)]
        moves = legal_moves(board, pieces)
        entry = {"n": n, "policy": policy.name, "board": grid,
                 "tray": [s[0] if s else None for s in slots], "score": score}
        if not in_game():
            if restart_app():
                entry["restart"] = "apka wznowiona po awarii (monkey, bez instalacji/ToS)"
                log.write(json.dumps(entry) + "\n")
                log.flush()
                print("restart udany, kontynuacja partii", flush=True)
                img, grid, slots = stable_state()
                continue
            entry["end"] = "gra nie jest na pierwszym planie"
            log.write(json.dumps(entry) + "\n")
            print(entry["end"], flush=True)
            break
        if not moves and (is_ad_screen(img) or board_and_tray_empty(grid, slots)):
            if not is_ad_screen(img):
                # `board_and_tray_empty` na przejściowej klatce prawdziwej planszy: nie jest
                # reklamą, więc stuknięcie w AD_CLOSE trafiłoby w ikonę Ustawień (#163) —
                # tylko odczyt ponownie, bez dotykania ekranu.
                entry = windowed_entry("plansza_pusta_przejsciowo")
                if "end" in entry:
                    break
                img, grid, slots = stable_state()
                continue
            if close_ad():
                entry = windowed_entry("reklama_interstitial zamknięta")
                if "end" in entry:
                    break
                img, grid, slots = stable_state()
                continue
            entry["end"] = "okno: reklama_interstitial"
            log.write(json.dumps(entry) + "\n")
            print(entry["end"], flush=True)
            break
        if not moves:
            entry["end"] = "brak legalnego ruchu wg odczytu"
            log.write(json.dumps(entry) + "\n")
            break
        window_streak = 0
        game = make_game_stub(board, pieces)
        t0 = time.perf_counter()
        i, x, y = policy.act(game, moves)
        decision_ms = (time.perf_counter() - t0) * 1000
        expected = simulate(board, pieces[i], x, y)
        info, aim = drag(slots[i][1], pieces[i], x, y)
        Image.fromarray(aim.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_aim.png"))
        img, observed, slots = stable_state()
        ok = observed == expected
        grid = observed
        ok_streak = ok_streak + 1 if ok else 0
        best_streak = max(best_streak, ok_streak)
        entry.update(move={"slot": i, "x": x, "y": y}, drag=info, expected=expected, observed=observed, ok=ok,
                      decision_ms=round(decision_ms, 2))
        log.write(json.dumps(entry) + "\n")
        log.flush()
        print(f"ruch {n}: slot {i} -> ({x},{y}) wynik {score} {'OK' if ok else 'ROZBIEŻNOŚĆ'}", flush=True)
        n += 1
    annotate(img, grid, os.path.join(OUT, "final.png"))
    print(f"najdłuższa seria zgodnych ruchów: {best_streak}")
    return best_streak


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30,
         resolve_policy_spec(sys.argv, os.environ),
         policy_spec_source(sys.argv, os.environ))
