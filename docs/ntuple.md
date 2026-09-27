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

### Drugi układ: `AD` (#149)

`square3` zabija **54,7%** partii (`docs/co-zabija-partie.md`), a wariant `A`
z konstrukcji nie widzi kwadratów 3×3 — łata-wiersz/łata-kolumna czyta pełną
linię, nie lokalny kwadrat. `ntuple.LAYOUTS["AD"]` dodaje do `A` wariant `D`
z #120 (kwadraty 3×3, `k=9`) **we wszystkich 36 położeniach** lewego-górnego
rogu na planszy 8×8 (`(8-2) × (8-2) = 36`): `16 + 36 = 52` łaty, `16 × 2**8 +
36 × 2**9 = 4096 + 18432 = 22528` wag. `A` (dzisiejszy `PATCH_LAYOUT`) zostaje
bez zmian — `AD` jest drugim, wybieralnym układem, nie zamiennikiem.

`NTupleValue(layout=...)` przyjmuje uklad jawnie (domyślnie `LAYOUTS["A"]`);
`NTupleValue.load` rozpoznaje układ **z zawartości** pola `patch_layout` pliku
— dopasowuje go do jednego z `ntuple.LAYOUTS`, nie do jednego ustalonego
`cls.layout` jak przed #149 — więc plik z `AD` wczytuje się bez żadnej nowej
składni po stronie wołającego (`benchmark.load_ntuple_weights` woła
`NTupleValue.load` bez zmian). Plik z układem, którego nie ma w `LAYOUTS`,
nadal się nie wczyta (`ValueError`). `tools/train_ntuple.py --layout A|AD`
(domyślnie `A`) zapisuje wybrany układ w stanie tak jak `--alpha`/`--reward`;
wznowienie z innym układem rzuca `ValueError` z tego samego powodu — inny
układ dałby przebieg, którego log kłamie o tym, co mierzył.

**Krok TD dla `AD`.** `NTupleValue.update` (nietknięty) dopisuje `alpha·błąd`
do **każdej aktywnej łaty** — jednej na łatę, czyli do `N_PATCHES` wag na
krok. Efektywna zmiana `V(afterstate)` po jednym kroku jest więc z grubsza
`alpha · N_PATCHES` (każda z aktywnych łat wnosi ten sam błąd raz), rosnąca
liniowo z liczbą łat: `A` ma 16, `AD` ma 52. Żeby krok efektywny dla `AD` był
równoważny `alpha=0.001` dla `A`, `alpha` dla `AD` powinno być
`0.001 · 16 / 52 ≈ 0.000308` — inaczej sieć `AD` uczyłaby się przy tym samym
`--alpha` z krokiem ok. 3,25× większym niż `A`, na innej liczbie wag, więc
krzywe obu układów nie byłyby porównywalne przy tym samym `--alpha`.

### Przebieg dymny `AD`/`survival` i czas na odcinek (#149)

Dwa polecenia, 300 odcinków każde, ten sam seed (`--seed 1`), pliki poza tym
repo (`/tmp`), ewaluacja co 100 odcinków na 20 partiach:

```
python tools/train_ntuple.py --state /tmp/ntuple149-a-state.json --out /tmp/ntuple149-a-weights.json \
    --episodes 300 --episodes-per-run 300 --seed 1 --reward survival --layout A \
    --eval-every 100 --eval-episodes 20 --best-out /tmp/ntuple149-a-best.json

python tools/train_ntuple.py --state /tmp/ntuple149-ad-state.json --out /tmp/ntuple149-ad-weights.json \
    --episodes 300 --episodes-per-run 300 --seed 1 --reward survival --layout AD \
    --eval-every 100 --eval-episodes 20 --best-out /tmp/ntuple149-ad-best.json
```

Czas na odcinek, zmierzony z `<stan>.log.jsonl` (suma `duration_s` z logu / liczba
odcinków — **nie** z pola `duration_s` w samym stanie, patrz odkrycie niżej),
na tych samych 300 odcinkach, ten sam sprzęt/sesja:

| układ | łat | wag | s/odcinek | odcinków/min | postawień/s |
|---|---|---|---|---|---|
| `A`  | 16 | 4096  | 0,01534 | 3910,5 | 1269,0 |
| `AD` | 52 | 22528 | 0,04695 | 1278,0 |  623,7 |

