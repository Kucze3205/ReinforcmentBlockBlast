# Jeden poziom za tacką: `LookaheadPolicy`

Zadanie: [#92](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/92).

**Wynik w jednym zdaniu:** `LookaheadPolicy(samples=2, branch=2, inner_beam=1,
inner_depth=1, beam=8)` daje na 100 partiach **5847,51 wyniku i 102,53 przeżycia**
wobec **3690,77 / 84,12** dla `TrayPolicy(beam=8)` na tych samych seedach (×1,58
wyniku, ×1,22 przeżycia), a jej ramię 600 partii wychodzi na **1211,7 s** przy
wagach domyślnych i **1316,9 s** przy `weights.json` — obie liczby poniżej limitu
1800 s.

## Co robi polityka

`TrayPolicy` (#58, #79) przeszukuje wyczerpująco **bieżącą** tackę i nic dalej.
`LookaheadPolicy` dokłada nad tym **węzeł losowy**: tam, gdzie kończy się bieżąca
tacka, gra sięga po nową (`game.apply_placement` odświeża tackę po trzecim
postawieniu, `game.py:96-98`), a nowa tacka jest losowa. To jest pierwsze miejsce
w tym repo, w którym przeszukanie wychodzi poza znaną tackę.

Kolejność jednej decyzji:

1. **Poziom pierwszy** — dokładnie przeszukanie `TrayPolicy` (`policies._tray_beam_search`,
   ta sama funkcja, ta sama `beam`). Wychodzi z niego wiązka stanów końcowych: plansza,
   combo i suma punktów po postawieniu **całej** bieżącej tacki.
2. **Kandydaci** — `branch` najlepszych stanów, po jednym na **odrębną pierwszą akcję**.
   Decyzja dotyczy tylko pierwszego ruchu, a wiązka potrafi oddać kilka wariantów tej
   samej pierwszej akcji; bez tego filtra drugi poziom liczyłby to samo po kilka razy
   i nie rozstrzygał niczego.
3. **Węzeł losowy** — `samples` losowań następnej tacki z `generator.Generator`, czyli
   z tego samego rozkładu (1/15 na typ, potem 1/n na orientację), którego używa gra.
   Te same próbki dla wszystkich kandydatów w obrębie jednej decyzji (wspólne liczby
   losowe): różnica między kandydatami jest wtedy różnicą polityki, nie różnicą losu.
4. **Poziom drugi** — dla każdej pary (kandydat, próbka) płytsze przeszukanie
   (`inner_beam` szerokości, `inner_depth` poziomów). Wartość kandydata to

       punkty po drodze + średnia po próbkach z (punkty z następnej tacki
                                                 + w · features(plansza po niej))

   czyli oczekiwana wartość po węźle losowym — expectimax z estymatorem Monte Carlo
   zamiast pełnej sumy po 15³ możliwych tackach.

**Determinizm.** Próbki idą z osobnej instancji `Generator`, zasianej z seeda partii w
`reset(game_seed)` — nigdy z generatora gry (`act` nie rusza stanu gry ani jego RNG,
sprawdzone testem). Dwa przebiegi tego samego seeda dają tę samą sekwencję akcji:
`tests/test_lookahead_policy.py::TestLookaheadSamplingIsDeterministic`.

`TrayPolicy` jest dokładnie przypadkiem granicznym `samples=0` — sprawdzane testem
porównującym całe sekwencje partii
(`tests/test_lookahead_policy.py::TestLookaheadDegeneratesToTray`).

## Metoda pomiaru

`tools/measure_lookahead_cost.py`, **te same seedy** co `tools/measure_tray_cost.py`
(funkcja `measurement_seeds`, sól `"tray-cost:79"`, 40 partii, rozłączne z
`bench/seeds_fixed.json`), sufit 2000 ruchów jak w `bench/config.json`. Mierzony jest
czas każdej decyzji (`time.perf_counter`) i `last_expanded` (suma kandydatów rozwiniętych
na **obu** poziomach), a per partia wynik i przeżycie. Tabele z
`docs/przeszukanie-tacki.md` (#79, #88) leżą na tych samych seedach i tym samym sprzęcie.

Kolumna **ramię 600 s** to ta sama ekstrapolacja, której użyły #79 i #88:

    śr. czas decyzji × śr. przeżycie (decyzji na partię) × 600 partii

600 = 300 seedów stałych + 300 rotowanych, czyli jedno ramię `benchmark.py`
(`bench/config.json`: `n_seeds = 300`). To jest liczba porównywana z limitem
**1800 s**, który #92 nałożyło na politykę domyślną — mniej więcej jedna trzecia
limitu 3600 s na pojedyncze polecenie z `.github/loop/loop.py:408`.

Uwaga, która rządzi całym doborem parametrów: **czas ramienia rośnie z jakością**.
Lepsza polityka gra dłuższe partie, więc płaci dwa razy — raz za droższą decyzję,
drugi raz za większą liczbę decyzji. `TrayPolicy(beam=8)` ma iloczyn
`10,671 ms × 84,12 = 898`; limit 1800 s to iloczyn 3000. Cały budżet, jaki #92
zostawia, to więc **czynnik ~3,3 na iloczynie czasu decyzji i długości partii**,
a nie czynnik 3 na samym czasie decyzji.

## Tabela: 40 partii, wszystkie sprawdzone konfiguracje

Oznaczenia: `s` = `samples` (próbek następnej tacki), `b` = `branch` (kandydatów
pierwszego poziomu), `in=W×D` = `inner_beam` × `inner_depth` (szerokość × głębokość
drugiego poziomu); `beam` niewymieniony = 8, czyli domyślny `TrayPolicy`.

| konfiguracja | śr. czas decyzji | p95 | rozgałęzienie | wynik | przeżycie | ramię 600 s |
|---|---:|---:|---:|---:|---:|---:|
| `tray beam=8` (odniesienie) | 10,677 ms | 35,06 ms | 216,70 | 4121,20 | 90,22 | 578,0 |
| `s=1 b=2 in=1×1` | 15,488 ms | 39,22 ms | 304,52 | 5470,48 | 117,62 | 1093,1 |
| `beam=6 s=2 b=2 in=1×1` | 17,650 ms | 37,46 ms | 350,51 | 5624,70 | 100,90 | 1068,5 |
| **`s=2 b=2 in=1×1`** | 19,994 ms | 44,69 ms | 403,02 | 8074,93 | 129,95 | 1558,9 |
| `beam=4 s=3 b=3 in=1×1` | 20,615 ms | 41,44 ms | 412,21 | 3174,45 | 76,55 | 946,8 |
| `s=2 b=3 in=1×1` | 24,298 ms | 49,96 ms | 485,18 | 6242,07 | 103,53 | 1509,3 |
| `beam=12 s=2 b=2 in=1×1` | 25,012 ms | 62,25 ms | 497,61 | 7475,90 | 109,28 | 1639,9 |
| `s=3 b=2 in=1×1` | 25,353 ms | 52,22 ms | 504,05 | 5478,45 | 97,92 | 1489,6 |
| `s=3 b=3 in=1×1` | 29,761 ms | 56,70 ms | 605,75 | 5730,50 | 93,47 | 1669,1 |
| `s=4 b=4 in=1×1` | 41,720 ms | 75,86 ms | 848,81 | 4580,57 | 88,25 | 2209,1 |
| `s=3 b=3 in=1×3` | 48,325 ms | 88,88 ms | 974,00 | 4178,10 | 71,53 | 2073,9 |
| `s=3 b=3 in=2×2` | 53,555 ms | 97,53 ms | 1086,23 | 6129,80 | 88,62 | 2847,8 |

Wiersz odniesienia odtworzył #88 co do cyfry (tam: 10,873 ms, 4121,20, 90,22) —
wynik i przeżycie **identyczne**, czyli wyniesienie pętli wiązki do
`_tray_beam_search` faktycznie nie ruszyło żadnej decyzji `TrayPolicy`, a sprzęt
runnera jest ten sam co w #79/#88.

Co z tej tabeli widać:

- **Głębiej nie znaczy lepiej.** `in=2×2` i `in=1×3` są najdroższe i gorsze od
  `in=1×1`. Drugi poziom ma być **płytki** — jego zadaniem jest wycenić planszę
  względem losowej tacki, nie rozegrać tej tacki.
- **Oszczędzanie na pierwszym poziomie się nie opłaca.** `beam=4 s=3 b=3` jest
  tanie (946,8 s), ale gorsze od samej `TrayPolicy(beam=8)` (3174 wobec 4121).
  Drugi poziom nie nadrabia obciętego pierwszego.
- **Wynik jest szumem, przeżycie mniej.** Kolejność wyniku nie jest monotoniczna
  ani w `s`, ani w `b` (`s=1`: 5470, `s=2`: 8075, `s=3`: 5478) — na 40 partiach o
  bardzo grubym ogonie średnia wyniku po prostu nie jest rozstrzygająca. Dlatego
  finalistów przemierzono na 100 partiach (niżej), a nie wybrano zwycięzcy tej tabeli.

## Tabela: 100 partii, finaliści

Te same seedy, ciąg dalszy tej samej deterministycznej sekwencji — pierwsze 40
pozycji jest wspólne z tabelą wyżej.

| konfiguracja | śr. czas decyzji | p95 | rozgałęzienie | wynik | przeżycie | ramię 600 s |
|---|---:|---:|---:|---:|---:|---:|
| `tray beam=8` (odniesienie) | 10,671 ms | 35,20 ms | 216,12 | 3690,77 | 84,12 | 538,6 |
| `s=1 b=2 in=1×1` | 15,008 ms | 38,85 ms | 304,50 | 5317,58 | 101,68 | 915,6 |
| **`s=2 b=2 in=1×1`** | 19,697 ms | 44,44 ms | 401,81 | 5847,51 | 102,53 | **1211,7** |
| `beam=12 s=2 b=2 in=1×1` | 24,908 ms | 62,51 ms | 501,47 | 7141,55 | 100,23 | 1497,9 |

Na 100 partiach zwycięzca tabeli 40-partiowej spadł z 8074,93 na 5847,51 — potwierdza
to, że tamta liczba była w dużej części szczęściem. Poprawa względem `TrayPolicy`
zostaje i jest wyraźna: **×1,58 wyniku i ×1,22 przeżycia**.

## Tabela: na wagach `weights.json` — to pojedzie w benchmarku

Ramieniem następnego pomiaru jest `lookahead:weights.json`, nie wagi domyślne. Wagi
strojone CEM (#87) grają dłuższe partie, a czas ramienia rośnie liniowo z długością
partii, więc tę kolumnę trzeba było zmierzyć osobno, a nie przepisać z tabeli wyżej.
100 partii, te same seedy.

| konfiguracja (wagi `weights.json`) | śr. czas decyzji | p95 | wynik | przeżycie | ramię 600 s |
|---|---:|---:|---:|---:|---:|
| `tray beam=8` | 10,745 ms | 35,39 ms | 4542,04 | 101,49 | 654,3 |
| **`s=2 b=2 in=1×1`** | 20,250 ms | 45,85 ms | 6714,95 | 108,39 | **1316,9** |
| `beam=12 s=2 b=2 in=1×1` | 25,011 ms | 62,37 ms | 6767,31 | 109,97 | 1650,3 |

To jest tabela, która rozstrzygnęła wybór `beam`. Na wagach domyślnych `beam=12`
wyglądał na wyraźnie lepszy (7141,55 wobec 5847,51). **Na wagach, które naprawdę
pojadą, ta przewaga znika**: 6767,31 wobec 6714,95, czyli +0,8% wyniku za +25%
czasu (1650,3 s wobec 1316,9 s). Gdyby wybrać `beam=12` na podstawie samych wag
domyślnych, benchmark zapłaciłby 333 s za nic i zszedł z 27% do 8% zapasu pod
limitem.

## Szacowany czas jednego ramienia 600 partii — liczba wymagana przez #92

Dla wybranych parametrów domyślnych (`beam=8, samples=2, branch=2, inner_beam=1,
inner_depth=1`), z ekstrapolacji `śr. czas decyzji × śr. przeżycie × 600`:

- `lookahead` (wagi domyślne): 19,697 ms × 102,53 × 600 = **1211,7 s ≈ 20,2 minuty**
- `lookahead:weights.json`: 20,250 ms × 108,39 × 600 = **1316,9 s ≈ 21,9 minuty**

Obie **poniżej 1800 s**. Wiążąca jest druga — to ona pojedzie jako ramię kandydata.
Zapas pod limitem: **27%**.

Dwuramienny przebieg `--candidate lookahead:weights.json --previous tray:weights.json`
to 1316,9 + 654,3 = **≈ 1971 s**, czyli ~55% limitu 3600 s na polecenie. Trzecie
ramię się jeszcze mieści, ale bez zapasu na wolniejszy runner — orchestrator powinien
liczyć dwa ramiona, nie trzy.

## Wybór parametrów domyślnych

**Biorę `beam=8, samples=2, branch=2, inner_beam=1, inner_depth=1`, bo** jest to
najwyżej punktujący wariant, którego ramię `weights.json` (1316,9 s) mieści się pod
limitem 1800 s z sensownym zapasem — jedyny droższy kandydat, `beam=12`, kupuje na
tych wagach +0,8% wyniku za +25% czasu, a wszystkie warianty z większym `samples`,
`branch` albo głębszym drugim poziomem są jednocześnie droższe i gorsze.

Warianty zmierzone, ale **nieaktywne**: `beam=12 s=2 b=2` (najlepszy wynik na wagach
domyślnych, 7141,55, ramię 1497,9 s / 1650,3 s na `weights.json`) oraz `s=1 b=2`
(najtańszy sensowny lookahead, ramię 915,6 s) — ten drugi jest wartym zapamiętania
planem B, gdyby limit czasu kiedyś stwardniał: oddaje 9% wyniku za 24% czasu.

## Kara za tackę nie do postawienia: zmierzona i usunięta

Pierwsza wersja polityki miała parametr `death_penalty`: próbka, w której wylosowanej
tacki nie da się w ogóle postawić (a więc koniec partii, `game._can_place_any`),
dostawała karę do wartości. Hipoteza brzmiała, że to jest **główny** mechanizm, przez
który drugi poziom coś kupuje.

Hipoteza jest fałszywa. Pomiar (40 partii, `s=2 b=2 in=1×1`) dla kary 0, −50 i −500:

| kara | rozgałęzienie | wynik | przeżycie |
|---:|---:|---:|---:|
| 0 | 403,02 | 8074,93 | 129,95 |
| −50 | 403,02 | 8074,93 | 129,95 |
| −500 | 403,02 | 8074,93 | 129,95 |

Identyczne co do cyfry, łącznie z rozgałęzieniem — kara nie zmieniła **ani jednej**
decyzji. Diagnostyka wyjaśniła dlaczego: na trzech pełnych partiach naliczono
**0 trafień na 2488 ocen wewnętrznych**. Stan, w którym cała losowa trójka klocków
nie wchodzi, po opróżnieniu bieżącej tacki po prostu nie występuje — plansza jest
wtedy świeżo po czyszczeniach, a pierwszy poziom i tak maksymalizuje `placeable_shapes`.
Ta sama obojętność wyszła na ręcznie zbudowanej planszy-pułapce (kary 0/−50/−200/−500
dają ten sam ruch).

Parametr usunięto — nieużywana gałąź w najgorętszej pętli przeszukania to koszt bez
pokrycia. Tym, co drugi poziom naprawdę kupuje, jest wycena planszy względem
**wylosowanych** tacek zamiast statycznego zamiennika `placeable_shapes`.

Skutek uboczny dla testów: `tests/test_lookahead_policy.py::TestLookaheadAvoidsTrapBoard`
przechodzi także dla `TrayPolicy` (sprawdzone) — jest zaporą na regresję, nie dowodem
wartości drugiego poziomu. Dowodem są tabele wyżej.
