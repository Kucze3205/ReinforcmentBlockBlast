# Szybsze indeksy łat N-tuple, bitowo ten sam wynik (#158)

Punkt wyjścia: [#149](../../issues/149)/[#152](../../issues/152) — układ `AD` (52 łaty)
wygrał z `A` na krzywej `survival`, ale kosztuje ≈3× więcej czasu na odcinek, bo
`ntuple.board_bits`/`ntuple._patch_index` składały indeks każdej łaty bit po bicie w
pętli Pythona (`docs/ntuple.md`, sekcja "Przebieg dymny `AD`/`survival`"). To zadanie
mierzy, gdzie idzie czas, i przyspiesza tylko to miejsce — bez zmiany żadnej wartości.

## Profil przed zmianą

`python3 -m cProfile -s cumulative` na dwóch obciążeniach, ten sam sprzęt/sesja,
kod sprzed tego zadania (commit `495cd91`):

- **Trening `AD`**: `tools/train_ntuple.py --episodes 40 --episodes-per-run 40 --seed 1
  --reward survival --layout AD` — 40 odcinków, 31421 wywołań `indices()`.
- **Partie `lookahead-ntuple`**: `benchmark.py --candidate
  lookahead-ntuple:ntuple/survival-ad-best.json --n-seeds 5 --jobs 1 --issue 158` — 5+5
  seedów (stałe+rotowane), 726822 wywołań `value()` z przeszukania wiązką.

Top funkcji `ntuple.py` wg czasu skumulowanego (profiler dodaje własny narzut na
wywołanie funkcji, więc bezwzględne sekundy nie są miarodajne — miarodajny jest
udział % w ramach tego samego przebiegu):

| obciążenie | funkcja | wywołań | % czasu (cumtime) | % czasu (tottime) |
|---|---|---|---|---|
| trening `AD` (2,551 s łącznie) | `indices()` | 31421 | 60,3% | 0,5% |
| trening `AD` | `patch_indices()` | 31421 | 55,6% | 7,0% |
| trening `AD` | `_patch_index()` | 1 633 892 | 48,6% | 48,6% |
| trening `AD` | `board_bits()` | 31421 | 4,2% | 4,2% |
| trening `AD` | `value_from_indices()` | 33229 | 10,7% | 0,7% |
| partie `lookahead-ntuple` (58,924 s łącznie) | `value()` | 726822 | 71,9% | 0,6% |
| partie `lookahead-ntuple` | `indices()` | 726822 | 61,1% | 0,4% |
| partie `lookahead-ntuple` | `patch_indices()` | 726822 | 56,4% | 6,9% |
| partie `lookahead-ntuple` | `_patch_index()` | 37 794 744 | 49,6% | 49,6% |
| partie `lookahead-ntuple` | `board_bits()` | 726822 | 4,2% | 4,2% |
| partie `lookahead-ntuple` | `value_from_indices()` | 726822 | 10,2% | 0,6% |

`_patch_index` (bit po bicie, pętla Pythona w `positions`) samo wyjaśnia ≈49% czasu
w obu obciążeniach — dominująca funkcja, zgodnie z przewidywaniem zadania. Reszta
`indices()` (składanie listy indeksów + `board_bits`) to kolejne kilka-kilkanaście
procent; `value_from_indices` (sumowanie po tabelach wag) to ok. 10%, nietknięte w
tej zmianie (issue: "suma w `value_from_indices` ma zostać w tej samej kolejności").

## Zmiana: tablice odczytu po bajtach wierszy, przygotowane raz na układ

`ntuple.board_bits` pakuje planszę tak, że bit `y*WIDTH+x` odpowiada wierszowi `y`,
kolumnie `x` — czyli każdy wiersz to osobny bajt (`WIDTH=8`). `_patch_index` czyta
jeden bit tej maski naraz. Nowa `patch_indices` (`ntuple.py:_row_tables`) grupuje,
dla każdej łaty danego układu, pozycje po numerze wiersza, i buduje **raz, przy
pierwszym użyciu układu** (i trzyma w `_row_tables_cache`, klucz to krotka `layout`)
tabelę 256 wpisów na każdą parę (łata, wiersz): `tabela[bajt_wiersza]` to wkład
bitów tego wiersza do indeksu łaty, już przesuniętych na właściwą pozycję.
`patch_indices` liczy 8 bajtów wierszy raz na planszę, potem dla każdej łaty robi
tyle odczytów z tabeli, ile wierszy ta łata faktycznie dotyka (1 dla łaty-wiersza,
8 dla łaty-kolumny, 3 dla kwadratu 3×3) i sumuje je OR-em — identyczny wynik, bo
każdy bit indeksu pochodzi z dokładnie jednego wiersza planszy, tylko mniej pracy
Pythona: dla `AD` suma odczytów po wszystkich łatach spada z 452 (16×8 + 36×9,
jeden na komórkę) do 180 (8×1 + 8×8 dla `A`, plus 36×3 dla `D`). `_patch_index`
zostaje w kodzie jako referencja bit-po-bicie, używana tylko przez test
równoważności — sama nie jest już na gorącej ścieżce.

Stara `_patch_index` i `board_bits` (pakowanie planszy) są nietknięte; `value_from_indices`
(kolejność sumowania po tabelach wag) też — jedyna zmiana jest w tym, jak powstają
same indeksy.

## Test równoważności

`tests/test_ntuple.py::TestPatchIndicesMatchesBitwiseReference` — 1000 losowych plansz
(RNG deterministyczny, seed 158) na układ, osobno dla `A` i `AD`: `patch_indices`
(nowa) porównana bit w bit z `[_patch_index(bits, positions) for positions in layout]`
(referencja). Zielony.

## Wagi identyczne: 30 odcinków `AD`/`survival`

`python tools/train_ntuple.py --state <s> --out <w> --episodes 30 --episodes-per-run 30
--seed 42 --reward survival --layout AD`, ten sam seed, przed i po zmianie (kod przed:
commit `495cd91`, po: ten commit). Porównane pole `weights` w pliku `--out` (nie
`state.json` — ten niesie też `duration_s`, który ta sama zmiana poprawia, patrz niżej):

| | sha256 pliku wag |
|---|---|
| przed | `7205435de1ab1ae389c9666f26af8551a4a68d886790e91a3a04714fdf2f42ea` |
| po | `7205435de1ab1ae389c9666f26af8551a4a68d886790e91a3a04714fdf2f42ea` |

Identyczne. Powtórzone też przy okazji pomiaru przyspieszenia niżej (300 odcinków,
`--seed 1`): hash wag `e36f6e32da4c0a3db171778555138f4f41c4770af07a71b87a66b3203969e531`
przed i po, też identyczny.

## Przyspieszenie: to samo polecenie przed i po

**Trening `AD`/`survival`, 300 odcinków, `--seed 1`** (s/odcinek liczone z
`<stan>.log.jsonl`, jak w `docs/ntuple.md` — nie z pola `duration_s` w stanie):

| | s/odcinek | czas ścienny (300 odc.) |
|---|---|---|
| przed (`495cd91`) | 0,04986 | 15,09 s |
| po | 0,02551 | 7,79 s |

**≈1,95× szybciej** na odcinek treningu `AD`.

**`benchmark.py --candidate lookahead-ntuple:ntuple/survival-ad-best.json --n-seeds 30
--jobs 1 --issue 158`** (30 seedów stałych + 30 rotowanych, ten sam pomiar co #8):

| | czas pomiaru | średnia | mediana | p10 | przeżycie |
|---|---|---|---|---|---|
| przed (`495cd91`) | 299,5 s | 8435,03 | 6417,5 | 450,1 | 176,43 |
| po | 150,4 s | 8435,03 | 6417,5 | 450,1 | 176,43 |

**≈1,99× szybciej**, wynik benchmarku (średnia/mediana/p10/przeżycie) identyczny co do
ostatniej cyfry — spodziewane, bo `patch_indices` daje te same indeksy, a
`NTupleLookaheadPolicy`/przeszukanie wiązką ich nie modyfikują.

## `state["duration_s"]` bez gubienia przyrostów

Odkrycie #149 (`docs/ntuple.md`): `run_generational` liczyło
`state["duration_s"] = round(state["duration_s"] + elapsed, 1)` po każdym odcinku.
Dla partii krótszych niż ~0,05 s (typowe dla `A`, i dla wczesnych, krótkich partii
`AD`) każdy pojedynczy przyrost ginął w zaokrągleniu do 0,1 s: `round(0.0 + 0.03, 1)
== 0.0`, więc kolejny odcinek znów dodawał `0.03` do `0.0`, nie do prawdziwej sumy —
pole nigdy nie ruszało się z miejsca, niezależnie od liczby odcinków.

Poprawka: `state["duration_s"] += elapsed`, bez zaokrąglania po drodze — suma jest
teraz dokładna (pełna precyzja `float`), zaokrąglenie zostaje tam, gdzie było już
poprawne: per-odcinkowy wpis w `<stan>.log.jsonl` (`entry["duration_s"] = round(elapsed,
3)`, nietknięty). Test: `tests/test_train_ntuple.py::TestDurationAccumulation` —
5 odcinków po dokładnie 0,01 s (zegar zaślepiony przez `mock.patch`), `state["duration_s"]`
po przebiegu to `0.05`, nie `0.0`, jak dawałby stary kod.

## Nie zmienione

`board_bits`, `_patch_index` (referencja), `value_from_indices` (kolejność sumowania),
`NTupleValue.update`/`save`/`load`, sygnał/cel TD w `run_episode`, `game.py`,
`scoring.py`, `generator.py`, `pieces.py`, `features.py`, `benchmark.py`, pliki w
`ntuple/`. `reward_shape_changed: no` — żadna wartość zwracana przez `game.step`
ani punktacja/nagroda TD nie zostały ruszone, tylko sposób liczenia indeksów łat.

## Rotacja logu odcinków na pliki-bloki (#187)

Log odcinków (`<stan>.log.jsonl`) nie jest czytany przez sam trening (tylko przez
`read_log`, do testów i analizy krzywej), więc przy skali 0,5–1 mln odcinków `ADC`
groził tylko rozmiarem pliku do commitu, nie wydajnością. Pomiar istniejących logów
`ntuple/*.log.jsonl` (100 tys. odcinków każdy):

| plik | wpisów | B/wpis (średnio) | B/wpis (max) |
|---|---|---|---|
| `survival-adc-state.log.jsonl` | 100 000 | 142,2 | 164 |
| `survival-adc-ss-state.log.jsonl` | 100 000 | 149,7 | 164 |

Przy 1 000 000 odcinków jeden plik urósłby do ~14,2–15,0 MB × 10 ≈ 142–150 MB —
ponad próg odrzucenia commitu GitHuba (100 MB) i daleko ponad kryterium akceptacji
tego zadania (40 MB).

Zmiana: `tools/train_ntuple.py` dzieli log na pliki-bloki po `BLOCK_EPISODES = 150_000`
odcinków (`log_block`, `log_path(state_path, episode)`). Blok 0 (odcinki 1..150 000)
zachowuje nazwę sprzed zmiany, `<stan>.log.jsonl` — istniejące pliki w `ntuple/`
(wszystkie < 150 000 odcinków) wczytują się bez zmiany nazwy. Kolejne bloki to
`<stan>.log.NNNN.jsonl` (np. `<stan>.log.0001.jsonl` dla odcinków 150 001..300 000).
`read_log` łączy wszystkie bloki w kolejności odcinków — interfejs dla testów/analizy
się nie zmienił.

Szacunek rozmiaru bloku przy 164 B/wpis (zmierzony max powyżej): `150 000 × 164 B ≈
24,6 MB` — pod limitem 40 MB z zapasem ~38%, mimo że układ `ADC` (136 tabel wag) ma
najdłuższe wpisy logu spośród dotychczas trenowanych układów. Przy 1 000 000 odcinków
`ADC` to 7 plików bloków (6 pełnych po ~24,6 MB + 1 niepełny), żaden nie przekracza
budżetu.

Rotacja jest szczegółem zapisu na dysk: `_append_log_entries` grupuje wpisy po bloku
i dopisuje każdą grupę do właściwego pliku — cel TD i aktualizacja wag w `run_episode`
jej nie widzą. Test `tests/test_train_ntuple_eval.py::TestLogRotation::
test_weights_are_bit_identical_regardless_of_block_size` uruchamia ten sam trening
(`--reward survival --layout ADC`, 6 odcinków, seed 13) z `BLOCK_EPISODES` zmockowanym
na 2 i z wartością domyślną — plik wag (`--out`) wychodzi bitowo identyczny (ten sam
sha256) w obu przypadkach. Wznowienie działa też w poprzek granicy bloku
(`test_resuming_across_a_block_boundary_matches_continuous_run`) i ze stanu sprzed tej
zmiany, skopiowanego do katalogu tymczasowego (`tests/test_train_ntuple_eval.py::
TestResumeFromExistingRepoState`, na `ntuple/survival-adc-state.json`) — pliki w
`ntuple/` weryfikowane sha256 przed i po pozostają identyczne.

Nie zmienione (dodatkowo do listy wyżej): `state["log_bytes"]` nadal śledzi tylko plik
bloku aktywnego w chwili ostatniego udanego zapisu (truncate przy wznowieniu po
przerwanej sesji działa jak wcześniej, tylko na właściwym pliku bloku zamiast
jedynego pliku logu). `--curve-out` i punkty ewaluacji (`state["eval"]`) nie czytają
logu wcale — liczą się przyrostowo w `state["windows"]`/`state["eval"]["points"]`
podczas treningu, więc rotacja logu ich nie dotyczy.
