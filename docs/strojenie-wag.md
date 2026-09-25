# Strojenie wag `features.py` — pierwszy przebieg CEM (`weights.json`)

Zadanie: [#81](../../issues/81). Pierwsze strojone wagi w historii repo — poprzedni
przebieg ([#59](../../issues/59)) puścił CEM w tle, sesja padła, nic nie przetrwało poza
samym narzędziem (`tools/tune_weights.py`, odzyskane w [#77](../../issues/77)). Ten
przebieg poszedł na pierwszym planie, **generacja po generacji, z commitem
`weights.json` po każdej** — sterownik `.session/cem_gen.py` (poza gitem, tylko
funkcje z `tools/tune_weights.py`, jedna generacja na wywołanie, stan w pickle między
wywołaniami). Punkt startowy: wagi ręczne z `docs/cechy-planszy.md` (762,5 dla
`heuristic` vs `greedy`).

## Parametry przebiegu

| parametr | wartość |
|---|---:|
| polityka strojona | `TrayPolicy` (`--policy tray`), `beam=8` (domyślny z [#79](../../issues/79)) |
| populacja | 14 |
| elita | 4 |
| gier na kandydata | 6 |
| seedów treningowych | 6 (= gier na kandydata) |
| sól seedów treningowych / RNG CEM | `81` |
| generacji | 10 |
| gier rozegranych łącznie | 840 |
| czas łączny | 2224,9 s (≈ 37 min 5 s) |

Liczbę generacji dobrano z budżetu sesji i pomiaru kosztu `TrayPolicy` z
`docs/przeszukanie-tacki.md` (śr. czas decyzji 34,10 ms przy `beam=8`) — jedna
generacja (14 kandydatów × 6 gier = 84 gry) kosztowała rosnąco od 109 s (generacja 1,
gry krótkie, polityka jeszcze słaba) do ~290 s (generacja 8+, gry dłuższe, bo lepsza
polityka przeżywa więcej ruchów). Przebieg zatrzymano po generacji 10 na wyraźnym
plateau: `elita_best` oscyluje 14486,83 → 14736 → 14486,83 → 14486,83 przez trzy
ostatnie generacje, a średnia populacji lekko *spada* (11931,96 → 11794,39 → 11534,24)
— rozkład CEM się zbiegł, dalsze generacje nie kupowałyby już wiele bez restartu z
większym `std`.

### Seedy treningowe

6 seedów, wylosowanych funkcją `training_seeds(6, bench_seeds, salt=81)` z
`tools/tune_weights.py`: `374911964, 1268297641, 1217179912, 1841921500, 1847351409,
308455418`. Rozłączność z `bench/seeds_fixed.json` (300 seedów benchmarku, #8)
wymuszona konstrukcją (pomijanie trafień) i potwierdzona asercją w samej funkcji.

## Krzywa najlepszego wyniku po generacjach

| generacja | średnia populacji | najlepszy w elicie | najlepszy dotąd |
|---:|---:|---:|---:|
| 1 | 3154,38 | 6723,50 | 6723,50 |
| 2 | 5669,38 | 9797,33 | 9797,33 |
| 3 | 6270,26 | 11025,67 | 11025,67 |
| 4 | 7032,79 | 9984,67 | 11025,67 |
| 5 | 8048,06 | 10478,00 | 11025,67 |
| 6 | 8932,93 | 13350,83 | 13350,83 |
| 7 | 10630,11 | 13831,83 | 13831,83 |
| 8 | 11931,96 | 14736,00 | **14736,00** |
| 9 | 11794,39 | 14486,83 | 14736,00 |
| 10 | 11534,24 | 14486,83 | 14736,00 |

(Wyniki na 6 seedach treningowych, nie na `bench/seeds_fixed.json` — patrz sekcja
„Wynik" niżej i zastrzeżenie o rozmiarze próby.)

## Wagi końcowe

`weights.json`, wektor z generacji 8 (najlepszy dotąd, `best_score=14736`):

| # | cecha | waga startowa (ręczna) | waga po CEM |
|---|---|---:|---:|
| 1 | `occupied_cells` | -0,5 | 0,272 |
| 2 | `surrounded_empty` | -10,0 | -10,516 |
| 3 | `empty_regions` | -2,0 | -1,726 |
| 4 | `largest_empty_rect` | 1,0 | 2,605 |
| 5 | `near_full_lines` | 3,0 | 3,195 |
| 6 | `placeable_shapes` | 0,5 | 1,349 |

**`surrounded_empty` dostała zdecydowanie największą wagę co do modułu (-10,52,
praktycznie bez zmiany względem ręcznej -10,0)** — to ma sens: taką dziurę da się
odzyskać wyłącznie wyczyszczeniem całej linii/kolumny (uzasadnienie w
`docs/cechy-planszy.md`), więc CEM niezależnie potwierdził, że to najdroższy błąd z
sześciu, zamiast go skorygować. `occupied_cells` zmieniła znak (-0,5 → +0,272) — przy
`TrayPolicy` (sekwencje do 3 klocków, nie pojedynczy ruch) sama liczba zajętych pól po
sekwencji przestała być dobrym sygnałem kary, skoro `surrounded_empty` i
`empty_regions` już łapią realny koszt fragmentacji.

## Wynik: wagi po CEM vs wagi domyślne, na seedach treningowych

Te same 6 seedów treningowych, `TrayPolicy(beam=8)`, sufit ruchów z
`bench/config.json` (2000), **to nie jest benchmark** — benchmark na 300 stałych
seedach to osobne zadanie (nie uruchomiony tutaj):

| wagi | średni wynik (6 seedów treningowych) |
|---|---:|
| domyślne (`TrayPolicy.DEFAULT_WEIGHTS`, ręczne z `docs/cechy-planszy.md`) | 4370,5 |
| po CEM (`weights.json`) | **14736,0** |

Δ = +237,2%. **Zastrzeżenie**: to pomiar na *tych samych* 6 seedach, na których CEM
bezpośrednio optymalizował wagi — różnica jest oczekiwanie ogromna i **nie mówi nic o
generalizacji** na 300 seedach `bench/seeds_fixed.json`. Sześć seedów treningowych to
mała próba (dobrana tak, by zmieściła 10 generacji w budżecie sesji); realny test
tego, czy strojenie faktycznie poprawiło politykę, a nie tylko dopasowało wagi do
sześciu konkretnych partii, to `benchmark.py --candidate tray:weights.json --previous
tray --issue <N>` — osobne zadanie (`rola:bench`), nieuruchomione tutaj zgodnie z
poleceniem zadania.

## Reprodukcja

```
python3 .session/cem_gen.py   # sterownik nie jest w repo; parametry i logika CEM
                                # (sample_population/update_distribution/evaluate_candidate)
                                # są w tools/tune_weights.py, stan startowy identyczny
                                # z --policy tray --population 14 --elite 4
                                # --games-per-candidate 6 --seed 81
```