`AD` kosztuje **≈3,06×** więcej czasu na odcinek niż `A` (blisko stosunku
liczby łat 52/16 ≈ 3,25 — `patch_indices` odczytuje każdą łatę raz, więc
koszt na odcinek rośnie w przybliżeniu liniowo z liczbą łat) i daje **≈2,03×**
mniej postawień/s (partie `AD` w tym przebiegu żyją dłużej — więcej
postawień na odcinek — więc spadek postawień/s jest mniejszy niż spadek
odcinków/min). Do doboru rozmiaru bloku `--episodes-per-run` pod limit
3400 s kolejnego zadania: przy `≈0,047 s/odcinek` (górna, bezpieczna granica
z tego pomiaru) blok 3400 s to **≈72 000 odcinków** dla `AD`, dla `A`
(`≈0,015 s/odcinek`) **≈220 000 odcinków** — obie liczby będą mniejsze przy
dłużej żyjących, dojrzałych partiach (patrz analogiczna uwaga dla `A` w
sekcji "Ile odcinków po 3600 s potrzeba" niżej).

Wynik ewaluacji po 300 odcinkach (jedynie dowód, że coś się uczy na tym
budżecie, nie zmierzona krzywa — to zadanie `rola:bench`): `A`
`wynik_sr=190,25 przezycie_sr=18,85`, `AD` `wynik_sr=616,2 przezycie_sr=37,45`.
Nie jest to porównanie wariantów (300 odcinków to szum, nie krzywa uczenia,
patrz #126) — samo `AD` uczy się (błąd TD i wynik ewaluacji nie stoją na
zerze), nic więcej.

**Odkrycie (poza zadaniem, nie naprawiane):** `state["duration_s"]`
(`tools/train_ntuple.py:run_generational`, `state["duration_s"] =
round(state["duration_s"] + elapsed, 1)`) zaokrągla **skumulowaną** sumę do
0,1 s po każdym odcinku — dla partii krótszych niż ~0,05 s (jak w tym
przebiegu `A`) każdy pojedynczy przyrost gubi się w zaokrągleniu i pole
zostaje `0.0` mimo 300 zmierzonych odcinków (wall-clock `time` na to samo
wywołanie: `5,565 s`, nie `0.0`). `<stan>.log.jsonl` ma poprawny,
niezaokrąglany `duration_s` per odcinek — tabela wyżej liczy z niego, nie z
pola stanu.

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

