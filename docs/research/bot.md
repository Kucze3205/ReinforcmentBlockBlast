# Jak gra bot: polityka, ocena, most do apki (#370, mapa #361)

Raport wyłącznie z kodu i danych repo (bez internetu). Znaczniki wg `researcher/SKILL.md`: `[D]` = kod/dokument
repo, który przeczytałem; `[K]` = liczba, którą da się odtworzyć (podano jak); `[Z]` = niezweryfikowane.
Wszystkie ścieżki względem korzenia repo, numery linii z `main` @ `06f9f31`.

## Streszczenie

Bot to **ta sama funkcja wywołana na dwa sposoby**: `NTupleLookaheadPolicy.act(game, actions)` dostaje planszę 8×8,
tackę trzech klocków i listę legalnych ruchów, a oddaje jeden ruch `(slot, x, y)`. W symulatorze ruch idzie do `Game.step`,
w prawdziwej apce most (`bridge.py`) odczytuje planszę i tackę ze zrzutu ekranu i wykonuje ruch gestem przez ADB.
- **Co robi polityka** `[D]`: rozwija **całą bieżącą tackę** (3 klocki, w dowolnej kolejności i pozycjach) wiązką 128 najlepszych
  stanów po każdym postawieniu. Stany końcowe ocenia sumą `punkty × 100 + ocena planszy`; przeżycie zapewnia
  `complete=1` (odrzuca ułożenia, które nie zużywają całej tacki; gdy wiązka takiego nie ma, robi przegląd wyczerpujący).
- **Ocena planszy** `[D]` = sieć n-tuple: 196 łat (wiersze, kolumny, kwadraty 3×3, prostokąty 2×3, 3×4), każda łata to
  tablica odczytu po wzorcu zajętych pól; razem **273 664 wagi**, plik 7,9 MB. Ocena ≈ „ile postawień jeszcze przeżyje ta
  plansza"; uczona TD(0) na nagrodzie `1 za postawienie`, 600 tys. odcinków (używany plik: stan z 400 tys.).
- **Kara terminalna: nie ma.** Nagroda gry to przyrost punktów; koniec partii nie dostaje kary (`game.py` zwraca przyrost
  ostatniego ruchu). Przeżycie bierze się z sygnału uczenia oceny, nie z kary w grze.
- **Wynik** `[K]`: w symulatorze 0 przegranych na 300+300 partii przy sufitie 64 000 ruchów (`bench/record.json`);
  na oryginale seria s7: 10/10 partii do 1 mln licznika apki (`GOAL_REACHED`, `docs/seria/s7/*/pomiar.json`).
- **Tempo** `[K]`: 18,4–26,9 postawień/min (mediana serii ~21,3); jeden ruch ≈ 2,6 s, z czego decyzja polityki ≈ 3 ms (0,1%),
  reszta to zrzuty ekranu, gest i czekanie na animacje.

## Ustalenia (pojęcia w kolejności dla laika)

### 1. Gra i punktacja (`game.py`, `scoring.py`, `board.py`)

- `[D]` Plansza 8×8, pole puste/zajęte. Gracz dostaje **tackę trzech klocków**; klocków nie wolno obracać. Stawia je jeden po
  drugim w dowolnej kolejności; po trzecim dochodzi nowa tacka (`game.py:74` `apply_placement`, odświeżenie po
  `round_placement == 3`). Pełny wiersz lub kolumna znika. Partia kończy się, gdy **żaden** pozostały klocek tacki nie mieści
  się na planszy (`game.py:110` `_can_place_any`).
- `[D]` 15 typów klocków (kropka, belki 2–5, kwadraty, L, T, S, przekątne, ...), po domknięciu na obroty/odbicia **41 pozycji**
  (`pieces.py`; zbiór klocków oryginału jest rekonstrukcją, nie pomiarem: `docs/calibration-assumptions.md`, Z-5).
- `[D]` Punkty za jeden ruch (`scoring.py`): `komórki klocka + combo × B(l)`, gdzie `B(0)=0`, `B(1)=10`, `B(l≥2)=10·l·(l−1)`,
  `l` = linie wyczyszczone naraz, `combo` liczone **po** zwiększeniu. Plansza pusta po ruchu: +300.
