# Pilot: uczenie oceny N-tuple na stanach z gry z przeszukaniem — zmierzone i odrzucone (#216)

Odtworzenie [#214](../../issues/214) (kaskada `blocked`, nigdy nie zmierzone). Pytanie: czy trening
TD(0), w którym ruch podczas zbierania danych wybiera **tania wiązka** zamiast zachłannego
`argmax` po jednym klocku, rusza wagi `ADC`/`survival` z plateau (#194, #213) — mierzone tam, gdzie
o jakości wag faktycznie decyduje ocena: polityka testowa `beam=128` (przy `beam=8`/zachłannie
wszystkie dotychczasowe warianty wag są w szumie, #201).

**Wynik jednym zdaniem**: trening na trajektoriach taniej wiązki (`beam=8`) **pogarsza** wynik przy
`beam=128` i pogarsza go **tym bardziej, im dłużej trwa** (8k odcinków: −46,6%; 16k odcinków:
−59,6% względem startu `adcga16-800k`, obie różnice >5 SE) — hipoteza issue jest **odrzucona** dla
tej, najtańszej, implementacji; grupa kontrolna (dalszy trening zachłanny, ten sam czas ścienny,
dużo więcej odcinków) też nie poprawiła wyniku, ale różnica nie jest istotna statystycznie
(−12,8%, 1,33 SE) — zwykłe dalsze trenowanie zachłanne przynajmniej nie szkodzi wprost.

## Wybrany wariant i powód

Wariant **2** z rankingu `docs/research/uczenie-z-przeszukania.md` sekcja (d): TD na trajektoriach
grywanych wiązką (`beam` 4–16) jako polityka behawioralna, cel TD nadal zachłanny (jedna tacka) —
wybrany bo wprost testuje hipotezę issue (behavior ≠ target z silniejszą polityką, nie tylko z
szumem eksploracyjnym) i literatura nie ma dla niego zmierzonego wyniku w grze z losowym dopływem
(luka nazwana w raporcie). Wariant 1 (mini-TreeStrap) był zapasową opcją "jeśli wariant 2 okaże się
za drogi" — kalibracja (16 odcinków, `beam=8`, `jobs=4`, tacki `ADC`, `move_cap=2000`) dała
**0,122 s/odcinek** (wiązka natywna, `nt_search`), czyli w budżecie bloku 3400 s mieściłoby się
≈27 800 odcinków — nie trzeba było sięgać po wariant 1.

Implementacja: nowy plik `tools/train_ntuple_search.py` (poprzednia sesja tego zadania, commit
`52ca547`, testy `tests/test_train_ntuple_search.py`, 10/10 zielone). Cel TD(0) identyczny jak
`tools/train_ntuple.py` (`r_t + V(afterstate_t)`), zmienia się wyłącznie źródło odwiedzanych
afterstate'ów: pierwszy ruch sekwencji wybranej przez `NTupleLookaheadPolicy` (ta sama funkcja co
polityka grająca `lookahead-ntuple`) zamiast `argmax` po jednym klocku. Równoległość: **local
SGD** — `--jobs` procesów gra swoją porcję odcinków rundy sekwencyjnie z kopią wag, po rundzie wagi
mistrza to średnia wag wszystkich procesów (`nt_search`/rdzeń natywny trzyma wagi w buforze C na
proces, współdzielona pamięć jest poza budżetem sesji — uzasadnienie pełne w docstringu narzędzia).

## Start, przebiegi, grupa kontrolna

Start: `ntuple/survival-adcga16-800k.json` (układ `ADC`, `alpha 0.000007352941176470588` jak w
`docs/ntuple-survival-adcga16.md`).

- **Wariant** `ntuple/survival-adcgx-*`: `tools/train_ntuple_search.py --init-weights
  ntuple/survival-adcga16-800k.json`, nowy stan (format 1 tego narzędzia, licz od odcinka 0, patrz
  docstring), `--search-beam 8 --search-samples 0` (tylko bieżąca tacka, tanio), `--jobs 4
  --round-episodes 40`.
- **Kontrola** `ntuple/survival-adcgctrl-*`: zwykły `tools/train_ntuple.py` (zachłanny), z tego
  samego startu — stan/wagi/best skopiowane z `ntuple/survival-adcga16-800k.json` pod nową nazwą,
  `eval` wyzerowany, bez starego logu (wzór `docs/ntuple-survival-adcga4.md`); numeracja odcinków
  **ciągła** ze źródła (od 800 000), bo `train_ntuple.py` (w przeciwieństwie do narzędzia
  wariantu) nie ma osobnego formatu stanu.

## Polecenia

Kalibracja (nie liczy się do budżetu treningu, usunięta po pomiarze s/odcinek):
```
python3 tools/train_ntuple_search.py --state ntuple/survival-adcgx-calib-state.json \
    --out ntuple/survival-adcgx-calib-weights.json --init-weights ntuple/survival-adcga16-800k.json \
    --reward survival --layout ADC --alpha 0.000007352941176470588 --seed 3 --move-cap 2000 \
    --jobs 4 --round-episodes 16 --episodes 16 --episodes-per-run 16 --search-beam 8
```

Wariant (dwa bloki na pierwszym planie, wznowienie automatyczne ze `--state`):
```
python3 tools/train_ntuple_search.py --state ntuple/survival-adcgx-state.json \
    --out ntuple/survival-adcgx-weights.json \
    --curve-out docs/data/ntuple-survival-adcgx-krzywa.json \
    --init-weights ntuple/survival-adcga16-800k.json --reward survival --layout ADC \
    --alpha 0.000007352941176470588 --seed 3 --move-cap 2000 --jobs 4 --round-episodes 40 \
    --search-beam 8 --episodes <8000|16000> --episodes-per-run <8000>
```

Kontrola (kopia startu pod nową nazwą — `ntuple/survival-adcga16-800k.json` na
`-weights.json`/`-best.json`, `ntuple/survival-adcga16-state.json` na `-state.json` z polem `eval`
wyzerowanym `{"every": null, "episodes": null, "points": [], "best": null}` i `log_bytes: 0`, bez
kopii pliku logu — wzór `docs/ntuple-survival-adcga4.md`; potem dwa bloki `train_ntuple.py`):
```
python3 tools/train_ntuple.py --state ntuple/survival-adcgctrl-state.json \
    --out ntuple/survival-adcgctrl-weights.json --best-out ntuple/survival-adcgctrl-best.json \
    --curve-out docs/data/ntuple-survival-adcgctrl-krzywa.json \
    --reward survival --alpha 0.000007352941176470588 --seed 3 --move-cap 2000 --layout ADC \
    --episodes <805000|895000> --episodes-per-run <5000|90000> --save-every <5000|90000>
```

Pomiar (rozłączne seedy, sól inna niż domyślna `siatka-195` narzędzia i inna niż `bench/seeds_fixed.json`):
```
python3 tools/measure_ntuple_search_grid.py --n-seeds 200 --jobs 4 \
    --seed-salt pilot-216 --search beam=128 \
    --weights ntuple/survival-adcga16-800k.json ntuple/survival-adcgx-8k.json \
              ntuple/survival-adcgx-16k.json ntuple/survival-adcgctrl-895k.json \
    --out docs/data/uczenie-z-przeszukania-pilot-pomiar.json
```
`tools/measure_ntuple_search_grid.py` dostało w tej sesji tryb `--weights`/`--search`/`--seed-salt`
(poprzednio mierzył tylko siatkę konfiguracji wiązki na jednym stałym pliku wag) — potrzebny do
porównania kilku *przebiegów treningu* przy tej samej, ustalonej polityce testowej `beam=128`;
tryb domyślny (bez `--weights`) zachowany bitowo bez zmiany (smoke test w tej sesji, patrz commit).

## Tabela bloków (czas, s/odcinek)

**Wariant** (`tools/train_ntuple_search.py`, `beam=8`, `jobs=4`, natywny rdzeń `nt_search`):

| blok | zakres odcinków | czas bloku (rzeczywisty) | s/odcinek | migawka |
|---|---|---|---|---|
| 1 | 0 -> 8 000 | 824,50 s | 0,10306 | `ntuple/survival-adcgx-8k.json` |
| 2 | 8 000 -> 16 000 | 581,64 s | 0,07270 | `ntuple/survival-adcgx-16k.json` |
| **razem** | 0 -> 16 000 | **1 406,14 s** | 0,08788 śr. | — |

**Kontrola** (`tools/train_ntuple.py`, zachłanny, jeden proces):

| blok | zakres odcinków | czas bloku (rzeczywisty) | s/odcinek | migawka |
|---|---|---|---|---|
| 1 | 800 000 -> 805 000 | 76,59 s | 0,01532 | — |
| 2 | 805 000 -> 895 000 | 1 391,55 s | 0,01546 | `ntuple/survival-adcgctrl-895k.json` |
| **razem** | 800 000 -> 895 000 | **1 468,14 s** | 0,01545 śr. | — |

Czas ścienny obu grup dobrany celowo podobny (1 406 s wariant vs 1 468 s kontrola, +4,4% —
"ten sam czas ściany, nie ta sama liczba odcinków", jak każe zadanie): wariant zrobił **16 000**
odcinków w tym czasie, kontrola **95 000** — koszt wiązki `beam=8` jako polityki behawioralnej to
≈**5,7×** więcej s/odcinek niż zachłannie w tym samym treningu (0,08788 / 0,01545), głównie bo
epizody z wiązką przeżywają dłużej (średnio 501 postawień/odcinek w kalibracji, wobec ~120-160
postawień/odcinek dla treningu zachłannego na wagach tej jakości, `docs/ntuple-survival-adcga16.md`).

## Tabela pomiaru (`beam=128`, 200 partii/wiersz, seedy rozłączne z `bench/seeds_fixed.json`, sól `pilot-216`)

| wagi | odcinków | wynik śr. | se | przeżycie śr. | vs `adcga16-800k` |
|---|---|---|---|---|---|
| `ntuple/survival-adcga16-800k.json` (start) | 800 000 | 90 597,10 | 6 847,17 | 671,58 | baza |
| `ntuple/survival-adcgx-8k.json` (wariant) | 8 000 | 48 414,21 | 3 758,87 | 478,17 | **−46,56%** (5,72 SE) |
| `ntuple/survival-adcgx-16k.json` (wariant) | 16 000 | 36 648,86 | 2 901,42 | 425,79 | **−59,55%** (7,40 SE) |
| `ntuple/survival-adcgctrl-895k.json` (kontrola) | 895 000 | 78 978,67 | 5 898,53 | 625,01 | −12,82% (1,33 SE, nieistotne) |

Wynik startu na tym pomiarze (90 597, przeżycie 671,58, 200 partii, sól `pilot-216`) jest zgodny co
do rzędu wielkości z rekordem `bench/record.json` (88 133,5 śr., przeżycie 647,3, 300 partii
mieszanych fixed+rotated, `bench/213-adgs2-400k-beam128.json` ramię `record`) — różne seedy, ten
sam plik wag, ten sam `beam=128`, więc pomiar tej sesji jest wiarygodny jako punkt odniesienia.

## Wniosek

Trening TD(0) na trajektoriach taniej wiązki (`beam=8`) pogarsza ocenę przy `beam=128` monotonicznie
z liczbą odcinków (−46,6% po 8k, −59,6% po 16k) — hipoteza issue **odrzucona** dla tej,
najtańszej, wersji wariantu 2; grupa kontrolna sugeruje, że samo dalsze trenowanie zachłanne w tym
punkcie też nie pomaga (choć różnica nieistotna), więc plateau #194/#213 nie jest kwestią *skąd
biorą się odwiedzane stany* w tej implementacji.

**Do benchmarku w cyklu 25**: **żadna** z migawek tej sesji nie bije startu na tym pomiarze —
`ntuple/survival-adcgx-8k.json` (sha256 `9b68f79df56383f5…`) i `ntuple/survival-adcgx-16k.json`
(sha256 `cc452b1d6f790ec2…`) są istotnie gorsze (>5 SE), `ntuple/survival-adcgctrl-895k.json`
(sha256 `ac61b6ffde5e407c…`) nie jest istotnie różna od startu `ntuple/survival-adcga16-800k.json`
(sha256 `0ca43a9190d1f1e3…`, niezmieniony, dla porównania). Nie polecam zlecania żadnej z nich do
oficjalnego benchmarku (#8) — pilot już pokazał na 200 partiach to, co bench potwierdziłby na 300
(fixed+rotated) drożej.

## Możliwe przyczyny pogorszenia (niezmierzone w tej sesji, do rozważenia przez orchestratora)

- **Niedopasowanie celu i zachowania**: cel TD nadal zakłada zachłanną kontynuację (`r_t +
  V(afterstate_t)` bez przeszukania w celu), ale afterstate'y pochodzą z polityki, która gra
  *inaczej* niż zachłannie dalej w grze — sieć uczy się wartości stanów, do których zachłanna
  kontynuacja i tak by nie trafiła tą samą ścieżką, więc `V` może uczyć się przeceniać stany
  osiągalne tylko przez wiązkę. To jest dokładnie "ogólne ostrzeżenie teoretyczne o niestabilności
  off-policy TD" z `docs/research/uczenie-z-przeszukania.md` sekcja (a.4) — tu zmierzone wprost,
  nie tylko teoretycznie.
- **Krótsze, ale bardziej ekstremalne epizody**: wiązka `beam=8` przeżywa średnio 501
  postawień/odcinek (kalibracja) wobec ~120-160 dla zachłannego — TD(0) z `alpha` dobranym do
  epizodów ~120-160 długich może być za duży/za mały krok dla epizodów ~4× dłuższych (więcej
  aktualizacji na epizod, inny rozkład stanów odwiedzanych pod koniec gry). Niezmierzone osobno.
- **`alpha` przeniesiony bez zmian** z przebiegu `adcga16` (dobrany dla treningu zachłannego) —
  nie próbowano w tej sesji żadnej innej wartości kroku dla wariantu; to jest naturalny kolejny
  krok, gdyby ktoś chciał ratować ten kierunek, ale sesja miała zmierzyć **ten** wariant z **tym**
  `alpha` (start jak `adcga16-800k`), nie przeszukiwać hiperparametry.
