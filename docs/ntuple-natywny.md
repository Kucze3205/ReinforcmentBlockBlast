# Rdzeń natywny N-tuple, bitowo ten sam wynik (#184)

Punkt wyjścia: [#158](../../issues/158) (`docs/ntuple-szybkosc.md`) wyciągnął z czystego
Pythona ≈2× i zostawił ≈0,15 s na odcinek treningu `ADC`. Literatura dla sieci N-tuple/TD
tego rzędu mówi o 1–5 mln odcinków (`docs/research/budzet-wyuczonej-oceny.md`), my mamy
70 tys. To zadanie przenosi gorącą ścieżkę do C, bez zmiany żadnej wartości.

**Wynik:** trening `ADC` **≈13,4×** szybciej, 3 partie `lookahead-ntuple` **≈32×** szybciej.
Te same wagi po treningu (sha256), te same wyniki partii, te same wartości `value()` (`==`).

## Profil przed zmianą

`cProfile`, kod sprzed zadania (commit `16a95f1`), ten sam sprzęt i sesja co pomiar niżej.
Dwa obciążenia, oba na `ADC` (136 łat):

- **Trening `ADC`**: wznowienie `ntuple/survival-adc-state.json` (odcinek 70 000) o 200
  odcinków, parametry przebiegu z `docs/ntuple-survival-adc.md` (`--reward survival --alpha
  0.00011764705882352942 --seed 3 --move-cap 2000 --layout ADC --eval-every 1000
  --eval-episodes 100 --episodes 70200 --episodes-per-run 200`; do odcinka 71 000
  ewaluacja nie startuje). Kopia stanu, logu, wag i `best` w katalogu tymczasowym,
  pliki w `ntuple/` nietknięte. 19 345 postawień, 669 916 wywołań `indices()`.
- **Partie `lookahead-ntuple`**: `benchmark.play_game` z
  `build_policy("lookahead-ntuple:ntuple/survival-adc-70k.json", config)` na pierwszych 3
  seedach z `bench/config.json` (`fixed_seed_file`), `move_cap` z configu. 356 751 wywołań
  `value()` z 3765 przeszukań wiązką.

Udział w czasie (profiler dokłada narzut na wywołanie funkcji, więc bezwzględne sekundy
nie są miarodajne — miarodajny jest udział w ramach tego samego przebiegu):

| obciążenie | co | % czasu (cumtime) |
|---|---|---|
| trening `ADC` (73,8 s pod profilerem) | `patch_indices` (indeksy łat) | 48,8% |
| | `sum()` po wagach (`value_from_indices`) | 23,3% |
| | `board_bits` | 3,7% |
| | `_simulate_placement` (kopia planszy, postawienie, czyszczenie, punkty) | 18,3% |
| | `game.available_actions` | 2,8% |
| partie `lookahead-ntuple` (38,8 s pod profilerem) | `patch_indices` | 48,0% |
| | `sum()` po wagach | 22,9% |
| | `board_bits` | 3,5% |
| | `_expand` (stan następczy wiązki) | 21,6% |
| | `_tray_beam_search` łącznie | 99,3% |

Sama ocena N-tuple (indeksy + suma + pakowanie planszy) to ≈75% w obu obciążeniach; stany
następcze (kopie `Board`, `check_full_lines`, punktacja) to kolejne ≈20%. Przyspieszenie
samej oceny dałoby najwyżej ≈4× (prawo Amdahla przy 75%), za mało na 5× — dlatego do C
poszły też stany następcze.

## Co przeniesiono

Nowe pliki: `ntuple_native.c` (rdzeń) i `ntuple_native.py` (kompilacja, ładowanie przez
`ctypes`, opakowanie). Oba dopisane do `HASHED_SOURCES` w `benchmark.py`.

- **Kompilacja przy pierwszym użyciu**: `cc` (albo `$CC`) `-O2 -shared -fPIC
  -fno-fast-math -ffp-contract=off` do `.ntuple_native/ntuple_native-<skrót>.so`
  (katalog w `.gitignore`; skrót ze źródła, kompilatora i flag — zmiana `.c` daje nowy
  plik). Kompilacja trwa ≈0,2 s, do pliku tymczasowego i `os.replace`, więc równoległe
  procesy `benchmark.py --jobs` nie widzą połowicznego pliku.
- **Ocena (`nt_value_bits`, `nt_value_idx`)**: plansza jako maska 64-bit (ta sama co
  `ntuple.board_bits`), indeks łaty składany z „przebiegów” — ciągłych kawałków łaty na
  kolejnych bitach planszy, wyliczonych w Pythonie z dowolnego układu. Suma wag po łatach
  **w kolejności łat, tym samym algorytmem co `sum()` interpretera**: od CPython 3.12
  `sum()` floatów jest kompensacyjne (Neumaier), wcześniej to zwykłe dodawanie. Tryb jest
  wykrywany próbą (`sum([1e100, 1.0, -1e100])`), pierwszy składnik to `0 + w` jak w
  `sum()` ze startem `int 0`. Po załadowaniu `_self_check` porównuje rdzeń z `sum()` na
  losowym układzie i wagach od 1e-20 do 1e20; przy jakiejkolwiek różnicy rdzeń nie jest
  używany.
- **Aktualizacja TD (`nt_update`)**: `w += delta` na aktywnej wadze każdej łaty. Wagi żyją
  w buforze C; `NTupleValue.weights` jest własnością, która przed wydaniem list dociąga
  je z bufora, a przy następnej operacji rdzenia wpycha z powrotem — kod, który zmienia
  `weights[p][i]` z zewnątrz, działa jak dotąd. Waga, która nie jest dokładnie `float`
  (np. `int`), wyłącza rdzeń dla tej sieci (`sum()` liczy inty inaczej).
- **Trening (`nt_afterstates`)**: `_choose_action` liczy w C stany następcze wszystkich
  akcji (postawienie, czyszczenie wierszy/kolumn), ich wartości, liczbę linii i pustość
  planszy. Przy `survival` (`r = 1` dla każdej akcji) rdzeń wybiera też najlepszą akcję
  (pierwszą przy remisie, jak `score > best_score`). Przy `score` punkty składa
  `policies._placement_gain` tymi samymi funkcjami `scoring.py`, a porównanie `r + V`
  zostaje w Pythonie.
- **Wiązka `lookahead-ntuple` (`nt_search`)**: `NTupleLookaheadPolicy._search` woła
  `_tray_beam_search_native` — całe przeszukanie (rozwijanie jak `_expand`, przejście
  combo/licznika, stabilne sortowanie malejąco jak `list.sort(reverse=True)`, cięcie do
  `beam`, liczba rozwinięć) w C. Punkty **nie są przepisane do C**: Python liczy
  `placement_points` każdego klocka tacki i `clear_points` dla każdej pary (combo, linie),
  jaką przeszukanie może spotkać, i przekazuje je jako tabele. Przypadek spoza tabel (np.
  plansza startowa z już pełnymi liniami) albo pola poza zakresem `int32` rdzeń zgłasza,
  a wiązkę liczy wtedy Python, jak dotąd.

**Zapasowa ścieżka**: `NTUPLE_NATIVE=0`, brak kompilatora, nieudana kompilacja albo
nieudany `_self_check` → `ntuple_native.available()` jest `False` i `ntuple.py`,
`policies.py`, `tools/train_ntuple.py` liczą w czystym Pythonie, tym samym kodem co
przed zadaniem. `NTupleValue(..., native=False)` wymusza to samo dla jednej sieci.

Nietknięte: `game.py`, `board.py`, `scoring.py`, `generator.py`, `pieces.py`, sygnał i cel
TD, nagroda. `reward_shape_changed: no`.

## Równoważność

`tests/test_ntuple_native.py` (pomijane bez rdzenia):

- `value()` natywne vs czyste na 1000 losowych planszach dla `A`, `AD`, `ADC`, wagi o
  rzędach 1e-12…1e12 (tam sumowanie kompensacyjne różni się od zwykłego) — `assertEqual`,
  plus to samo na wagach `ntuple/survival-adc-70k.json`;
- aktualizacje TD → identyczne wagi; zmiana wagi z zewnątrz widziana przez rdzeń; waga
  `int` → Python;
- wiązka natywna vs `_tray_beam_search` z liściem N-tuple na 300 losowych stanach
  (różne `beam`, `depth`, `root_actions`, `gain`/`placed`), wysokie combo, plansza bez
  ruchów, przypadek spoza tabel punktów;
- trening 200 odcinków `ADC`/`survival` i 30 odcinków `AD`/`score` z tego samego ziarna
  obiema ścieżkami → identyczny sha256 wag i identyczny log (bez `duration_s`);
- `play_game` z `lookahead-ntuple:ntuple/survival-adc-70k.json` na 3 seedach → te same
  krotki (wynik, przeżycie, ucięcie) obiema ścieżkami;
- `TestFallback`: `NTUPLE_NATIVE=0` → brak rdzenia, polityka działa.

`python3 -m unittest discover -s tests -q` zielony z rdzeniem i z `NTUPLE_NATIVE=0`
(348 testów; w drugim przypadku 11 pominiętych — testy porównujące).

## Pomiar przed/po

Ten sam sprzęt i sesja: Intel Xeon Platinum 8370C @ 2,80 GHz, 4 rdzenie, CPython 3.12.3,
cc (GCC) 13.3.0, `.so` już skompilowane. Każdy przebieg w osobnym procesie, bez profilera.
„Przed” to kod sprzed zadania (`16a95f1`, osobny `git worktree`); „zapasowa” to ta gałąź z
`NTUPLE_NATIVE=0`.

**Trening `ADC`, wznowienie z 70 000, 200 odcinków** (s/odcinek ze średniej `duration_s`
z `<stan>.log.jsonl`, jak w `docs/ntuple-szybkosc.md`):

| ścieżka | s/odcinek | czas ścienny (200 odc.) | sha256 wag po treningu |
|---|---|---|---|
| przed (`16a95f1`) | 0,14871 | 29,87 s | `a69e4e26e43cf0c3…` |
| zapasowa (`NTUPLE_NATIVE=0`) | 0,14957 / 0,15019 | 30,05 / 30,17 s | `a69e4e26e43cf0c3…` |
| natywna | 0,01101 / 0,01112 | 2,36 / 2,38 s | `a69e4e26e43cf0c3…` |

**≈13,4×** na odcinek (0,14871 / 0,01107). Sha256 pełny:
`a69e4e26e43cf0c30387207451f0c9da67b570ce0c9b48091d53c964f7882286`, identyczny we wszystkich
trzech. Ścieżka zapasowa kosztuje ≈0,6–1% więcej niż kod sprzed zadania (sprawdzenie, czy
jest rdzeń, i własność `weights`).

**3 partie `lookahead-ntuple:ntuple/survival-adc-70k.json`** (seedy 1259289227,
1358106528, 1524307444):

| ścieżka | czas 3 partii | wyniki (wynik, przeżycie, ucięta) |
|---|---|---|
| przed (`16a95f1`) | 15,92 s | (10465, 269, nie), (16539, 281, nie), (7904, 227, nie) |
| zapasowa (`NTUPLE_NATIVE=0`) | 16,06 / 16,00 s | identyczne |
| natywna | 0,50 / 0,49 s | identyczne |

**≈32×** (15,92 / 0,495).

Obie liczby są powyżej progu 5× z issue.

## Co zjada resztę czasu

Profil po zmianie (ścieżka natywna, te same obciążenia):

- **Trening** (4,26 s pod profilerem): `game.available_actions` ≈47% (z czego
  `Board.can_place_piece` ≈34%), wywołanie rdzenia `afterstates` ≈14%,
  `game.apply_placement` ≈11%, zapis stanu/wag JSON reszta. Legalne akcje liczy gra
  (`game.py`, poza zakresem zmian), rdzeń sam je sprawdza jeszcze raz — kolejny krok to
  liczenie listy akcji w C, ale wymaga to dotknięcia pętli gry, nie tylko oceny.
- **Partie** (0,76 s pod profilerem): `nt_search` w C ≈44%, opakowanie w Pythonie
  (tabele punktów, odtworzenie stanów wiązki jako `Board`) ≈34%,
  `game.available_actions` ≈12%.

Koszt odcinka dalej rośnie liniowo z przeżyciem, ale z ≈0,11 ms zamiast ≈1,54 ms na
postawienie w treningu `ADC` (19 345 postawień na 200 odcinków, ≈97 na odcinek:
0,01107 s wobec 0,14871 s na odcinek).
