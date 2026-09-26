# Co zabija partię: pomiar stanu terminalnego i czego nie widzą ręczne cechy

Zadanie: [#128](../../issues/128). **Ten dokument raportuje liczby, nie zmienia kodu** —
`features.py`, `policies.py`, `game.py`, `scoring.py`, `generator.py`, `pieces.py`,
`benchmark.py` i `bench/record.json` są nietknięte. `reward_shape_changed: no`.

## Metoda

Narzędzie: `tools/measure_terminal_state.py` (nowe w tym zadaniu). `docs/data/serie-300-lookahead-previous.json`
z [#119](../../issues/119) niesie tylko podsumowanie punktowe/combo partia-po-partii — **bez stanów
planszy** — więc nie wystarcza do (a)/(b)/(c)/(d) i partie rozegrano od nowa. Własna pętla
rozgrywki (wzór: `tools/measure_score_noise.py --detailed`), czyta publiczny stan
`Game`/`Board` z zewnątrz i niczego w nim nie zmienia; symulacje jednego pół-ruchu w przód
(kopia planszy przez `Board.copy()`) to ten sam trik co `policies._simulate_placement` i
`measure_score_noise._any_action_would_clear`.

Przebieg: `lookahead:weights.json`, **100 partii** na pierwszych 100 seedach z
`bench/seeds_fixed.json`, `move_cap=2000` z `bench/config.json`. Czas: **3 min 48 s** (zgodnie
z ≈4 min z #119 dla 100 partii `lookahead`), na pierwszym planie, jedno polecenie:

```
python3 tools/measure_terminal_state.py --n-games 100 --weights-file weights.json \
    --out docs/data/terminal-state-100-summary.json \
    --series-out docs/data/terminal-state-100.json
```

Żadna z 100 partii nie została ucięta sufitem `move_cap` (`n_capped: 0`) — każda skończyła się,
bo plansza przestała przyjmować klocki, zgodnie z ustaleniem #119.

## (a) Jak wygląda plansza w chwili śmierci

Rozkład na 100 partiach (`docs/data/terminal-state-100-summary.json`, `terminal_board`):

| metryka | mediana | p10 | p90 |
|---|---:|---:|---:|
| zajęte komórki (na 64) | 32,0 | 23,9 | 39,1 |
| liczba rozłącznych pustych regionów (4-sąsiedztwo) | 3,0 | 1,0 | 6,0 |
| wielkość największego pustego regionu (komórek) | 20,5 | 11,9 | 39,0 |

Plansza w chwili śmierci jest **w połowie pusta** (mediana 32/64 zajętych), nie zapchana pod
korek — i wciąż ma jeden duży spójny pusty obszar (mediana 20,5 komórek, czyli **32% całej
planszy**). Śmierć nie jest więc brakiem miejsca w sensie ilości wolnej powierzchni: to
niedopasowanie *kształtu* dostępnego miejsca do kształtów klocków na tacce — spójny obszar
pustych pól bywa duży, ale rzadko ma kształt (rozmiar prostokąta), w który wchodzi klocek 3×3
albo 2×3 (patrz (b) niżej). `largest_empty_rect` z `features.py` (największy **prostokąt**, nie
dowolny spójny obszar) na terminalu ma medianę tylko 10,0 (p10 8,0, p90 16,0) — dużo mniej niż
20,5 komórek największego spójnego (niekoniecznie prostokątnego) regionu; różnica między tymi
dwiema liczbami jest dokładnie miarą fragmentacji kształtu, nie ilości miejsca.

## (b) Który klocek zabija

Wszystkie klocki wciąż w tacce w chwili `_can_place_any() == False` nie mają z definicji żadnego
legalnego postawienia (funkcja sprawdza każdy z osobna) — rozkład ich typów kanonicznych na 117
takich klocków z 100 partii (`killer_piece_types`):

| typ | liczba | % |
|---|---:|---:|
| `square3` (3×3) | 64 | **54,70%** |
| `rect23` (2×3/3×2) | 26 | 22,22% |
| `beam5` (1×5) | 9 | 7,69% |
| `S` | 8 | 6,84% |
| `corner5` | 4 | 3,42% |
| `diag3` | 2 | 1,71% |
| `L` | 2 | 1,71% |
| `corner3` | 1 | 0,85% |
| `T` | 1 | 0,85% |

**`square3` dominuje wyraźnie** — ponad połowa (54,70%) klocków-zabójców to kwadrat 3×3, a razem
z `rect23` (2×3) te dwa największe klocki-bloki odpowiadają za **76,92%** wszystkich zgonów. To
spójne z (a): duże klocki wymagają dużego **spójnego prostokąta**, a mediana największego
prostokąta na terminalu (10,0 komórek — 2×5 albo 3×3 z zapasem) jest blisko granicy, przy której
`square3` (9 komórek, musi być dokładnie 3×3) i `rect23` (6 komórek, 2×3) przestają się mieścić.
Małe klocki (`1x1`, `beam2`, `beam3`, `beam4`, `diag2`, `square2`, `corner3`, `T`) prawie nigdy nie
zabijają — w tym zbiorze `1x1` i `beam2`/`beam3`/`beam4`/`diag2`/`square2` w ogóle się nie
pojawiły jako klocek-zabójca.

## (c) Czy śmierć jest przewidywalna: sześć cech `features.FEATURE_NAMES`

Dla każdej cechy: jej wartość `K` postawień przed końcem (`K ∈ {1, 5, 10, 20}`) kontra wartość w
jednej losowo wybranej turze tej samej partii (RNG zasiane seedem partii, jedna próbka na grę,
współdzielona między wszystkimi `K`). Separacja mierzona **Cliff's delta** (`-1..+1`; `0` = brak
rozdzielenia rozkładów, `±1` = rozdzielenie pełne; dodatnia = wartości `K`-przed-końcem typowo
większe niż losowa tura). Pełne mediany/p10/p90 w
`docs/data/terminal-state-100-summary.json` → `feature_predictiveness`; tu tylko delta:

| cecha | K=1 | K=5 | K=10 | K=20 | jedno zdanie |
|---|---:|---:|---:|---:|---|
| `occupied_cells` | 0,659 | 0,402 | 0,232 | 0,086 | Rozdziela mocno tuż przed końcem (planek wyraźnie pełniejsza niż losowo), ale sygnał słabnie szybko i po 20 postawieniach prawie znika. |
| `surrounded_empty` | 0,039 | 0,009 | 0,048 | 0,032 | **Nie widzi nic, na żadnym horyzoncie** — delta bliska zeru nawet tuż przed śmiercią. |
| `empty_regions` | 0,346 | 0,122 | 0,095 | -0,015 | Umiarkowany sygnał tylko tuż przed końcem (K=1), zanika do szumu już przy K=5 i ginie przy K=20. |
| `largest_empty_rect` | -0,784 | -0,586 | -0,375 | -0,231 | **Najsilniejsza i najbardziej trwała separacja ze wszystkich sześciu** — ujemna (mniejszy największy prostokąt niż losowo) i wciąż wyraźna nawet 20 postawień przed końcem. |
| `near_full_lines` | 0,482 | 0,196 | 0,078 | 0,014 | Umiarkowany sygnał na K=1, słabnie szybciej niż `largest_empty_rect` i prawie znika przy K=10. |
| `placeable_shapes` | -0,672 | -0,219 | -0,069 | -0,032 | Silny sygnał tuż przed końcem (prawie tautologiczny — to niemal ta sama definicja co `_can_place_any`), ale zanika najszybciej ze wszystkich sześciu po K=1. |

**Werdykt (c)**: pięć z sześciu cech widzą nadchodzącą śmierć przynajmniej na krótkim horyzoncie
(K=1), jedna (`surrounded_empty`) nie widzi jej wcale. Najbliżej śmierci — czyli cecha z
najsilniejszą i najbardziej trwałą separacją na wszystkich czterech horyzontach — jest
**`largest_empty_rect`**: to jedyna cecha, która pozostaje wyraźnie rozdzielona (`|delta|>0,2`)
nawet 20 postawień przed końcem partii.

## (d) Czy polityka mogła uciec

Dla każdej z ostatnich 10 tur każdej partii: symulacja jednego pół-ruchu w przód (kopia planszy)
sprawdza, czy istniał legalny ruch **inny niż wybrany**, po którym gra nie kończyłaby się od razu
(przynajmniej jedno postawienie zostałoby jeszcze możliwe dla reszty tacki). `pos_from_end=0` to
sama ostatnia tura partii — to dosłowna odpowiedź na pytanie "czy śmierć dało się ominąć":

| `pos_from_end` (0 = ostatnia tura) | wymuszona (`forced_pct`) | z wyboru polityki (`policy_choice_pct`) |
|---:|---:|---:|
| 0 (śmierć) | **87,0%** | **13,0%** |
| 1 | 15,0% | 85,0% |
| 2 | 85,0% | 15,0% |
| 3 | 6,0% | 94,0% |
| 4 | 14,0% | 86,0% |
| 5 | 85,0% | 15,0% |
| 6 | 2,0% | 98,0% |
| 7 | 13,0% | 87,0% |
| 8 | 85,0% | 15,0% |
| 9 | 4,0% | 96,0% |

**Na samej ostatniej turze 87,0% śmierci było wymuszonych** — żaden inny legalny ruch w tamtej
turze nie ratowałby gry choćby o jeden pół-ruch dłużej; tylko **13,0%** miało dostępną (a
niewybraną) alternatywę, która przeżyłaby ten pół-ruch.

**Odkrycie poza (d) wprost, ale w tych samych danych**: `forced_pct` na pozycjach 1–9 nie maleje
monotonicznie z odległością od końca — oscyluje z okresem 3 (≈85% na pozycjach 2/5/8, ≈14% na
pozycjach 1/4/7, ≈2–6% na pozycjach 3/6/9), dokładnie zgodnie z cyklem tacki (3 klocki na rundę,
`game.py`: `round_placement`). To sugeruje, że „wymuszoność” w ostatnich turach jest w większości
artefaktem tego, KTÓRE miejsce w rundzie (1., 2. czy 3. klocek świeżo wylosowanej trójki) akurat
wypada na daną pozycję przed końcem, a nie rosnącą z bliskością śmierci — poza samą ostatnią turą,
która wybija się wyraźnie ponad wzorzec swojej grupy (87,0% vs. sąsiednie ~85%/~2–6%). Nie badano
tu głębiej, do której pozycji w rundzie faktycznie należy każdy `pos_from_end` — to obserwacja z
danych, nie zweryfikowany mechanizm.

## Werdykt jednym zdaniem

**Sześć ręcznych cech widzi nadchodzącą śmierć częściowo i tylko na krótką metę**: pięć z sześciu
(`occupied_cells`, `empty_regions`, `largest_empty_rect`, `near_full_lines`, `placeable_shapes`)
rozdzielają rozkład "K postawień przed końcem" od losowej tury przy `K=1`, ale tylko
**`largest_empty_rect`** utrzymuje wyraźną separację (`|Cliff's delta|` 0,78→0,23) na całym
zbadanym horyzoncie do 20 postawień wstecz, podczas gdy **`surrounded_empty` nie widzi śmierci na
żadnym horyzoncie** (`|delta|<0,05` wszędzie) — a śmierć sama w sobie jest w 87,0% wymuszona
geometrią tacki i planszy w ostatniej turze, nie wyborem polityki, i najczęściej ma kształt
klocka `square3` (3×3, 54,70% zgonów) niepasującego do sporego, ale nieprostokątnego wolnego
miejsca.

## Czego nie wiem

- Definicja (d) mierzy tylko jeden pół-ruch w przód (jak każe kryterium akceptacji), nie pełną
  re-symulację reszty partii z alternatywnym wyborem — `policy_choice_pct=13,0%` na ostatniej
  turze mówi "istniała alternatywa, która przeżyłaby JESZCZE JEDNO postawienie", nie "istniała
  alternatywa, która przeżyłaby dłużej o więcej niż jedno postawienie". Głębsza analiza
  wymagałaby symulacji wielopoziomowej, poza budżetem tego zadania.
- Okresowość 3-turowa w `forced_pct` (patrz (d)) nie została zweryfikowana względem faktycznej
  pozycji klocka w rundzie (`round_placement` z `game.py`) — to obserwacja z danych zagregowanych,
  nie zmierzony mechanizm.
- Wielkość próby to 100 partii (zgodnie z kryterium akceptacji „≥100"), nie 300 jak w #119 —
  część rozkładów (zwłaszcza rzadkie typy klocków w (b), np. pojedyncze wystąpienia `corner3`/`T`)
  może być szumem małej liczby zdarzeń.
