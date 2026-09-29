# Gwarancja ułożenia tacki (`complete=1`, #239)

## Po co: streszczenie #236

Pomiar #236 (`tools/measure_death_avoidability.py`, dane: `docs/data/death-avoidability-100.json`) zbadał 100 partii
polityki rekordowej (`lookahead-ntuple:ntuple/survival-adcga16-800k.json@beam=128,samples=0`, 100 śmierci, 0 partii
dobitych do sufitu). Dla każdej śmierci sprawdzono przeglądem wyczerpującym (kolejności × pozycje, z czyszczeniem linii
między postawieniami), czy tacka, na której partia się skończyła, dawała się ułożyć w całości z planszy z jej początku.
Dawała się we **wszystkich 100 przypadkach** (`a_search_miss` = 100). Generator świadomy planszy losuje tackę „do
skutku", aż `board.tray_playable` zwróci prawdę (`generator.py`, `next_pieces`), więc w symulatorze partia może się
skończyć wyłącznie błędem przeszukania (wiązka o szerokości 128 nie znalazła istniejącego ułożenia) albo wyczerpaniem
`REJECT_MAX_ATTEMPTS`. Druga część pomiaru (b): w 100/100 przypadków dało się też uniknąć śmierci jedną tackę wcześniej
(mediana ~2 261 plansz końcowych na tackę) — tym się tu nie zajmujemy, gwarancja dotyczy wyłącznie (a).

## Jak działa

Włączana parametrem specyfikacji: `lookahead-ntuple:<wagi>@beam=128,samples=0,complete=1`. Parametr jest w
`benchmark.NTUPLE_SEARCH_PARAMS` i w konstruktorze `NTupleLookaheadPolicy(..., complete=0)`; domyślnie 0.

Po przeszukaniu wiązką `LookaheadPolicy.act` woła hak `_complete_frontier`; klasa bazowa zwraca front bez zmian,
`NTupleLookaheadPolicy` go nadpisuje:

1. `complete=0` — zwraca front nietknięty. Żadna inna ścieżka kodu się nie zmienia, więc zachowanie jest bit w bit
   dzisiejsze (sprawdzone: pierwsze 5 seedów `bench/seeds_fixed.json` na rekordzie daje
   `[62079, 85821, 5366, 248599, 75607]`, czyli `arms.record.fixed.scores[:5]` z `bench/227-baseline-gen2.json`).
2. `complete=1`, front wiązki zawiera stany **z wykorzystaną całą tacką** — zostają tylko one. Wybór wśród nich robi ta
   sama ocena `score` (liść N-tuple planszy końcowej + składnik ścieżki `placed`/`gain`), co w wiązce. Ten sam filtr
   działa przed `_distinct_first_actions`, więc przy `samples>0` drugi poziom też rozważa tylko ruchy z kompletnych
   ułożeń.
3. `complete=1`, front wiązki nie zawiera kompletnego stanu — **przegląd wyczerpujący** `_tray_complete_search`: poziom po
   poziomie, bez przycinania do `beam`, każde legalne postawienie każdego pozostałego klocka; stany identyczne (ta sama
   plansza i zużycie klocków, przy `gain` także combo i licznik) scala, zostawiając większą sumę ścieżki; stan bez
   ruchu przed końcem tacki odpada. Stany końcowe dostają `score` jak w wiązce. Przy `samples>0` scalanie po stanie
   może zgubić alternatywne pierwsze akcje prowadzące do tej samej planszy (ocena jest ta sama), co jest
   akceptowane.
4. Tacka faktycznie nieukładalna (przegląd nic nie znalazł) — zostaje wynik wiązki, więc polityka nadal zwraca
   legalną akcję i nie rzuca wyjątku.

Wybrałem „sprawdź front wiązki + zapasowy przegląd", a nie sam przegląd: wiązka i tak już policzyła front, w praktyce
prawie zawsze zawiera ułożenie kompletne (niżej), a przegląd (mediana ~2 261 plansz końcowych na tackę, z pośrednimi
znacznie więcej) w Pythonie kosztuje na tyle, żeby nie chcieć go w każdej decyzji.

