# Most: wykrycie zawieszenia planszy i wariant końca z wolną animacją (#218, dane #212)

Sesja danych #212 (`bridge/runs/1b1763a/`, 27 kawałków) znalazła dwa mechaniczne problemy
mostu, żadnego z gry:

1. Od ruchu 23 kawałka 25 plansza przestała się zmieniać. Most przez ~67 ruchów (reszta
   kawałka 25, całe kawałki 26 i 27) powtarzał ten sam ruch `slot1->(3,5)`, za każdym razem
   z `ROZBIEŻNOŚĆ`, bez żadnego wpisu `okno` w logu — spalił trzy kawałki sesji.
2. Kawałek 6: nowy wariant ekranu końca partii (tło fioletowo-złote z koroną i confetti,
   `chunk6_025_end.png`) miał licznik wyniku wciąż animujący się przy każdym odczycie —
   `stable_score` wyczerpał domyślny limit 6 prób bez dwóch zgodnych odczytów z rzędu.

## Zawieszenie planszy

### Czemu `petla_bez_postepu` tego nie złapała

Istniejący bezpiecznik postępu (`PROGRESS_SAFEGUARD_TRIES`, #163) liczy tylko wpisy
**okienkowe** (`windowed_entry`: dialog wyjścia, Ustawienia, menu główne, reklama statyczna)
— `window_streak` zeruje się na *każdym* zwykłym wpisie ruchu, niezależnie od tego, czy ruch
się powiódł (`ok`) czy nie (`ROZBIEŻNOŚĆ`). Zawieszenie planszy generuje zwykłe wpisy ruchu
(`ROZBIEŻNOŚĆ`, nie `okno`), więc `window_streak` zerował się w kółko i bezpiecznik nigdy nie
odpalił.

### Sygnał: obserwacja identyczna z planszą sprzed ruchu

Na materiale `bridge/runs/1b1763a/chunk25_moves.jsonl` (`board`/`observed` per wpis) pole
`observed` przestaje się różnić od pola `board` (stan **sprzed** tego samego ruchu) dokładnie
od ruchu n=23 i już nigdy się nie zmienia do końca kawałków 25-27 — 37+30+30 wpisów z rzędu
`observed == board`. To odróżnia zawieszenie od zwykłego szumu OCR: przy normalnym
`ROZBIEŻNOŚĆ` (np. ruchy n=20-22 tego samego kawałka) `observed != board`, bo tacka/plansza
faktycznie się zmieniają, tylko nie tak, jak przewidywał symulator.

Przegląd całego dostępnego materiału `bridge/runs/*/*.jsonl` potwierdza, że
`observed == board` (obserwacja po ruchu identyczna z planszą przed ruchem) w normalnej grze
zdarza się co najwyżej **raz** pod rząd (pojedynczy szum OCR, `chunk1_moves.jsonl` z #212,
`1bd38fa/moves.jsonl`, `4fb5ed9/chunk1_moves.jsonl`) i nigdy się nie powtarza — poza samym
zawieszeniem (7, potem 30, potem 30 wpisów z rzędu). Osobny przypadek, `b4a7d26/moves.jsonl`
(144 z rzędu), to już znany i osobno obsłużony modal Ustawień z wcześniejszej sesji, nie ten
typ zatrzymania.

### Próg i działanie

`BOARD_STUCK_TRIES = 3`: trzy ruchy z rzędu z `observed == board` (plansza sprzed ruchu)
kończą kawałek. Margines nad zmierzonym maksimum szumu (1) jest szeroki, a koszt
(2 dodatkowe ruchy nawigacji spalone, zanim most się zatrzyma) minimalny w porównaniu do
obecnych 67. Most przy odpaleniu progu:

- zapisuje zrzut bieżącego ekranu do `bridge-out/NNN_stuck.png`,
- loguje wpis ruchu z dodatkowymi polami `"okno": "plansza_zawieszona"`,
  `"end": "okno: plansza_zawieszona"`, `"zrzut_zawieszenia": "NNN_stuck.png"`,
- kończy `main()` (kawałek), tak jak inne warunki `"end"`.

Test na zapisanych danych i na atrapie planszy zamrożonej między ruchami:
`tests/test_bridge_moves_log.py::TestMainDetectsFrozenBoard`.

### Hipoteza odzyskania (do zmierzenia przez verifiera — most tego nie robi)

Ręczna diagnoza po kawałku 27 (`pomiar.json`, klucz `reczna_diagnoza_zawieszenia`) wykazała:

- „wstecz" → menu główne → „Classic" wraca do **tej samej** zawieszonej planszy (diff pikseli
  regionu planszy = 0).
- Pełny restart procesu apki (`force-stop` + `monkey`) → menu główne → „Classic" wraca do **tej
  samej** zawieszonej planszy co do bajtu — stan jest zapisany/przywracany przez autozapis,
  nie żyje tylko w pamięci procesu.
- W oknie czasowym zawieszenia widoczne aktywne wątki UnityAds/BidTokenEncoder w logcacie —
  hipoteza: apka czeka na interstitial, który nigdy się nie załadował/wyrenderował w tym
  środowisku, i blokuje odświeżanie planszy do jego zamknięcia.

Nie zmierzono: czy dłuższe oczekiwanie (minuty, nie sekundy) odblokowuje planszę, czy zmiana
orientacji/rozdzielczości coś zmienia, ani czy da się wymusić zamknięcie zawieszonej reklamy
mimo braku jej obrazu na ekranie. Do zmierzenia przez verifiera na żywym emulatorze.

## Wariant końca partii z wolną animacją (fioletowo-złoty, korona i confetti)

`is_game_over_screen` już rozpoznaje ten wariant bez zmian — test fioletu (`b > r > g` z
marginesem) daje 0,976 na `chunk6_025_end.png`, dobrze powyżej progu 0,5, i mieści się w tym
samym `GAME_OVER_SCORE_BOX` co inne warianty fioletowe (kod koloru trafia w tę samą gałąź, nie
w gałąź niebieską). Rozpoznanie nie było problemem.

Problem był w `stable_score`: seria odczytów na tym zrzucie to `[None, 8004, 14226, 20284,
25644, 30179]` — sześć prób (domyślny limit), przyrosty malejące (8004, 6222, 6058, 5360,
4535), ale nigdy dwa zgodne odczyty z rzędu. Most przyjął ostatnią wartość (30179) tylko
dlatego, że akurat pokrywała się z prawdziwym wynikiem końcowym — przypadek, nie
gwarancja.

Poprawka: wywołanie `stable_score` na ekranie końca partii dostaje osobny, wyższy limit prób,
`GAME_OVER_SCORE_TRIES = 12`, zamiast domyślnych 6 — margines, żeby zobaczyć powtórzenie
wartości, gdy animacja rzeczywiście się kończy, także na tym wariancie. Test odtwarza
dokładnie zmierzoną serię z jedną dodatkową próbą (powtórzenie 30179):
`tests/test_bridge_moves_log.py::TestStableScore::test_slow_gold_variant_animation_converges_within_game_over_tries`.
Rozpoznanie samego wariantu jest sprawdzone osobno:
`tests/test_bridge_moves_log.py::TestIsGameOverScreenGoldVariant`.

## #235: „wstecz" na jasnej reklamie, seria pustych plansz, luźniejszy bezpiecznik

Materiał: sesja danych #223 (`bridge/runs/7e25817/`), dwa kawałki skończone
`okno: petla_bez_postepu`, choć most mógł iść dalej.

- **`reklama_jasna`** nie kończy już kawałka: most naciska „wstecz" i liczy wpis do bezpiecznika
  (pomiar #223: jeden „wstecz" zamknął jasną reklamę). `BRIGHT_AD_MIN_COLORS` bez zmian.
- **Seria `plansza_pusta_przejsciowo`** (kawałek 6: reklama Nike o 7 895 kolorach czytana jako
  pusta plansza sześć razy z rzędu): po `EMPTY_BOARD_BACK_TRIES = 3` z rzędu jeden „wstecz"
  (wpis `plansza_pusta_wstecz`). Trzy dają zwykłej przejściowej klatce szansę, a seria sześciu
  z #223 nie dochodzi do końca. Dialog wyjścia, gdyby „wstecz" go otworzył, obsługuje
  `is_exit_dialog_screen`.
- **`PROGRESS_SAFEGUARD_TRIES` 6 → 12**: sekwencja z kawałka 10 (2× `reklama_statyczna`,
  `ustawienia_wstecz`, koniec partii, `ustawienia_wstecz`, `menu_glowne`) ma 6 wpisów i kończyła
  się grywalną planszą; pętla z #159 miała setki wpisów na stałym `n`, więc 12 nadal ją łapie.
- Każda nowa gałąź „wstecz" idzie przez `windowed_entry`, więc ekran, który się nie zmienia, nie
  kręci się bez końca (testy: stała jasna reklama, stała pusta plansza, 30 naprzemiennych okien).