`benchmark.HASHED_SOURCES` **zawiera** `ntuple.py` od [#140](../../issues/140)
(osobny commit): ocena liścia ramienia `lookahead-ntuple:` żyje w tym pliku, więc
odcisk źródeł bez niego nie widział zmiany mierzonej polityki — to wywróciło
pomiar [#127](../../issues/127). Wcześniej (#123) plik był z odcisku świadomie
wyłączony, bo ramię było tylko szkieletem.

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
przydatne, gdy jedna sesja ma czas na więcej niż jeden odcinek na raz. Od #140
stan i wagi nie idą na dysk po każdym odcinku, tylko co `--save-every`
odcinków — patrz sekcja „Sygnał, ewaluacja, zapis przyrostowy (#140)” niżej.

Seedy partii są wyprowadzone z `(--seed, numer_odcinka)` (`train_ntuple.episode_seed`)
i sprawdzone asercją na rozłączność z `bench/seeds_fixed.json` — ten sam wzór co
`tools/tune_weights.training_seeds()` (#59). Wznowienie po śmierci sesji
odtwarza dokładnie te partie, które zagrałby przebieg nieprzerwany (zweryfikowane
testem `tests/test_train_ntuple.py::TestResumableTraining::
test_resumed_run_matches_continuous_run`: wagi i seedy identyczne dla "2 odcinki
w jednym wywołaniu" vs "2 wywołania po jednym").

## Sygnał, ewaluacja, zapis przyrostowy (#140)

Narzędzie pod dwa równoległe treningi porównujące sygnał uczenia. Trzy zmiany,
każda wznawialna tym samym poleceniem co dotąd.

**`--reward score|survival`** (domyślnie `score`). `score` to `gain` gry, bez
zmian (bitowo te same wagi co przed #140). `survival` to nagroda `1` za każde
postawienie i `target = 0` po stanie terminalnym, więc V szacuje liczbę
pozostałych postawień. To opcja sygnału treningu, nie nagrody środowiska —
`game.py`/`scoring.py` są nietknięte. Wartość siedzi w stanie (`params.reward`)
i w pliku wag (pole `reward`); wznowienie z inną rzuca `ValueError`, jak zmiana
`--seed`/`--alpha`/`--move-cap`. Stan i plik wag bez pola `reward` (sprzed #140,
m.in. `ntuple-weights.json`/`ntuple-state.json` w korzeniu repo) czyta się jako
`score`.

`NTupleLookaheadPolicy` maksymalizuje ten sam zwrot, na którym sieć się uczyła:
przy wagach `survival` suma ścieżki w `_tray_beam_search` to liczba postawień
(`placed`), nie punkty; przy wagach `score` — `gain`, jak dotąd.

**`--eval-every N --eval-episodes M --best-out PLIK`**. Co `N` odcinków treningu
narzędzie gra `M` partii zachłanną polityką treningu **bez uczenia** i zapisuje
punkt (odcinki, średni wynik, średnie przeżycie) w stanie. `PLIK` jest
nadpisywany wagami (plus pole `ewaluacja` z punktem), gdy średni wynik jest
najlepszy dotąd — kryterium to wynik dla obu sygnałów. Seedy ewaluacji
(`train_ntuple.eval_seeds`) są te same w każdym punkcie i niezależne od
`--seed`, więc oba treningi grają na tych samych partiach; leżą w
`[2**31, 2**32)`, poza zakresem seedów treningu i rotowanych seedów benchmarku
(`[1, 2**31 - 1)` — rozłączne dla każdego numeru issue), i są asercją rozłączne
z `bench/seeds_fixed.json`. Zmiana `--eval-every`/`--eval-episodes` przy
wznowieniu stanu, który ma już punkty ewaluacji, rzuca `ValueError` —
najlepszy punkt z innego zestawu partii nie byłby porównywalny.

**`--curve-out PLIK`**: krzywa w formacie `docs/data/ntuple-krzywa.json` (okna
po 2000 odcinków, z dodatkowym `sredni_abs_blad_td`) plus sekcja `ewaluacja`
(punkty i najlepszy). Okna są liczone przyrostowo w stanie, nie z logu.

**Zapis przyrostowy.** Stan nie trzyma już logu odcinków: log jest dopisywany
do `<stan>.log.jsonl` (np. `ntuple-state.log.jsonl`), a stan (wagi + małe
liczniki, stały rozmiar) i wagi idą na dysk co `--save-every` odcinków
(domyślnie 100), przy każdej ewaluacji i na końcu wywołania. **Przerwany blok
traci najwyżej `--save-every − 1` odcinków (domyślnie 99)**; wznowienie
powtarza je z tych samych seedów i daje te same wagi co przebieg nieprzerwany.
Log dopisany za ostatnim zapisem stanu jest przy wznowieniu obcinany
(`log_bytes` w stanie). Stan w starym formacie (z `log` w środku) jest przy
pierwszym wznowieniu jednorazowo przenoszony do `.log.jsonl`.

Zmierzone (ten sprzęt, te same odcinki 301–500 wznowione z tego samego stanu,
różni się tylko rozmiar logu, czas procesu / 200):

| kod | log 300 wpisów | log 100 300 wpisów |
|---|---|---|
| przed #140 (pełny stan po każdym odcinku) | 0,0395 s/odc. | 0,7217 s/odc. |
| #140, `--save-every 100` (domyślnie) | 0,0288 s/odc. | 0,0292 s/odc. |
| #140, `--save-every 1` | 0,0373 s/odc. | 0,0369 s/odc. |

Polecenie wznawiania dwóch treningów (każde wywołanie jednym poleceniem na
pierwszym planie; `--episodes-per-run` dobrać pod limit czasu bloku):

```
python tools/train_ntuple.py --state ntuple-score-state.json --out ntuple-score-weights.json \
    --episodes 100000 --episodes-per-run 20000 --seed 1 --alpha 0.001 --reward score \
    --eval-every 1000 --eval-episodes 100 --best-out ntuple-score-best.json \
    --curve-out ntuple-score-krzywa.json

python tools/train_ntuple.py --state ntuple-survival-state.json --out ntuple-survival-weights.json \
    --episodes 100000 --episodes-per-run 20000 --seed 1 --alpha 0.001 --reward survival \
    --eval-every 1000 --eval-episodes 100 --best-out ntuple-survival-best.json \
    --curve-out ntuple-survival-krzywa.json
```

Kolejny blok to to samo polecenie. Liczby `--eval-every`/`--eval-episodes`
wyżej są przykładem, nie decyzją; raz wybrane trzeba trzymać do końca
przebiegu. Plik `--best-out` wchodzi do benchmarku jako
`lookahead-ntuple:<plik>`.

## Przebieg dymny (#123)

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

## Realny trening: 43 020 odcinków, krzywa uczenia (#126)

Wznowienie przebiegu dymnego z #123 (`ntuple-state.json` na 20/20 odcinków,
`--seed 1 --alpha 0.001 --move-cap 2000`), cel podniesiony do `--episodes 100000`.
**Nie osiągnięto 100 000** — sesja skończyła na **43 020 odcinkach** (43 000
nowych w tej sesji); cel z Cel #126 to "tyle, ile zmieści się w jednej sesji",
nie literalnie 100 000. Pięć bloków na pierwszym planie, każdy `--episodes-per-run`
tym samym poleceniem (`--state ntuple-state.json --out ntuple-weights.json
--episodes 100000 --seed 1`), stan i wagi scommitowane po każdym:

| blok | `--episodes-per-run` | odcinki po bloku | czas bloku (rzeczywisty) |
|---|---|---|---|
| 1 | 2000 | 2020 | 1m32.8s |
| 2 | 20000 | 22020 | 46m4.6s |
| 3 | 5000 | 27020 | 19m4.4s |
| 4 | 8000 | 35020 | 36m12.1s |
| 5 | 8000 | 43020 | 42m44.2s |

Wszystkie pięć poniżej limitu 3400 s. Rozmiar bloku był zmniejszany między
blokami 2→3, bo czas na odcinek rósł (patrz odkrycie I/O niżej) — blok 2 na
tamtym tempie przy większym `--episodes-per-run` przekroczyłby 3400 s.

**Przepustowość**: w całym logu (43 020 odcinków) `1 728 756` postawień w
`1255,8 s` czasu obliczeń per-odcinek (`duration_s` ze stanu, suma czasu
`run_episode`, nie czas procesu) → **≈ 1376,6 postawień/s**, tego samego rzędu
co `≈ 1397 postawień/s` z przebiegu dymnego, ale mierzone osobno w pierwszym i
ostatnim oknie po 2000 odcinków daje odpowiednio `≈ 931/s` i `≈ 970/s` — niżej
niż w #123 o ok. 30%, najpewniej inny sprzęt sesji (ta wielkość jest tam wprost
nazwana jako "ten sprzęt, ta sesja", nie stała). Średnio `40,18` postawień na
odcinek w całym logu, `0,0292 s` na odcinek.

### Krzywa uczenia (`docs/data/ntuple-krzywa.json`, okna po 2000 odcinków)

| okno (odcinki) | n | średni wynik | średnie przeżycie |
|---|---|---|---|
| 1-2000 | 2000 | 506,45 | 28,41 |
| 2001-4000 | 2000 | 634,69 | 31,48 |
| 4001-6000 | 2000 | 761,28 | 34,33 |
| 6001-8000 | 2000 | 848,86 | 37,32 |
| 8001-10000 | 2000 | 967,36 | 40,13 |
| 10001-12000 | 2000 | 1034,17 | 41,48 |
| 12001-14000 | 2000 | 1099,04 | 42,72 |
| 14001-16000 | 2000 | 1136,71 | 44,13 |
| 16001-18000 | 2000 | 1165,19 | 44,47 |
| 18001-20000 | 2000 | 1131,37 | 43,16 |
| 20001-22000 | 2000 | 1144,41 | 43,84 |
| 22001-24000 | 2000 | 1198,31 | 44,90 |
| **24001-26000 (szczyt)** | 2000 | **1220,10** | **45,64** |
| 26001-28000 | 2000 | 1155,01 | 44,55 |
| 28001-30000 | 2000 | 1143,42 | 43,99 |
| 30001-32000 | 2000 | 1055,27 | 41,27 |
| 32001-34000 | 2000 | 1031,48 | 41,19 |
| 34001-36000 | 2000 | 980,46 | 40,01 |
| 36001-38000 | 2000 | 912,13 | 38,52 |
| 38001-40000 | 2000 | 896,34 | 37,89 |
| 40001-43020 (ostatnie) | 3020 | 819,42 | 36,39 |

**Werdykt**: krzywa **nie jest płaska ani rosnąca na końcu przebiegu — spada**.
Rośnie monotonicznie od okna 1 do okna 13 (24001-26000: wynik 1220,10,
przeżycie 45,64), potem opada przez 8 kolejnych okien do ostatniego
(40001-43020: wynik 819,42, przeżycie 36,39) — spadek z dwóch ostatnich okien
do porównania: okno 20 (38001-40000) `896,34/37,89` → okno 21 (40001-43020)
`819,42/36,39`, oba w dół. To gorszy wynik niż płaska krzywa: sieć nie tylko
przestała się poprawiać, ona się cofa. Średni `|błąd_td|` na oknie (log)
rośnie z `30,4` (okno 1) do szczytu `~78,8` (okno 13), potem tylko lekko opada
do `~65,9` (okno 21) — nie maleje w stronę zera, co jest zgodne z krzywą wyniku:
sieć nie zbiega, oscyluje/rozjeżdża się.

**Przeżycie kontra wynik**: przeżycie **nie** rośnie szybciej niż wynik — jest
odwrotnie. Od okna 1 do szczytu (okno 13): wynik ×2,41 (506→1220), przeżycie
×1,61 (28,4→45,6). Od okna 1 do ostatniego okna (netto, po spadku): wynik ×1,62
(506→819), przeżycie ×1,28 (28,4→36,4). W obu porównaniach wynik rośnie
proporcjonalnie szybciej niż przeżycie — dokładnie ten wzorzec, przed którym
ostrzega [#119](../../issues/119) ("poprzedni kandydat kupił tempo za
przeżycie i przegrał"), tylko tutaj w nieukończonym, wciąż uczącym się
przebiegu, nie w gotowym kandydacie do benchmarku.

### Odkrycie: zapis pełnego stanu po każdym odcinku kosztuje coraz więcej (rozjazd, nie naprawiane)

*Usunięte w [#140](../../issues/140): zapis przyrostowy, patrz sekcja „Sygnał,
ewaluacja, zapis przyrostowy (#140)”. Opis niżej zostaje jako zapis pomiaru z #126.*

`write_json(args.state, state)` w `tools/train_ntuple.py` serializuje **cały**
`state["log"]` (rosnącą listę wszystkich dotychczasowych odcinków) do pliku na
dysku po **każdym** odcinku, nie tylko przyrost. Zmierzone w tej sesji: `blok 2`
(20 000 odcinków, log rósł z ~2020 do ~22020 wpisów) trwał `46m4,6s` realnego
czasu przy zaledwie `637,5 s` zsumowanego czasu `run_episode` (`duration_s`) —
**różnica ~85% czasu bloku to zapis na dysk**, nie trening. Koszt na odcinek
rósł z blokiem: `~0,046 s/odcinek` (blok 1, log ~2-4 tys. wpisów) →
`~0,229 s/odcinek` (blok 3, log ~22-27 tys. wpisów) — w przybliżeniu liniowo z
rozmiarem logu, więc łączny koszt do 100 000 odcinków rósłby w przybliżeniu
kwadratowo. Ekstrapolacja z dwóch zmierzonych punktów: dobicie od 43 020 do
100 000 odcinków kosztowałoby rzędu **10 godzin** realnego czasu przy obecnym
tempie wzrostu kosztu zapisu, nie godzin przeliczonych z samej przepustowości
symulatora (`docs/ntuple.md` sekcja wyżej). Plik `ntuple-state.json` ważył
`4,2 MB` przy 22 020 odcinkach; przy 43 020 znacznie więcej. To jest dokładnie
rodzaj rozjazdu, o którym mówi Cel #126 ("zaraportuj, nie naprawiaj") —
nie zmieniam formatu zapisu (np. log w osobnym pliku append-only, albo bez
przechowywania pełnego logu w state) w tym zadaniu; to osobna decyzja dla
kolejnego cyklu, bo zmienia format `ntuple-state.json`, na którym opiera się
wznawianie.
