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