- `[K]` Przykłady (`scoring.clear_points`): klocek 4-polowy, 1 linia, combo 1 → 4+10 = **14**; ta sama linia przy combo 5 →
  4+50 = **54**; 2 linie naraz przy combo 3 → 3×(10·2·1) = **60** + komórki klocka; 3 linie przy combo 4 → 4×60 = **240**.
  Combo rośnie o 1 przy każdym ruchu czyszczącym, **nie** o liczbę linii.
- `[D]` Combo wygasa przez licznik: po czyszczeniu `combo_counter = 3 + (klocki zostałe w tacce)`; każdy ruch bez czyszczenia
  odejmuje 1; gdy licznik ≤ 1 przy ruchu bez czyszczenia, combo = 0 (`game.py:74-101`). To dlatego łańcuch czyszczeń „co ruch"
  daje punkty rosnące kwadratowo (`docs/combo-w-ocenie.md`).
- `[K]` Skala w symulatorze: rekord ≈ 690 pkt/postawienie, 44,16 mln średnio na partię 64 000 ruchów (`bench/record.json`,
  `docs/journal/cykl-0034.md`). Licznik **apki** liczy inaczej niż nasz wzór (`docs/punktacja-apka-vs-wzor.md`): w s7 do 1 mln
  licznika apki wystarczyło od 919 do 3299 postawień (`docs/seria/s7/partia-*/pomiar.json`), więc „1 mln" nie przekłada się
  na stałą liczbę ruchów.

### 2. Generator tacek (`generator.py`)

- `[D]` Typ klocka losowany z **wag zmierzonych na moście** (978 klocków z 326 tacek; `PIECE_TYPE_WEIGHTS = [13, 60, 56, 135,
  58, 100, 116, 53, 33, 141, 32, 7, 6, 79, 89]`, `generator.py:43`, metoda: `docs/generator-wagi-typow.md`), potem
  jednostajnie jedna z orientacji typu. Rzadkie: przekątna 2 i przekątna 3 (wagi 7 i 6), częste: L (141) i belka 4 (135).
- `[D]` **Generator świadomy planszy**: wylosowana tacka musi dać się ułożyć w całości na bieżącej planszy (z czyszczeniem linii
  między ruchami), inaczej losuje się od nowa (`board.tray_playable`, `generator.py:74`). Dopasowanie na 693 parach z mostu wybrało ten
  model (`docs/z6-model-generatora.md`).
- `[Z]` Że oryginał robi dokładnie to samo, wiadomo tylko pośrednio: model pasuje do danych z mostu; mechanizmu oryginału nikt
  nie widział. Seria s7 (10/10 do 1 mln) jest dowodem skuteczności bota, nie dowodem, że oryginał gwarantuje grywalną tackę.
- `[D]` Bot **nie zna przyszłej tacki**: widzi tylko trzy aktualne klocki. Wariant z losowaniem następnej tacki (`samples>0`, drugi
  poziom) w rekordzie jest wyłączony: `samples=0`.

### 3. Wiązka 128 (`policies.py:414` `_tray_beam_search`)

Wyobrażenie: ruch na planszy to drzewo wyborów. Z planszy `P` i tacki {A, B, C} jest kilkadziesiąt do ~140 legalnych ruchów
pierwszego klocka; po każdym z nich kilkadziesiąt kolejnych itd. Pełne drzewo to dziesiątki–setki tysięcy plansz na tackę, więc po
każdym poziomie bot zostawia tylko **128 najlepiej ocenionych** (wiązka, *beam search*).
1. `[D]` Poziom 0: wszystkie legalne ruchy wszystkich trzech klocków (`_tray_legal_actions`), każdy daje nowy stan (`_expand`, kopia
   logiki `game.py` z gain, combo, licznikiem, +300 za pustą planszę).
2. `[D]` Każdy stan dostaje `score = ścieżka + ocena(plansza)` (niżej), stany sortowane malejąco, zostaje 128.
3. `[D]` Poziomy 1 i 2 powtarzają to dla pozostałych klocków (dowolny klocek w dowolnej kolejności).
4. `[D]` Po ostatnim poziomie z najlepszego stanu bierze się **pierwszą akcję** i tylko ją się wykonuje; po ruchu gra woła `act` od nowa
   (kolejne ruchy tej samej tacki są przeliczane na nowo).
