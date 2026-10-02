# #350 — czas życia napisu po czyszczeniu linii

Serie: 80 (jedna na ruch czyszczący linię; polityka rekordu, beam=128). Klatki co ~0,2 s przez 6 s od końca przeciągnięcia (czas = środek między początkiem a końcem `screencap`; jeden `screencap` ≈ 0,2 s). Rodzaj napisu: wzrokowo z zrzutów (klatka z największym rozrzutem w wierszach 3–5); „Perfect!” i „Good!” — **zero trafień**.

Metryki (mediana / p95 / max, s):
- `t_zniknie` — pierwsza klatka, od której surowy `read_board` == ostatnia klatka serii (definicja z zadania);
- `t_zniknie_trwale` — pierwsza klatka, od której wszystkie następne są równe ostatniej;
- `t_wizualny` — ostatnia klatka z nakładką w wierszach 3–5 (`cell_flatness` ≥ `NAPIS_ROZRZUT`); baner poza wierszami 3–5 (np. seria 15, Combo 17 niżej) tego nie łapie;
- `t_stable` — czas, po którym zwykły `stable_state()` zwróciłby wynik (dwie zgodne klatki).

| rodzaj | n | t_zniknie | t_zniknie_trwale | t_wizualny | t_stable |
|---|---|---|---|---|---|
| napis „Combo N” (z „+N” albo bez) | 61 | 0.10 / 1.21 / 2.41 | 1.13 / 1.35 / 2.42 | 1.10 / 1.55 / 2.03 (n=60) | 1.12 / 1.51 / 2.64 |
| duża liczba 300…20000 (kamień punktowy) | 12 | 0.97 / 1.34 / 1.36 | 1.22 / 1.36 / 1.38 | 1.16 / 1.60 / 1.64 (n=12) | 0.86 / 1.56 / 1.58 |
| puchar | 2 | 0.10 / 0.10 / 0.10 | 2.32 / 2.41 / 2.41 | 2.02 / 2.02 / 2.02 (n=2) | 1.99 / 2.61 / 2.61 |
| pasek „+10” z poświatą | 2 | 0.09 / 0.10 / 0.10 | 0.58 / 0.68 / 0.68 | 0.49 / 0.49 / 0.49 (n=2) | 0.80 / 0.91 / 0.91 |
| tylko poświata czyszczenia, bez napisu | 2 | 0.10 / 0.10 / 0.10 | 1.22 / 1.28 / 1.28 | — (n=0) | 1.12 / 1.36 / 1.36 |
| „Great!” / „Excellent!” (pochwała) | 1 | 0.09 / 0.09 / 0.09 | 0.71 / 0.71 / 0.71 | 0.91 / 0.91 / 0.91 (n=1) | 0.91 / 0.91 / 0.91 |

## Ile serii nadal miało napis po T s

Warunek: ostatnia klatka z nakładką (`t_wizualny`) albo ostatnia klatka różna od końcowej (`t_zniknie_trwale`) później niż T.

| rodzaj | n | >2 s | >3 s | >5 s | >6 s |
|---|---|---|---|---|---|
| napis „Combo N” (z „+N” albo bez) | 61 | 2 | 0 | 0 | 0 |
| duża liczba 300…20000 (kamień punktowy) | 12 | 0 | 0 | 0 | 0 |
| puchar | 2 | 2 | 0 | 0 | 0 |
| pasek „+10” z poświatą | 2 | 0 | 0 | 0 | 0 |
| tylko poświata czyszczenia, bez napisu | 2 | 0 | 0 | 0 | 0 |
| „Great!” / „Excellent!” (pochwała) | 1 | 0 | 0 | 0 | 0 |
| wszystkie | 80 | 4 | 0 | 0 | 0 |

## `stable_state()` i korekty `drop_banner_*`

- serie z wynikiem `stable_state()` (dwie zgodne klatki): 80/80;
- korekta (`drop_banner_ghosts` albo `drop_banner_text`) odpaliła na klatce `stable_state()`: 34;
- surowa klatka `stable_state()` == ostatnia klatka serii: 45/80;
- po korekcjach plansza == ostatnia klatka: 76/80;
- po korekcjach plansza == `expected` symulatora: 76/80;
- ostatnia klatka serii == `expected`: 80/80.

Serie, w których po korekcjach plansza ≠ ostatnia klatka (stan po `stable_state()` byłby błędny): s3 (combo, t_stable 0.933, t_zniknie_trwale 1.127), s7 (kamien_punktowy, t_stable 0.939, t_zniknie_trwale 1.344), s43 (trofeum, t_stable 1.371, t_zniknie_trwale 2.234), s74 (combo, t_stable 0.954, t_zniknie_trwale 1.352).
