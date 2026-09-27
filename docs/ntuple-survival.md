# Trening N-tuple, sygnał survival: krzywa uczenia (#142)

Ramię eksperymentu z [#142](../../issues/142): sygnał TD **survival** (nagroda
`1` za każde postawienie, `target = 0` po stanie terminalnym), `--alpha 0.001
--seed 3 --move-cap 2000` — ten sam krok co [#126](../../issues/126) (`score`,
`alpha 0.001`), żeby różnił się tylko sygnał uczenia. **40 000 odcinków**, cztery
bloki na pierwszym planie, stan/wagi/krzywa commitowane po każdym:

```
python3 tools/train_ntuple.py --reward survival --alpha 0.001 --seed 3 --move-cap 2000 \
    --state ntuple/survival-state.json --out ntuple/survival-weights.json \
    --best-out ntuple/survival-best.json --curve-out docs/data/ntuple-survival-krzywa.json \
    --eval-every 1000 --eval-episodes 100 --episodes 40000 --episodes-per-run <K>
```

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 2000 | 2000 | 0m42.5s |
| 2 | 10000 | 12000 | 5m14.1s |
| 3 | 15000 | 27000 | 10m3.1s |
| 4 | 13000 | 40000 (KONIEC) | 9m37.6s |

Wszystkie cztery poniżej limitu 3400 s.

## Krzywa uczenia (`docs/data/ntuple-survival-krzywa.json`, okna po 2000 odcinków)

Polityka behawioralna (zachłanna, bez przeszukania tacki) w kolejnych oknach:

| okno (odcinki) | n | średni wynik | średnie przeżycie |
|---|---|---|---|
| 1-2000 | 2000 | 347,43 | 24,75 |
| 2001-4000 | 2000 | 524,01 | 30,64 |
| 4001-6000 | 2000 | 672,67 | 34,76 |
| 6001-8000 | 2000 | 742,35 | 37,00 |
| 8001-10000 | 2000 | 865,91 | 39,62 |
| 10001-12000 | 2000 | 961,39 | 42,39 |
| 12001-14000 | 2000 | 1031,15 | 43,86 |
| 14001-16000 | 2000 | 1072,01 | 45,39 |
| 16001-18000 | 2000 | 1191,81 | 47,61 |
| 18001-20000 | 2000 | 1216,51 | 48,18 |
| 20001-22000 | 2000 | 1258,81 | 49,20 |
| 22001-24000 | 2000 | 1315,69 | 50,21 |
| 24001-26000 | 2000 | 1268,65 | 50,28 |
| 26001-28000 | 2000 | 1398,10 | 52,13 |
| 28001-30000 | 2000 | 1427,33 | 54,01 |
| 30001-32000 | 2000 | 1477,43 | 54,89 |
| 32001-34000 | 2000 | 1448,52 | 54,31 |
| 34001-36000 | 2000 | 1495,29 | 55,12 |
| 36001-38000 | 2000 | 1468,11 | 55,08 |
| **38001-40000 (ostatnie)** | 2000 | **1593,17** | **57,12** |

## Punkty ewaluacji (bez uczenia, 100 partii na punkt, co 1000 odcinków)

Najlepszy punkt (kryterium: średni wynik) i punkt końcowy:

| punkt | odcinki | średni wynik | średnie przeżycie |
|---|---|---|---|
| **najlepszy** | **39 000** | **1984,92** | **64,24** |
| pierwszy | 1 000 | 342,42 | 25,00 |
| ostatni (40 000) | 40 000 | 1677,31 | 56,99 |

`ntuple/survival-best.json` zapisano przy odcinku **39 000** (średni wynik
ewaluacji 1984,92, średnie przeżycie 64,24).

## Werdykt

Krzywa **rośnie** — zarówno okna treningu, jak i punkty ewaluacji rosną z
wahaniami aż do końca przebiegu (40 000 odcinków), bez oznak spadku pod koniec
jak w [#126](../../issues/126) (tam szczyt w oknie 13 — odcinki 24001–26000 —
po czym spadek przez 8 kolejnych okien do końca). Tutaj ostatnie okno treningu
(38001-40000: 1593,17/57,12) jest wyższe niż przedostatnie (1468,11/55,08), a
najlepszy punkt ewaluacji (39 000 odcinków) leży tuż przed samym końcem
przebiegu, nie w jego środku — sygnał, że krzywa nie zdążyła jeszcze
zawrócić w tym budżecie odcinków.

## Porównanie z #126 (`score`, ten sam krok) na tych samych liczbach odcinków

Okna po 2000 odcinków, ten sam `--alpha 0.001`, różny tylko sygnał uczenia:

