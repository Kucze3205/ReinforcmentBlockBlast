# Jeden poziom za tacką: `LookaheadPolicy`

Zadanie: [#92](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/92).

> Ten dokument jest w trakcie pisania — tabela pomiarowa i wybór parametrów
> domyślnych dopisywane po zakończeniu przebiegu `tools/measure_lookahead_cost.py`.

## Co robi polityka

`TrayPolicy` (#58, #79) przeszukuje wyczerpująco **bieżącą** tackę i nic dalej.
`LookaheadPolicy` dokłada nad tym **węzeł losowy**: tam, gdzie kończy się bieżąca
tacka, gra sięga po nową (`game.apply_placement` odświeża tackę po trzecim
postawieniu, `game.py:96-98`), a nowa tacka jest losowa. To jest pierwsze miejsce
w tym repo, w którym przeszukanie wychodzi poza znaną tackę.

Kolejność jednej decyzji:

1. **Poziom pierwszy** — dokładnie przeszukanie `TrayPolicy` (`policies._tray_beam_search`,
   ta sama funkcja, ta sama `beam`). Wychodzi z niego wiązka stanów końcowych: plansza,
   combo i suma punktów po postawieniu **całej** bieżącej tacki.
2. **Kandydaci** — `branch` najlepszych stanów, po jednym na **odrębną pierwszą akcję**.
   Decyzja dotyczy tylko pierwszego ruchu, a wiązka potrafi oddać kilka wariantów tej
   samej pierwszej akcji; bez tego filtra drugi poziom liczyłby to samo po kilka razy
   i nie rozstrzygał niczego.
3. **Węzeł losowy** — `samples` losowań następnej tacki z `generator.Generator`, czyli
   z tego samego rozkładu (1/15 na typ, potem 1/n na orientację), którego używa gra.
   Te same próbki dla wszystkich kandydatów w obrębie jednej decyzji (wspólne liczby
   losowe): różnica między kandydatami jest wtedy różnicą polityki, nie różnicą losu.
4. **Poziom drugi** — dla każdej pary (kandydat, próbka) płytsze przeszukanie
   (`inner_beam` szerokości, `inner_depth` poziomów). Wartość kandydata to

       punkty po drodze + średnia po próbkach z (punkty z następnej tacki
                                                 + w · features(plansza po niej))

   czyli oczekiwana wartość po węźle losowym — expectimax z estymatorem Monte Carlo
   zamiast pełnej sumy po 15³ możliwych tackach.

**Kara za śmierć.** Tacka, której nie da się postawić, kończy partię
(`game._can_place_any`, `game.py:103-111`). Próbka, w której to się dzieje, dostaje
`death_penalty` do wartości. To jest główny mechanizm, przez który ten poziom ma coś
kupić: pozwala odrzucić planszę, która w samych cechach wygląda dobrze, a jest pułapką
na losową tackę. Kara to wewnętrzna wycena polityki — nagrody z `game.step` nie dotyka.

**Determinizm.** Próbki idą z osobnej instancji `Generator`, zasianej z seeda partii w
`reset(game_seed)` — nigdy z generatora gry (`act` nie rusza stanu gry ani jego RNG,
sprawdzone testem). Dwa przebiegi tego samego seeda dają tę samą sekwencję akcji:
`tests/test_lookahead_policy.py::TestLookaheadSamplingIsDeterministic`.

`TrayPolicy` jest dokładnie przypadkiem granicznym `samples=0` — sprawdzane testem
porównującym całe sekwencje partii
(`tests/test_lookahead_policy.py::TestLookaheadDegeneratesToTray`).

## Metoda pomiaru

`tools/measure_lookahead_cost.py`, **te same seedy** co `tools/measure_tray_cost.py`
(funkcja `measurement_seeds`, sól `"tray-cost:79"`, 40 partii, rozłączne z
`bench/seeds_fixed.json`), sufit 2000 ruchów jak w `bench/config.json`. Mierzony jest
czas każdej decyzji (`time.perf_counter`) i `last_expanded` (suma kandydatów rozwiniętych
na **obu** poziomach), a per partia wynik i przeżycie. Tabele z
`docs/przeszukanie-tacki.md` (#79, #88) leżą na tych samych seedach i tym samym sprzęcie.

Kolumna **ramię 600 s** to ta sama ekstrapolacja, której użyły #79 i #88:

    śr. czas decyzji × śr. przeżycie (decyzji na partię) × 600 partii

600 = 300 seedów stałych + 300 rotowanych, czyli jedno ramię `benchmark.py`
(`bench/config.json`: `n_seeds = 300`). To jest liczba porównywana z limitem
**1800 s**, który #92 nałożyło na politykę domyślną — trzeci limitu 3600 s na
pojedyncze polecenie z `.github/loop/loop.py:408`.
