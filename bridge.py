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
"Play") i listę wszystkich odczytów wyniku aż do ich ustabilizowania (#198). Ekran głównego
menu apki (`menu_glowne`, #204) — kafelki Adventure/Classic/More Games — most odróżnia od
modalu Ustawień i stuka kafelek „Classic", zamiast „wstecz", żeby wrócić do partii w toku;
`restart_app` robi to samo, gdy start apki po restarcie ląduje w tym menu zamiast w grze.
Zawieszenie planszy (#218) — obserwacja po ruchu identyczna z planszą sprzed ruchu przez
`BOARD_STUCK_TRIES` ruchów z rzędu — kończy kawałek wpisem `okno: plansza_zawieszona` ze
zrzutem, zamiast powtarzać ten sam ruch bez końca (`docs/most-zawieszenie-planszy.md`).

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
TRAY_BG_DIST = 60  # read_tray: piksel bliżej mediany paska (w sumie |ΔRGB|) to tło, nie klocek (#294)
SCORE_BOX = (60, 70, 260, 130)
GAME_OVER_SCORE_BOX = (60, 312, 260, 368)  # wynik na ekranie fioletowym "Can you Top that?" (#169)
GAME_OVER_SCORE_BOX_BLUE = (60, 268, 260, 318)  # wynik na ekranie niebieskim "Your Best is Next" (#173):
# cyfry "20345" na chunk15_after_back.png leżą w wierszach 273-312, wyżej niż na wariancie fioletowym
# (321-361) — GAME_OVER_SCORE_BOX go nie łapie wcale.
DIGIT_TEMPLATES_FILE = "bridge_digits.npz"  # średnie wzorce cyfr HUD z 15 zrzutów 01eb4dd (#290)
DIGIT_INK_TEMPLATES_FILE = "bridge_digits_ink.npz"  # wzorce dla odczytu tło/tusz, budowane przez tools/wzorce_hud.py (#294)
DIGIT_GLYPH_H, DIGIT_GLYPH_W = 36, 30  # rozmiar znormalizowanego glifu we wzorcach
HUD_DIGIT_DARK = 150  # piksel cyfry HUD: max kanału poniżej (cyfry 74,77,90; tło i żółty romb > 200)
HUD_INK_MIN_DIST = 150  # `_hud_ink_unmixed`: suma |ΔRGB| od tła, od której kolor liczy się jako tusz cyfr
HUD_INK_RESID = 0.35  # odrzuć piksel, którego odległość od prostej tło→tusz przekracza tyle długości odcinka
HUD_INK_LOW = 0.55  # rzut na odcinek tło→tusz poniżej tego to tło (blady romb skórki teal ma ok. 0.3-0.5)
HUD_INK_MASK = 0.5  # piksel jest cyfrą, gdy `soft` z `_hud_ink_unmixed` > tyle
DIGIT_MAX_DIST = 0.35  # odrzuć glif, gdy L1 do najlepszego wzorca > tyle masy glifu (zmierzone max 0.16)
DIGIT_MAX_RATIO = 0.95  # odrzuć glif, gdy najlepszy wzorzec prawie remisuje z drugim (zmierzone max 0.91)
GAME_OVER_PURPLE_FRAC = 0.5  # próg dla is_game_over_screen: tło ma 0.92-0.96, reszta ekranów <=0.065
FRAMES = 3
FAST_FRAME_PAUSE = 0.2  # nowa ścieżka (#266): przerwa między klatkami stable_state (stara: 0.25 s x 3 klatki)
IN_GAME_EVERY = 10  # nowa ścieżka (#266): `dumpsys window` co tyle ruchów, gdy ostatni ruch był zgodny
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
MAIN_MENU_TEAL_FRAC = 0.03  # próg dla is_main_menu_screen, patrz docstring
MAIN_MENU_TILE_BOX = (66, 463, 254, 506)  # kafelek „Classic" (x0, y0, x1, y1), patrz CLASSIC_BUTTON
MAIN_MENU_TILE_FRAC = 0.5  # ile kafelka ma być teal: menu 0.85; klocki skórki teal na planszy najwyżej 0.02 (#294)
TROPHY_GOLD_CENTER = 0.25  # is_trophy_overlay_screen: progi, patrz docstring
TROPHY_GOLD_TEXT = 0.1
TROPHY_GEM_PIXELS = 100
CLASSIC_BUTTON = (160, 484)  # środek kafelka "Classic" na menu głównym, zmierzony na
# bridge/runs/4a1796f/chunk4_003_menu_end.png (#204): maska koloru kafelka (teal, patrz
# is_main_menu_screen) daje x 66-253, y 463-505 bez plakietki "Continue!"; bliskie ręcznemu
# tapnięciu verifiera (160,483) z tego samego zrzutu, ale zmierzone z geometrii, nie z oka.
# Dialog wyjścia „Are you sure you want to leave?" (#150/#163): punkty i kolory zmierzone na
# bridge/runs/495cd91/loop2_after_no.png i after_back4.png. Tło dialogu (90,130,230), przycisk
# „No" (8,154,214), przycisk „Yes" (41,170,25) — trójka nie występuje razem na modalu Ustawień
# ani na prawdziwej planszy z tego samego przebiegu.
EXIT_DIALOG_BG = ((160, 300), (90, 130, 230))
EXIT_DIALOG_NO = ((97, 360), (8, 154, 214))
EXIT_DIALOG_YES = ((225, 360), (41, 170, 25))
EXIT_DIALOG_TOL = 20
# K wpisów okienkowych z rzędu bez wykonanego ruchu, #163. 12 (#235): sekwencja 6 okien z
# chunk10 (7e25817) kończyła się grywalną planszą, a pętla z #159 miała setki wpisów.
PROGRESS_SAFEGUARD_TRIES = 12
# #235: tyle `plansza_pusta_przejsciowo` z rzędu → jeden „wstecz" (chunk6: 6 z rzędu na jasnej
# reklamie, którą zamknął jeden „wstecz"; 3 daje szansę zwykłej przejściowej klatce).
EMPTY_BOARD_BACK_TRIES = 3
BOARD_STUCK_TRIES = 3  # K ruchów z rzędu, po których plansza wcale się nie zmienia (#218):
# na materiale #212 (`bridge/runs/1b1763a/chunk{25,26,27}_moves.jsonl`) plansza zamarła na
# 67 ruchów z rzędu (obserwacja == plansza sprzed ruchu, za każdym razem ten sam ruch
# slot1->(3,5)); w całym pozostałym materiale `bridge/runs/*` taka zbieżność zdarzyła się
# co najwyżej raz pod rząd (OCR, nie zawieszenie) i nigdy się nie powtórzyła — próg 3
# odróżnia realne zawieszenie od pojedynczego szumu, tracąc najwyżej 2 ruchy nawigacji.
NO_MOVE_REREAD_TRIES = 4  # ponowne odczyty przy „braku ruchu" bez ekranu końca w serii, nim to uznamy za koniec (#295)
TRAY_DEAL_WAIT = 1.0  # s przerwy przed ponownym odczytem, gdy tacka jest pusta albo widać nakładkę pucharu (#294)
GAME_OVER_SCORE_TRIES = 12  # limit prób `stable_score` na ekranie końca partii (#218): wariant
# fioletowo-złoty z koroną i confetti (`chunk6_025_end.png`, #212) miał serię rosnącą
# [None, 8004, 14226, 20284, 25644, 30179] z malejącymi przyrostami (8004, 6222, 6058, 5360,
# 4535) w 6 próbach domyślnych — limit wyczerpał się o próbę za wcześnie, żeby zobaczyć dwa
# zgodne odczyty z rzędu; margines do 12 daje miejsce na dokończenie animacji tego wariantu.


def adb(*args):
    return subprocess.run(["adb", *args], check=True, capture_output=True).stdout


def tempo_stare():
    """`BRIDGE_TEMPO=stare` włącza dzisiejszą (wolną) ścieżkę ruchu 1:1; bez niej działa nowa (#266,
    `docs/most-tempo.md`). Czytane przy każdym wywołaniu, żeby test mógł przełączać."""
    return os.environ.get("BRIDGE_TEMPO") == "stare"


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


def is_main_menu_screen(img):
    """Ekran głównego menu apki „Block Blast Adventure Master" (#204): most trafiał tu po
    błędnym `press_back` na modalu Ustawień (`is_settings_screen` fałszywie łapał to okno na
    innej, nieutrwalonej klatce w sesji `4a1796f`) i po `restart_app`, który zamiast partii w
    toku odpalał apkę od tego menu.

    Rozpoznanie po kolorze kafelka „Classic" (teal/zielonkawoniebieski, dominacja G i B nad R):
    na `bridge/runs/4a1796f/chunk4_003_menu_end.png` zajmuje 0,038 pikseli kadru. Najbliższy
    fałszywy trop w całym `bridge/runs/*` (ok. 700 zrzutów innych okien — plansza, Ustawienia,
    dialog wyjścia, oba warianty końca partii, ekran domowy, obie reklamy) to 0,021 (reklama
    jasna `44a8ea2/p2b_ad_before.png`/`p2b_ad_after_back.png`, już złapana wcześniej w pętli
    przez `is_bright_ad_screen`) — próg 0,03 zostawia margines i tak wyklucza tę reklamę
    jawnie, na wypadek gdyby coś wywołało tę funkcję poza zwykłą kolejnością pętli.

    Skórka teal planszy (#294, s1: jasne tło, turkusowe klocki; `docs/seria/s1/partia-4/kawalek_1/final.png`,
    `partia-6/kawalek_1/final.png`) ma ten sam kolor klocków, a odsetek teal pikseli całego kadru to tam 0.031
    przy 0.038 na menu — sam odsetek ich nie rozdziela i most stukał „Classic" w pętli. Rozdziela miejsce:
    kafelek „Classic" wypełnia `MAIN_MENU_TILE_BOX` w 0.85, a klocki skórki teal w najwyżej 0.02.
    """
    if is_bright_ad_screen(img):
        return False
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    teal = (g > 150) & (b > 100) & (b < 220) & (r < 80) & (g > r + 80) & (b > r + 60)
    x0, y0, x1, y1 = MAIN_MENU_TILE_BOX
    return bool(teal.mean() > MAIN_MENU_TEAL_FRAC and teal[y0:y1, x0:x1].mean() > MAIN_MENU_TILE_FRAC)


def is_trophy_overlay_screen(img):
    """Nakładka kamienia milowego „Better than N%!" z pucharem (#294, s1 partia 10): na środku planszy złoty puchar
    z czerwonym klejnotem, nad nim złoty napis z procentem. Most czytał puchar jako klocki, a tacka bywała wtedy pusta
    („brak legalnego ruchu wg odczytu"). Znika sama po chwili, więc pętla tylko czeka i czyta ponownie.

    Trzy znaki naraz, bo każdy pojedynczo zdarza się w zwykłej grze (złoty klocek, napis pochwalny): złoto w środku
    planszy (`partia-10/kawalek_1/048_state.png`: 0.47; najwyżej 0.36 na innych zrzutach s1), złoto w pasie napisu
    (0.19; inne najwyżej 0.34) i czerwony klejnot pod nim (ponad 100 px; klocki czerwone tam nie leżą razem ze złotem)."""
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    gold = (r > 200) & (g > 130) & (g < 225) & (b < 100) & (r - b > 120)
    gem = (r > 190) & (g < 90) & (b < 110) & (r - g > 100)
    return bool(gold[240:370, 100:220].mean() > TROPHY_GOLD_CENTER
                and gold[168:198, 190:270].mean() > TROPHY_GOLD_TEXT
                and gem[262:300, 140:180].sum() > TROPHY_GEM_PIXELS)


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


def tray_awaiting_deal(grid, slots):
    """Wszystkie trzy sloty puste przy niepustej planszy (#294): most czyta klatkę po postawieniu ostatniego
    klocka, zanim apka dosypie nową trójkę (s1, partie 7-9: `tray: [null, null, null]`). Pusta tacka przy pustej
    planszy to inny przypadek (`board_and_tray_empty`, nierozpoznane okno)."""
    return all(s is None for s in slots) and any(any(row) for row in grid)


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


def tap_classic():
    """Stuka kafelek „Classic" na menu głównym (#204): kontynuuje partię w toku zamiast
    zaczynać Adventure/More Games — `CLASSIC_BUTTON` zmierzony na zrzucie menu."""
    x, y = CLASSIC_BUTTON
    touch("DOWN", x, y)
    touch("UP", x, y)
    time.sleep(2)


def restart_app(tries=RESTART_TRIES, wait=RESTART_WAIT):
    """Podnosi zabitą apkę zwykłym startem — bez instalacji i bez ToS, z lokalnego
    autozapisu (#129: logcat 1bd38fa, `app died, no saved state`). True, gdy wróciła.

    Start czasem ląduje na menu głównym zamiast w partii w toku (#204, sesja `4a1796f`,
    kawałek 4) — wtedy stuka „Classic" zanim zwróci sukces, żeby wywołujący dostał z powrotem
    planszę, nie menu."""
    for attempt in range(1, tries + 1):
        print(f"restart {attempt}/{tries}: {PACKAGE}", flush=True)
        adb("shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
        time.sleep(wait)
        if in_game():
            if is_main_menu_screen(screenshot()):
                tap_classic()
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


def _frame_key(grid, tray):
    return json.dumps([grid, [s[0] if s else None for s in tray]])


def fast_stable_state(tries=6):
    """Nowa ścieżka (#266): jedna klatka na odczyt zamiast trzech; stop, gdy dwie kolejne klatki
    dają ten sam stan. Wynik: suma pól z obu klatek (jak w settled_state), tacka z ostatniej."""
    prev = None
    for _ in range(tries):
        img = screenshot()
        grid, tray = read_board(img), read_tray(img)
        if prev is not None and _frame_key(grid, tray) == _frame_key(*prev):
            merged = [[max(grid[r][c], prev[0][r][c]) for c in range(8)] for r in range(8)]
            return img, merged, tray
        prev = (grid, tray)
        time.sleep(FAST_FRAME_PAUSE)
    return img, prev[0], prev[1]


def stable_state(tries=6):
    """Czeka, aż dwa kolejne odczyty będą identyczne: czyszczenie linii i licznik wyniku są animowane."""
    if not tempo_stare():
        return fast_stable_state(tries)
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
    """Trzy sloty: (kształt, środek w px) albo None, gdy slot pusty.

    Tło tacki skórki fioletowej (#294, `docs/seria/s1/partia-2/kawalek_2/056_state.png`) to opalizujący błękit
    (148,202,255) z rozpiętością kanałów równą progowi `is_block`, więc 23 896 z 46 400 pikseli paska
    przechodziło jako klocki i wszystkie trzy sloty wychodziły jako kształt 9x7. Piksel bliski medianie paska
    (tło zajmuje ponad połowę paska) nie jest klockiem: odległość L1 od mediany to tam najwyżej 70
    (99. percentyl 28), a klocka 74-154."""
    strip = img[TRAY_Y0:TRAY_Y1]
    bg = np.median(strip.reshape(-1, 3), axis=0)
    mask = is_block(strip) & (np.abs(strip - bg).sum(axis=-1) > TRAY_BG_DIST)
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


_DIGIT_TEMPLATES = {}


def _digit_templates(name=DIGIT_TEMPLATES_FILE):
    if name not in _DIGIT_TEMPLATES:
        with np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), name)) as z:
            _DIGIT_TEMPLATES[name] = {k: z[k].astype(float) / 255 for k in z.files}
    return _DIGIT_TEMPLATES[name]


def _hud_ink_dark(crop):
    """Cyfry ciemne na jasnym tle (skórka oryginalna, #290): miękka maska `soft` (1 = tusz)."""
    return np.clip((200 - crop.max(axis=2)) / 126.0, 0, 1)


def _hud_ink_unmixed(crop):
    """Cyfry dowolnego koloru na tle o jednym kolorze (skórki teal, różowa, domyślna, fioletowa, s1 / #294):
    tło = najczęstszy kolor kadru, tusz = najczęstszy kolor od niego odległy; `soft` to rzut piksela na
    odcinek tło→tusz, z odrzuceniem pikseli leżących daleko od tej prostej (romb, konfetti, cienie).
    None, gdy kadr nie ma drugiego koloru (brak cyfr)."""
    flat = crop.reshape(-1, 3)
    q = (flat // 16).astype(int)
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    order = np.argsort(-counts)
    bg = flat[keys == vals[order[0]]].mean(axis=0)
    ink = None
    for i in order[1:]:
        c = flat[keys == vals[i]].mean(axis=0)
        if np.abs(c - bg).sum() > HUD_INK_MIN_DIST:
            ink = c
            break
    if ink is None:
        return None
    d = ink - bg
    n2 = float((d * d).sum())
    diff = crop - bg
    t = (diff @ d) / n2
    resid = np.linalg.norm(diff - t[..., None] * d, axis=-1)
    return np.clip((t - HUD_INK_LOW) / (1 - HUD_INK_LOW), 0, 1) * (resid < HUD_INK_RESID * np.sqrt(n2))


def _hud_canvases(soft, mask):
    """Glify licznika jako płótna DIGIT_GLYPH_H x DIGIT_GLYPH_W (po kolumnach, skala do stałej wysokości);
    None, gdy podział nie wygląda na cyfry (sklejone, różnej wysokości, za dużo/mało)."""
    cols = mask.any(axis=0)
    runs, start = [], None
    for i, v in enumerate(list(cols) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i))
            start = None
    if not 1 <= len(runs) <= 9:
        return None
    spans = [np.nonzero(mask[:, a:b].any(axis=1))[0] for a, b in runs]
    heights = [ys.max() - ys.min() + 1 for ys in spans]
    if min(heights) < 0.6 * max(heights):
        return None
    canvases = []
    for (a, b), ys in zip(runs, spans):
        if b - a > 1.15 * DIGIT_GLYPH_W or len(ys) < 10:  # sklejone cyfry albo śmieć
            return None
        g = soft[ys.min():ys.max() + 1, a:b]
        new_w = min(DIGIT_GLYPH_W, max(1, round((b - a) * DIGIT_GLYPH_H / g.shape[0])))
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((new_w, DIGIT_GLYPH_H), Image.BILINEAR)
        canvas = np.zeros((DIGIT_GLYPH_H, DIGIT_GLYPH_W))
        off = (DIGIT_GLYPH_W - new_w) // 2
        canvas[:, off:off + new_w] = np.asarray(im) / 255.0
        canvases.append(canvas)
    return canvases


def _hud_match(canvases, templates):
    """Liczba z płócien glifów albo None, gdy którykolwiek glif nie pasuje jednoznacznie do wzorca."""
    text = ""
    for canvas in canvases:
        dist = sorted((float(np.abs(canvas - t).sum()), d) for d, t in templates.items())
        if dist[0][0] > DIGIT_MAX_DIST * canvas.sum() or dist[0][0] > DIGIT_MAX_RATIO * dist[1][0]:
            return None
        text += dist[0][1]
    return int(text)


def read_hud_score(img, box=SCORE_BOX):
    """Licznik HUD dopasowaniem wzorców cyfr; None, gdy glify nie pasują (#290).

    Tesseract mylił cyfry pod żółtym rombem (1512468 czytał jako 1519468), a dwa zgodne odczyty nie
    chronią przed błędem powtarzalnym. Tu: podział na glify po kolumnach, skala do stałej wysokości,
    odległość L1 do średniego wzorca każdej cyfry; odczyt niejednoznaczny albo z dziwnym kształtem
    glifu to None, nie zgadywanie.

    Kolor cyfr zależy od skórki apki (#294: ciemne na jasnym, białe na różowym/granatowym/beżowym,
    turkusowe, niebieskie) — najpierw maska ciemnych cyfr skórki oryginalnej, a gdy ta nie daje odczytu,
    maska z rozdzielenia tło/tusz (`_hud_ink_unmixed`). Zły odczyt jest gorszy niż brak, więc wszystkie
    progi odrzucenia są wspólne."""
    x0, y0, x1, y1 = box
    # uint8, nie int ze `screenshot()`: wzorce `bridge_digits.npz` powstały z tej reprezentacji (200 - uint8 zawija
    # się dla jasnego tła, więc `soft` jest tam 1 w całym glifie); na `int` ten sam zrzut dawał None (#294)
    crop = img[y0:y1, x0:x1].astype(np.uint8)
    soft = _hud_ink_dark(crop)
    canvases = _hud_canvases(soft, crop.max(axis=2) < HUD_DIGIT_DARK)
    value = None if canvases is None else _hud_match(canvases, _digit_templates())
    if value is not None:
        return value
    soft = _hud_ink_unmixed(crop.astype(float))
    if soft is None:
        return None
    canvases = _hud_canvases(soft, soft > HUD_INK_MASK)
    return None if canvases is None else _hud_match(canvases, _digit_templates(DIGIT_INK_TEMPLATES_FILE))


def read_score(img, box=SCORE_BOX):
    """OCR wyniku; None, gdy się nie da.

    HUD w trakcie partii (`SCORE_BOX`) czyta `read_hud_score` (wzorce cyfr, #290); ekran końca
    partii ma wynik w innym miejscu (`GAME_OVER_SCORE_BOX`, #169) i inne kolory — tam tesseract."""
    if box == SCORE_BOX:
        return read_hud_score(img, box)
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
    if tempo_stare():
        touch("DOWN", sx, sy)
        glide((sx, sy), (fx, fy))
    else:
        # #266: DOWN i wszystkie MOVE w jednym wywołaniu `adb shell` (jedno zamiast 11)
        steps = 10
        cmds = [f"input motionevent DOWN {int(sx)} {int(sy)}"]
        for k in range(1, steps + 1):
            cmds.append(f"input motionevent MOVE {int(sx + (fx - sx) * k / steps)} {int(sy + (fy - sy) * k / steps)}")
        adb("shell", "; ".join(cmds))
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


def main(max_moves, policy_spec="greedy", policy_source="domyślna", seria=False):
    """`seria=True` (#283, `tools/partia_serii.py`): ekran końca partii kończy kawałek wpisem
    `end: koniec_partii` i nie stuka „Play” — dla serii to koniec partii."""
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
    board_stuck_streak = 0
    empty_streak = 0
    no_move_streak = 0
    no_move_stan = None
    game_number = 1
    po_ruchu = None  # plansza i reszta tacki po ostatnim ruchu — odczyt ekranu końca gry jest nakładką-śmieciem (#292)

    def write_row(entry):
        entry["t"] = round(time.time(), 3)
        log.write(json.dumps(entry) + "\n")

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
        write_row(entry)
        log.flush()
        print(f"okno: {okno}" + (f", {entry['end']}" if "end" in entry else ""), flush=True)
        return entry

    last_ok = False
    moves_since_in_game = IN_GAME_EVERY
    while n < max_moves:
        t_start = time.perf_counter()
        score = read_score(img)
        Image.fromarray(img.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_state.png"))
        if tempo_stare():
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
        if is_main_menu_screen(img):
            tap_classic()
            entry = windowed_entry("menu_glowne")
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
            # #235: „wstecz" zamknął jasną reklamę w pomiarze #223; wpis liczy się do
            # bezpiecznika, więc stała reklama kończy kawałek w skończonej liczbie kroków.
            press_back()
            entry = windowed_entry("reklama_jasna")
            if "end" in entry:
                break
            img, grid, slots = stable_state()
            continue
        if is_trophy_overlay_screen(img):
            time.sleep(TRAY_DEAL_WAIT)  # nakładka znika sama; nie dotykamy ekranu (#294)
            entry = windowed_entry("nakladka_better_than")
            if "end" in entry:
                break
            img, grid, slots = stable_state()
            continue
        if is_game_over_screen(img):
            end_path = os.path.join(OUT, f"{n:03d}_end.png")
            Image.fromarray(img.astype(np.uint8)).save(end_path)
            final_score, score_reads = stable_score(img, game_over_score_box(img), tries=GAME_OVER_SCORE_TRIES)
            game_number += 1
            window_streak += 1
            entry = {"n": n, "policy": policy.name, "board": grid,
                     "tray": [s[0] if s else None for s in slots], "score": score,
                     "koniec_partii": True, "wynik_koncowy": final_score,
                     "wynik_koncowy_odczyty": score_reads,
                     "zrzut_konca": os.path.basename(end_path), "nowa_partia": game_number}
            if po_ruchu is not None:
                entry["przed_koncem"] = po_ruchu
            if seria:
                entry["end"] = "koniec_partii"
            elif window_streak >= PROGRESS_SAFEGUARD_TRIES:
                entry["end"] = "okno: petla_bez_postepu"
            write_row(entry)
            log.flush()
            print(f"koniec_partii, wynik {final_score}, nowa_partia {game_number}"
                  + (f", {entry['end']}" if "end" in entry else ""), flush=True)
            if "end" in entry:
                break
            tap_play()
            po_ruchu = None
            img, grid, slots = stable_state()
            continue
        board = Board()
        board.grid = [row[:] for row in grid]
        pieces = [Piece(s[0], f"slot{i}", -1) if s else None for i, s in enumerate(slots)]
        moves = legal_moves(board, pieces)
        entry = {"n": n, "policy": policy.name, "board": grid,
                 "tray": [s[0] if s else None for s in slots], "score": score}
        moves_since_in_game += 1
        if tempo_stare() or not moves or not last_ok or moves_since_in_game >= IN_GAME_EVERY:
            moves_since_in_game = 0
            focused = in_game()
        else:
            focused = True  # nowa ścieżka (#266): po zgodnym ruchu nie pytamy `dumpsys window` co ruch
        if not focused:
            last_ok = False
            if restart_app():
                entry["restart"] = "apka wznowiona po awarii (monkey, bez instalacji/ToS)"
                write_row(entry)
                log.flush()
                print("restart udany, kontynuacja partii", flush=True)
                img, grid, slots = stable_state()
                continue
            entry["end"] = "gra nie jest na pierwszym planie"
            write_row(entry)
            print(entry["end"], flush=True)
            break
        if not moves and (is_ad_screen(img) or board_and_tray_empty(grid, slots)):
            if not is_ad_screen(img):
                # `board_and_tray_empty` na przejściowej klatce prawdziwej planszy: nie jest
                # reklamą, więc stuknięcie w AD_CLOSE trafiłoby w ikonę Ustawień (#163) —
                # tylko odczyt ponownie, bez dotykania ekranu.
                empty_streak += 1
                if empty_streak >= EMPTY_BOARD_BACK_TRIES:
                    # #235: seria pustych odczytów to zwykle nierozpoznana reklama — jeden „wstecz".
                    empty_streak = 0
                    press_back()
                    entry = windowed_entry("plansza_pusta_wstecz")
                else:
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
            write_row(entry)
            print(entry["end"], flush=True)
            break
        if not moves and tray_awaiting_deal(grid, slots):
            # #294: ostatni klocek tacki postawiony, nowa trójka jeszcze nie dosypana — pusta tacka nigdy nie jest
            # końcem gry. Czekamy i czytamy ponownie; wpis liczy się do bezpiecznika postępu.
            time.sleep(TRAY_DEAL_WAIT)
            entry = windowed_entry("tacka_pusta_przejsciowo")
            if "end" in entry:
                break
            img, grid, slots = stable_state()
            continue
        if not moves and seria:
            # #295: w serii „brak ruchu" bez ekranu końca to zwykle klatka przejściowa (napis combo, nakładka) —
            # czekamy i czytamy ponownie; kończymy dopiero, gdy stan stoi przez cały bezpiecznik.
            stan = (grid, [s[0] if s else None for s in slots])
            no_move_streak = no_move_streak + 1 if stan == no_move_stan else 1
            no_move_stan = stan
            if no_move_streak <= NO_MOVE_REREAD_TRIES:
                time.sleep(TRAY_DEAL_WAIT)
                entry = windowed_entry("brak_ruchu_ponowny_odczyt")
                if "end" in entry:
                    break
                img, grid, slots = stable_state()
                continue
        if not moves:
            entry["end"] = "brak legalnego ruchu wg odczytu"
            write_row(entry)
            break
        no_move_streak = 0
        no_move_stan = None
        window_streak = 0
        empty_streak = 0
        game = make_game_stub(board, pieces)
        t0 = time.perf_counter()
        i, x, y = policy.act(game, moves)
        t1 = time.perf_counter()
        decision_ms = (t1 - t0) * 1000
        expected = simulate(board, pieces[i], x, y)
        info, aim = drag(slots[i][1], pieces[i], x, y)
        Image.fromarray(aim.astype(np.uint8)).save(os.path.join(OUT, f"{n:03d}_aim.png"))
        t2 = time.perf_counter()
        img, observed, slots = stable_state()
        t3 = time.perf_counter()
        ok = observed == expected
        frozen = observed == board.grid
        board_stuck_streak = board_stuck_streak + 1 if frozen else 0
        grid = observed
        ok_streak = ok_streak + 1 if ok else 0
        best_streak = max(best_streak, ok_streak)
        last_ok = ok
        po_ruchu = {"board": expected, "tray": [p.shape if p is not None and j != i else None
                                                for j, p in enumerate(pieces)]}
        entry["t_ms"] = {"odczyt": round((t0 - t_start) * 1000, 1), "decyzja": round(decision_ms, 1),
                         "przeciagniecie": round((t2 - t1) * 1000, 1), "stabilny_stan": round((t3 - t2) * 1000, 1)}
        entry.update(move={"slot": i, "x": x, "y": y}, drag=info, expected=expected, observed=observed, ok=ok,
                      decision_ms=round(decision_ms, 2))
        if board_stuck_streak >= BOARD_STUCK_TRIES:
            stuck_path = os.path.join(OUT, f"{n:03d}_stuck.png")
            Image.fromarray(img.astype(np.uint8)).save(stuck_path)
            entry["okno"] = "plansza_zawieszona"
            entry["end"] = "okno: plansza_zawieszona"
            entry["zrzut_zawieszenia"] = os.path.basename(stuck_path)
            write_row(entry)
            log.flush()
            print(f"okno: plansza_zawieszona, zrzut {stuck_path}", flush=True)
            break
        write_row(entry)
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
