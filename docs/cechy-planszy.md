# Cechy planszy i `HeuristicPolicy`

Zadanie: [#57](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/57). Kierunek
uzasadniony w `docs/research/kierunek-algorytmiczny.md` (c): w tej rodzinie gier wygrywa
decyzja 1-ply nad dobrą funkcją oceny planszy, nie przeszukiwanie w czasie gry. Ten
dokument opisuje fundament — `features.py` i `HeuristicPolicy` (`policies.py`) — oraz
dwa pomiary zlecone przez to samo issue: wynik `HeuristicPolicy` na tle zachłannej
i rozgałęzienie gry.

**Wagi poniżej są dobrane ręcznie, na oko.** Strojenie to osobne zadanie — nie zostało
tu zrobione nawet tam, gdzie widać, że dałoby się lepiej.

## Cechy (`features.py`)

Kolejność zgodna z `FEATURE_NAMES`. Kategorie (kara za fragmentację/dziury, nagroda za
elastyczność) przeniesione z tabeli Dellacherie-Thiery cytowanej w (c) — nie liczby,
bo mechanika czyszczenia linii+kolumn na planszy 8×8 bez spadania jest inna niż w
Tetrisie.

| # | cecha | waga domyślna | uzasadnienie |
|---|---|---:|---|
| 1 | `occupied_cells` — liczba zajętych pól | -0.5 | mniej zajętych pól po ruchu (czyli więcej wyczyszczonych linii) zostawia więcej miejsca na kolejne klocki. |
| 2 | `surrounded_empty` — puste pole otoczone z 4 stron (zajęte pole albo krawędź) | -10.0 | takie pole da się odzyskać wyłącznie wyczyszczeniem całej linii/kolumny, więc to najdroższy błąd z sześciu — analogon „holes” z Tetrisa, tam też najmocniej karane. |
| 3 | `empty_regions` — liczba spójnych obszarów pustych | -2.0 | jeden duży obszar mieści więcej kształtów niż ta sama liczba pustych pól rozbita na kawałki — kara za rozdrobnienie, nie za samą pustkę (którą liczy cecha 1). |
| 4 | `largest_empty_rect` — pole największego pustego prostokąta | +1.0 | duże klocki (belka 1×5, kwadrat 3×3) mieszczą się tylko w spójnym prostokącie odpowiedniego rozmiaru; nagradza trzymanie takiej rezerwy. |
| 5 | `near_full_lines` — liczba wierszy i kolumn, którym brakuje ≤2 pól do pełna | +3.0 | to bezpośredni prekursor punktowanego czyszczenia linii i combo (R-2..R-4 w `game.py`) — najwyższa dodatnia waga, bo najbliżej przekłada się na przyszłe punkty. |
| 6 | `placeable_shapes` — liczba kanonicznych typów z `pieces.py`, które da się jeszcze gdziekolwiek postawić | +0.5 | mała, ale dodatnia: szeroki wachlarz wciąż grywalnych kształtów zmniejsza ryzyko przegranej niezależnie od tego, co akurat leży w tacce. |

`HeuristicPolicy.act` ocenia każde legalne postawienie jako
`immediate_gain + w · features(plansza po postawieniu i ewentualnym czyszczeniu)`,
na kopii planszy (`policies.py:_simulate_placement`, wspólne dla `HeuristicPolicy`
i starego `_immediate_gain`) — nie dotyka stanu gry.

## Wynik: `heuristic` vs `greedy`

`python benchmark.py --candidate heuristic --previous greedy --issue 57` — pełne
**300** seedów (mieściło się w budżecie czasu: 144 s, próg z zadania to 20 min),
sufit 2000 ruchów, ε = 0.

| polityka | średnia | mediana | p10 | przeżycie |
|---|---:|---:|---:|---:|
| zachłanna (`greedy`, referencja z `docs/calibration-assumptions.md`) | 704,79 | 486,0 | 160,0 | 34,99 |
| **heurystyczna (`heuristic`, ten pomiar)** | **762,5** | **515,5** | **139,9** | **36,84** |

Sparowane na wspólnych seedach: Δ średniej = +57,72 (+8,19%), poniżej progu ±10% —
benchmark etykietuje to jako **„bez zmian”**, nie „poprawa”. Przeżycie rośnie (34,99 →
36,84), średnia rośnie (+8,2%), ale p10 (najgorsze partie) *spada* (160,0 → 139,9) —
heurystyka gra ostrożniej średnio, ale ma gorszy dolny ogon niż czysto zachłanna
maksymalizacja punktu z ruchu. To jest wynik do zapisania, zgodnie z zadaniem —
wagi nie były dostrajane w odpowiedzi na tę liczbę.

## Rozgałęzienie gry

Zmierzone jako `len(game.available_actions())` przy **każdym** ruchu, `GreedyPolicy`,
300 gier na stałych seedach (`bench/seeds_fixed.json`, te same co zestaw „fixed”
benchmarku), sufit 2000 ruchów. Pomiar tani (4,6 s) — pełne 300, bez skracania.

| statystyka | wartość |
|---|---:|
| liczba zmierzonych ruchów (300 partii) | 10 496 |
| średnia | 39,66 |
| mediana | 32,0 |
| maksimum | 170 |
| minimum | 1 |

To odpowiada na lukę nazwaną w `docs/research/kierunek-algorytmiczny.md`, sekcja
„Czego nie udało się ustalić": rozgałęzienie *w obrębie jednej znanej tacki* nie jest
strukturalną hipotezą rzędu ~162 (branching factor pojedynczej tury Tetris Link), tylko
zmierzoną średnią **39,66** i medianą **32** — wyraźnie w paśmie, w którym tamten sam
dokument (na podstawie eksperymentu na planszach Hex, arXiv:2004.00377) opisuje MCTS
jako wciąż użyteczne (próg podany tam to rozgałęzienie < 49). Maksimum 170 pokazuje
jednak, że pojedyncze wczesne ruchy (plansza prawie pusta, pełna tacka trzech dużych
klocków) potrafią lokalnie przekroczyć ten próg z zapasem — średnia i mediana same nie
mówią, jak kosztowne byłyby najgorsze przypadki przeszukiwania całej tacki.
