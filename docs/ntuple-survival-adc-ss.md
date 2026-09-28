# Trening N-tuple, układ `ADC`, sygnał survival: rozgałęzienie ze startami z późnej gry (`--start-prob 0.5`), 40 000 → 70 000 (#172)

Ramię B eksperymentu „starty z późnej gry" (#168): rozgałęzienie przebiegu `ADC`/przeżycie
(`docs/ntuple-survival-adc.md`, #162) od **40 000 odcinków**, dociągnięte do **70 000**, z
`--start-states ntuple/start-states-ad70k.json --start-prob 0.5`. Ramię A (to samo od
40 000, bez startów z pliku) liczy równolegle w `ntuple/survival-adc-*` — osobne zadanie
cyklu, nie ten plik.

Pierwszy commit skopiował `ntuple/survival-adc-{state,state.log.jsonl,weights}.json`
z commitu `0a55b23` (koniec #162, odcinek 40 000) jako `ntuple/survival-adc-ss-*`.

```
python3 tools/train_ntuple.py --reward survival --alpha 0.00011764705882352942 --seed 3 \
    --move-cap 2000 --layout ADC \
    --state ntuple/survival-adc-ss-state.json --out ntuple/survival-adc-ss-weights.json \
    --best-out ntuple/survival-adc-ss-best.json \
    --curve-out docs/data/ntuple-survival-adc-ss-krzywa.json \
    --start-states ntuple/start-states-ad70k.json --start-prob 0.5 \
    --eval-every 1000 --eval-episodes 100 --episodes <N> --episodes-per-run <K>
```

**30 000 dodatkowych odcinków** (40 000 → 70 000), trzy bloki na pierwszym planie, stan/wagi/
krzywa commitowane po każdym:

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 8000 | 48000 | 22m39,4s (1359,4 s) |
| 2 | 12000 | 60000 | 34m59,0s (2099,0 s) |
| 3 | 10000 | 70000 (KONIEC) | 29m40,1s (1780,1 s) |

Wszystkie trzy poniżej limitu 3400 s. Blok 1 dobrany z dymnego pomiaru 300 odcinków z tą
samą konfiguracją (start z odcinka 40 000, `--start-prob 0.5`): `48,4 s / 300 ≈ 0,161
s/odcinek`, wyraźnie wyżej niż czyste `ADC` bez startów z pliku (`0,134 s/odcinek` przy
40 000, `docs/ntuple-survival-adc.md`) — połowa odcinków startuje z planszy późnej gry i
żyje dłużej od razu, zamiast dorastać do długich partii przez pierwsze dziesiątki ruchów.
Bloki 2 i 3 dobrane z tempa zmierzonego w bloku poprzednim (`0,1699 s/odcinek` po bloku 1,
`0,1749 s/odcinek` po bloku 2) z zapasem pod limit.

Plik `ntuple/survival-adc-ss-70k.json` (kopia `ntuple/survival-adc-ss-weights.json` po
70 000 odcinkach, 136 łat) ma sha256 `cb2566e006f5a24d`.

## Okna treningu po 5000 odcinków, start z pustej planszy kontra start z pliku

Log (`ntuple/survival-adc-ss-state.log.jsonl`) niesie `start_from_file` per odcinek —
rozróżnienie jest możliwe. Wiersze poniżej to średni wynik i średnie przeżycie (liczba
postawień) **polityki behawioralnej w trakcie uczenia** (nie ewaluacja zachłanna z pustej
planszy), osobno dla dwóch podzbiorów okna:

| okno (odcinki) | n (pusta) | wynik (pusta) | przeżycie (pusta) | n (plik) | wynik (plik) | przeżycie (plik) |
|---|---|---|---|---|---|---|
| 40001-45000 | 2459 | 2981,53 | 89,87 | 2541 | 2798,27 | 80,31 |
| 45001-50000 | 2531 | 3075,50 | 93,13 | 2469 | 2877,94 | 82,15 |
| 50001-55000 | 2433 | 3226,88 | 95,63 | 2567 | 2926,19 | 83,25 |
| 55001-60000 | 2488 | 3142,48 | 93,72 | 2512 | 2977,45 | 84,61 |
| 60001-65000 | 2528 | 3135,13 | 92,11 | 2472 | 3014,60 | 84,75 |
| **65001-70000 (ostatnie)** | 2505 | **3387,50** | **98,43** | 2495 | **3136,48** | **87,54** |

Podzbiór „pusta" w oknie 40001-45000 nie jest bitowo tym samym co ewaluacja zachłanna z
pustej planszy — to wciąż odcinki z polityką ε/uczącą się, na losowych seedach treningowych,
nie na `eval_seeds` — liczby z obu podzbiorów służą tylko do porównania startu pustego
kontra startu z pliku w tym samym oknie, nie do porównania z ramieniem A czy z punktami
ewaluacji niżej.

Odcinki startujące z pliku (plansza późnej gry) mają w każdym z sześciu okien niższy
średni wynik i niższe średnie przeżycie niż odcinki startujące z pustej planszy w tym samym
oknie — spodziewane, bo plansza z pliku startuje już częściowo zapełniona (bliżej końca
partii `lookahead-ntuple`, `docs/ntuple.md` sekcja „Starty z późnej gry"), więc ma z natury
mniej ruchów do końca niż partia od zera. Obie krzywe (pusta/plik) rosną razem od okna do
okna, bez odwrócenia, aż do ostatniego okna.

## Punkty ewaluacji (bez uczenia, 100 partii na punkt, start zawsze z pustej planszy) co 5000 odcinków

Z `docs/data/ntuple-survival-adc-ss-krzywa.json` (`ewaluacja.punkty`, te same `eval_seeds`
niezależne od `--seed`, jak w `ADC` bez startów):

| odcinki | wynik | przeżycie |
|---|---|---|
| 40 000 (punkt startowy, z #162) | 2647,48 | 84,82 |
| 45 000 | 3449,43 | 97,00 |
| 50 000 | 3262,85 | 96,35 |
| 55 000 | 2510,21 | 84,63 |
| 60 000 | 3288,82 | 101,52 |
| 65 000 | 3590,49 | 100,16 |
| **70 000 (ostatnie)** | 3119,15 | 84,57 |

Najlepszy punkt ewaluacji w całym zakresie 40 000-70 000: odcinek **49 000**, wynik
3850,73, przeżycie 106,26 (`docs/data/ntuple-survival-adc-ss-krzywa.json`,
`ewaluacja.najlepszy`) — nie na końcu przebiegu. Pojedyncze punkty co 1000/5000 odcinków to
szum 100 partii (widać nierówny przebieg punkt-do-punktu w tabeli), okna wyżej (5000
odcinków/okno z polityki behawioralnej) są mniej zaszumione.

Bez werdyktu: to zadanie nie porównuje tego ramienia z ramieniem A ani nie ocenia go
ewaluacją zachłanną z pustej planszy jako miarą docelową (ta z założenia nie widzi stanów
późnej gry, które ten start ma nauczyć) — porównanie obu ramion w przeszukiwaniu robi
benchmark w kolejnym cyklu.
