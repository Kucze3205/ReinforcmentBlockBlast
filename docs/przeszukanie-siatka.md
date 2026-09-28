# Siatka koszt/jakość: parametry przeszukiwania `lookahead-ntuple`

Zadanie: [#195](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/195). Kontynuacja
[#92](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/92) (`docs/lookahead.md`) i
[#184](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/184)
(`docs/ntuple-natywny.md`): rdzeń natywny skrócił partię `lookahead-ntuple` ~32×, więc limit
1800 s/ramię, pod który #92 dobrało `samples=2, branch=2, inner_beam=1, inner_depth=1, beam=8`,
przestał być wiążący. To zadanie sprawdza, czy nadwyżka czasu daje się zamienić na jakość.

**Wynik w jednym zdaniu:** dokładanie `samples`/`branch`/głębszego drugiego poziomu (kierunek,
który #195 podało jako przykład) **nie kupuje nic** ponad to, co daje samo **poszerzenie
pierwszego poziomu** (`beam`) — `beam=32` sam w sobie (+91,5% wyniku, ×6,3 se, koszt ×2,3) bije
`beam=32 samples=16 branch=8 inner=4×3` (+62,7% wyniku, koszt ×68) niemal dwukrotnie taniej.

## Parametry w specyfikacji: co zaimplementowano

`benchmark.py --candidate` przyjmuje teraz

    lookahead-ntuple:<plik>@k=v,k=v,...

z kluczami `beam`, `samples`, `branch`, `inner_beam`, `inner_depth` (dokładnie kwargs
konstruktora `NTupleLookaheadPolicy` poza `ntuple` i `seed`), np.

    lookahead-ntuple:ntuple/survival-ad-70k.json@samples=8,branch=4,inner_beam=4,inner_depth=3

Specyfikacja **bez** `@...` daje bitowo te same partie co dziś (kwargs puste = wartości
domyślne klasy) — sprawdzone testem `tests/test_benchmark_ntuple_weights.py` i niezmienionym
przejściem `tests/test_lookahead_ntuple_regression.py`/`test_ntuple_native.py`. Nieznana nazwa
parametru albo wartość, która nie jest liczbą całkowitą, kończy się `ArmUnavailable` — czytelnym
błędem, nie cichym pominięciem (`tests/test_benchmark_ntuple_weights.py`,
`test_unknown_param_name_raises_arm_unavailable` i sąsiednie). Rekord ramienia (`bench/<sha>.json`)
dostał pole `spec` z pełną specyfikacją — dotąd `arm["policy"]` niosło tylko stałą nazwę klasy
(`"lookahead-ntuple"`), bez pliku wag ani parametrów, więc pomiar nie dałby się odtworzyć z samego
rekordu. `tools/merge_bench.py` (`--shard`) niesie i porównuje to pole między kawałkami tak samo
jak `weights_hash`.

## Metoda pomiaru siatki

`tools/measure_ntuple_search_grid.py`: ten sam harness co `benchmark.py`
(`build_policy` + `run_set`, `--jobs 4`), na wagach rekordu `ntuple/survival-ad-70k.json`
(reward `survival`, więc ścieżka wiązki sumuje `placed`, jak w `NTupleLookaheadPolicy`),
`move_cap = 2000` z `bench/config.json`. **300 seedów, sól `"siatka-195"`, jawnie rozłącznych
z `bench/seeds_fixed.json`** (`grid_seeds`: losuje pulę i odrzuca trafienia w zbiór seedów
stałych, zamiast liczyć na brak kolizji). Wszystkie konfiguracje grają na **tych samych** 300
seedach, więc różnice są różnicą polityki, nie różnicą losu.

`se` w tabeli to błąd standardowy średniej pojedynczej konfiguracji
(`pstdev(scores) / sqrt(n)`); do porównania z domyślną liczony jest **`se` złożony**
(`sqrt(se_a² + se_b²)`, konserwatywne przybliżenie z góry — realny błąd sparowany na wspólnych
seedach jest mniejszy, bo odejmuje wspólny szum seeda). Wynik uznaję za odróżnialny od domyślnej
konfiguracji przy `|różnica| ≥ 2 · se złożone`, zgodnie z instrukcją zadania.

## Tabela: wszystkie zmierzone konfiguracje

300 partii każda, wagi `ntuple/survival-ad-70k.json`, `move_cap = 2000`, `--jobs 4`, seedy jak
wyżej. `Δ vs domyślna` i `Δ/se` liczone względem wiersza pierwszego.

| konfiguracja | wynik | se | Δ vs domyślna | Δ/se złożone | przeżycie | s/partię | ramię 600 partii |
|---|---:|---:|---:|---:|---:|---:|---:|
| **domyślna** `beam=8 s=2 b=2 in=1×1` | 23291,63 | 1441,74 | — | — | 280,99 | 0,061 | 9,2 s |
| `s=4 b=3 in=2×2` | 19642,72 | 1257,86 | −3648,91 | −1,91 | 272,82 | 0,153 | 23,0 s |
| `s=8 b=4 in=4×3` (przykład z treści #195) | 22677,51 | 1420,19 | −614,12 | −0,30 | 315,90 | 0,585 | 87,8 s |
| `beam=16 s=2 b=2 in=1×1` | 35162,49 | 2163,52 | +11870,86 | **+4,57** | 368,84 | 0,099 | 14,9 s |
| `beam=16 s=4 b=4 in=2×2` | 21614,63 | 1336,34 | −1677,00 | −0,85 | 278,49 | 0,213 | 32,0 s |
| `beam=24 s=2 b=2 in=1×1` | 39145,92 | 2509,05 | +15854,29 | **+5,48** | 382,25 | 0,115 | 17,3 s |
| `beam=32 s=2 b=2 in=1×1` | 44605,04 | 3066,91 | +21313,41 | **+6,29** | 406,90 | 0,140 | 21,0 s |
| `beam=32 s=16 b=8 in=4×3` | 37897,34 | 2083,22 | +14605,71 | **+5,77** | 499,71 | 4,165 | 2499,0 s |
| `beam=48 s=2 b=2 in=1×1` | 46567,60 | 3306,53 | +23275,97 | **+6,45** | 396,42 | 0,168 | 25,2 s |
| `beam=64 s=2 b=2 in=1×1` | 47033,47 | 3221,27 | +23741,84 | **+6,73** | 400,26 | 0,206 | 30,9 s |
| `beam=96 s=2 b=2 in=1×1` | 45679,73 | 3043,86 | +22388,10 | **+6,65** | 387,84 | 0,318 | 47,7 s |
| `beam=128 s=2 b=2 in=1×1` | 51431,99 | 3358,83 | +28140,36 | **+7,70** | 432,58 | 0,412 | 61,8 s |

„Ramię 600 partii” to `s/partię × 600` — koszt **jednej** strony pomiaru (kandydat **albo**
odniesienie) przy `--jobs 4`, żeby dało się je zestawić z pułapem ~2400 s (40 min) na cały
dwuramienny przebieg z treści zadania.

## Co z tego wynika

- **Szeroki pierwszy poziom bije głęboki drugi.** Podwojenie samego `beam` (8→16, reszta bez
  zmian) daje +51,0% wyniku za +62% czasu decyzji — najtańszy skuteczny ruch w całej tabeli.
  To ten sam wniosek co #92 (`docs/lookahead.md`: „głębiej nie znaczy lepiej”), tylko przeniesiony
  z drugiego poziomu na pierwszy: rdzeń natywny (#184) zrobił z `beam` dźwignię, która w Pythonie
  była za droga, żeby ją w ogóle przetestować powyżej 12.
- **Przykład z treści zadania (`s=8 b=4 in=4×3`) nie działa** — wynik nieodróżnialny od domyślnej
  (Δ/se = −0,30), za cenę ×9,6 czasu decyzji. Przeżycie owszem rośnie (315,90 wobec 280,99), ale
  #195 ocenia po wyniku, nie po samym przeżyciu, a to jest dokładnie ten sam wzorzec błędu, który
  #92 opisało jako „wynik jest szumem” — więcej próbek tacki i głębszy drugi poziom nie
  poprawiają jakości oceny liścia, tylko rozmywają czas na coś, co nie rozstrzyga.
- **Łączenie szerokiego `beam` z ciężkim drugim poziomem jest stratą.** `beam=32 s=16 b=8 in=4×3`
  (2499 s/ramię) wypada **gorzej** niż goły `beam=32 s=2 b=2 in=1×1` (21 s/ramię) — 37897 wobec
  44605 wyniku, za ×119 czasu. Różnica jest w granicy szumu obu pomiarów (obie wartości mieszczą
  się we wzajemnych ±1 se), więc nie twierdzę, że cięższy drugi poziom **szkodzi** — ale na pewno
  nie kupuje niczego, czego nie dawałby sam `beam`, i kosztuje dwa rzędy wielkości więcej.
- **Krzywa `beam` przy stałym `s=2 b=2 in=1×1` rośnie, potem płaska, potem znów w górę.** 16→24→32
  to wyraźny, malejący przyrost (+51%, +68%, +92%); 32→48→64→96 to płasko w granicach ±1 se
  (44605…47033…45680) — czterokrotny wzrost `beam` (32→96) bez odróżnialnej zmiany wyniku;
  `beam=128` wygląda na kolejny skok (+120,8%, 51432), ale to **pojedynczy punkt** bez sąsiada,
  który by go potwierdził — nie da się odróżnić od kontynuacji szumu, który już widać na płaskim
  odcinku. Nie ekstrapoluję dalej niż zmierzone `beam=128`.
- **Zgodnie z zadaniem: nikt tu nie ocenia rekordu.** Baza porównania to `bench/192-ad-70k-baza.json`
  (25946,36 na oficjalnych 300 seedach stałych) i moje 23291,63 na *innych* 300 seedach — różnica
  między nimi to spodziewany rozstrzał między pulami seedów (obie wewnątrz jednego se), nie sygnał.
  Który wariant naprawdę wygrywa na oficjalnych seedach, rozstrzyga osobne zadanie `rola:bench`.

## `do_benchu`: dwa kandydaci

Oba mieszczą się w pułapie ~40 min dla pełnego dwuramiennego przebiegu (kandydat + odniesienie,
600+600 partii, `--jobs 4`) z wielkim zapasem — nawet droższy z nich to **62 s** samego ramienia
kandydata.

1. **`lookahead-ntuple:ntuple/survival-ad-70k.json@beam=32,samples=2,branch=2,inner_beam=1,inner_depth=1`**
   — koniec wyraźnego, monotonicznego wzrostu (16→24→32: +51%, +68%, +92%) tuż przed płaskim
   odcinkiem 32–96; tani (21 s/ramię), bezpieczny wybór „gdzie krzywa przestaje rosnąć wyraźnie”.
2. **`lookahead-ntuple:ntuple/survival-ad-70k.json@beam=128,samples=2,branch=2,inner_beam=1,inner_depth=1`**
   — najwyższy zmierzony wynik (+120,8%, Δ/se = 7,70), wciąż tani (62 s/ramię); wart osobnego
   zmierzenia na oficjalnych seedach, bo pojedynczy punkt bez sąsiada na tej sile nie potwierdza,
   czy to realny dalszy wzrost, czy szczyt lokalnego szumu.

Żaden wariant z dołożonym `samples`/`branch`/`inner_depth` (przykład z treści zadania, `beam=16/32
s=4 b=4 in=2×2`, `beam=32 s=16 b=8 in=4×3`) nie trafia na listę — albo nie przewyższa domyślnej o
≥ 2 se, albo jest zdominowany kosztowo przez sam `beam` przy nieodróżnialnym wyniku.

Surowe dane (wszystkie 12 wierszy, z `spec` gotowym do `--candidate`): `docs/data/przeszukanie-siatka.json`.
