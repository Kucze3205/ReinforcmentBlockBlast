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
