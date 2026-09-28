# Trening N-tuple, układ `ADC`, sygnał survival: krzywa 40 000 odcinków kontra układ `AD` (#162)

Ramię eksperymentu z [#162](../../issues/162): to samo polecenie co
[#152](../../issues/152)/`docs/ntuple-survival-ad.md`, zmienione tylko: `--layout ADC`,
`--alpha` przeliczone dla `ADC` (`0.001 · 16 / 136 = 0.00011764705882352942`,
[#149](../../issues/149)/`docs/ntuple.md` — ten sam krok efektywny `alpha · N_łaty`
co dla `A`), ścieżki `ntuple/survival-adc-*` i
`--curve-out docs/data/ntuple-survival-adc-krzywa.json`. Reszta bez zmian.

```
python3 tools/train_ntuple.py --reward survival --alpha 0.00011764705882352942 --seed 3 --move-cap 2000 \
    --layout ADC \
    --state ntuple/survival-adc-state.json --out ntuple/survival-adc-weights.json \
    --best-out ntuple/survival-adc-best.json --curve-out docs/data/ntuple-survival-adc-krzywa.json \
    --eval-every 1000 --eval-episodes 100 --episodes 40000 --episodes-per-run <K>
```

**40 000 odcinków**, trzy bloki na pierwszym planie, stan/wagi/krzywa commitowane po każdym:

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 15000 | 15000 | 28m40,9s (1720,9 s) |
| 2 | 12000 | 27000 | 31m36,1s (1896,1 s) |
| 3 | 13000 | 40000 (KONIEC) | 38m12,0s (2292,0 s) |

Wszystkie trzy poniżej limitu 3400 s (blok 1 dobrany z dymnego pomiaru 300 odcinków
na tym układzie, `≈0,052 s/odcinek`, z zapasem na dojrzewającą politykę; bloki 2 i 3
dobrane z tempa `<stan>.log.jsonl` poprzedniego bloku — 0,104 s/odcinek po bloku 1,
0,1435 s/odcinek po bloku 2 — konserwatywnie, żeby zostać pod limitem).

## Okna treningu po 5000 odcinków: `ADC` kontra `AD`

Polityka behawioralna (zachłanna, bez przeszukania tacki), okna liczone wprost z
`<stan>.log.jsonl` obu przebiegów (ten sam `--seed 3`, różny tylko układ i `--alpha`
równoważny):

| okno (odcinki) | wynik `ADC` | przeżycie `ADC` | wynik `AD` | przeżycie `AD` |
|---|---|---|---|---|
| 1-5000 | 917,51 | 42,49 | 803,28 | 39,62 |
| 5001-10000 | 1665,25 | 61,86 | 1175,60 | 50,29 |
| 10001-15000 | 2078,91 | 70,24 | 1480,64 | 58,12 |
| 15001-20000 | 2375,54 | 77,35 | 1770,26 | 65,56 |
| 20001-25000 | 2595,71 | 81,85 | 2048,27 | 71,72 |
| 25001-30000 | 2686,88 | 83,14 | 2309,15 | 76,55 |
| 30001-35000 | 2894,71 | 88,02 | 2414,60 | 79,70 |
| **35001-40000 (ostatnie)** | **2979,43** | **89,56** | 2613,81 | 83,22 |

`ADC` prowadzi w obu miarach (wynik i przeżycie) w **każdym** z ośmiu okien, od
pierwszego do ostatniego. Przewaga na oknie 1-5000 to +14,2% wyniku, na oknie
ostatnim +14,0% — utrzymuje się przez cały przebieg, nie zanika i nie rośnie
wyraźnie dalej po połowie przebiegu.

## Punkty ewaluacji (bez uczenia, 100 partii na punkt) co 5000 odcinków

Te same seedy ewaluacji dla obu przebiegów (`train_ntuple.eval_seeds`, niezależne
od `--seed`):

| odcinki | wynik `ADC` | przeżycie `ADC` | wynik `AD` | przeżycie `AD` |
|---|---|---|---|---|
| 5 000 | 1537,23 | 56,49 | 1029,77 | 49,06 |
| 10 000 | 1445,52 | 53,90 | 1410,28 | 60,51 |
| 15 000 | 2273,77 | 72,71 | 1880,25 | 66,76 |
| 20 000 | 2349,13 | 80,33 | 1978,27 | 72,19 |
| 25 000 | 2215,57 | 71,69 | 2545,35 | 82,16 |
| 30 000 | 2982,18 | 90,07 | 2357,83 | 78,67 |
| 35 000 | 3112,01 | 93,64 | 2243,52 | 74,17 |
| **40 000 (ostatnie)** | 2647,48 | 84,82 | **3085,02** | **91,21** |

`ADC` wygrywa wynikiem na sześciu z ośmiu punktów (przegrywa na 25 000 i na
40 000, ostatnim) i przeżyciem na pięciu z ośmiu (przegrywa dodatkowo na
10 000, gdzie mimo to wygrywa wynikiem) — pojedynczy punkt to szum 100 partii,
nie krzywa (patrz okna wyżej, dużo mniej zaszumione: tam `ADC` prowadzi w obu
miarach na wszystkich ośmiu).

## Najlepszy punkt i czas na odcinek

`ntuple/survival-adc-best.json` zapisano przy odcinku **39 000**: wynik 3649,62,
przeżycie 97,71 (100 partii) — najlepszy punkt w całym przebiegu `ADC`, tuż przed
końcem (tak jak najlepszy punkt `AD` w #152 leżał na samym końcu, odcinek 40 000).
W tym samym zakresie (odcinki ≤ 40 000) najlepszy punkt `AD` to 40 000
(3085,02/91,21) — `ADC` przy swoim najlepszym punkcie jest wyżej o **+18,3%**
wyniku i **+7,1%** przeżycia.

| układ | najlepszy punkt (odcinki, ≤40 000) | wynik | przeżycie | s/odcinek (log, cały przebieg) |
|---|---|---|---|---|
| `ADC` | **39 000** | **3649,62** | **97,71** | 0,13402 |
| `AD` (#152) | 40 000 | 3085,02 | 91,21 | 0,15193 |

`ADC` (136 łat, 27904 wag) ma niższe `s/odcinek` niż `AD` (52 łat, 22528 wag)
mierzone tutaj — **nie jest to porównanie kosztu na łatę**: liczba `AD` z #152
pochodzi sprzed przyspieszenia `patch_indices` po bajtach wierszy ([#158](../../issues/158)),
`ADC` liczono już z tym przyspieszeniem. Późniejszy ciąg dalszy `AD` po #158
(`docs/ntuple-survival-ad.md`, sekcja „Ciąg dalszy do 70 000") mierzy
`0,19664 s/odcinek` na dłużej żyjących partiach — wyżej niż `ADC` tutaj mimo
mniejszej liczby łat, bo koszt na odcinek rośnie przede wszystkim z długością
partii (liczbą postawień), nie z samą liczbą łat, gdy odczyt łat jest szybki.

## Werdykt

**`ADC` lepszy od `AD`** przy tej samej liczbie odcinków: prowadzi w obu miarach
na wszystkich ośmiu oknach treningu (mniej zaszumionych, 5000 partii/okno) oraz
wynikiem na sześciu z ośmiu punktów ewaluacji co 5000 odcinków (przegrywa
wynikiem tylko na dwóch pojedynczych, zaszumionych punktach 100-partiowych —
25 000 i 40 000; przeżyciem przegrywa dodatkowo na 10 000), a
najlepszy punkt `ADC` (3649,62/97,71 przy 39 000) jest wyraźnie wyższy niż
najlepszy punkt `AD` w tym samym zakresie (3085,02/91,21 przy 40 000). Przewaga
w oknach jest stała w czasie (+14,2% na starcie, +14,0% na końcu) — nie rośnie
dalej, ale też nie zanika, więc kwadraty 3×3 (`D`) i prostokąty 2×3/3×2 (`C`)
razem widzą wystarczająco więcej niż samo `AD`, żeby stale prowadzić przy tym
budżecie odcinków.

**Krzywa `ADC` jeszcze rośnie przy 40 000**: okno ostatnie (35001-40000,
2979,43/89,56) jest wyższe niż okno poprzednie (30001-35000, 2894,71/88,02,
+2,9% wyniku, +1,8% przeżycia) — przyrost okno-do-okna zwalnia w porównaniu do
wcześniejszych okien (np. +747,74 wyniku między oknami 1 i 2, tylko +84,72
między ostatnimi dwoma), ale nie odwraca się jak w `A` (#126, spadek ośmiu okien
z rzędu). Najlepszy punkt ewaluacji (39 000, tuż przed końcem, nie w środku
przebiegu) potwierdza ten sam sygnał: budżet 40 000 odcinków nie wystarczył,
żeby `ADC` osiągnął sufit, tak jak `AD` w #152 przed swoim wznowieniem do
70 000 w #157.

## Ciąg dalszy do 70 000 (#166)

Wznowienie tym samym poleceniem (zmienione wyłącznie `--episodes`/`--episodes-per-run`)
od 40 000 do **70 000 odcinków**, trzy bloki na pierwszym planie, stan/wagi/krzywa
commitowane po każdym. Wagi 40 000 zamrożone pod niezmienną nazwą przed startem
(`ntuple/survival-adc-40k.json`, sha256 `913323c98017dd80`).

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 10000 | 50000 | 31m27,7s (1887,7 s) |
| 2 | 12000 | 62000 | 37m27,3s (2247,3 s) |
| 3 | 8000 | 70000 (KONIEC) | 26m11,9s (1571,9 s) |

Wszystkie trzy poniżej limitu 3400 s (blok 1 dobrany konserwatywnie z tempa końca
przebiegu 0-40 000, 0,1435 s/odcinek, #162, z zapasem; bloki 2 i 3 dobrane z tempa
bloku poprzedniego liczonego z `<stan>.log.jsonl`: 0,17125 s/odcinek po bloku 1,
0,17010 s/odcinek po bloku 2).

### Okna treningu po 5000 odcinków, 40 001-70 000: `ADC` kontra `AD`

Polityka behawioralna (zachłanna, bez przeszukania tacki), okna liczone z
`<stan>.log.jsonl` obu przebiegów (ten sam `--seed 3`, `AD` z #157):

| okno (odcinki) | wynik `ADC` | przeżycie `ADC` | wynik `AD` | przeżycie `AD` |
|---|---|---|---|---|
| 40001-45000 | 2987,37 | 89,98 | 2719,78 | 85,38 |
| 45001-50000 | 3035,75 | 90,94 | 2786,52 | 88,00 |
| 50001-55000 | 3109,28 | 92,08 | 2918,12 | 89,36 |
| 55001-60000 | 3146,86 | 93,53 | 2988,67 | 91,39 |
| 60001-65000 | 3174,95 | 93,51 | 3137,71 | 93,85 |
| **65001-70000 (ostatnie)** | **3169,82** | **93,57** | 3099,56 | 94,01 |

`ADC` prowadzi wynikiem na wszystkich sześciu oknach 40 001-70 000, ale przewaga
zanika: z +9,8% na oknie 40001-45000 do +1,2% na oknie ostatnim (65001-70000), a na
oknie 60001-65000 `AD` doganiał w przeżyciu (93,51 wobec 93,85 — pierwsza chwila, gdy
`ADC` nie prowadzi w tej mierze). Okno ostatnie `ADC` to pierwszy spadek średniego
wyniku okna w tej części przebiegu (3174,95 → 3169,82, -0,17%), podobnie jak u `AD`
w tym samym zakresie (3137,71 → 3099,56, -1,2%) — obie krzywe zaczynają płaszczeć się
w tym samym miejscu (okolice 60 000-65 000).

### Punkty ewaluacji (bez uczenia, 100 partii na punkt) co 5000 odcinków

| odcinki | wynik `ADC` | przeżycie `ADC` |
|---|---|---|
| 40 000 | 2647,48 | 84,82 |
| 45 000 | 3067,46 | 94,32 |
| **50 000** | **3467,78** | **100,60** |
| 55 000 | 3223,48 | 93,87 |
| 60 000 | 3254,87 | 90,49 |
| 65 000 | 2943,60 | 84,81 |
| 70 000 (ostatnie) | 3175,06 | 89,63 |

Żaden z punktów siatki co 5000 po 50 000 nie przebija punktu 50 000 — sam siatkowy
sygnał sugeruje szczyt wcześnie, ale poza siatką co 1000 leży punkt **68 000**
(3738,19/104,05), nowy najlepszy punkt całego przebiegu (patrz niżej) — zaszumienie
100-partiowej ewaluacji nie pokrywa się tu z gładszymi oknami treningu wyżej.

### Najlepszy punkt i czas na odcinek

`ntuple/survival-adc-best.json` nadpisano przy odcinku **68 000**: wynik 3738,19,
przeżycie 104,05 (100 partii) — przebija poprzedni najlepszy punkt z #162 (odcinek
39 000: 3649,62/97,71) i pozostaje najlepszy do końca przebiegu (70 000).

Czas na odcinek z `<stan>.log.jsonl` (nie z zaokrąglanego pola `duration_s` stanu):
**0,17259 s/odcinek** dla nowej części (odcinki 40 001-70 000, 30 000 odcinków),
**0,15055 s/odcinek** licząc cały przebieg od zera (70 000 odcinków) — wolniej niż
średnia 0-40 000 (0,13402), zgodnie z rosnącą długością dojrzewających partii, ten
sam kierunek co u `AD` (0,19664 dla jego nowej części, #157).

### Werdykt

**Krzywa `ADC` nadal rośnie przy 70 000, ale z wyraźnie malejącym tempem od ~55 000
i pierwszym mikroskopijnym spadkiem okna na samym końcu** (65001-70000: -0,17%
wyniku wobec okna poprzedniego) — nie odwraca się jak `A` (#126), płaszczy się w tym
samym miejscu co `AD` w tym samym zakresie odcinków (60 000-65 000). Przewaga `ADC`
nad `AD` w oknach 5000-partiowych utrzymuje się przez całą część 40 001-70 000, ale
zanika z +9,8% do +1,2% między pierwszym i ostatnim oknem tego zakresu (w części
0-40 000 była płasko na +14%) — `AD` dogania `ADC`, nie odwrotnie. Najlepszy punkt
całego przebiegu `ADC` (68 000: 3738,19/104,05) jest wyżej niż najlepszy punkt `AD`
w tym samym zakresie odcinków (50 000: 3582,91/102,58, #157), więc `ADC` zostaje
lepszym układem przy 70 000, tak jak był przy 40 000 — ale margines się kurczy.

## Ciąg dalszy do 100 000 (#178)

Wznowienie tym samym poleceniem (zmienione wyłącznie `--episodes`/`--episodes-per-run`)
od 70 000 do **100 000 odcinków**, trzy bloki na pierwszym planie, stan/wagi/krzywa
commitowane po każdym. Wagi 70 000 zamrożone pod niezmienną nazwą przed startem
(`ntuple/survival-adc-70k.json`, sha256 `65dd0764e5c3bbe9`, #172).

Ramię `B` tego samego eksperymentu (`ntuple/survival-adc-ss-*`, `docs/ntuple-survival-adc-ss.md`)
dociąga w tym samym cyklu, niezależnie — nie jest tu poruszane.

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 10000 | 80000 | 32m38,0s (1958,0 s) |
| 2 | 10000 | 90000 | 32m53,6s (1973,6 s) |
| 3 | 10000 | 100000 (KONIEC) | 32m14,3s (1934,3 s) |

Wszystkie trzy poniżej limitu 3400 s (wybrane z tempa `<stan>.log.jsonl` bloku 3
poprzedniego ciągu, 0,17010 s/odcinek, z zapasem konserwatywnym; tempo rzeczywiste
tych trzech bloków wyszło zbliżone, ok. 0,195 s/odcinek).

### Okna treningu po 5000 odcinków, 70 001-100 000

Polityka behawioralna (zachłanna, bez przeszukania tacki), okna liczone wprost z
`<stan>.log.jsonl` (`--seed 3`). Porównania z `AD` brak — przebieg `AD` (#157) nie
sięga poza 70 000.

| okno (odcinki) | wynik `ADC` | przeżycie `ADC` |
|---|---|---|
| 70001-75000 | 3390,43 | 98,25 |
| 75001-80000 | 3347,24 | 97,91 |
| 80001-85000 | 3433,21 | 98,72 |
| 85001-90000 | 3348,62 | 96,68 |
| 90001-95000 | 3343,29 | 97,28 |
| **95001-100000 (ostatnie)** | **3320,14** | **96,17** |

### Punkty ewaluacji (bez uczenia, 100 partii na punkt) co 5000 odcinków

| odcinki | wynik `ADC` | przeżycie `ADC` |
|---|---|---|
| 75 000 | 3502,09 | 97,38 |
| 80 000 | 3284,72 | 93,77 |
| **85 000** | **4249,51** | **116,55** |
| 90 000 | 3561,45 | 100,04 |
| 95 000 | 3662,16 | 107,02 |
| 100 000 (ostatnie) | 3218,57 | 91,94 |

### Najlepszy punkt i czas na odcinek

`ntuple/survival-adc-best.json` nadpisano przy odcinku **85 000**: wynik 4249,51,
przeżycie 116,55 (100 partii) — przebija poprzedni najlepszy punkt z #166 (odcinek
68 000: 3738,19/104,05) i pozostaje najlepszy do końca przebiegu (100 000).

Czas na odcinek z `<stan>.log.jsonl` (nie z zaokrąglanego pola `duration_s` stanu):
**0,17727 s/odcinek** dla nowej części (odcinki 70 001-100 000, 30 000 odcinków),
**0,15857 s/odcinek** licząc cały przebieg od zera (100 000 odcinków) — zbliżone do
tempa nowej części poprzedniego ciągu (0,17259, #166), lekki dalszy wzrost, zgodny
z rosnącą długością partii.

Snapshot `ntuple/survival-adc-100k.json` (kopia `ntuple/survival-adc-weights.json`
po 100 000, 136 łat), sha256 `3e75cd9c41264fd5`.

Bez werdyktu tutaj — o zakończeniu treningu decyduje benchmark (#8), nie ta krzywa.
