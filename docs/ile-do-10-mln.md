# Skąd biorą się punkty, ile postawień do 10 mln i rozstrzygnięcie `sd_diff`

Zadanie: [#119](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/119), domknięcie
[#112](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/112) i [#101](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/101).
**Ten dokument raportuje liczby, nie zmienia kodu** — `policies.py`, `features.py`, `game.py`,
`scoring.py`, `benchmark.py` i `bench/record.json` są nietknięte.

## Metoda

Narzędzie: `tools/measure_score_noise.py --detailed` (nowe w tym zadaniu, na bazie `--seed-file`/
`--series-out` z #112, odzyskanych cherry-pickiem `970d526`). Rozgrywa partie własną pętlą (nie
`benchmark.play_game`), żeby na każde postawienie rozbić przyrost punktów na `placement_points`
(`scoring.placement_points(piece)`) i `clear_points` (`gained - placement_points`, czyli
`scoring.clear_points(combo, lines)` **plus** ewentualny `FULL_CLEAR_BONUS` — oba pochodzą z tego
samego wywołania `apply_placement`, więc suma obu pól jest dokładnie równa `score` partii; rzadki
bonus za pełne wyczyszczenie planszy jest więc liczony razem z `clear_points`, nie osobno). Dla
combo liczy: maksimum, średnią combo w chwili czyszczenia, długość każdego nieprzerwanego łańcucha
(wartość `combo` tuż przed zerwaniem) i przyczynę zerwania — `brak_legalnego_czyszczenia`, gdy
żadna z dostępnych akcji tej tury nie wyczyściłaby linii (sprawdzone symulacją na kopii planszy,
`Board.copy()`, ten sam trik co `policies._simulate_placement`), albo `wybor_polityki`, gdy taka
akcja istniała, a polityka wybrała inną. Zerwanie to wyłącznie przejście `combo>0 → combo==0` bez
czyszczenia w tym postawieniu (`game.py:85-89`); łańcuch wciąż żywy w chwili końca partii (albo
sufitu ruchów) trafia do rozkładu długości osobno, jako **ucięty** (game.py go nie zerwał — partia
się po prostu skończyła), nie jako zerwanie.

Przebieg: `lookahead:weights.json`, **300 partii** na `bench/seeds_fixed.json` (pierwsze 300 —
dokładnie ten sam zestaw, na którym liczy `benchmark.py`), `move_cap=2000` z `bench/config.json`.
Zaczęte od 30 partii (72 s), podniesione do 100 (3 min 49 s) i do 300 (10 min 59 s), zgodnie z
kryterium akceptacji — czas na to pozwolił, więc oddany jest pełny zestaw benchmarku, nie próbka.
Dla rozstrzygnięcia `sd_diff` rozegrano **drugi** komplet 300 partii na tych samych seedach,
`lookahead:weights-lookahead.json` (10 min 37 s) — to jest dokładnie ramię `candidate` z
`bench/111-cem.json`, `weights.json` to ramię `previous` (potwierdzone hashami niżej). Surowe
serie (nie commitowane w pełnej formie repo-śledzonych plików do dalszej analizy, ale zapisane w
`docs/data/`, więc odtwarzalne bez ponownego 22-minutowego przebiegu):

    python3 tools/measure_score_noise.py --policy lookahead --weights-file weights.json \
        --n-games 300 --seed-file bench/seeds_fixed.json --detailed \
        --out docs/data/serie-300-lookahead-previous-summary.json \
        --series-out docs/data/serie-300-lookahead-previous.json

    python3 tools/measure_score_noise.py --policy lookahead --weights-file weights-lookahead.json \
        --n-games 300 --seed-file bench/seeds_fixed.json --detailed \
        --out docs/data/serie-300-lookahead-candidate-summary.json \
        --series-out docs/data/serie-300-lookahead-candidate.json

**Reprodukowalność sprawdzona wprost**: `source_hashes()` z `benchmark.py` dla `game.py`,
`scoring.py`, `generator.py`, `pieces.py`, `features.py`, `policies.py`, `benchmark.py` są dziś
identyczne z zapisanymi w `bench/111-cem.json` — kod symulatora się nie ruszył od tego pomiaru.
Przy `epsilon=0` (deterministyczne polityki) średnie wyniku z moich 300 partii wychodzą
`6171,04` (`weights.json`) i `5772,95` (`weights-lookahead.json`) — **co do grosza** te same
liczby, co `arms.previous.fixed.mean` i `arms.candidate.fixed.mean` w `bench/111-cem.json`. To
nie jest przybliżenie — to bitowa reprodukcja tego samego pomiaru, więc rozstrzygnięcie `sd_diff`
niżej porównuje to samo, nie coś zbliżonego.

## (a) Skąd biorą się punkty: `clear_points` kontra `placement_points`

300 partii, `lookahead:weights.json` (ramię `previous`):

| źródło | suma punktów | % wyniku |
|---|---:|---:|
| `placement_points` | 129 057 | 6,97% |
| `clear_points` (combo + rzadki pełny clear) | 1 722 256 | 93,03% |
| **razem** | **1 851 313** | **100%** |

Potwierdza to hipotezę z sekcji `## Cel`: **prawie wszystko bierze się z combo**, nie z samego
stawiania klocków. Drugie ramię (`weights-lookahead.json`, `candidate`) daje ten sam obraz:
`6,97%`/`7,16%` placement, `93,03%`/`92,84%` clear — stabilne między dwoma różnymi wektorami wag
tej samej polityki.

## (b) Rozkład długości nieprzerwanych łańcuchów combo

300 partii `weights.json`: **902 zerwane łańcuchy** + **285 ucięte końcem partii** (łańcuch wciąż
żywy, gdy gra się skończyła).

| | zerwane (902) + ucięte (285), razem 1187 |
|---|---:|
| mediana | 9 |
| p90 | 26,0 |
| maksimum | 96 |

(`weights-lookahead.json`: mediana 9, p90 26,0, maksimum 66 — ten sam rząd wielkości.)

Łańcuchy **nie rosną bez ograniczeń** — mediana to 9 kolejnych czyszczeń, nie setki. To jest
bezpośrednia przyczyna, dla której oszacowanie `≈5n²` z sekcji `## Cel` (które zakłada właśnie
nieograniczony wzrost combo) nie wytrzymuje pomiaru — patrz werdykt niżej.

## (c) Ile razy na partię łańcuch się zrywa i co go zrywa

| | `weights.json` (previous) | `weights-lookahead.json` (candidate) |
|---|---:|---:|
| zerwań / partię (średnio) | 3,01 | 2,77 |
| `brak_legalnego_czyszczenia` | 901 (99,89%) | 825 (99,28%) |
| `wybor_polityki` | 1 (0,11%) | 6 (0,72%) |

**Łańcuch zrywa się niemal wyłącznie dlatego, że w danej turze żadna dostępna akcja nie czyściłaby
linii** — nie dlatego, że polityka miała okazję i ją zignorowała. `lookahead` (jedno- i
dwupółruchowe przeszukiwanie w przód, `docs/lookahead.md`) prawie nigdy nie zostawia czyszczenia
na stole, gdy jest dostępne; jeśli łańcuch pada, to z powodu geometrii planszy/tacki, nie wyboru
polityki. To ma znaczenie dla kierunku cyklu: **skracanie łańcuchów przez lepszą politykę ma mały
sufit poprawy** (0,1–0,7% zerwań to w ogóle „wybór”), więc dłuższe łańcuchy trzeba by wymuszać
przez lepsze rozstawianie klocków na wcześniejszych turach (przygotowanie planszy), nie przez samo
niemarnowanie okazji do czyszczenia w danej turze.

## (d) Ile postawień potrzeba do 10 mln

Z 300 partii `weights.json`: `mean(score)=6171,04`, `mean(survival)=110,5`,
`max(survival)=524` (z **żadnej** partii nieuciętej sufitem `2000` — `capped=false` we
wszystkich 300, zgodnie z `overfit_gap`/`capped_pct=0%` w `bench/111-cem.json`).

**Tempo stałe** (średnie punkty na postawienie w całej serii, `Σscore/Σplacements = 55,85`):

```
n = 10 000 000 / 55,85 ≈ 179 057 postawień
```

**Tempo rosnące z combo** — trzy dopasowania modelu `score ≈ k·n²` (bo `clear_points` skaluje się
z combo, a combo rośnie z liczbą postawień) do tej samej serii, żeby pokazać wrażliwość na metodę:

| dopasowanie | `k` | `n` do 10 mln |
|---|---:|---:|
| najmniejsze kwadraty (`Σscore·n²/Σn⁴`, ważone dużymi partiami) | 0,213 | ≈ 6 852 |
| średnia `score/n²` po partii | 0,524 | ≈ 4 369 |
| mediana `score/n²` po partii | 0,464 | ≈ 4 642 |
| regresja log-log (`score = e^a·n^b`, wykładnik dopasowany, nie założony `2`) | `b=1,55` | ≈ 14 982 |

Regresja log-log jest tu najuczciwsza, bo nie narzuca wykładnika `2` — i wychodzi **`1,55`**,
między liniowym a kwadratowym, zgodnie z (b): łańcuchy pękają regularnie (mediana 9), więc combo
nie akumuluje się przez całą partię jak zakładał wzór z `## Cel`.

**Każde z tych oszacowań — od 4 369 do 179 057 postawień — jest daleko poza tym, co partia
kiedykolwiek osiąga w praktyce**: najdłuższa z 300 partii przetrwała 524 postawienia, średnia to
110,5, a partia kończy się przez zapełnienie planszy (brak legalnego ruchu), nie przez sufit `2000`
— żadna z 600 rozegranych partii (obu ramion) nie została ucięta sufitem. 10 mln punktów jest więc
nieosiągalne dla tej polityki i tych wag w praktyce, niezależnie od tego, który wariant tempa
przyjmiemy — ograniczeniem nie jest sufit ruchów, tylko to, że gra kończy się dużo wcześniej.

## Werdykt: `≈5n²` z sekcji `## Cel`

**Nie zgadza się z pomiarem.** Górna granica `5n²` (10 mln przy `n≈1414`) zakładała czyszczenie
jednej linii na każde postawienie **bez zrywania łańcucha** — combo rosnące bez ograniczeń przez
całą partię. Pomiar pokazuje, że tak nie jest:

- mediana długości nieprzerwanego łańcucha to **9**, nie setki czy tysiące (b);
- łańcuch zrywa się średnio **3 razy na partię**, niemal zawsze wymuszony brakiem legalnego
  czyszczenia (99,89%), a nie wyborem polityki (c);
- rzeczywisty współczynnik przy `n²` (dopasowanie LSQ) to `0,213` — **~24× mniejszy** niż
  teoretyczne `5`; rzeczywisty wykładnik zależności `score(n)` (regresja log-log) to `1,55`, nie
  `2`.

Skutek: liczba postawień potrzebna do 10 mln jest **3–130× większa** niż `1414` z `## Cel`
(zależnie od przyjętego modelu tempa), i w każdym wariancie przekracza jakąkolwiek partię
kiedykolwiek zaobserwowaną (max 524 z 600 partii). Kierunek cyklu 9 (który nie wiedział, czy gonić
długość partii czy punkty na postawienie) miał rację podejrzewać problem — ale odpowiedź nie jest
„to się i tak nie wydarzy pod sufitem 2000 ruchów”, tylko **„gra kończy się o dwa rzędy wielkości
za wcześnie, żeby 10 mln było w ogóle w zasięgu tej polityki”**; poprawa musiałaby wydłużyć
przeżycie partii (dziś ~110 postawień), nie tylko podnosić tempo punktowania na postawienie.

## Rozstrzygnięcie `sd_diff`

`bench/111-cem.json` raportuje dla `kandydat vs previous` (`lookahead:weights-lookahead.json` vs
`lookahead:weights.json`, 300 seedów stałych): `sd_diff = 9035,82`, `se_diff = 521,68`.

Policzone bezpośrednio z parowanych różnic `candidate − previous` na tych samych 300 seedach
(`statistics.pstdev`, ta sama funkcja, której używa `benchmark.paired_delta`):

```
sd_diff (moje, pary) = 9035,82
se_diff (moje, pary) = 521,68
```

**Identyczne co do drugiego miejsca po przecinku** z `bench/111-cem.json` — oczekiwane, bo kod
symulatora jest bit-w-bit ten sam (hashe wyżej) i polityki są deterministyczne (`epsilon=0`).
`bench/111-cem.json`'s `sd_diff` jest więc **policzone poprawnie** dla tego, co miało policzyć.

Skąd w takim razie luka z `√(σ²+σ²) ≈ 7484` z `## Cel`? Ta liczba pochodzi z
`docs/szum-oceny-kandydata.md` (#101) i jest policzona dla **innej pary ramion na innej populacji
seedów**: `sigma(tray:weights.json)=4423,98` i `sigma(lookahead:weights.json)=6036,91`, obie na
**150 seedach treningowych** (rozłącznych z benchmarkiem, `tools.tune_weights.training_seeds()`).
To porównanie `tray` kontra `lookahead` — dwie **różne polityki**. `bench/111-cem.json` porównuje
`lookahead` kontra `lookahead` — **ta sama polityka, dwa różne wektory wag** — na **300 seedach
benchmarku** (`bench/seeds_fixed.json`), zupełnie innej populacji map. `7484` nigdy nie było
oszacowaniem sigmy różnicy dla pary z `bench/111-cem.json`; porównywanie go z `9035,82` to
zestawienie dwóch niepowiązanych pomiarów, nie sprzeczność w żadnym z nich.

Policzone poprawnie, na **tej samej** parze ramion i **tej samej** populacji seedów co
`bench/111-cem.json` (moje 300 partii wyżej): `sigma(previous, bench_seeds) = 7602,86`,
`sigma(candidate, bench_seeds) = 5984,85` (obie zauważalnie wyższe niż na seedach treningowych —
zgodnie z pytaniem otwartym nr 3 w `docs/szum-oceny-kandydata.md`: sigma zależy od populacji
seedów). Założenie niezależności dałoby:

```
sqrt(7602,86² + 5984,85²) ≈ 9675,85
```

czyli **więcej** niż zmierzone sparowane `sd_diff = 9035,82` — zgodnie z oczekiwaniem CRN (wspólne
seedy dla obu ramion w `benchmark.py`): korelacja wynik-po-wyniku między `candidate` a `previous`
na tym samym seedzie jest dodatnia (Pearson `0,1316`), więc wariancja różnicy jest **mniejsza** niż
suma niezależnych wariancji, tak jak przewiduje teoria CRN — nie większa, jak sugerowałoby błędne
porównanie z `7484`.

**Werdykt jednym zdaniem**: `sd_diff = 9035,82` w `bench/111-cem.json` jest policzone poprawnie
(zreplikowane bit-w-bit); `7484` z #101 jest też policzone poprawnie dla tego, co miało mierzyć
(`tray` vs `lookahead` na seedach treningowych), ale **nie jest właściwym komparatorem** dla
`sd_diff` z #111 — to zestawienie dwóch różnych par ramion na dwóch różnych populacjach seedów, nie
błąd w żadnym z dwóch obliczeń, i porównane poprawnie (ta sama para, ta sama populacja) sparowany
`sd_diff` wychodzi **mniejszy** niż niezależne oszacowanie, dokładnie jak powinien przy CRN. **Każda
dotychczasowa promocja rekordu oparta na `se_diff` z `benchmark.py` stoi na poprawnie policzonej
liczbie** — nie ma tu problemu nadrzędnego do zaraportowania.

## Czego nie wiem

- Czy wykładnik `1,55` z regresji log-log jest stabilny między różnymi politykami/wagami — policzony
  tylko dla `lookahead:weights.json` na 300 partiach; `weights-lookahead.json` ma bardzo podobny
  rozkład długości łańcucha (mediana 9), więc spodziewałbym się podobnego wykładnika, ale tego nie
  dopasowałem osobno.
- Dlaczego `sigma` na seedach benchmarku (`7602,86`/`5984,85`) jest wyraźnie wyższa niż na seedach
  treningowych zmierzonych w #101 (`6036,91` dla tego samego `weights.json`) — różnica populacji
  map, nie zbadana głębiej tutaj (poza zakresem tego zadania, ale warta odnotowania: benchmark i
  trening CEM widzą różny rozrzut trudności).
- Czy `0,72%` zerwań „wyborem polityki” w ramieniu `candidate` (6 z 831, wobec `0,11%`/1 z 902 w
  `previous`) to sygnał, czy szum na małej liczbie zdarzeń — nie testowałem istotności różnicy.
