# Ocena N-tuple: układ, nagroda, wznawianie, budżet (#123)

Szkielet — kod, który działa i ma testy, nie zmierzony wynik. Zmierzonego wyniku
nie oczekuje od tego zadania [#123](../../issues/123) i nie wolno go udawać:
sieć nauczona na kilkudziesięciu odcinkach będzie gorsza od ręcznych cech
(`weights.json`/`weights-lookahead.json`) — to jest oczekiwane. Ten dokument jest
instrukcją dla `rola:bench` z następnego cyklu: jak odpalić i wznowić realny
trening, i ile odcinków to prawdopodobnie potrzebuje.

## Układ łat i skąd wzięty

`ntuple.py:PATCH_LAYOUT` — **wariant A** z `docs/research/budzet-wyuczonej-oceny.md`
([#120](../../issues/120), sekcja 3): 8 łat-wierszy + 8 łat-kolumn, każda po
`k=8` komórek, `c=2` (pusta/zajęta) → `16 × 2**8 = 4096` wag. Ten sam raport
policzył trzy inne warianty (B: kwadraty 2×2, 784 wag; C: prostokąty 2×3/3×2,
5376 wag; D: kwadraty 3×3, 18432 wag) i **nie rozstrzygnął**, który jest
lepszy dla mechaniki usuwania linii — to jest wprost nazwane jako otwarte w
tamtym raporcie ("czego ten dobór łat nie rozstrzyga").

Skoro #120 nie rozstrzyga, wybór wariantu A jest mój, z trzech powodów:

1. **To jest dokładnie propozycja z treści issue #123** ("8 wierszy plus osiem
   kolumn... 4096 wag") — trzymanie się jej minimalizuje liczbę niezależnych
   decyzji w jednym zadaniu-szkielecie.
2. **Strukturalne dopasowanie do jedynego mechanizmu nagrody poza postawieniem**:
   linia czyści się cała naraz, po wierszu albo kolumnie — łata-wiersz/łata-kolumna
   widzi bezpośrednio "ile brakuje do pełna" w jednym odczycie LUT, bez potrzeby
   składania informacji z wielu małych łat. Warianty B/D (kwadraty) widzą lepiej
   lokalną fragmentację (to już robi ręczna cecha `surrounded_empty`/`empty_regions`
   z `features.py`), nie kompletność linii.
3. **Najmniejszy z czterech (4096 wag)** — mniej wag do wypełnienia sensownymi
   wartościami w krótkim budżecie treningu, zgodnie z jedynym niekwestionowanym
   wnioskiem #120 (sekcja 2): nie ma wzoru episody(wagi), ale mniejsza sieć nie
   jest gorsza wtedy, gdy budżet jest wspólnym, wąskim gardłem — a `rola:bench`
   pierwszego cyklu na pewno nim będzie.

`PATCH_LAYOUT` pokrywa każdą z 64 komórek planszy co najmniej raz (test
`test_ntuple.py::TestPatchLayout::test_layout_covers_every_cell_at_least_once`),
każda komórka wewnętrzna wchodzi w skład dokładnie dwóch łat (jednej wiersza,
jednej kolumny).

**Czego ten wybór nie rozstrzyga** (odziedziczone po #120, nie zmierzone tutaj):
czy warianty B–D albo ich połączenie (np. A+C) uczyłyby się szybciej albo do
wyższego sufitu — to jest osobne, przyszłe pytanie pomiarowe, nie część tego
szkieletu. Zmiana wariantu wymaga tylko zmiany `PATCH_LAYOUT` w jednym miejscu
(`ntuple.py`) i przetrenowania od zera — pliki wag z jednym układem nie wczytują
się z innym (`NTupleValue.load` sprawdza to asercją).

## Gdzie się wpina

`ntuple.NTupleValue.value(board)` zastępuje `policies._weighted_features(weights,
board, combo, combo_counter)` jako wartość liścia w przeszukaniu tacki — ale
tylko w nowej klasie `policies.NTupleLookaheadPolicy`, nie w
`TrayPolicy`/`LookaheadPolicy`, które zostają nietknięte (zero zmiany
zachowania, patrz test regresji niżej).

**Sygnatura haka: trójka, ocena: sama plansza** (#125, przy scalaniu na `main`).
`_tray_beam_search(..., leaf_value=...)` woła hak dokładnie tymi argumentami,
którymi woła `_weighted_features` — `(board, combo, combo_counter)` — a adapter
`NTupleLookaheadPolicy._ntuple_leaf` **ignoruje dwa ostatnie** i zwraca
`NTupleValue.value(board)`. Dwie strony tej decyzji, obie celowe:

- *Dlaczego liść nie dostaje członu combo*: `gain` już niesie efekt combo dla
  ocenianego ruchu, a `V(board)` ma szacować przyszłość samej planszy; jedyny
  pomiar combo w ocenie liścia wyszedł **ujemnie** (#122: −6,6%, przeżycie
  95,97 wobec 110,5), więc skopiowanie tego członu tutaj skopiowałoby zmierzony
  błąd.
- *Dlaczego argumenty zostają w sygnaturze*: dosypanie combo do oceny N-tuple
  później — gdyby pomiar kiedyś wyszedł inaczej — jest wtedy zmianą w jednym
  adapterze, bez kolejnej zmiany sygnatury haka i bez ruszania
  `TrayPolicy`/`LookaheadPolicy`.

Pilnuje tego `tests/test_leaf_value_hook.py`: hak widzi tę samą trójkę co
domyślna ocena, a wartość liścia N-tuple nie zmienia się przy combo 0, 1, 7 i 40.
`benchmark.py --candidate lookahead-ntuple:<plik>` buduje to ramię tak jak
`lookahead:<plik>` buduje `LookaheadPolicy` z wagami — `<plik>` jest w formacie
`ntuple.NTupleValue.save()`, nie `weights.json` (`features.FEATURE_NAMES`).

`features.py` i sześć ręcznych cech nie są ruszone — ocena N-tuple jest
alternatywnym, wybieralnym źródłem wartości liścia, nie zamiennikiem.

`benchmark.HASHED_SOURCES` **nie zawiera** `ntuple.py` — decyzja świadoma, nie
przeoczenie: to ramię jest szkieletem, nie zmierzonym w tym cyklu; czy dopisać
`ntuple.py` do odcisku źródeł (#102) rozstrzyga `rola:bench` przy pierwszym
realnym pomiarze `lookahead-ntuple:`.

## Kształt nagrody użyty w TD

**Nietknięty.** `tools/train_ntuple.py` używa dokładnie tego, co zwraca
`policies._simulate_placement` (ten sam wzór co `Game.apply_placement`,
`scoring.clear_points`/`placement_points`) jako `gain` — nie definiuje własnego
sygnału nagrody.

TD(0) po stanach następczych (afterstate — plansza zaraz po postawieniu i
ewentualnym czyszczeniu linii, przed dociągiem kolejnej tacki):

```
target          = gain_t + V(afterstate_t)
V(afterstate_{t-1}) += alpha * (target - V(afterstate_{t-1}))
```

Po ostatnim postawieniu partii (stan terminalny — gra się skończyła, żadnej
przyszłej nagrody nie będzie) jest jedna dodatkowa aktualizacja z `target = 0`.

Polityka behawioralna (ta, która zbiera dane i której szukamy najlepszej akcji)
jest zachłanna o jeden pół-ruch w przód: `gain(akcja) + V(afterstate(akcja))`,
maksymalizowane po wszystkich legalnych akcjach bieżącej tacki — **nie**
przeszukanie tacki (`TrayPolicy`/`LookaheadPolicy`), żeby jeden odcinek
treningu był tani. `combo`/`combo_counter` nie wchodzą do stanu wartościowanego
przez sieć: `gain` już niesie efekt combo dla *tego* ruchu, `V(board)` szacuje
wartość *przyszłą* samej planszy.

Uwaga aktualizacyjna (#125): `_weighted_features` **ma** od #118 człon combo, więc
zdanie „tak samo jak dziś w `HeuristicPolicy`/`TrayPolicy`" z pierwszej wersji
tego dokumentu już nie jest prawdą — na `main` liść ręcznych wag może combo
wyceniać, tylko `weights.json` ma ogon combo zerowy. Brak członu combo w liściu
N-tuple **nie jest** więc odziedziczoną własnością, jest decyzją: jedyny pomiar
tego członu w ocenie liścia wyszedł ujemnie (#122, −6,6%). Kwestia, czy inny
sposób wpuszczenia combo do wyuczonej oceny by pomógł, została nazwana w
`docs/research/budzet-wyuczonej-oceny.md` sekcja 6 i pozostaje otwarta.

## Jak wznowić trening jednym poleceniem

```
python tools/train_ntuple.py --state ntuple-state.json --out ntuple-weights.json \
    --episodes <N> --seed <S>
```

Jedno wywołanie = jeden odcinek (jedna partia), bo `--episodes-per-run`
domyślnie `1`. Kolejne wywołanie **z tymi samymi argumentami** wczytuje
`ntuple-state.json`, drukuje `Wznawiam ...: odcinek K/N` i liczy odcinek `K+1`.
Zmiana `--seed`/`--alpha`/`--move-cap` między wywołaniami na ten sam plik stanu
jest zablokowana asercją (`ValueError`) — inny parametr dałby przebieg, którego
log kłamie o tym, co mierzył (wzór z `tools/tune_weights.load_state`, #104).

`--episodes-per-run N` liczy `N` odcinków w jednym wywołaniu, zamiast jednego —
przydatne, gdy jedna sesja ma czas na więcej niż jeden odcinek na raz; stan i
wagi są zapisywane po **każdym** odcinku niezależnie od tego parametru, nie
tylko na końcu wywołania.

Seedy partii są wyprowadzone z `(--seed, numer_odcinka)` (`train_ntuple.episode_seed`)
i sprawdzone asercją na rozłączność z `bench/seeds_fixed.json` — ten sam wzór co
`tools/tune_weights.training_seeds()` (#59). Wznowienie po śmierci sesji
odtwarza dokładnie te partie, które zagrałby przebieg nieprzerwany (zweryfikowane
testem `tests/test_train_ntuple.py::TestResumableTraining::
test_resumed_run_matches_continuous_run`: wagi i seedy identyczne dla "2 odcinki
w jednym wywołaniu" vs "2 wywołania po jednym").

## Przebieg dymny (ten zrobiony w tym zadaniu)

Dwa polecenia na pierwszym planie, `ntuple-state.json`/`ntuple-weights.json`
scommitowane w tym repo jako dowód, że stan naprawdę się wznawia:

```
$ python tools/train_ntuple.py --state ntuple-state.json --out ntuple-weights.json --episodes 2 --seed 1
Nowy przebieg ntuple-state.json: 0/2 odcinkow
odcinek 1/2: seed=672817299 wynik=112 postawienia=14 ...
Zapisano ntuple-weights.json i ntuple-state.json (1/2 odcinkow, 1 partii)

$ python tools/train_ntuple.py --state ntuple-state.json --out ntuple-weights.json --episodes 2 --seed 1
Wznawiam ntuple-state.json: odcinek 1/2
odcinek 2/2: seed=1632622963 wynik=68 postawienia=16 ...
Zapisano ntuple-weights.json i ntuple-state.json (2/2 odcinkow, KONIEC, 2 partii)
```

Potem 18 dalszych odcinków w jednym wywołaniu (`--episodes 20 --episodes-per-run 18`)
do zmierzenia przepustowości na więcej niż dwóch punktach — plik stanu w repo
ma więc `20` odcinków, nie `2`; dwa pierwsze wpisy logu są dokładnie powyższą
parą wywołań.

**Epizody na minutę (zmierzone, ten sprzęt, ta sesja)**: 20 odcinków, suma
czasu odcinków (nie czas procesu — ten sam wzór co `duration_s` w
`tools/tune_weights.py`) `0,325 s` → **≈ 3690 odcinków/min** *przy tej długości
partii* (średnio `22,7` postawień/odcinek — polityka zachłanna bez przeszukania
tacki na wagach jeszcze bliskich zeru umiera szybko, oczekiwane). Odporniejsza
na porównania między sprzętem/etapami treningu miara: **≈ 1397 postawień/s**
(454 postawienia / 0,325 s) — to jest to, co ogranicza czas odcinka, nie liczba
odcinków wprost, bo dłużej żyjąca partia (bliżej `110,5` postawień z baseline'u
`tray`/`lookahead`, `docs/research/budzet-wyuczonej-oceny.md`) kosztuje
proporcjonalnie więcej czasu, nie mniej odcinków na sekundę przy stałym koszcie
na postawienie.

Osobno: sama `NTupleValue.value(board)` (bez gry, bez wyboru akcji) mierzy się
na `≈ 92 000 ocen/s` na tym sprzęcie (`tests/test_ntuple.py::TestNTupleValueSpeed`
tylko dowodzi mierzalności, nie asercji na liczbę — sprzęt sesji nieznany z
góry). Różnica między `92 000 ocen/s` i `1397 postawień/s` to koszt
przeszukania akcji (`_choose_action` liczy `value()` raz na każdą legalną akcję
tacki, nie raz na postawienie) plus koszt samej gry (`Game.step`,
`Board.can_place_piece` po komórkach — nieoptymalizowane bitowo, poza budżetem
tego zadania).

## Ile odcinków po 3600 s potrzeba na budżet z #120

`docs/research/budzet-wyuczonej-oceny.md` (sekcja 2) **nie ustaliło** liczby
odcinków — to jest udokumentowany wynik negatywny: literatura N-tuple/TD nie ma
wzoru episody(wagi), a jedyny znaleziony analog `c=2` z usuwaniem linii
(SZ-Tetris, GECCO 2015) użył **4 mln gier** dla sieci >4 mln wag, z hipotezą
(niezweryfikowaną) "nasza sieć, ~1000× mniejsza, prawdopodobnie potrzebuje
wyraźnie mniej — ale to nie jest liczba". Jedyna brakująca liczba nazwana tam
wprost — **przepustowość naszego symulatora** — jest teraz zmierzona (sekcja
wyżej): **≈ 1397 postawień/s, jeden wątek, polityka zachłanna bez przeszukania**.
Z tego arytmetyka (nie nowe ustalenie o tym, ile odcinków *wystarczy* — tylko
przeliczenie sekund→odcinki dla podanej liczby):

| cel (odcinki) | źródło celu | ~postawień/odcinek | ~sekund | ~ile wywołań `--episodes-per-run 1` (bloki 3600 s) |
|---|---|---|---|---|
| 100 000 | rząd wielkości "wyraźnie mniej niż SZ-Tetris", dolny koniec | 22,7 (wczesny etap, umiera szybko) | 1 625 | **1** (< 1 h) |
| 100 000 | jw. | 110,5 (dojrzała polityka, baseline `tray`/`lookahead`) | 7 910 | **3** |
| 1 000 000 | 10× wyżej, wciąż < SZ-Tetris | 110,5 | 79 102 | **22** |
| 4 000 000 | SZ-Tetris (GECCO 2015), górna referencja, **nie cel** | 110,5 | 316 410 | **88** |

**Jak czytać tę tabelę**: kolumny 1–2 to cudzy wybór (#120, niezweryfikowany
pomiarem u nas), kolumny 3–5 to moja arytmetyka z jednej zmierzonej liczby
(postawień/s). Rozstrzygnięcie, **ile odcinków faktycznie potrzeba** dla
`PATCH_LAYOUT` wariantu A na tej grze, wymaga zmierzenia krzywej uczenia
wprost — to jest zadanie `rola:bench`, nie coś, co ten szkielet mógł ustalić.
Rekomendacja praktyczna: zacząć od najmniejszego wiersza (**100 000 odcinków,
~3 bloki 3600 s** przy dojrzałej długości partii) i sprawdzić, czy krzywa
uczenia jeszcze rośnie przed inwestowaniem w więcej — nie zakładać z góry
4 mln.

## Testy

```
python3 -m unittest tests.test_ntuple tests.test_train_ntuple \
    tests.test_lookahead_ntuple_regression tests.test_benchmark_ntuple_weights \
    tests.test_leaf_value_hook tests.test_lookahead_regression -v
```

`test_lookahead_ntuple_regression.py` jest ramieniem odniesienia wymaganym
przez #123: `LookaheadPolicy(weights=weights.json)` na 20 seedach
`bench/seeds_fixed.json` daje dziś **identyczną, znak-w-znak** sekwencję
ruchów co przed dodaniem haka `_leaf_value`/`NTupleLookaheadPolicy` — fixture
`tests/fixtures/lookahead_regression.json` został przechwycony PRZED tą zmianą.

Po scaleniu na `main` (#125) chronią tego samego dwa złote zapisy, nie jeden, i
**żadnego się nie regeneruje**: `test_lookahead_regression.py` (24 partie,
zapis z #118, `tests/data/lookahead_weights_moves.json`) oraz powyższy (20
seedów, zapis z #123). Ten pierwszy pilnuje, że sygnatura z combo nie ruszyła
ruchów; ten drugi — że nie ruszył ich hak liścia. `test_leaf_value_hook.py`
(#125) domyka sam hak: trójka argumentów u haka i u domyślnej oceny jest ta
sama, a adapter N-tuple daje tę samą wartość przy combo 0, 1, 7 i 40.
