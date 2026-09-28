# Wagi typów klocków w `generator.py` — kalibracja z danych mostu (#186)

Bilet: [#186](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/186) · poprzedzające pomiary:
[#182](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/182) (`docs/z6-tacka-a-plansza.md`, sekcja
„Pomiar 2") i [#78](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/78) · skrypty:
`tools/z6_artefakt.py` (sprawdzenie artefaktu rozpoznawania), `tools/z6_wagi.py` (wagi typów i test
orientacji) · dane: `docs/data/z6-pary.json` (ekstrakcja `tools/z6_pary.py`, teraz z dołożonym przebiegiem
`bridge/runs/d878d79/`).

Pomiar #182 odrzucił jednostajność typów (1/15) na progu p ≈ 2,8·10⁻⁷² (897 klocków, 299 tacek), ale nie
zmienił `generator.py` — to zadanie ekstrahuje z tego samego rodzaju danych konkretne wagi i wpisuje je do
kodu. Świadomość planszy (Z-6 sensu stricto — czy dobór klocków zależy od KONKRETNEJ planszy) zostaje
nierozstrzygnięta i **nietknięta**: generator dalej losuje trzy klocki niezależnie od stanu planszy, zmieniają
się wyłącznie wagi typów.

## Wykluczenie artefaktu rozpoznawania

Pytanie: czy niedobór `diag2`, `diag3`, `1x1` w próbie jest tym, że most częściej gubi (czyta jako pusty
slot albo nie rozpoznaje kształtu) akurat te klocki — bo są najmniejsze/najbardziej "dziurawe" i najtrudniejsze
do złapania progiem `is_block` w `bridge.read_tray` (zwraca `None` przy < 20 dopasowanych pikselach)? Jeśli
tak, całe tacki z tymi klockami wypadałyby z próby `z6-pary.json` (który liczy tackę tylko, gdy wszystkie
trzy sloty są rozpoznane), co zaniżałoby ich obserwowaną częstość niezależnie od prawdziwej wagi generatora.

**Metoda** (`tools/z6_artefakt.py`): "świeża tacka" zdefiniowana strukturalnie, nie przez pełne rozpoznanie
(inaczej niż filtr `_is_full_tray` w `tools/z6_pary.py`, który sam wymaga pełnego rozpoznania i dlatego nie
nadaje się do zmierzenia stopy utraty). Wiersz `i` liczy się jako świeża tacka, gdy poprzedni wiersz `i-1`
(w tym samym pliku) miał dokładnie 1 niepusty slot — czyli poprzedni ruch postawił ostatni klocek starej
tacki, a wiersz `i` to pierwszy odczyt PO tym ruchu, kiedy powinna pojawić się nowa, pełna tacka. Dla każdego
takiego wiersza liczymy 3 sloty: `pusty` (`tray[slot] is None`), `nierozpoznany` (kształt nie pasuje do
żadnej z 41 póz `pieces.py`) albo `rozpoznany`. `bridge/runs/d550db3/pomiar.json` nie ma surowych `*.jsonl`
(już jest przefiltrowany do 100% rozpoznanych z pomiaru #78), więc nie wnosi wierszy do tego liczenia.

**Wynik** (wszystkie 47 plików `*.jsonl` z `bridge/runs/*/`, poza `d550db3`):

| wielkość | wartość |
|---|---|
| plików przeskanowanych | 47 |
| świeżych tacek (strukturalnie) | 301 |
| sloty łącznie (301 × 3) | 903 |
| sloty puste (`None`) | 3 |
| sloty niepusty-ale-nierozpoznany kształt | 3 |
| sloty rozpoznane | 897 |
| **stopa utraty slotu** | **0,0066** (6 / 903) |
| tacki z ≥1 utraconym slotem | 2 / 301 |

**Porównanie z niedoborem.** Pomiar #182 (i powtórzony tu na 326 tackach, patrz niżej) pokazuje niedobór
rzędu 40–53 obserwacji na typ dla `1x1`/`diag2`/`diag3` względem oczekiwanych ~65 przy 1/15 (deficyt sumaryczny
ok. 150 z 195 oczekiwanych na te trzy typy łącznie). Nawet w najbardziej skrajnym, niemożliwym do utrzymania
założeniu, że WSZYSTKIE 6 utraconych slotów w całej próbie należało do tych trzech typów, wyjaśniałoby to co
najwyżej 6 z ~150 brakujących obserwacji — **0,66% stopy utraty nie może wyjaśnić deficytu rzędu 75% oczekiwanej
liczby dla tych typów.** Wniosek: niedobór `1x1`/`diag2`/`diag3` **nie jest artefaktem rozpoznawania**, tylko
realną (nierówną) wagą, z jaką te typy wypadają z generatora oryginału. `generator.py` można bezpiecznie
kalibrować na tych danych.

## Źródło i liczność próby

Użyto **wszystkich** 326 zweryfikowanych par z `docs/data/z6-pary.json` po dołożeniu przebiegu
`bridge/runs/d878d79/` (94 ruchy, #181) do wcześniejszych 299 z #182 — `tools/z6_pary.py` uruchomiony
ponownie bez zmian w logice ekstrakcji, tylko z nowym przebiegiem na dysku. Uzasadnienie wyboru:

- **Cała dostępna próba, nie podzbiór.** Sekcja wyżej pokazuje, że stopa utraty slotu przy weryfikacji jest
  znikoma (0,66%), więc dodatkowe filtrowanie (np. tylko przebiegi z najwyższą jakością odczytu) nie zmienia
  jakości próby, tylko zmniejsza jej liczność — a przy typach z już observed n < 10 (`diag2`, `diag3`) każda
  utracona obserwacja bezpośrednio poszerza przedział ufności.
- **Jednostka próby to tacka, licząc każdą raz.** Trzy klocki jednej tacki nie są niezależnymi próbami tego
  samego mechanizmu losowania w sensie "porównywalnych warunków" — ale są trzema niezależnymi losowaniami
  generatora w ramach tej samej wywołanej tacki (`next_pieces()` = trzy niezależne `_next_piece()`), więc
  liczenie 3 × 326 = 978 klocków jako 978 obserwacji jest zgodne z modelem H0 (`generator.py`: trzy klocki
  niezależnie). Deduplikacja (plansza + trzy nazwy w kolejności slotów) w `tools/z6_pary.py` już usuwa
  duplikaty z retry-loopów mostu, więc tacki nie są liczone wielokrotnie.
- 978 obserwacji na 15 kategorii daje oczekiwaną liczność ~65/typ przy 1/15 — dość, by odróżnić 2× i 0,2×
  efekty widoczne w pomiarze #182, za mało, by ufnie kalibrować POŁOŻENIE (orientację) rzadszych typów
  (`diag2`: 7 obs., `diag3`: 6 obs.) — stąd orientacja zostaje 1/n (patrz niżej), nie osobno ważona.

## Wagi typów

`tools/z6_wagi.py`: MLE = `n_obs / 978` (proporcja multinomialu), przedział ufności Wilsona 95% (dwumianowy
per typ, standardowe przybliżenie marginesu multinomialu; bez korekty za liczbę typów — to opis rozkładu,
nie test istotności).

| typ | komórki | n obserwacji | waga (MLE) | CI 95% |
|---|---|---:|---:|---|
| L | 4 | 141 | 0,1442 | [0,1235; 0,1676] |
| beam4 | 4 | 135 | 0,1380 | [0,1178; 0,1611] |
| rect23 | 6 | 116 | 0,1186 | [0,0998; 0,1404] |
| square2 | 4 | 100 | 0,1022 | [0,0848; 0,1228] |
| T | 4 | 89 | 0,0910 | [0,0745; 0,1107] |
| S | 4 | 79 | 0,0808 | [0,0653; 0,0995] |
| beam2 | 2 | 60 | 0,0613 | [0,0480; 0,0782] |
| beam5 | 5 | 58 | 0,0593 | [0,0462; 0,0759] |
| beam3 | 3 | 56 | 0,0573 | [0,0444; 0,0736] |
| square3 | 9 | 53 | 0,0542 | [0,0417; 0,0702] |
| corner3 | 3 | 33 | 0,0337 | [0,0241; 0,0470] |
| corner5 | 5 | 32 | 0,0327 | [0,0233; 0,0458] |
| 1x1 | 1 | 13 | 0,0133 | [0,0078; 0,0226] |
| diag2 | 2 | 7 | 0,0072 | [0,0035; 0,0147] |
| diag3 | 3 | 6 | 0,0061 | [0,0028; 0,0133] |

Suma obserwacji: 978 (326 tacek × 3). Wzorzec zgadza się z pomiarem #182 na 299 tackach: `L`/`beam4`/`rect23`
najczęstsze (~1,7–2,2× oczekiwania pod 1/15), `1x1`/`diag2`/`diag3` najrzadsze (~0,1–0,2×). Dołożenie
`d878d79` (27 nowych par) nie zmienia kierunku ani rzędu wielkości żadnej wagi.

`generator.py` koduje te wagi jako `PIECE_TYPE_WEIGHTS` — surowe liczby obserwacji (nie znormalizowane
ułamki), bo `random.Random.choices(weights=...)` normalizuje sam, a liczby całkowite unikają błędów
zaokrąglenia i są bezpośrednio audytowalne względem tabeli wyżej.

## Orientacja w obrębie typu

Kryterium: orientacja zostaje 1/n, chyba że test na danych odrzuca to po korekcie na liczbę typów. Test:
dla każdego typu z >1 pozą, chi-kwadrat częstości póz WEWNĄTRZ tego typu (nie całej puli 41 póz — łączny
test na całej puli byłby konfundowany nierównymi wagami typów, patrz zastrzeżenie w
`docs/z6-tacka-a-plansza.md` przy teście (a)) wobec jednostajnego 1/n_poz, na klockach tego typu z tych
samych 326 tacek. Korekta Bonferroniego za 12 testowalnych typów (`1x1`, `square2`, `square3` mają dokładnie
1 pozę — nie da się ich testować), α = 0,05/12 = 0,00417.

| typ | n póz | n obs | chi² | df | p | werdykt (α=0,00417) |
|---|---:|---:|---:|---:|---:|---|
| beam2 | 2 | 60 | 0,600 | 1 | 0,439 | 1/n OK |
| beam3 | 2 | 56 | 1,143 | 1 | 0,285 | 1/n OK |
| **beam4** | 2 | 135 | 35,267 | 1 | **2,9·10⁻⁹** | **odrzuca 1/n** |
| beam5 | 2 | 58 | 0,069 | 1 | 0,793 | 1/n OK |
| rect23 | 2 | 116 | 0,034 | 1 | 0,853 | 1/n OK |
| corner3 | 4 | 33 | 9,545 | 3 | 0,023 | 1/n OK (> α po korekcie) |
| **L** | 8 | 141 | 24,050 | 7 | **0,0011** | **odrzuca 1/n** |
| corner5 | 4 | 32 | 0,250 | 3 | 0,969 | 1/n OK |
| diag2 | 2 | 7 | 0,143 | 1 | 0,706 | 1/n OK |
| diag3 | 2 | 6 | 0,000 | 1 | 1,000 | 1/n OK |
| S | 4 | 79 | 1,759 | 3 | 0,624 | 1/n OK |
| T | 4 | 89 | 6,506 | 3 | 0,089 | 1/n OK |

**Werdykt: mieszany.** 10 z 12 testowalnych typów nie odrzucają jednostajnej orientacji po korekcie. Dwa —
`beam4` (2 poz: pozioma/pionowa belka 1×4) i `L` (8 póz) — odrzucają, oba silnie (p ≈ 2,9·10⁻⁹ i p ≈ 0,0011).
To realny sygnał, nie szum: `beam4` przy n=135 i df=1 to duży efekt.

**Decyzja: orientacja w `generator.py` zostaje 1/n dla WSZYSTKICH typów, także `beam4` i `L`.** Cel #186
ogranicza zmianę do wag typów ("Zmienić mają się tylko wagi typów"); estymacja wag orientacji to osobna
kalibracja o innym kształcie (per-poza, nie per-typ) i przy obecnej liczności próby byłaby nierówna między
typami — `diag2`/`diag3` mają po 6–7 obserwacji na 2 pozy, za mało, by cokolwiek policzyć, podczas gdy `L`
ma 141 na 8 póz. Kalibrowanie orientacji tylko dla `beam4`/`L` (bo tam akurat starczyło danych, by odrzucić
1/n) i pozostawienie 1/n gdzie indziej byłoby niespójne i wykraczałoby poza budżet tego zadania. Odnotowane
jako odkrycie do osobnego zadania kalibracyjnego (patrz `## Odkrycia` w raporcie sesji).

## Zmiana w kodzie

`generator.py`: `_next_piece` losuje typ przez `rng.choices(PIECE_TYPES, weights=PIECE_TYPE_WEIGHTS, k=1)`
zamiast `rng.choice(PIECE_TYPES)`; orientacja w obrębie typu niezmieniona (`rng.choice(pose_indices)`, 1/n).
Deterministyczne z seeda (`random.Random(seed)`, `choices` konsumuje `rng.random()`). Dane źródłowe:
`docs/data/z6-pary.json` (326 tacek, 978 klocków, ekstrakcja `tools/z6_pary.py` z `bridge/runs/*` włącznie
z `d878d79`). Test: `tests/test_generator_weights.py` (częstości na 120 000 losowań zgadzają się z wagami
w granicach 6σ, ten sam seed daje tę samą sekwencję, orientacja w obrębie typu pozostaje ~jednostajna).

`reward_shape_changed: no` — zmiana dotyczy wyłącznie rozkładu, z jakiego losowane są typy klocków w tacce,
nie funkcji nagrody, punktacji ani żadnej wartości zwracanej przez `game.step`.