Nagroda gry, `game.py`, `generator.py`, `scoring.py`, `pieces.py` i pliki `ntuple*` nie zostały ruszone.
Zmiana dotyka `policies.py`, więc hash rekordu benchmarku się zmienia (#8) — pomiar zleca orchestrator.

## Pomiar śmierci: `docs/data/239-complete-death.json`

`lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1`, 40 pierwszych seedów
`bench/seeds_fixed.json`, `--jobs 4`, sufit 4000 postawień:

| | |
|---|---|
| partie | 40 |
| `n_capped` | **40** (każda partia doszła do sufitu 4000 postawień) |
| `n_deaths` | 0 |
| `a_search_miss` | **0** |
| postawień razem | 160 000 |
| średnia punktów | 548 768,2 |
| punkty na postawienie | 137,19 |
| czas | 360,5 s (4 procesy) |

`a_search_miss` = 0 jest tu prawdziwe, ale trywialne: nie było ani jednej śmierci, którą dałoby się zaklasyfikować.
Punktu odniesienia z tego samego pomiaru dla `complete=0` nie ma: #236 mierzył inne wagi (`adcga16-800k`; średnio
100 026 punktów i 707,1 postawienia na partię, 100/100 śmierci z układalną tacką), więc liczb nie zestawiam jako
efektu gwarancji. Porównanie na tych samych wagach (`adce-400k`) i seedach, 8 pierwszych seedów: `complete=0` — wszystkie
8 partii kończy się śmiercią (4 623 postawień razem, średnio 89 374 punkty), `complete=1` — wszystkie 8 dobija do sufitu
(32 000 postawień, średnio 532 562 punkty). To próbka orientacyjna (8 partii), nie pomiar benchmarkowy.

## Jak często wchodzi przegląd zapasowy

Na tych samych 40 partiach (160 000 decyzji, skrypt jednorazowy, nie w repo): filtr frontu zmienił front w 4 339
decyzjach (2,7%) — tyle razy wiązka miała w froncie także stany utknięte obok kompletnych — a **przegląd zapasowy nie
uruchomił się ani razu**. Wiązka o szerokości 128 zawsze trzymała w froncie jakieś ułożenie kompletne, gdy takie było.
Ścieżka zapasowa jest więc pokryta testem jednostkowym (`tests/test_ntuple_complete_tray.py`), a nie ruchem z
pomiaru; jej koszt w realnej partii jest nieznany (nie wystąpiła). Osobny pomiar samego przeglądu wołanego na początku
każdej tacki (300 tacek z 3 partii `complete=1`, pierwsze 300 postawień): mediana 0,24 s, maksimum 3,9 s, średnio
5 330 plansz końcowych — około 60 razy więcej niż zwykła decyzja (~4 ms), więc gdyby wchodził często, byłby
dominującym kosztem; przy 0 wejść na 160 000 decyzji nie jest.

## Koszt

Te same wagi (`adce-400k`), 6 pierwszych seedów z `bench/seeds_fixed.json`, jeden proces, do 600 postawień na partię:

| tryb | postawień | czas | postawień/s |
|---|---|---|---|
| `complete=0` | 2 264 (wszystkie partie umarły) | 8,5 s | 265,8 |
| `complete=1` | 3 600 (wszystkie dobiły do 600) | 13,6 s | 264,9 |

Narzut gwarancji przy niewyzwolonym zapasowym przeglądzie to filtr po froncie (rząd 128 stanów na decyzję) — poniżej
szumu pomiaru. Trajektorie obu trybów się rozchodzą (partie `complete=0` giną), więc to nie jest ten sam zestaw
pozycji. Ograniczenie wykonania: partie `complete=1` dochodzą do sufitu, czyli 4000 postawień na partię — 40 partii przy
`beam=128` i 4 procesach zajęło 6 minut.

## Testy

`tests/test_ntuple_complete_tray.py`: wiązka `beam=1` na planszy z 2×2 w rogu i przekątną pojedynczych dziur wybiera
1×1 w (0, 0) i utyka; `complete=1` wybiera ruch, po którym reszta się mieści (także przy `samples>0`);
tacka nieukładalna (1×1 + 3×3 na przekątnych dziurach) daje legalną akcję bez wyjątku; `complete` jest w
`NTUPLE_SEARCH_PARAMS`, domyślnie 0, i `complete=0` daje te same akcje co brak parametru.
