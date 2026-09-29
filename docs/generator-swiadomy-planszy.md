# Generator świadomy planszy jako domyślne zachowanie `Game` (#221)

Bilet: [#221](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/221) · dokańcza:
[#217](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/217) · model i dopasowanie:
`docs/z6-model-generatora.md`.

## Wybrany model i powód

`docs/z6-model-generatora.md` (sekcje #211/#217) wybrało **M2-simple**: `PIECE_TYPE_WEIGHTS` bez zmian
(dopasowane wagi nie biją ich o > 1 SE na teście, `## Decyzja kryterium 2` tamtego dokumentu) plus
odrzucanie tacek nieukładalnych na BIEŻĄCEJ planszy „do skutku" (`p=1,0000`, `REJECT_MAX_ATTEMPTS=1000`
w `generator.py` — w praktyce limit nigdy nieosiągany poza planszami, na których żadna tacka nie jest
grywalna, gdzie i tak przegrywa). #217 wdrożyło ten model w `generator.py` jako **opt-in**
(`Generator(seed, board=...)`), bo `game.py` było wtedy poza budżetem biletu.

#221 kończy wdrożenie: `Game.__init__` (`game.py`) domyślnie konstruuje `Generator(seed, board=self.board)`
— referencja, nie kopia, więc `next_pieces()` widzi bieżący stan planszy przy każdym odświeżeniu tacki bez
dodatkowego wpinania. `Game(seed, legacy_generator=True)` wyłącza świadomość planszy i odtwarza sekwencję
tacek sprzed #217/#221 bit w bit (test: `tests/test_engine.py::TestBoardAwareGameDefault::test_legacy_switch_reproduces_blind_generator_sequence_bit_for_bit`).
Pomocnicy monkeypatchujący `generator.attach_to_game`/`generator.patch_game_for_board_awareness` — obejście
na czas, gdy `game.py` był poza budżetem #217 — są usunięte z `generator.py` (i nie mają już odbiorców).

Generator próbkujący wewnątrz `policies.py` (`LookaheadPolicy._sampler`, symulacje przyszłych tacek na
potrzeby przeszukiwania) **zostaje bez planszy** — to osobny generator od `game.generator`, celowo poza
budżetem #221 (`policies.py` nietknięte, patrz `## Kryteria akceptacji` #221).

`reward_shape_changed: no` — `game.step`, punktacja i kary są niezmienione. Zmienia się **dynamika
środowiska**: rozkład tacek zależy teraz od stanu planszy (redraw na nieukładalnych) zamiast być stałym
procesem niezależnym od planszy — to wpływa na to, JAKIE stany agent odwiedza, nie na to, jak są nagradzane.

## Koszt: `next_pieces()`

Zmierzone na trudnej planszy w połowie partii (`GreedyPolicy`, 140 postawień, seed
`"z6-217-hard-board"` — ta sama metoda próbkowania co `tests/test_generator_weights.py::_mid_game_board`),
20 000 wywołań `next_pieces()` na tej samej planszy, seria po sobie (bez rozgrzewki interpretera osobno
mierzonej):

| generator | czas/wywołanie | 20 000 wywołań razem |
|---|---:|---:|
| stary (`legacy=True`, ślepy) | 4,53 µs | 0,091 s |
| nowy (`legacy=False`, świadomy planszy) | 759,68 µs | 15,194 s |

**Nowy generator jest ~168× wolniejszy na wywołanie** — koszt to `board.tray_playable` (DFS na planszy),
wołane co najmniej raz na odświeżenie tacki, więcej razy tylko gdy pierwszy rzut wypadnie nieukładalny
(rzadko, patrz odsetek niżej). W absolutnych liczbach to wciąż ok. 0,76 ms na odświeżenie tacki (raz na 3
postawienia), więc koszt jest zdominowany przez politykę wybierającą ruch (`lookahead-ntuple` z `beam=128`
kosztuje rzędu milisekund na POSTAWIENIE), nie przez generator — patrz koszt treningu niżej.

## Pomiar: stary kontra nowy generator

Ramię: `lookahead-ntuple:ntuple/survival-adcga16-800k.json@beam=128,samples=0`. 200 seedów rozłącznych z
`bench/seeds_fixed.json` (sól `siatka-195`, `tools/measure_ntuple_search_grid.py::grid_seeds`, te same
seedy dla obu generatorów — porównanie sparowane). Sufit 4000 postawień/partię. Narzędzie:
`tools/measure_ntuple_search_grid.py --compare-generators` (rozszerzenie #221 — `benchmark.py` jest
nietknięte przez tę gałąź, więc `benchmark.play_game`/`run_set` zawsze konstruują `Game` domyślnie; własna
pętla partii w `measure_ntuple_search_grid.py` wybiera `legacy_generator` jawnie).

    python3 tools/measure_ntuple_search_grid.py --compare-generators --n-seeds 200 --jobs 4 --move-cap 4000

| generator | n partii | średnia | se | przeżycie (śr. postawień) | `capped_pct` | tacka nieukładalna od razu po rzucie | s/partia |
|---|---:|---:|---:|---:|---:|---:|---:|
| stary | 200 | 88 490,99 | 6 961,60 | 634,43 | 0,0% | 0,0% | 0,91 |
| nowy | 200 | 102 763,56 | 8 327,66 | 732,98 | 1,0% | 0,0% | 1,10 |

„Tacka nieukładalna od razu po rzucie" liczy partie, które kończą się natychmiast po odświeżeniu tacki
(`round_placement` wraca do 0 tuż przed `game.done`, bez żadnego postawienia z nowej tacki) — na tej próbie
200 seedów zdarzenie nie wystąpiło w ŻADNYM z dwóch ramion; sam wynik i przeżycie i tak rosną wyraźnie pod
nowym generatorem (średnia +16%, przeżycie +15,5%), spójnie z tym, że unikanie tacek bliskich
nieukładalności (nie tylko całkowicie martwych) poprawia grę silnego przeszukiwania, nie tylko ratuje przed
odosobnionymi nagłymi zgonami. `capped_pct` (partie ucięte sufitem 4000) rośnie z 0% do 1% — konsekwencja
dłuższych partii pod nowym generatorem, nie osobne zjawisko.

## Koszt treningu: `tools/train_ntuple.py` (bez zmian w pliku)

`tools/train_ntuple.py` jest nietknięte przez tę gałąź (weryfikacja #221 to sprawdza wprost), więc pomiaru
nie da się przełączyć flagą — porównano to samo, niezmienione polecenie uruchomione na dwóch stanach
repozytorium: `git worktree` na commicie `c1d3027` (tuż przed zmianą `game.py` w tej sesji, `Game`
konstruuje ślepy `Generator(seed)`) kontra bieżący `HEAD` (`Game` domyślnie świadoma planszy). Ten sam
`--seed 12345`, te same zakazane seedy (`bench/seeds_fixed.json`), 50 odcinków w jednym wywołaniu
(`--episodes-per-run 50`), wagi domyślne (świeży `NTupleValue`, układ `A`):

    python3 tools/train_ntuple.py --state /tmp/state.json --episodes 50 --episodes-per-run 50 --seed 12345 --out /tmp/weights.json

| generator | 50 odcinków razem | s/odcinek |
|---|---:|---:|
| stary | 0,40 s | 0,0080 s |
| nowy | 0,52 s | 0,0104 s |

**~1,3× wolniej na odcinek** — dużo mniej niż 168× na samo `next_pieces()`, bo odcinek treningowy dominuje
koszt wyboru ruchu (`_choose_action`/TD(0)) po KAŻDYM postawieniu, a `next_pieces()` woła się raz na 3
postawienia. Część wzrostu to też dłuższe partie pod nowym generatorem (więcej postawień do przeliczenia
TD(0)) — ten sam efekt co wyższe `survival_mean` w tabeli pomiaru wyżej. Próba jest mała (50 odcinków, wagi
początkowe niewytrenowane) — liczba orientacyjna, nie pełny pomiar kosztu treningu.

## Zmienione złote sekwencje

`Game(seed=...)` bez `legacy_generator=True` (domyślne wywołanie w obu plikach testowych niżej) zmienia
strumień tacek, nawet gdy mierzona polityka jest identyczna — więc złote sekwencje ruchów zapisane
wcześniej przestały się zgadzać i wymagały ponownego nagrania na bieżącym kodzie:

- `tests/data/lookahead_weights_moves.json` (24 partie, `lookahead:weights.json`,
  `tests/test_lookahead_regression.py`) — przeliczone `build_policy("lookahead:weights.json", ...)` na tych
  samych 24 seedach.
- `tests/fixtures/lookahead_regression.json` (20 partii, `LookaheadPolicy(weights=load_tuned_weights("weights.json"))`,
  `tests/test_lookahead_ntuple_regression.py`, sufit 60 ruchów) — przeliczone identycznie na tych samych 20
  seedach.

Same ruchy WYBIERANE przez te polityki na danej planszy+tacce się nie zmieniły (`policies.py` nietknięte) —
zmieniło się tylko to, JAKIE tacki dostają do wyboru, więc partie rozjeżdżają się od pierwszego odświeżenia
tacki, na którym stary generator wylosowałby coś innego niż nowy.

## Hashe źródeł (`benchmark.source_hashes()`)

`generator.py`:
```
5b11ec3b1759b05f
```

`game.py`:
```
9ce7d22a3b62df05
```
