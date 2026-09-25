# Koszt decyzji `TrayPolicy` i domyślny `beam`

Zadanie: [#79](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/79). `TrayPolicy`
(#58, odzyskana w [#77](../../issues/77)) przeszukuje wyczerpująco bieżącą tackę z wiązką
`beam` ograniczającą liczbę stanów trzymanych na każdym poziomie. Twórca zostawił dobór
`beam` jako „co dalej" — to jest ten pomiar, zanim CEM (dziesiątki tysięcy partii) i
benchmark (600 partii × 2 ramiona) polecą na tej polityce na ślepo.

## Metoda

`tools/measure_tray_cost.py`. Dla `beam ∈ {1, 2, 4, 8, 16}` — **40 partii na wartość
beam** (200 partii łącznie), na tym samym, jawnie wygenerowanym zbiorze 40 seedów
(`measurement_seeds`, sól `"tray-cost:79"`, deterministyczne odrzucanie kolizji z
`bench/seeds_fixed.json` — rozłączność z zestawem benchmarku sprawdzona w kodzie, nie
na oko), sufit 2000 ruchów jak w `bench/config.json`. Na każdą decyzję (`TrayPolicy.act`)
mierzony jest czas (`time.perf_counter`) i `last_expanded` — suma kandydatów rozwiniętych
na wszystkich poziomach tej decyzji, **przed** przycięciem do `beam` (miara rozgałęzienia
sekwencji, nie efekt samego parametru).

Całkowity czas pomiaru: **447,8 s (7 min 28 s)** — w budżecie 20 minut z zapasem.

## Wynik

| `beam` | śr. czas decyzji | p95 czas decyzji | śr. rozgałęzienie sekwencji | śr. wynik | śr. przeżycie |
|---:|---:|---:|---:|---:|---:|
| 1 | 9,49 ms | 27,51 ms | 60,08 | 1334,35 | 45,75 |
| 2 | 12,92 ms | 38,49 ms | 80,98 | 2023,60 | 62,65 |
| 4 | 20,30 ms | 66,48 ms | 127,86 | 2080,55 | 63,83 |
| 8 | 34,10 ms | 113,47 ms | 216,70 | 4121,20 | 90,22 |
| 16 | 58,80 ms | 200,84 ms | 371,58 | 5532,15 | 94,35 |

(1830–3774 decyzji zmierzonych na wartość `beam`, w zależności od tego, jak długo
przeżywały te same 40 partii przy danej wiązce — więcej decyzji przy większym `beam`,
bo polityka gra dłużej.)

## Rozgałęzienie sekwencji vs rozgałęzienie pojedynczego ruchu

`docs/cechy-planszy.md` mierzy rozgałęzienie **pojedynczego** ruchu (`len(available_actions())`):
średnia 39,66, mediana 32, maksimum 170. `TrayPolicy` rozwija **sekwencje** (do 3 klocków
tacki na raz), więc jej rozgałęzienie rośnie odpowiednio szybciej niż liniowo z `beam` —
od 60,08 (`beam=1`, praktycznie pierwszy poziom tylko) do 371,58 (`beam=16`), czyli
2,3× do ~9,3× rozgałęzienia pojedynczego ruchu. To spodziewane: przy w pełni wyczerpującym
przeszukaniu (bez wiązki) rozgałęzienie sekwencji 3 klocków byłoby iloczynem rozgałęzień
kolejnych poziomów (rzędu dziesiątek tysięcy przy średniej 39,66) — `beam` właśnie po to
istnieje, żeby to przyciąć.

## Kompromis jakość/czas i wybór `beam`

Skok jakości nie jest liniowy w `beam`:

- `1 → 2`: wynik +51,7%, przeżycie +37,0% — duży, tani skok.
- `2 → 4`: wynik +2,8%, przeżycie +1,9% — **plateau**: czas decyzji rośnie o 57%, jakość
  prawie się nie rusza. Ten poziom `beam` sam w sobie nie ma sensu jako wybór domyślny.
- `4 → 8`: wynik +98,1%, przeżycie +41,4% — drugi duży skok, wyraźnie najlepszy stosunek
  przyrostu jakości do przyrostu czasu (czas decyzji +68%, wynik prawie się podwaja).
- `8 → 16`: wynik +34,2%, ale przeżycie +4,6% (prawie płasko) — czas decyzji rośnie o 72%
  za jakość, która w praniu (przeżycie) już prawie nie rośnie.

**Wybrany domyślny `beam = 8`.** Uzasadnienie: to punkt, w którym kolejne podwojenie
`beam` ostatni raz kupuje proporcjonalny skok jakości (przeżycie +41%); podwojenie z 8
do 16 kosztuje tyle samo czasu, ale przeżycie już się nie rusza — dodatkowa jakość przy
`beam=16` to głównie wyższy wynik przy tej samej długości partii, nie odporność na
przegraną. `beam=2` i `beam=4` są tańsze, ale zostawiają na stole prawie całą jakość,
którą `TrayPolicy` w ogóle ma do zaoferowania względem `beam=1`.

Ustawione w `policies.py` (`TrayPolicy.DEFAULT_BEAM = 8`, uzasadnienie jedną linijką w
komentarzu przy stałej).

## Szacowany czas pełnego benchmarku (600 partii) przy `beam = 8`

`benchmark.py` gra 300 partii na stałych seedach + 300 na rotowanych = 600 partii na
ramię. Ekstrapolacja z pomiaru (śr. czas decyzji × śr. liczba decyzji na partię × 600
partii, przy `beam=8`: 34,10 ms × 90,22 decyzji/partia):

**≈ 1846 s ≈ 30,8 minuty na jedno ramię `tray`.**

Dla porównania, ta sama ekstrapolacja dla pozostałych zmierzonych wartości:

| `beam` | szac. czas 600 partii (jedno ramię) |
|---:|---:|
| 1 | ≈ 4,3 min |
| 2 | ≈ 8,1 min |
| 4 | ≈ 13,0 min |
| 8 | **≈ 30,8 min** |
| 16 | ≈ 55,5 min |

Jeśli `tray` gra jako jedno z kilku ramion benchmarku (np. `--candidate tray --previous
heuristic --record model.pth`), sam koszt gry ramienia `tray` mnoży czas przebiegu o
tę wartość ponad ramiona bez przeszukania — orchestrator powinien liczyć z ~31 minutami
tylko na to ramię przy `beam=8`, nie z budżetem rzędu heurystyki (144 s / 300 partii,
`docs/cechy-planszy.md`).

## Przyspieszenie `features.py` (#88): te same decyzje, mniej sekund

Zadanie: [#88](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/88). Job
benchmarku zabija pojedyncze polecenie po 3600 s (`.github/loop/loop.py:408`); ~31 min
na samo ramię `tray` przy `beam=8` (wyżej) zjadało ~60% tego budżetu, więc każdy przyszły
kandydat żyjący dłużej groził ucięciem pomiaru w połowie. `TrayPolicy` sama się nie
zmieniła — profil (`cProfile`) na 10 partiach × 60 ruchów pokazał, że ~90% czasu
`TrayPolicy.act` to `features()` (wołana raz na każdego rozwijanego kandydata, przy
`beam=8` to setki wywołań na decyzję), głównie `_placeable_shapes` (dawniej:
`Board.can_place_piece` per komórka klocka, na każdej pozycji, dla wszystkich 41
orientacji) i histogramowe `_largest_empty_rectangle` / rekurencyjny `_empty_regions`.

`features.py` przepisano na maski bitowe planszy (bit `y·WIDTH+x`): `_placeable_shapes`
porównuje prekomputowane maski pozycji klocków z maską planszy jednym AND zamiast
przechodzić po komórkach; `_largest_empty_rectangle` liczy AND masek pustych wierszy
zamiast histogramu; `_empty_regions` rozlewa się przez przesunięcia bitowe zamiast stosu
`(y, x)`. Wartości identyczne z implementacją sprzed zmiany — zweryfikowane na 20 000
losowych plansz (`features(board)` porównane bezpośrednio) i testem równoważności w
`tests/test_tray_policy.py::TestTrayPolicySpeedupPreservesDecisions`, który gra pełne
partie starą i nową implementacją na wspólnym zbiorze seedów i porównuje całe sekwencje
ruchów, na **obu** zestawach wag (`TrayPolicy.DEFAULT_WEIGHTS` i `weights.json`).

### Pomiar: przed vs po, ten sam sprzęt, te same seedy

`tools/measure_tray_cost.py`, seedy identyczne z pomiarem #79 powyżej (`measurement_seeds`,
sól `"tray-cost:79"`, 40 partii na wartość `beam`, rozłączne z `bench/seeds_fixed.json`).
Kolumny „przed" to tabela z sekcji „Wynik" wyżej (ten sam sprzęt runnera GitHub Actions);
`wynik` i `przeżycie` są w tabeli „po" identyczne z „przed" na każdym `beam` — dowód, że
przyspieszenie nie zmieniło ani jednej decyzji.

| `beam` | śr. czas decyzji — przed | śr. czas decyzji — po | przyspieszenie | wynik (przed = po) | przeżycie (przed = po) |
|---:|---:|---:|---:|---:|---:|
| 1 | 9,49 ms | 2,91 ms | 3,26× | 1334,35 | 45,75 |
| 2 | 12,92 ms | 3,989 ms | 3,24× | 2023,60 | 62,65 |
| 4 | 20,30 ms | 6,323 ms | 3,21× | 2080,55 | 63,83 |
| 8 | 34,10 ms | 10,873 ms | 3,14× | 4121,20 | 90,22 |
| 16 | 58,80 ms | 19,02 ms | 3,09× | 5532,15 | 94,35 |

Całkowity czas pomiaru (200 partii, 5 wartości `beam`): **143,8 s**, wobec 447,8 s przed
zmianą — **3,11× szybciej** na tym samym zbiorze partii.

### Szacowany czas ramienia `tray` na 600 partii przy `beam=8`, po zmianie

Ta sama ekstrapolacja co w sekcji wyżej (śr. czas decyzji × śr. liczba decyzji na partię
× 600 partii), z nowym czasem decyzji: 10,873 ms × 90,22 decyzji/partia × 600 partii:

**≈ 589 s ≈ 9,8 minuty na jedno ramię `tray`** (wobec ~31 minut przed zmianą) — z powrotem
wygodnie w budżecie 3600 s na polecenie, nawet gdyby przyszły `beam` większy niż 8 albo
strojenie z [#87](../../issues/87) wydłużyło partie.