| odcinki | wynik `score` (#126) | wynik `survival` (#142) | przeżycie `score` (#126) | przeżycie `survival` (#142) |
|---|---|---|---|---|
| 1-2000 | 506,45 | 347,43 | 28,41 | 24,75 |
| 8001-10000 | 967,36 | 865,91 | 40,13 | 39,62 |
| 16001-18000 | 1165,19 | 1191,81 | 44,47 | 47,61 |
| 24001-26000 (szczyt #126) | **1220,10** | 1268,65 | **45,64** | 50,28 |
| 38001-40000 / ostatnie | 896,34 *(38001-40000)* | **1593,17** | 37,89 | **57,12** |
| 40001-43020 (ostatnie #126) | 819,42 | — | 36,39 | — |

Do okna 8 (odcinki 1–10000) `score` prowadzi lekko w wyniku; od okna 9
(16001-18000) `survival` wyprzedza `score` w obu miarach jednocześnie i
odstęp rośnie do końca przebiegu — w oknie odpowiadającym szczytowi #126
(24001-26000) `survival` ma już wyższy wynik (1268,65 wobec 1220,10) **i**
wyższe przeżycie (50,28 wobec 45,64) niż szczyt drugiego ramienia, a w
ostatnim oknie #126 (po którym krzywa `score` spadła do 819,42/36,39) krzywa
`survival` stoi przy 1593,17/57,12 i wciąż rośnie. To zgodne z hipotezą z Celu
#142: trening wprost na przeżyciu nie tylko żyje dłużej, ale w tym budżecie
odcinków daje też wyższy wynik niż trening na `gain`, bez odpowiednika spadku
widocznego w #126.

**Aktualizacja (#147):** ciąg dalszy do 100 000 odcinków (sekcja niżej)
przesunął najlepszy punkt ewaluacji z 39 000 na **66 000** — powyższy opis
`ntuple/survival-best.json` (zapisany przy odcinku 39 000) jest więc
nieaktualny, plik nadpisano wagami z odcinka 66 000.

## Ciąg dalszy do 100 000 (#147)

Wznowienie tym samym poleceniem od 40 000 do **100 000 odcinków**, trzy bloki
na pierwszym planie, stan/wagi/krzywa commitowane po każdym:

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 15000 | 55000 | 16m23.3s |
| 2 | 25000 | 80000 | 27m38.6s |
| 3 | 20000 | 100000 (KONIEC) | 21m44.9s |

Wszystkie trzy poniżej limitu 3400 s (0,065–0,066 s/odcinek average).

### Punkty ewaluacji co 5000 odcinków

| odcinki | średni wynik | średnie przeżycie |
|---|---|---|
| 5 000 | 640,38 | 34,87 |
| 10 000 | 991,49 | 40,84 |
| 15 000 | 1006,19 | 45,28 |
| 20 000 | 1174,85 | 46,58 |
| 25 000 | 1375,97 | 53,59 |
| 30 000 | 1416,37 | 49,52 |
| 35 000 | 1595,77 | 56,43 |
| 40 000 | 1677,31 | 56,99 |
| 45 000 | 1514,34 | 55,46 |
| 50 000 | 1432,85 | 54,42 |
| 55 000 | 1720,20 | 62,29 |
| 60 000 | 1555,69 | 57,90 |
| 65 000 | 1815,78 | 58,66 |
| 70 000 | 1632,67 | 58,44 |
| 75 000 | 1509,20 | 56,93 |
| 80 000 | 1665,08 | 60,01 |
| 85 000 | 1595,38 | 56,14 |
| 90 000 | 1490,63 | 53,85 |
| 95 000 | 1305,88 | 51,35 |
| **ostatni (100 000)** | 1482,90 | 52,50 |

Najlepszy punkt (kryterium: średni wynik) leży poza siatką co 5000, przy
odcinku **66 000**: średni wynik **2225,73**, średnie przeżycie **64,92**
(100 partii). `ntuple/survival-best.json` nadpisano tymi wagami.

### Werdykt

Krzywa **rośnie z szumem do odcinka 66 000** (najlepszy punkt ewaluacji), a
od odcinka **~70 000 wypłaszcza się**: średnie w oknach po 10 000 odcinków
idą 1364 (21–30k) → 1611 (31–40k) → 1556 (41–50k) → 1662 (51–60k) → **1740
(61–70k, szczyt)** → 1565 (71–80k) → 1577 (81–90k) → 1575 (91–100k) — po
szczycie trzy kolejne okna po 10 000 odcinków stoją w wąskim paśmie
1565–1577 bez dalszego wzrostu, ale też bez trwałego spadku jak w #126 (tam
osiem okien z rzędu w dół po szczycie). Odczyt: plateau, nie zawrót.
