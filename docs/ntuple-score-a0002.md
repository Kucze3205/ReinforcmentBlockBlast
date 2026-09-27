# Trening N-tuple, sygnał wynik, alpha 0,0002: krzywa i ewaluacja (#141)

Drugie ramię eksperymentu z [#126](../../issues/126): sam sygnał (`--reward score`),
5× mniejszy krok (`--alpha 0.0002` wobec `0.001`), hipoteza: krok w #126 był za duży
wobec ciężkoogonowego `gain` (mnożnik combo bez górnej granicy), krzywa przy mniejszym
kroku rośnie wolniej, ale nie zawraca.

Polecenie (dokumentowane w `docs/ntuple.md` po [#140](../../issues/140)):

```
python3 tools/train_ntuple.py --reward score --alpha 0.0002 --seed 2 --move-cap 2000 \
    --state ntuple/score-a0002-state.json --out ntuple/score-a0002-weights.json \
    --best-out ntuple/score-a0002-best.json --curve-out docs/data/ntuple-score-a0002-krzywa.json \
    --eval-every 1000 --eval-episodes 100 --episodes 40000 --episodes-per-run <K>
```

**40 000 odcinków** w pięciu blokach na pierwszym planie, każdy poniżej 3400 s, commit po
każdym (`--episodes-per-run`: 2000, 8000, 10000, 10000, 10000 — czasy rzeczywiste 0m35s,
2m27s, 3m41s, 3m57s, 4m10s).

## Krzywa treningu (okna po 2000 odcinków, `docs/data/ntuple-score-a0002-krzywa.json`)

| okno (odcinki) | n | średni wynik | średnie przeżycie | średni \|błąd_td\| |
|---|---|---|---|---|
| 1-2000 | 2000 | 474,57 | 28,22 | 20,98 |
| 2001-4000 | 2000 | 482,80 | 28,02 | 27,00 |
| 4001-6000 | 2000 | 522,40 | 29,55 | 28,40 |
| 6001-8000 | 2000 | 553,66 | 30,75 | 30,85 |
| 8001-10000 | 2000 | 587,24 | 31,02 | 33,77 |
| 10001-12000 | 2000 | 626,47 | 32,47 | 36,98 |
| 12001-14000 | 2000 | 683,88 | 33,68 | 40,38 |
| 14001-16000 | 2000 | 720,48 | 33,61 | 44,43 |
| 16001-18000 | 2000 | 712,24 | 33,63 | 45,58 |
| 18001-20000 | 2000 | 779,10 | 35,55 | 48,33 |
| 20001-22000 | 2000 | 806,96 | 36,21 | 50,26 |
| 22001-24000 | 2000 | 839,06 | 37,02 | 51,33 |
| 24001-26000 | 2000 | 877,13 | 37,24 | 54,89 |
| 26001-28000 | 2000 | 886,96 | 38,18 | 55,83 |
| 28001-30000 | 2000 | 914,70 | 38,75 | 56,54 |
| 30001-32000 | 2000 | 953,70 | 39,48 | 59,14 |
| 32001-34000 | 2000 | 976,57 | 40,00 | 60,95 |
| 34001-36000 | 2000 | 1051,58 | 41,73 | 63,30 |
| 36001-38000 | 2000 | 1056,18 | 42,00 | 64,92 |
| **38001-40000 (ostatnie)** | 2000 | **1062,13** | **42,42** | 64,07 |

**Werdykt: rośnie.** Krzywa jest wzrostowa niemal monotonicznie (jedno wahnięcie w dół,
okno 8→9: 720,48→712,24) od okna 1 do ostatniego okna 20 (38001-40000), które jest
jednocześnie najwyższym punktem całego przebiegu (1062,13/42,42) — brak śladu odwrócenia,
jakie widać w [#126](../../issues/126) po oknie 13.

## Punkty ewaluacji (bez uczenia, 100 partii, co 1000 odcinków)

Najlepszy punkt — ten, przy którym `ntuple/score-a0002-best.json` zapisało wagi:

| odcinek | średni wynik ewaluacji | średnie przeżycie ewaluacji |
|---|---|---|
| **39000 (najlepszy)** | **1125,76** | **42,96** |

Pełna krzywa ewaluacji (40 punktów) jest w `docs/data/ntuple-score-a0002-krzywa.json`
(sekcja `ewaluacja.punkty`) — waha się odcinek do odcinka (100 partii to szum), ale bez
trendu spadkowego w drugiej połowie przebiegu: ostatnie punkty (35000: 1085,11/41,45;
36000: 1083,70/41,14; 38000: 1067,86/42,77; 39000: 1125,76/42,96; 40000: 1062,17/41,72)
są w tym samym paśmie co szczyt, nie poniżej.

## Porównanie z #126 (`score`, `alpha 0.001`, `docs/data/ntuple-krzywa.json`), te same okna

| okno (odcinki) | #141 alpha=0,0002 wynik/przeżycie | #126 alpha=0,001 wynik/przeżycie |
|---|---|---|
| 1-2000 | 474,57 / 28,22 | 506,45 / 28,41 |
| 2001-4000 | 482,80 / 28,02 | 634,69 / 31,48 |
| 4001-6000 | 522,40 / 29,55 | 761,28 / 34,33 |
| 6001-8000 | 553,66 / 30,75 | 848,86 / 37,32 |
| 8001-10000 | 587,24 / 31,02 | 967,36 / 40,13 |
| 10001-12000 | 626,47 / 32,47 | 1034,17 / 41,48 |
| 12001-14000 | 683,88 / 33,68 | 1099,04 / 42,72 |
| 14001-16000 | 720,48 / 33,61 | 1136,71 / 44,13 |
| 16001-18000 | 712,24 / 33,63 | 1165,19 / 44,47 |
| 18001-20000 | 779,10 / 35,55 | 1131,37 / 43,16 |
| 20001-22000 | 806,96 / 36,21 | 1144,41 / 43,84 |
| 22001-24000 | 839,06 / 37,02 | 1198,31 / 44,90 |
| 24001-26000 | 877,13 / 37,24 | **1220,10 / 45,64 (szczyt #126)** |
| 26001-28000 | 886,96 / 38,18 | 1155,01 / 44,55 |
| 28001-30000 | 914,70 / 38,75 | 1143,42 / 43,99 |
| 30001-32000 | 953,70 / 39,48 | 1055,27 / 41,27 |
| 32001-34000 | 976,57 / 40,00 | 1031,48 / 41,19 |
| 34001-36000 | 1051,58 / 41,73 | 980,46 / 40,01 |
| 36001-38000 | 1056,18 / 42,00 | 912,13 / 38,52 |
| **38001-40000** | **1062,13 / 42,42** | 896,34 / 37,89 |

Do okna 13 (24001-26000) #126 jest wyżej na każdym oknie — rośnie szybciej, tak jak
przewiduje mniejszy krok. Ale #126 szczytuje na oknie 13 i potem spada siedem okien z
rzędu (do okna 20: 896,34, w dół o `26,5 %` od szczytu); #141 w tym samym przedziale
**dalej rośnie** i na oknie 19 (36001-38000) wyprzedza #126 na tym samym oknie
(1056,18 wobec 912,13), a na ostatnim oknie 20 różnica jest jeszcze większa (1062,13
wobec 896,34). Hipoteza zadania — mniejszy krok rośnie wolniej, ale nie zawraca —
jest zgodna z tymi 40 000 odcinkami: #141 nie osiągnął (jeszcze) szczytu #126, ale nie
pokazuje żadnego z ośmiu okien spadku, które widać w #126 od okna 14.

Zastrzeżenie: to porównanie dwóch przebiegów na różnych seedach (`--seed 2` vs `--seed 1`)
i różnej długości (40 000 vs 43 020 odcinków) — okna 1-20 są bezpośrednio porównywalne
(te same liczby odcinków), ale różnica krzywych niesie też szum losowości seedu, nie
tylko efekt `alpha`.
