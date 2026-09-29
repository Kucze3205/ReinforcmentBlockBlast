# Drugi poziom przeszukiwania `lookahead-ntuple` przy `beam=128`: pomaga? da się tanio poprawić?

Zadanie: [#210](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/210). Kontynuacja diagnozy
[#202](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/202)
(`docs/przeszukanie-glebokie-diagnoza.md`) na rekordzie #201
(`lookahead-ntuple:ntuple/survival-adcga16-800k.json@beam=128`, drugi poziom domyślny
`samples=2 branch=2 inner_beam=1 inner_depth=1`). **Zaraportuj, nie wdrażaj jako domyślne** —
`lookahead-ntuple:<plik>` bez `@...` zostaje bitowo taki sam (`tests/test_lookahead_margin_regression.py`,
50 partii).

**Wynik w jednym zdaniu:** przy `beam=128` i `branch=2` (domyślnym) żaden zmierzony wariant drugiego
poziomu — wyłączenie (`samples=0`), więcej próbek (`samples` ∈ {4, 8, 16}) ani tania poprawka
marginesu (`margin`) — nie odróżnia się od domyślnej konfiguracji o więcej niż 1 se (sparowane); **drugi
poziom zostaje bez zmian**, a jedyny praktyczny wniosek to że `samples=0` daje tę samą jakość ~18% taniej
i to on, nie domyślna specyfikacja, jest wart zmierzenia w benchmarku cyklu 24.

## Propozycja (1) z #202 (podział próbek wybór/ocena): sprawdzona w kodzie, pominięta

Uwaga orchestratora do zadania kazała sprawdzić, zanim cokolwiek się wdroży: „w korzeniu drzewa
wartość zwycięzcy nigdzie dalej nie idzie, więc sam podział „wybór/ocena” nie zmienia **decyzji**”.
Potwierdzone czytaniem `LookaheadPolicy.act` (`policies.py:236-249`, numeracja po zmianach tego
zadania — mechanika bez zmian): pętla po `candidates` liczy `value` dla każdego kandydata i
zapamiętuje `best_action`/`best_value` tylko po to, żeby na końcu zwrócić `best_action` — `best_value`
nie trafia do żadnego dalszego porównania, żadnej rekurencji, żadnego zwracanego pola. Propozycja (1)
(rozdzielić próbki, które wybierają zwycięzcę, od próbek, które raportują jego wartość) usuwa
obciążenie **raportowanej wartości**, ale tu nic tej wartości dalej nie używa — usunięcie obciążenia w
polu, które i tak ginie po `return`, nie zmienia, który `first_action` wygra. Pomijam tę opcję zgodnie
z instrukcją zadania; nie została zmierzona, bo nie ma czego mierzyć (nie zmienia żadnej decyzji).

Tańsze dźwignie z treści zadania — „więcej próbek przy wąskim `branch`” (pytanie 2) i „mniejsza waga
drugiego poziomu, np. tylko rozstrzyganie remisów pierwszego poziomu” (pytanie 3) — **zmieniają**
decyzję (pierwsza: ten sam wybór spośród tych samych 2 kandydatów, ale inaczej uśredniony; druga:
inny, mniejszy zestaw kandydatów w ogóle dostaje drugi poziom), więc obie warte pomiaru.

## Poprawka z pytania 3: opcja `margin` w `policies.py`

`LookaheadPolicy`/`NTupleLookaheadPolicy` dostały nowy kwarg konstruktora `margin` (domyślnie `None`
— zachowanie bez zmian, sprawdzone testem regresji na 50 partiach). Gdy ustawiony, `_distinct_first_actions`
odcina kandydatów, których `score` pierwszego poziomu jest gorszy niż `margin` od najlepszego w
`frontier` — zamiast zawsze brać `branch` najlepszych niezależnie od tego, jak daleko w tyle są już na
płytkiej, pełnej (nie próbkowanej) ocenie. To dosłownie realizuje sugestię zadania: przy `branch=2`
(domyślnym) i `margin=0` drugi poziom dostaje tylko dokładne remisy pierwszego poziomu — praktycznie
nigdy się nie zdarzają na tych wagach (patrz niżej), więc `margin=0` **degeneruje się do `samples=0`**.
`margin=1` (rząd wielkości typowego rozstępu ocen między dwoma najlepszymi kandydatami na tych wagach,
zmierzony osobno: mediana ~1,07, model rozkładu silnie skośny w stronę zera) wpuszcza drugiego kandydata
częściej.

Specyfikacja wpina to przez `benchmark.parse_ntuple_spec`: `lookahead-ntuple:<plik>@margin=<liczba>`
(`benchmark.py`: `margin` to jedyny parametr `NTUPLE_SEARCH_PARAMS`, który może być ułamkowy — parser
próbuje najpierw `int`, potem `float`). `tools/measure_ntuple_search_grid.py` dostał dwa nowe wiersze,
`beam=128 margin=0` i `beam=128 margin=1`.

## Metoda pomiaru

`tools/measure_ntuple_search_grid.py --weights ntuple/survival-adcga16-800k.json` (wagi rekordu #201,
nowe `--weights`, domyślna wartość modułu zostaje przy wagach #195, więc stare wywołania bez tej flagi
dają bitowo te same specyfikacje co dotąd), `--seed-salt drugi-poziom-210` (nowa flaga, rozłączność z
`bench/seeds_fixed.json` sprawdzana jawnie przez `grid_seeds`, tak jak w #195 — inna sól niż `siatka-195`
z poprzedniej siatki, żeby nie mierzyć na dokładnie tej samej puli 300 seedów). **200 partii na wiersz**,
`move_cap` z `bench/config.json`, `--jobs 4`. `Δ vs domyślna` — sparowane na wspólnych seedach
(`benchmark.paired_delta`, `mean_diff_over_se` — czulsze niż `se` złożone z dwóch niezależnych ramion,
bo odejmuje wspólny szum seeda); wiersz odniesienia to `beam=128 s=2 b=2 in=1x1` (rekord #201, ten sam
co domyślna specyfikacja `lookahead-ntuple:<plik>@beam=128` bez dalszych parametrów). Surowe dane:
`docs/data/przeszukanie-drugi-poziom.json`.

## Tabela wyników

| wiersz | pytanie | wynik | se | przeżycie | `capped_pct` | s/partię | Δ vs domyślna | Δ/se (sparowane) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **domyślna** `beam=128 s=2 b=2 in=1×1` (rekord #201) | — | 86332,56 | 6437,69 | 642,11 | 5,0% | 1,047 | — | — |
| `beam=128 s=0` (bez 2. poziomu) | 1 | 82966,73 | 6032,40 | 593,64 | 5,0% | 0,859 | −3365,84 | **−0,38** |
| `beam=128 s=4 b=2` | 2 | 91211,46 | 6087,14 | 699,47 | 6,5% | 1,223 | +4878,90 | **+0,60** |
| `beam=128 s=8 b=2` | 2 | 83221,74 | 5633,15 | 616,85 | 5,0% | 1,284 | −3110,82 | **−0,38** |
| `beam=128 s=16 b=2` | 2 | 94221,04 | 6330,96 | 689,23 | 4,0% | 1,885 | +7888,48 | **+0,93** |
| `beam=128 margin=0` | 3 | 82966,73 | 6032,40 | 593,64 | 5,0% | 0,926 | −3365,84 | **−0,38** |
| `beam=128 margin=1` | 3 | 88359,10 | 6255,85 | 641,00 | 6,5% | 0,979 | +2026,55 | **+0,24** |

`margin=0` i `beam=128 s=0` mają **identyczne** `mean`/`se`/`survival_mean`/`capped_pct` — nie
zaokrąglenie, tylko ten sam wynik: przy `branch=2` na tych wagach dokładny remis pierwszego poziomu
(`score` dwóch kandydatów równy co do bitu) nie wystąpił ani razu w żadnej z 200 partii, więc
`_distinct_first_actions` z `margin=0` zawsze ucina do 1 kandydata — dokładnie to, co robi
`samples<=0`/`len(candidates)<2` w `act` (`policies.py:232-233`). To odpowiedź samo w sobie: „tylko
remisy” to w praktyce „nigdy”, nie licząc symbolicznego przypadku.

## Odpowiedzi na pytania zadania

1. **Ile daje drugi poziom przy `beam=128`?** Nieodróżnialnie od zera: `samples=0` wobec domyślnej to
   Δ/se = −0,38 (kierunek nawet lekko na korzyść **braku** drugiego poziomu, ale w granicach szumu).
   Przy szerokim pierwszym poziomie (`beam=128`) i wąskim `branch=2` drugi poziom nie kupuje ani nie
   szkodzi w sposób, który 200 partii odróżnia od szumu.
2. **Czy więcej próbek pomaga przy `branch=2`?** Brak spójnego kierunku: `s=4` i `s=16` wypadają
   nieznacznie **lepiej** (+0,60 se, +0,93 se), `s=8` nieznacznie **gorzej** (−0,38 se) — niemonotoniczne,
   żaden wynik nie przekracza nawet 1 se, więc żadnego z nich nie da się odróżnić od domyślnej. To
   inaczej niż w #202 (tam `branch=3` na `beam=8` dawało odróżnialną (Δ/se ≈ −1,9, potem potwierdzone
   przy 9,4 se na diagnozie obciążenia) stratę) — zgodne z hipotezą tamtej diagnozy, że przy **wąskim**
   `branch=2` przekleństwo optymalizatora jest „niegroźne”, bo prawie zawsze i tak wygrywa jeden z 2
   najlepszych płytkich kandydatów; samo zwiększanie `samples` (bez poszerzania `branch`) nie ma tu
   dużo do ugrania w żadną stronę.
3. **Tania poprawka (`margin`).** Zaimplementowana jako opcja domyślnie wyłączona (patrz wyżej).
   `margin=0` okazała się w praktyce tożsama z `samples=0` (patrz tabela) — nie jest to niezależny
   pomiar. `margin=1` (+0,24 se) jest nieodróżnialna od domyślnej, jak reszta wiersza. Poprawka nie
   pomaga wykrywalnie na tych wagach/tym `beam` — ale też nic nie psuje, więc pozostaje dostępna jako
   opcja specyfikacji na przyszłość (np. do przetestowania przy szerszym `branch`, gdzie diagnoza #202
   przewiduje, że powinna mieć więcej do ugrania).

## Wniosek

**Drugi poziom: zostaje.** Żaden zmierzony wariant (wyłączenie, więcej próbek, poprawka marginesu) nie
przekracza progu odróżnialności (~2 se) od domyślnej konfiguracji `samples=2 branch=2 inner_beam=1
inner_depth=1` przy `beam=128` na wagach rekordu. Domyślna specyfikacja `lookahead-ntuple:<plik>`
zostaje bez zmian (`tests/test_lookahead_margin_regression.py` potwierdza bitową identyczność na 50
partiach), zgodnie z Celem zadania.

**Jedna specyfikacja do benchmarku w cyklu 24:**
`lookahead-ntuple:ntuple/survival-adcga16-800k.json@beam=128,samples=0` — nieodróżnialna jakościowo od
rekordu (Δ/se = −0,38) za **18% niższy koszt na partię** (0,859 s wobec 1,047 s) i strukturalnie
prostsza (bez węzła losowego, bez ryzyka przekleństwa optymalizatora opisanego w #202 w ogóle — nie ma
czego obciążać). To jedyny wariant z tej siatki, który ma jakikolwiek praktyczny sens do zmierzenia na
oficjalnych seedach: reszta (`s=4/8/16`, `margin=0/1`) albo kosztuje więcej bez wykrywalnego zysku, albo
(w wypadku `margin=0`) po prostu powtarza `s=0` innym zapisem.

## Nietknięte pliki

`ntuple.py`, `ntuple_native.c`, `ntuple_native.py`, `tools/train_ntuple.py`, `game.py`, `scoring.py`,
`generator.py`, `bench/*` — bez zmian z tej sesji (drift `bench/config.json` względem `origin/main`
pochodzi z punktu rozgałęzienia `task/210`, sprzed tego zadania — `git diff` względem commita bazowego
gałęzi jest pusty na tych ścieżkach). `reward_shape_changed: no`.

Dotknięte celowo: `policies.py` (opcja `margin`), `benchmark.py` (spec `margin=...`, `float` fallback w
`parse_ntuple_spec`), `tools/measure_ntuple_search_grid.py` (`--weights`, `--seed-salt`,
`--baseline-label`, `capped_pct` w wyniku, nowe wiersze), testy (`tests/test_lookahead_policy.py`,
`tests/test_benchmark_ntuple_weights.py`, `tests/test_lookahead_margin_regression.py` + fixture).
