# Trening N-tuple, układ `AD`, sygnał survival: krzywa 40 000 odcinków kontra układ `A` (#152)

Ramię eksperymentu z [#152](../../issues/152): to samo polecenie co
[#142](../../issues/142)/`docs/ntuple-survival.md`, zmienione tylko: `--layout AD`,
`--alpha` przeliczone dla `AD` (`0.001 · 16 / 52 = 0.0003076923076923077`,
[#149](../../issues/149)/`docs/ntuple.md`), ścieżki `ntuple/survival-ad-*` i
`--curve-out docs/data/ntuple-survival-ad-krzywa.json`. Reszta bez zmian.

```
python3 tools/train_ntuple.py --reward survival --alpha 0.0003076923076923077 --seed 3 --move-cap 2000 \
    --layout AD \
    --state ntuple/survival-ad-state.json --out ntuple/survival-ad-weights.json \
    --best-out ntuple/survival-ad-best.json --curve-out docs/data/ntuple-survival-ad-krzywa.json \
    --eval-every 1000 --eval-episodes 100 --episodes 40000 --episodes-per-run <K>
```

**40 000 odcinków**, trzy bloki na pierwszym planie, stan/wagi/krzywa commitowane po każdym:

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 20000 | 20000 | (nie mierzony `time`, kompute `duration_s` 2538,3 s) |
| 2 | 12000 | 32000 | 38m40s (2320 s) |
| 3 | 8000 | 40000 (KONIEC) | 27m41s (1661 s) |

Wszystkie trzy poniżej limitu 3400 s (blok 1 dobrany z tempa `≈0,047 s/odcinek`
zmierzonego przez #149 na 300 odcinkach; bloki 2 i 3 dobrane konserwatywnie z
rosnącego tempa poprzedniego bloku, żeby zostać pod limitem mimo dojrzewającej,
dłużej żyjącej polityki).

## Okna treningu po 5000 odcinków: `AD` kontra `A`

Polityka behawioralna (zachłanna, bez przeszukania tacki), okna liczone z
`<stan>.log.jsonl` obu przebiegów (ten sam `--seed 3`, różny tylko układ i
`--alpha` równoważny):

| okno (odcinki) | wynik `AD` | przeżycie `AD` | wynik `A` | przeżycie `A` |
|---|---|---|---|---|
| 1-5000 | 803,28 | 39,62 | 480,23 | 29,01 |
| 5001-10000 | 1175,60 | 50,29 | 780,72 | 37,69 |
| 10001-15000 | 1480,64 | 58,12 | 1013,56 | 43,62 |
| 15001-20000 | 1770,26 | 65,56 | 1175,59 | 47,35 |
| 20001-25000 | 2048,27 | 71,72 | 1279,93 | 49,94 |
| 25001-30000 | 2309,15 | 76,55 | 1387,50 | 52,39 |
| 30001-35000 | 2414,60 | 79,70 | 1454,41 | 54,30 |
| **35001-40000 (ostatnie)** | **2613,81** | **83,22** | 1538,60 | 56,31 |

`AD` prowadzi w obu miarach (wynik i przeżycie) w **każdym** z ośmiu okien, od
pierwszego do ostatniego, z rosnącym w czasie odstępem.

## Punkty ewaluacji (bez uczenia, 100 partii na punkt) co 5000 odcinków

Te same seedy ewaluacji dla obu przebiegów (`train_ntuple.eval_seeds`,
niezależne od `--seed`):

| odcinki | wynik `AD` | przeżycie `AD` | wynik `A` | przeżycie `A` |
|---|---|---|---|---|
| 5 000 | 1029,77 | 49,06 | 640,38 | 34,87 |
| 10 000 | 1410,28 | 60,51 | 991,49 | 40,84 |
| 15 000 | 1880,25 | 66,76 | 1006,19 | 45,28 |
| 20 000 | 1978,27 | 72,19 | 1174,85 | 46,58 |
| 25 000 | 2545,35 | 82,16 | 1375,97 | 53,59 |
| 30 000 | 2357,83 | 78,67 | 1416,37 | 49,52 |
| 35 000 | 2243,52 | 74,17 | 1595,77 | 56,43 |
| **40 000 (ostatnie)** | **3085,02** | **91,21** | 1677,31 | 56,99 |

`AD` wygrywa w obu miarach na **wszystkich** ośmiu punktach ewaluacji co
5000 odcinków, na tych samych liczbach odcinków co `A`.

## Najlepszy punkt i czas na odcinek

**Nieaktualne od [#157](../../issues/157):** wznowienie do 70 000 odcinków przebiło ten
punkt przy odcinku 50 000 (3582,91 wyniku, 102,58 przeżycia → patrz sekcja „Ciąg
dalszy do 70 000" niżej);
`ntuple/survival-ad-best.json` nadpisano nowymi wagami. Akapit i tabela niżej opisują
stan sprzed wznowienia (koniec #152, 40 000 odcinków).

| układ | najlepszy punkt (odcinki) | wynik | przeżycie | s/odcinek (log, cały przebieg) |
|---|---|---|---|---|
| `AD` | **40 000** | **3085,02** | **91,21** | 0,15193 |
| `A` (#142) | 39 000 | 1984,92 | 64,24 | 0,03479 |

`ntuple/survival-ad-best.json` zapisano przy odcinku **40 000** — punkt
najlepszy leży na samym końcu przebiegu (tak jak w `A`, gdzie najlepszy punkt
39 000 też leżał tuż przed końcem), sygnał, że krzywa `AD` też nie zdążyła
zawrócić w tym budżecie odcinków.

`AD` kosztuje **≈4,37×** więcej czasu na odcinek niż `A` na tym przebiegu
(0,15193 wobec 0,03479 s/odcinek, licząc z `<stan>.log.jsonl`, nie z pola
`duration_s` stanu — ten sam powód co odkrycie w `docs/ntuple.md`: pole stanu
zaniża sumę dla szybkich odcinków). To więcej niż `≈3,06×` zmierzone przez
#149 na 300 niedojrzałych odcinkach — zgodne z zastrzeżeniem tamtego pomiaru
("obie liczby będą mniejsze przy dłużej żyjących, dojrzałych partiach"): partie
`AD` w tym przebiegu dojrzewają do średnio ok. 91 postawień (najlepszy punkt),
znacznie dłużej niż w 300-odcinkowej próbce, więc koszt na odcinek rośnie
więcej niż proporcjonalnie do samej liczby łat (52/16 ≈ 3,25×).

## Werdykt

**`AD` lepszy od `A`** przy tej samej liczbie odcinków, konsekwentnie: wygrywa
w obu miarach (wynik, przeżycie) na wszystkich ośmiu oknach treningu i
wszystkich ośmiu punktach ewaluacji co 5000 odcinków, a najlepszy punkt `AD`
(3085,02 wyniku, 91,21 przeżycia przy 40 000 odcinkach) jest wyraźnie wyższy
niż najlepszy punkt `A` (1984,92/64,24 przy 39 000). Przewaga rośnie z liczbą
odcinków (w oknie 1-5000 `AD` ma wynik ×1,67 `A`, w oknie 35001-40000 już
×1,70 — utrzymuje się, nie zanika), zgodne z hipotezą Celu #152: łaty widzące
kwadraty 3×3 — główny zabójca partii (54,7% wg `docs/co-zabija-partie.md`) —
uczą się zarówno szybciej, jak i wyżej niż układ `A` bez nich, kosztem ≈4,4×
więcej czasu na odcinek (52 łaty i 22528 wag wobec 16 łat i 4096 wag).

## Ciąg dalszy do 70 000 (#157)

Wznowienie tym samym poleceniem (zmienione wyłącznie `--episodes`/`--episodes-per-run`)
od 40 000 do **70 000 odcinków**, trzy bloki na pierwszym planie, stan/wagi/krzywa
commitowane po każdym:

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 10000 | 50000 | 35m19,9s (2119,9 s) |
| 2 | 12000 | 62000 | 43m11,3s (2591,3 s) |
| 3 | 8000 | 70000 (KONIEC) | 29m45,1s (1785,1 s) |

Wszystkie trzy poniżej limitu 3400 s (blok 1 dobrany konserwatywnie z tempa końca #152
≈0,21 s/odcinek; bloki 2 i 3 dobrane z tempa bloku poprzedniego, licząc z
`<stan>.log.jsonl`: 0,1922 s/odcinek dla bloku 1, 0,1962 dla bloku 2, 0,2028 dla bloku 3 —
tempo w tym zakresie odcinków rośnie wolniej niż w #152, bez wyraźnego trendu).

### Okna treningu po 5000 odcinków, 40 001-70 000

Polityka behawioralna (zachłanna, bez przeszukania tacki), okna liczone z
`<stan>.log.jsonl`:

| okno (odcinki) | wynik `AD` | przeżycie `AD` |
|---|---|---|
| 40001-45000 | 2719,78 | 85,38 |
| 45001-50000 | 2786,52 | 88,00 |
| 50001-55000 | 2918,12 | 89,36 |
| 55001-60000 | 2988,67 | 91,39 |
| 60001-65000 | 3137,71 | 93,85 |
| **65001-70000 (ostatnie)** | **3099,56** | **94,01** |

Okno 65001-70000 to pierwszy spadek średniego wyniku okna w całym przebiegu AD
(3137,71 → 3099,56, -1,2%); przeżycie w tym oknie wciąż rośnie nieznacznie.
Tempo przyrostu między oknami spadło wyraźnie względem 0-40 000 (tam ostatnie
przyrosty okno-do-okna sięgały +100-260 wyniku; tutaj +67, +131, +70, +149, -38).

### Punkty ewaluacji (bez uczenia, 100 partii na punkt) co 5000 odcinków

| odcinki | wynik `AD` | przeżycie `AD` |
|---|---|---|
| 40 000 | 3085,02 | 91,21 |
| 45 000 | 2546,96 | 82,63 |
| **50 000 (najlepsze)** | **3582,91** | **102,58** |
| 55 000 | 3266,72 | 95,49 |
| 60 000 | 3175,08 | 93,61 |
| 65 000 | 3200,95 | 96,56 |
| 70 000 (ostatnie) | 3341,52 | 93,36 |

Żaden z pięciu punktów ewaluacji po odcinku 50 000 nie przebił punktu 50 000
(najbliżej: 70 000 z 3341,52, oraz nie ujęty w siatce co 5000 punkt 66 000 z
3503,87 — patrz okna treningu wyżej dla ciągłości między punktami siatki).

### Najlepszy punkt i czas na odcinek

`ntuple/survival-ad-best.json` nadpisano przy odcinku **50 000**: wynik 3582,91,
przeżycie 102,58 (100 partii) — przebija poprzedni najlepszy punkt z #152
(odcinek 40 000: 3085,02/91,21) i pozostaje najlepszy do końca przebiegu (70 000).

Czas na odcinek z `<stan>.log.jsonl` (nie z zaokrąglanego pola `duration_s` stanu,
patrz `docs/ntuple.md`): **0,19664 s/odcinek** dla nowej części (odcinki 40 001-70 000,
30 000 odcinków), **0,17109 s/odcinek** licząc cały przebieg od zera (70 000 odcinków) —
wolniej niż średnia 0-40 000 (0,15193), zgodnie z rosnącą długością dojrzewających partii.

### Werdykt

Krzywa **rośnie z wyraźnie malejącym tempem od odcinka ~50 000 i płaszczy się
od ~60 000-65 000**: okna treningu (5000 partii/okno, dużo mniejszy szum niż
ewaluacja 100 partii) rosną monotonicznie aż do okna 60001-65000, po czym okno
65001-70000 jako pierwsze w całym przebiegu AD spada (o 1,2%). Punkt ewaluacji
najlepszy leży przy 50 000 (3582,91/102,58); żaden z pięciu kolejnych punktów co
1000 do 70 000 go nie przebił, choć 66 000 (3503,87) i 70 000 (3341,52) zostają
blisko — sygnał spłaszczenia w okolicy szczytu, nie jednoznacznego zawrotu jak
w `docs/co-zabija-partie.md`-owym wzorcu spadku ośmiu okien z rzędu (#126). Dla
porównania, `A` ([#147](../../issues/147)) wypłaszczył się dopiero od ~66 000 —
`AD` sygnalizuje spłaszczenie wcześniej (~60 000), przy wyższym poziomie wyniku
(najlepszy punkt `AD` 3582,91 wobec `A` 2225,73 przy 66 000).
