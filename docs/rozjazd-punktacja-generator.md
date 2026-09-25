# Rozjazd: punktacja i generator — gałąź domyślna kontra `wayfinder/38-generator`

Bilet: [#50](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/50).
Zaraportowano, nie naprawiono — zgodnie z poleceniem issue, żaden plik silnika
(`scoring.py`, `game.py`, `generator.py`, `pieces.py`, `board.py`) nie jest
ruszony w tym commicie.

Gałąź `wayfinder/38-generator` niesie trzy commity, które nigdy nie zostały
scalone do gałęzi domyślnej:

| commit | co robi | bilet |
|---|---|---|
| `6f4b273` | dodaje `playability.py` (grywalność tacki na bitboardzie) i `FillPolicy` w `policies.py` — **żadnej zmiany w `game.py`/`scoring.py`** | #37 |
| `eae980f` | drabinka punktów: `U(combo)` 10/15/20 zamiast stałego `10`; combo rośnie o liczbę wyczyszczonych linii, nie o 1 | #33 |
| `022d410` | generator zależny od planszy: wagi typów + powtórzenie + filtr grywalności; `game.py` zaczyna wołać `next_pieces(self.board.grid)` | #38 |

Gałąź domyślna (`main`) w tym samym miejscu ma `scoring.py` zamrożone na
pomiarze z `docs/calibration-assumptions.md` (sekcja Z-9, „Pomiar 1 z 3 (R10)”,
2026-09-21, apka 10.7.5) i `generator.py` bez świadomości planszy (losowanie
niezależne typ→poza, Z-6 nierozstrzygnięte).

## 1. Tabela: reguła po regule

| Reguła | Gałąź domyślna (`main`) | `wayfinder/38-generator` | Podstawa każdego wariantu |
|---|---|---|---|
| Jednostka bazowa za 1 linię, `U` | stała `10` niezależnie od combo — `scoring.py:26-32` (`line_bonus`) | schodkowa `combo_unit(combo)`: `10` dla combo 1–5, `15` dla 6–10, `20` od 11 wzwyż — `scoring.py` po `eae980f` | main: Z-1, 18 ruchów z mostu, sesja R10 z 2026-09-21 ([#18](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/18)). `wayfinder`: pomiar z 11 przebiegów mostu, 914 czyszczeń ([#33](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/33), commit `eae980f`, `tools/analyze_ladder.py`) |
| Przyrost combo po czyszczeniu | `self.combo += 1` niezależnie od liczby linii — `game.py:78` | `self.combo += lines` — czyszczenie 2 linii na raz podnosi combo o 2 | main: Z-2, ten sam pomiar R10 (2 linie przy combo 0 → bonus 20, nie 40). `wayfinder`: `eae980f`/#33 — autorzy twierdzą, że R10 pomylił przyrost combo z wygasaniem drabinki przy wieloliniowych ruchach powyżej combo 16 |
| Bonus wielolinijkowy `B(l)`, `l≥2` | `10 * l * (l-1)` | `U(combo) * l * (l-1)` — ten sam kształt, ale `U` już nie jest stałą `10` | jak wyżej |
| Bonus za pełne wyczyszczenie planszy | `FULL_CLEAR_BONUS = 300` (`scoring.py`, `game.py:89-90`) | bez zmian w tych trzech commitach — nadal `300` na tej gałęzi w tym punkcie historii | main: dwa źródła referencyjne dają 300 (Z-4 pozostaje niepotwierdzone na tej gałęzi commitów; osobna gałąź `wayfinder/30-generator` już to zmierzyła na zero, ale to poza budżetem tego biletu) |
| Pula typów klocków / orientacji | 15 typów kanonicznych, 41 orientacji (`pieces.py`, niezmienione żadnym z trzech commitów) | bez zmian w typach; `022d410` dodaje tylko wagi *między* tymi samymi 15 typami | wspólne dla obu gałęzi — Z-5 |
| Rozkład doboru typu w tacce | jednostajny 1/15 na typ, potem 1/n na pozę — `generator.py::_next_piece` przed `022d410` | nierówne wagi `WAGI` (14 wolnych parametrów) na typ, poza nadal jednostajna w obrębie typu | main: założenie modelowe autora referencji, nigdy nie zmierzone (Z-6). `wayfinder`: `022d410`/#38, dopasowanie do 744 unikalnych tacek z logów mostu, `tools/analyze_generator.py`, model B (wagi+filtr) wygrywa AIC 15727,1 vs 15900,8 (ślepe wagi) vs 15818,5 (wagi warunkowane zapełnieniem) |
| Powtórzenie typu w tacce | brak — trzy klocki losowane niezależnie | klocek po pierwszym z p=0,09 kopiuje typ innego klocka z tej samej tacki | `022d410`/#38 — obserwacja 37,0% tacek z powtórzonym typem vs 23,1% przewidywane przez model B bez tego parametru |
| Świadomość planszy przy losowaniu tacki | brak — `next_pieces()` bez argumentu planszy | `next_pieces(grid)`: przelosowanie tacki do 200 prób, aż `playability.all_fit` potwierdzi, że wszystkie trzy klocki wejdą po kolei | `022d410`/#38, oparte na wcześniejszym pomiarze grywalności z `6f4b273`/#37 (`policies.FillPolicy`, dwa przebiegi po 200 ruchów, 0 przegranych partii mimo zapychania planszy do 49/64 pól) |

## 2. Przykład liczbowy: ten sam ruch, dwa wzory

Ruch: postawienie klocka o 4 komórkach, które czyści **2 linie jednocześnie**,
przy stanie **combo tuż przed tym ruchem = 9**. Kolejność w kodzie: `apply_placement`
najpierw inkrementuje `self.combo`, potem woła `clear_points(self.combo, lines)`
(`game.py:77-80`).

| krok | gałąź domyślna | `wayfinder/38-generator` |
|---|---|---|
| combo po tym ruchu | `9 + 1 = 10` | `9 + 2 = 11` |
| `U`/`B(1 linia)` przy tym combo | `line_bonus` nie patrzy na combo → `10` na linię | `combo_unit(11) = 20` (próg 10→11 właśnie przekroczony) |
| `B(2 linie) = U · l · (l-1)` | `10 · 2 · 1 = 20` | `20 · 2 · 1 = 40` |
| `clear_points(combo, 2) = combo · B(2)` | `10 · 20 = 200` | `11 · 40 = 440` |
| `gained` (punkty za postawienie + czyszczenie) | `4 + 200 = 204` | `4 + 440 = 444` |

**Różnica: 444 vs 204 — 2,18×**, w kierunku wayfinder-wyżej. Rozjazd ma dwa
niezależne źródła, które się mnożą: (a) combo rośnie o 2 zamiast o 1, więc
`wayfinder` trafia próg `>10` już przy tym ruchu, podczas gdy `main` zostaje
na combo 10; (b) nawet przy tym samym combo `U` z `wayfinder` jest ≥ stałej
`10` z `main` (równe dla combo ≤5, wyżej powyżej).

Dla kontrastu — pierwsze czyszczenie w partii (combo przed ruchem = 0,
1 linia, klocek 1-komórkowy) oba wzory się zgadzają:
`main`: `1 + 1·10 = 11`. `wayfinder`: combo `0+1=1`, `combo_unit(1)=10`,
`1 + 1·10 = 11`. Rozjazd jest więc **narastający z długością gry i z liczbą
wieloliniowych czyszczeń**, nie stały procent — dokładnie dlatego linie
bazowe benchmarku (§5) rozjeżdżają się bardziej niż różnica w pojedynczym
ruchu sugeruje.

Test z samej gałęzi (`tests/test_engine.py`, `eae980f`) potwierdza kierunek
na wysokim combo: `clear_points(30, 1)` wg `wayfinder` = `30·20 = 600`,
wg wzoru `main` na tym samym combo byłoby `30·10 = 300` — też dokładnie 2×.

## 3. Czy `eae980f`/`022d410` zmieniają nagrodę `game.step`, czy tylko wynik partii

**`eae980f` zmienia nagrodę zwracaną przez `game.step`, nie tylko licznik wyniku.**
`game.step()` (`game.py:47-61`) woła `apply_placement()`, które liczy `gained`
i zwraca je jako pierwszy element krotki (`game.py:61`, `return gained, ...`) —
to jest właśnie sygnał nagrody, którego uczy się agent (patrz `agent.py`/pętla
treningowa, gdzie pierwszy element `step()` jest nagrodą). `eae980f` zmienia
dwie rzeczy bezpośrednio na tej ścieżce:

- `game.py:78`: `self.combo += 1` → `self.combo += lines`,
- `scoring.py`: `line_bonus`/`clear_points` — `B(l)` przestaje być stałą i
  zależy teraz od `combo` przez `combo_unit`.

Obie zmiany wchodzą do `gained` w tym samym ruchu, w którym następuje
czyszczenie (`game.py:80`, `gained += clear_points(self.combo, lines)`), więc
trafiają do agenta natychmiast, a nie tylko do skumulowanego `self.score`
widocznego w statystykach partii. To jest zdanie, przed którym ostrzega
issue: `eae980f` **nie** jest kosmetyczną zmianą wyświetlanego wyniku.

**`022d410` nie zmienia nagrody zwracanej przez `game.step`.** Jego jedyna
zmiana w `game.py` to dwa wywołania (`game.py`, w `reset()` i w gałęzi
`round_placement == 3` wewnątrz `apply_placement()`):
`self.generator.next_pieces()` → `self.generator.next_pieces(self.board.grid)`.
`scoring.py` nie jest w ogóle dotknięty przez ten commit (patrz `git show
022d410 --stat` — plik nieobecny na liście). Funkcja nagrody `f(stan, akcja) →
gained` jest identyczna przed i po `022d410`. Zmienia się za to **rozkład
stanów i akcji, które w ogóle się zdarzają**: filtr grywalności eliminuje
tacki, których nie da się w całości rozegrać, więc znika pewna klasa ruchów
kończących partię (i tym samym ujemnych nagród `-5` za `game_over`) oraz
zmienia się częstość, z jaką pojawiają się okazje do wieloliniowych czyszczeń.
To zmiana dynamiki środowiska (MDP), nie zmiana kształtu nagrody.

`6f4b273` nie dotyka `game.py` ani `scoring.py` wcale (`git show 6f4b273
--stat`: `.github/workflows/bridge.yml`, `bridge.py`, `playability.py`,
`policies.py`) — zero wpływu na nagrodę.

## 4. Testy, które przyjeżdżają z tą gałęzią

Issue #50 wspomina `tests/test_ladder.py` jako osobny plik — **taki plik nie
istnieje** ani na `wayfinder/38-generator`, ani na `main`
(`git ls-tree -r origin/wayfinder/38-generator --name-only | grep ladder`
zwraca tylko `tools/analyze_ladder.py`). Testy drabinki punktów leżą w
`tests/test_engine.py`, dopisane przez `eae980f`:

- `TestScoringFormula.test_ladder_has_three_steps_and_no_fourth` — sprawdza
  `combo_unit` na progach 1/5/6/10/11/16/17/39/100 i trzy przykłady `clear_points`.
- `TestComboMechanics.test_combo_rises_by_lines_cleared_not_by_one` — stawia
  klocek czyszczący 2 linie i sprawdza `game.combo == 2` oraz `gained == 2 + 2*20`.

`022d410` dopisuje do tego samego pliku `TestGeneratorTacki` (4 testy: sumowanie
wag do 1,0; że tacka z planszy zawsze wchodzi albo plansza jest w pełni
zablokowana nawet po 200 próbach; że generator kończy na pełnej planszy zamiast
się zapętlić; że nadwyżka powtórzonych typów przekracza 31%) i zamienia
`test_sampling_is_uniform_over_types_not_poses` na
`test_poses_are_uniform_within_a_type` (bo poza w obrębie typu jest wciąż
jednostajna, ale typ już nie).

**Czy przechodzą na drzewie `main` po samym przeniesieniu punktacji:** próbowano
to sprawdzić przez `git cherry-pick -n eae980f` na czystym drzewie `origin/main`
w tymczasowym `git worktree` (bez commitowania, worktree usunięty po teście).
Wynik cherry-picka to **trzy konflikty**, wszystkie mechaniczne, nie merytoryczne:

- `scoring.py` — konflikt tylko w docstringu modułu (opis wzoru); ciała funkcji
  (`combo_unit`, `line_bonus`, `clear_points`) scaliły się bez konfliktu.
- `tests/test_engine.py` — konflikt w linii importu (`main` importuje
  `FULL_CLEAR_BONUS`, `wayfinder` dodaje `Piece`, `plausible`, `combo_unit`) —
  rozwiązanie to suma obu zestawów importów.
- `policies.py` — jedyny konflikt z realną treścią: `main` ma w
  `_immediate_gain` blok `board.clear_lines(...)` + `FULL_CLEAR_BONUS`, którego
  nie ma w przodku `wayfinder/38-generator` (rozbieżność sprzed tego biletu,
  niezwiązana z #33/#38 — `_immediate_gain` ewoluowała inaczej na obu gałęziach
  po punkcie rozejścia `92f6ea5`). Sama zmiana z `eae980f`
  (`game.combo + 1` → `game.combo + lines`) nakłada się na ten blok bez
  sprzeczności.

Po ręcznym rozwiązaniu tych trzech konfliktów (suma treści, żadna linia
odrzucona) drzewo się kompiluje strukturalnie (import się zgadza, funkcje
istnieją). **Nie udało się jednak wykonać samych testów** — środowisko sesji
implementera blokuje uruchamianie `python3`/`pytest` (polecenie odrzucone przez
politykę uprawnień, niezależnie od argumentów, także dla `python3 -c
"print(1)"`). To ograniczenie tej sesji, nie właściwość kodu — werdykt „testy
zielone po przeniesieniu” wymaga uruchomienia przez sesję, która ma do tego
uprawnienia (np. `rola:verifier` albo runner z innymi uprawnieniami Bash).

## 5. Linie bazowe benchmarku

Wszystkie trzy przebiegi: `policy=greedy`, 300 seedów, `move_cap=2000`,
`epsilon=0.0` (config identyczny we wszystkich trzech plikach).

| plik | commit | `scoring.py` hash | `pieces.py` hash | `generator.py` hash | mean | mediana | p10 | przeżycie (postawienia) | overfit_gap_pct |
|---|---|---|---|---|---|---|---|---|---|
| `bench/43d1e7cf8035132ea52f67865c3473aefeda8741.json` | `43d1e7cf` (aktualna `main`, wzór zamrożony, #17) | `1e4a1b8730243ce6` | `7d857149777bdab6` | — (brak w `source_hashes`) | **704,79** | 486,0 | 160,0 | 34,99 | 2,05% |
| `bench/eae980fd02c720a5362873982a5402d48649d824.json` | `eae980f` (drabinka punktów, #33) | `31bd0b7dad74b0be` | `e6647a52ac266624` | — | **1002,61** | 589,5 | 161,9 | 34,92 | 5,53% |
| `bench/022d410c565316c3edf4225151eb625d1a5af7fd.json` | `022d410` (generator zależny od planszy, #38) | `31bd0b7dad74b0be` | `e6647a52ac266624` | `307d7885f2dccaa7` | **3104,74** | 1619,5 | 319,7 | 57,3 | 12,35% |

Uwaga do tabeli: `pieces.py` różni się między `main` i `wayfinder/38-generator`
hashem, ale **nie pulą klocków** — jedyna różnica to funkcja pomocnicza
`plausible()` dodana na gałęzi `wayfinder` (odczyt tacki z mostu), niezwiązana
z #33/#38 i nieujęta w tym bilecie jako engine change do naprawy.

Odczyt kierunku i skali:

- **Sama drabinka punktów (`eae980f` względem `main`) podnosi średnią o
  +42% (704,79 → 1002,61)** przy praktycznie tym samym przeżyciu (34,99 →
  34,92 postawień) — spójne z §2: ten sam styl gry, wyżej punktowany, bo combo
  rośnie szybciej i drabinka mnoży wysokie combo przez 2× względem stałej `10`.
- **Generator zależny od planszy (`022d410` na bazie już podniesionej punktacji)
  dokłada kolejne +210% średniej (1002,61 → 3104,74) i +64% przeżycia
  (34,92 → 57,3 postawień)** — to już nie jest efekt samej punktacji: filtr
  grywalności wydłuża partie (mniej ślepych końców gry), a dłuższa partia z
  drabinką punktów, która rośnie z długością comba, mnoży się w wyniku.
  `overfit_gap_pct` też rośnie monotonicznie (2,05% → 5,53% → 12,35%) — każda
  z tych zmian sprawia, że polityka `greedy` coraz bardziej różni się między
  zestawem seedów `fixed` i `rotated`, czyli coraz mocniej dopasowuje się do
  konkretnej gry, jaką stała się symulacja.

**Żadna z tych trzech liczb nie jest porównywalna z drugą przez prostą
proporcję** — `eae980f` zmienia funkcję nagrody, `022d410` zmienia dynamikę
środowiska (dobór klocków), więc `3104,74 / 704,79 ≈ 4,4×` miesza oba efekty
i nie mówi, ile z tego to punktacja, a ile grywalność.

## 6. Zgodność z ograniczeniem „żaden plik silnika nie zmieniony”

`git diff --name-only origin/main...HEAD` w tej sesji nie zawiera `scoring.py`,
`game.py`, `generator.py`, `pieces.py` ani `board.py` — jedyna zmiana jest ten
plik.