- `[K]` Przykład z symulatora (seed 7, `NTupleLookaheadPolicy` z wagami rekordu, uruchomienie w czystym Pythonie bo rdzeń C nie jest
  dostępny na tej maszynie): pusta plansza, tacka {belka 5, kwadrat 2×2, belka 2} → **137** legalnych ruchów, **16 065** rozwiniętych
  kandydatów, decyzja 745 ms; ruch 2 tej samej tacki: 90 legalnych, 3 652 kandydatów; ruch 3: 45 legalnych, 45 kandydatów
  (ostatni klocek = brak wyboru po pierwszym poziomie). Na 60 ruchach: mediana 54,5 legalnych ruchów, 1 105 kandydatów.
  Skrypt: patrz „Jak odtworzyć" na końcu.
- `[K]` Czas decyzji: z rdzeniem natywnym (`ntuple_native.c`) mediana 2,6 ms, p95 16,6 ms, max 86 ms na 3299 ruchach partii s7/1
  (`docs/seria/s7/partia-1/pomiar.json`, pole `decision_ms`); bez rdzenia mediana 50 ms w przykładzie wyżej.
- `[D]` `gain_weight=100000` = w ścieżce **jeden punkt waży 100 postawień** (`placed + w/1000 · gain`, `docs/punkty-na-postawienie.md`).
  Ocena planszy ma rząd ~200 i różnice między planszami rzędu jednostek (`[K]` w przykładzie: 199,8–209,9), więc w praktyce
  o wyborze między kompletnymi ułożeniami rozstrzygają **punkty**, a ocena sieci tylko remisy punktowe. `[D]` To zmiana z #248:
  przy gwarancji tacki partie nie umierają, więc o średniej decydują punkty na postawienie.
- `[D]` Combo w oglądanej ścieżce jest uwzględnione tylko przez `gain` (punkty policzone wzdłuż ścieżki w obrębie tacki); sam liść
  oceny **nie widzi combo** (decyzja #125, pomiar #122: człon combo w liściu −6,6%, `docs/combo-w-ocenie.md`).

### 4. Gwarancja tacki `complete=1` (`policies.py:349`, `docs/gwarancja-tacki.md`)

- `[K]` Skąd się wzięła: pomiar #236 (100 partii starszego rekordu bez gwarancji): **100/100 śmierci** to „chybienia wiązki"
  (tacka dawała się ułożyć w całości, wiązka 128 tego ułożenia nie znalazła) (`docs/data/death-avoidability-100.json`).
- `[D]` Działanie: z ostatniego poziomu wiązki zostają **tylko stany, w których zużyto całą tackę**; wybór wśród nich robi ta sama
  ocena. Gdy wiązka takiego stanu nie ma, `_tray_complete_search` robi przegląd wyczerpujący (bez przycinania, scalając identyczne
  plansze); mediana ~2 261 plansz końcowych na tackę. Gdy tacki naprawdę nie da się ułożyć, zostaje wynik wiązki.
- `[K]` Efekt: 0/300 przegranych fixed i 0/300 rotated przy sufitie 64 000 ruchów (`bench/record.json`, #279; sufit ≈ 16× dłużej niż
  potrzeba do 1 mln licznika apki, szacunek właściciela ~3 950 postawień z #262).

### 5. Ocena n-tuple (`ntuple.py`, `tools/train_ntuple.py`)

**Czym jest.** `[D]` Zamiast ręcznych cech to **tablica odczytu po fragmentach planszy**. Łata (*patch*) to zbiór pól, np. jeden
wiersz (8 pól). Wzorzec zajętości łaty (0/1 na każdym polu) to liczba 0…2ᵏ−1, indeks do tablicy wag **tej łaty**. Ocena planszy =
**suma** wag odczytanych ze wszystkich łat (funkcja liniowa po cechach „łata X ma wzorzec Y"). Ocena pustej planszy = suma wag z
indeksu 0 każdej łaty.

**Układ `ADCE`** `[D]` (`ntuple.py`, `docs/ntuple-wieksze-laty.md`), policzone `[K]` z pliku wag
(`python -c "import json; w=json.load(open('ntuple/survival-adce-400k.json'))['weights']; print(len(w), sum(map(len,w)))"` → `196 273664`):

| rodzina łat | liczba | pól w łacie | wpisów w tablicy | wag razem |
|---|---|---|---|---|
| wiersze + kolumny (A) | 16 | 8 | 256 | 4 096 |
| kwadraty 3×3, wszystkie położenia (D) | 36 | 9 | 512 | 18 432 |
| prostokąty 2×3 i 3×2 (C) | 84 | 6 | 64 | 5 376 |
| prostokąty 3×4 i 4×3 (E) | 60 | 12 | 4 096 | 245 760 |
| **razem** | **196** | | | **273 664** (plik JSON 7,9 MB) |

Uzasadnienie wyboru łat `[D]`: `square3` i `rect23` to klocki, które najczęściej kończą partie (76,9% razem, `docs/co-zabija-partie.md`),
stąd kwadraty i prostokąty obok wierszy/kolumn. Pojemność kupiła jakość: `ADCE` bije `ADC` +23,6% przy 100 tys. odcinków i +34,6% przy
200 tys. (`docs/ntuple-wieksze-laty.md`).

**Jak uczona.** `[D]` TD(0) po „stanach następczych" (*afterstate* = plansza zaraz po ruchu i czyszczeniu, przed dociągiem tacki;
`tools/train_ntuple.py`, `run_episode`). Bot gra zachłannie z oceną `r + V(afterstate)`, a po każdym kroku:
`V(poprz.) += α · (r + V(nast.) − V(poprz.))`; po końcu partii cel = 0. Sygnał `survival`: `r = 1` za każde postawienie, więc
`V` szacuje **liczbę postawień, jakie plansza jeszcze przeżyje**. Parametry pliku `survival-adce-400k.json` `[K]` (z
`ntuple/survival-adce-state.json`): α = 8,16·10⁻⁵ (= 0,001·16/196, skalowanie od układu A), `move_cap` 2000, seed 3, 1 etap,
nowy generator świadomy planszy; plik wag to zapis po 400 tys. odcinków z jednego przebiegu 600 tys. (łącznie 15 673 s CPU treningu).
- `[K]` Przykład: ocena pustej planszy `V = 208,6` (≈ „przeżyje ~209 postawień"); w 60 ruchach partii przykładowej (seed 7) ocena
  mieściła się w 199,8–209,9 i nie jest monotoniczna po liczbie zajętych pól.
- `[D]` Porównanie sygnałów: `survival` > `score` (`docs/ntuple-survival.md`, cykl 28), dlatego przeżycie jest sygnałem uczenia, a w
  grze punkty jedynie rozstrzygają remisy.

**Kara terminalna / combo / gain_weight w jednym miejscu** `[D]`:

| element | gdzie | wartość / rola |
|---|---|---|
| kara za przegraną | `game.py` | **brak**; krok terminalny zwraca przyrost ostatniego ruchu (`docs/kara-terminalna-decyzja.md`, #56); `-5` tylko w nieosiągalnym `wrong_placement` |
| nagroda w treningu oceny | `train_ntuple.py` | `r = 1` na postawienie (`--reward survival`), cel 0 po końcu |
| combo w ocenie liścia | `policies.py:345` | **ignorowane** (#125); wpływa tylko przez `gain` w ścieżce |
| `gain_weight` | `policies.py:278` | 100 000 → punkt = 100 postawień w sumie ścieżki |
| `complete` | `policies.py:349` | 1 → tylko stany z całą tacką |
| `beam` | `policies.py:414` | 128 (`beam=256` ≈ `beam=128`, `docs/journal/cykl-0034.md`) |
| `samples` | `policies.py:221` | 0 (bez drugiego poziomu) |

### 6. Po stronie apki: most (`bridge.py`)

Specyfikacja polityki używanej w serii `[K]`: `lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000`
(pole `polityka` w każdym `docs/seria/s7/partia-*/pomiar.json`).

Pętla jednego ruchu (`bridge.py:1040` `main`), emulator 320×640, apka `com.block.juggle`:

```
zrzut ekranu (adb exec-out screencap)
  -> read_board  : 64 komórek, średnia kolor z okna 11x11 px w środku pola; is_block = nasycony+jasny albo zielony/fioletowy wyjątek
  -> read_tray   : pasek y=440..585 w 3 slotach po 1/3 szerokości; maska klocka bez tła (mediana paska), kształt = obwiednia / 16 px na komórkę
  -> read_score  : cyfry HUD dopasowane do wzorców (bridge_digits*.npz), None gdy niejednoznaczne
  -> legal_moves + make_game_stub -> policy.act(...)   (decyzja ~3 ms)
  -> drag(slot, piece, x, y) : DOWN + 10x MOVE jednym `adb shell`, 0,5 s czekania, zrzut celowania, UP
  -> stable_state : zrzuty co 0,2 s do dwóch identycznych odczytów
  -> porównanie z `expected` (symulacja ruchu): ok / rozbieżność -> zapis wiersza do bridge-out/moves.jsonl
```

- `[D]` **Geometria** (`bridge.py:42-68`): plansza zaczyna się w (17,136) px, komórka 35,6 px; komórka tacki 16 px. Po podniesieniu klocek
  jest `LIFT = 80,6` px nad palcem i przesuwa się `DRAG_GAIN = 1,5` razy szybciej niż palec, więc `drag` liczy punkt palca
  z celu: `fx = sx + (cx − sx)/1,5`, `fy = sy + (cy − (sy − LIFT))/1,5`. Wartości zmierzone na emulatorze; aktualizacja gry może je zepsuć.
- `[K]` Przykład wiersza z s7 (`docs/seria/s7/partia-1/chunk3_moves.jsonl`, `n=40`): licznik 34 400, tacka {L 3×2, kolumna 2×3 z podstawą, belka 4}, ruch
  `slot 0 → (x=2, y=5)`, palec w (104,5; 466,3), `ok=true`; czasy ms: odczyt 630, decyzja 5,7, przeciągnięcie 1 092, stabilny stan 576.
  Wiersz niesie `board`, `tray` (maski klocków), `move`, `expected`, `observed`, `t_ms`.
- `[K]` Mediany czasu ruchu (150 ruchów kawałka 3 partii 1): odczyt 607 ms, decyzja 3,2 ms, przeciągnięcie 1 112 ms, stabilny stan
  899 ms; łącznie ≈ 2,6 s, czyli ≈ 23 ruchy/min teoretycznie; zmierzone tempo serii 18,4–26,9 postawień/min
  (`docs/seria/s7/partia-*/pomiar.json`, pole `postawien_na_minute`; stara ścieżka 12,6/min w #262, `docs/most-tempo.md`).
  Wszystkie 150 ruchów tego kawałka `ok=true`.
- `[D]` **Stan, który bot „dostaje"**: stub gry z planszą, tacką i **`combo=0`, `combo_counter=3` zawsze** (`make_game_stub`,
  `bridge.py:1016`). Bot nie śledzi combo apki; ścieżka w wiązce liczy punkty od combo 0 w każdym ruchu. Skutek dla jakości wyboru nie
  był zmierzony osobno (patrz „Czego nie wiadomo").
- `[D]` **Licznik apki** służy do zatrzymania, nie do decyzji: `ProgLicznika` — odczyt HUD ≥ progu przez 3 kolejne odczyty daje wpis
  `stop_prog`; `tools/partia_serii.py` potwierdza go dwoma zgodnymi odczytami (do 5 ponowień co 1,5 s, bo licznik po ostatnim ruchu
  jeszcze się doliczał, `docs/seria/s7/stop-prog.md`). Próg 1 000 000 = limit długości partii ustalony przez właściciela
  (`CONTEXT.md`, „Cel").
- `[D]` **Okna spoza gry** (reklamy wideo/interaktywne/statyczne/jasne, ustawienia, menu główne, ekran startowy, dialog wyjścia, nakładka
  pucharu, ekran końca partii) most rozpoznaje po progach pikseli i obsługuje (wstecz, „Skip", „Classic", czekanie); bezpiecznik
  `PROGRESS_SAFEGUARD_TRIES=12` wpisów bez ruchu → twardy restart apki, drugi taki ciąg kończy kawałek.
  Napisy „Perfect!/Combo N" na planszy mają kolory klocków i są odfiltrowywane funkcjami `drop_banner_ghosts`/`drop_banner_text`
  (`docs/seria/ok-false.md`).
- `[K]` Wynik końcowy: `GOAL_REACHED` — seria s7, run 37046972994 @ `40137e2`, apka 10.7.5: **10/10 partii do 1 mln licznika**, 0 przegranych,
  0 przerwań, 0 ponowień. Długość partii (postawienia / minuty): 919 / 43,8 … 3 299 / 155,8 (`pomiar.json` partii 1–10).

## Kandydaci do ilustracji (z danymi, które już są w repo)

| # | Co pokazać | Dane / źródło |
|---|---|---|
| 1 | Plansza 8×8 + tacka + jeden ruch, numery komórek zgodne z `(slot, x, y)` | dowolny wiersz `docs/seria/s7/partia-*/chunk*_moves.jsonl` (`board`, `tray`, `move`) + `*_state.png`/`*_aim.png` |
| 2 | Punktacja: ten sam klocek przy combo 1 vs 5; 1, 2, 3 linie naraz; licznik wygasania combo | `scoring.py` (liczby w §1) |
| 3 | Animacja drzewa wiązki: 137 ruchów → 128 stanów → ... → wybór pierwszego ruchu | przykład z §3 (137 / 90 / 45 legalnych, 16 065 kandydatów), do dopasowania na realnej planszy |
| 4 | Łata sieci n-tuple: wiersz jako 8 bitów → indeks → waga → suma po 196 łatach; mapa „gdzie leży która rodzina łat" | `ntuple.py` `LAYOUTS["ADCE"]`, `ntuple/survival-adce-400k.json`; tabela z §5 |
| 5 | Krzywa uczenia oceny: przeżycie (postawienia) vs odcinki | `docs/data/ntuple-survival-krzywa.json`, `ntuple/survival-adce-state.json` (okna), `bench/` rekordy |
| 6 | Dlaczego `complete=1`: plansza, na której wiązka gubi ułożenie całej tacki, a przegląd wyczerpujący je znajduje | `docs/data/death-avoidability-100.json` (100 przypadków), `docs/gwarancja-tacki.md` |
| 7 | Pipeline mostu: zrzut → odczyt → decyzja → gest → odczyt; czasy kroków (607 / 3 / 1 112 / 899 ms) | §6, `t_ms` w `moves.jsonl` |
| 8 | Zrzut z nałożoną siatką odczytu (zielone/magenta kropki = odczytane pola) | `bridge.annotate`; zapisywane tylko przy `BRIDGE_TEMPO=stare` i jako `final.png` |
| 9 | Geometria gestu: tor palca, `LIFT`, `DRAG_GAIN`, zrzut `*_aim.png` przed puszczeniem | `bridge.drag`, `docs/seria/s7/partia-*/kawalek_*/*_aim.png` (jeśli są zachowane) |
| 10 | Liczba postawień/minuta i czas do 1 mln w 10 partiach s7 | `pomiar.json` partii 1–10 |

## Cytaty

Nic nie przepisano z zewnątrz. Cytaty z własnych plików repo (jedyne dosłowne):

> Combo jest MNOŻNIKIEM całego bonusu za czyszczenie, nie dodatkiem (R-2).
> — `scoring.py`, docstring

> Liść ocenia wyłącznie planszę, bez członu combo (decyzja #125).
> — `policies.py`, docstring `NTupleLookaheadPolicy`

## Czego nie wiadomo

- Czy oryginał gwarantuje grywalną tackę (jak nasz generator „do skutku"), czy to artefakt dopasowania do 693 par: `[Z]`.
- Wpływ `combo=0` w stubie mostu na jakość decyzji: bot w apce liczy `gain` bez prawdziwego combo; skutek w serii nie był mierzony
  osobno (s7 przeszło 10/10, ale to nie izoluje wpływu).
- Dokładny rozkład czasu ruchu w całych 10 partiach s7: tu podano medianę z jednego kawałka (150 ruchów); `pomiar.json` ma
  `decision_ms` dla partii, ale nie ma sumarycznego `t_ms` w części plików; rozkład „odczyt/przeciągnięcie/stabilny stan" liczono
  tylko dla `chunk3` partii 1.
- Ile z 273 664 wag jest aktywnych w typowej partii (które wzorce łat realnie występują): nie mierzono; tabela wag nie była analizowana
  wzorzec po wzorcu.
- Rdzeń natywny (`ntuple_native.c`) nie wczytał się na tej maszynie (Windows, brak biblioteki): liczby czasowe z przykładu
  (745 ms, mediana 50 ms) pochodzą z czystego Pythona; czasy z rdzeniem to dane serii s7 z runnera.
- Stabilność geometrii (`BOARD_X`, `LIFT`, `DRAG_GAIN`) wobec aktualizacji apki albo innej skórki/rozdzielczości: zmierzono tylko dla apki
  10.7.5 na emulatorze 320×640.

## Jak odtworzyć liczby z §3 i §5

`python` na korzeniu repo, polityka z `benchmark.build_policy("lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000", {"torch_seed": 0})`,
`Game(seed=7)`, `policy.reset(7)`, pętla `policy.act(game, game.available_actions())` + `game.step`; odczyty: `policy.last_expanded`
(kandydaci), `len(actions)` (legalne), `policy.ntuple.value(game.board)` (ocena). Skrypt roboczy nie jest w repo.
