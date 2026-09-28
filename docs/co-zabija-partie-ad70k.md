# Co zabija partię: #128 (lookahead) kontra polityka rekordu (AD 70k)

Zadanie: [#170](../../issues/170). Powtórka pomiaru [#128](../../issues/128)
(`docs/co-zabija-partie.md`) na polityce rekordu `lookahead-ntuple:ntuple/survival-ad-70k.json`
zamiast `lookahead:weights.json`. **Ten dokument raportuje liczby, nie zmienia kodu i nie
rekomenduje zmian** — `features.py`, `policies.py`, `game.py`, `scoring.py`, `generator.py`,
`pieces.py`, `benchmark.py`, `ntuple.py`, `bench/record.json` nietknięte. `reward_shape_changed: no`.

## Metoda

Ten sam `tools/measure_terminal_state.py`, z nowym `--policy` (#170) zamiast `--weights-file`.
Te same 100 pierwszych seedów z `bench/seeds_fixed.json`, ten sam `move_cap=2000` z
`bench/config.json`, jedno polecenie:

```
python3 tools/measure_terminal_state.py --n-games 100 --jobs 4 \
    --policy lookahead-ntuple:ntuple/survival-ad-70k.json \
    --out docs/data/terminal-state-ad70k.json \
    --series-out docs/data/terminal-state-ad70k-series.json
```

`n_capped: 0` — jak w #128, żadna z 100 partii nie została ucięta sufitem `move_cap`; każda
skończyła się, bo plansza przestała przyjmować klocki. Kolumna „#128 (lookahead)" niżej to liczby
już opublikowane w `docs/co-zabija-partie.md` / `docs/data/terminal-state-100-summary.json`,
przepisane bez przeliczania.

## Długość partii

| metryka (liczba postawień) | #128 `lookahead` | rekord `ntuple/survival-ad-70k` |
|---|---:|---:|
| średnia | 114,81 | 287,93 |
| mediana | 87,5 | 243,5 |
| p10 | 35 | 77 |
| p90 | 245 | 599 |

Polityka rekordu przeżywa **2,5× dłużej** w medianie (87,5 → 243,5 postawień) i rozrzut rośnie
proporcjonalnie (p90 245 → 599) — zgodne z `bench/record.json` (`survival_mean` 216,57/257,36 na
pełnych 300 seedach stałych/rotowanych; tu 100 pierwszych seedów stałych, mean 287,93, w tym samym
rzędzie wielkości).

## Zapełnienie planszy przy śmierci

| metryka | #128 `lookahead` (mediana / p10 / p90) | rekord (mediana / p10 / p90) |
|---|---:|---:|
| zajęte komórki (na 64) | 32,0 / 23,9 / 39,1 | 30,0 / 23,0 / 38,1 |
| liczba rozłącznych pustych regionów | 3,0 / 1,0 / 6,0 | 3,0 / 1,0 / 4,0 |
| wielkość największego pustego regionu (komórek) | 20,5 / 11,9 / 39,0 | 28,0 / 14,0 / 39,0 |
| największy pusty **prostokąt** (`largest_empty_rect`, terminal = K=1) | 10,0 / 8,0 / 16,0 | 14,0 / 9,0 / 20,0 |

Plansza w chwili śmierci jest niemal identycznie zapełniona (mediana zajętych komórek 32,0 → 30,0,
różnica w granicach szumu 100 partii), ale **fragmentacja jest słabsza** niż u #128: największy
spójny pusty region rośnie (mediana 20,5 → 28,0 komórek) i rośnie też największy pusty
*prostokąt* (10,0 → 14,0). Innymi słowy — polityka rekordu umiera na planszy z relatywnie większym
i mniej pociętym wolnym miejscem niż stara `lookahead`, a mimo to wciąż nie mieści klocka z tacki
(patrz niżej, kto zabija).

## Rozkład klocka-zabójcy

| typ | #128 `lookahead` | rekord `ntuple/survival-ad-70k` |
|---|---:|---:|
| `square3` (3×3) | **54,70%** | **61,16%** |
| `rect23` (2×3/3×2) | 22,22% | 4,96% |
| `beam5` (1×5) | 7,69% | 22,31% |
| `corner5` | 3,42% | 5,79% |
| `S` | 6,84% | — |
| `diag3` | 1,71% | 3,31% |
| `L` | 1,71% | 0,83% |
| `corner3` | 0,85% | — |
| `T` | 0,85% | — |
| `square2` | — | 0,83% |
| `beam4` | — | 0,83% |
| razem klocków-zabójców (partie × ~1,2) | 117 | 121 |

`square3` pozostaje zdecydowanie najczęstszym zabójcą i to z jeszcze wyższym udziałem (54,70% →
61,16%). Zmienia się jednak **drugi w kolejności**: u #128 to `rect23` (2×3), a w rekordzie
`rect23` prawie znika (22,22% → 4,96%) i jego miejsce zajmuje `beam5` (1×5), który u #128 był
marginalny (7,69% → 22,31%). To spójne z tabelą wyżej: skoro terminalny największy prostokąt
urósł (mediana 10,0 → 14,0), krótszy i szerszy `rect23` (6 komórek) częściej się mieści, a
`beam5` — który wymaga **prostej linii długości 5**, niezależnie od tego, jak duży jest otaczający
ją prostokąt — częściej zostaje jedynym niepasującym kształtem.

## Przewidywalność cech i wymuszoność śmierci (kontekst, nie kryterium tabeli)

Cliff's delta na `K=1` (tuż przed końcem) zostaje tego samego znaku i rzędu wielkości dla
większości cech (`occupied_cells` 0,659→0,668, `empty_regions` 0,346→0,380,
`largest_empty_rect` -0,784→-0,678, `near_full_lines` 0,482→0,499, `surrounded_empty` 0,039→0,120
— cały czas najsłabsza), poza `placeable_shapes`, gdzie sygnał wyraźnie słabnie (-0,672 → -0,189):
w partiach rekordu liczba możliwych kształtów tuż przed śmiercią jest bliżej maksimum (mediana
nadal 15) niż u #128, więc różnica względem losowej tury jest mniejsza.

Największa pojedyncza zmiana jest w (d), „czy śmierć dało się ominąć jeden pół-ruch dalej": na
samej ostatniej turze `forced_pct` spada z **87,0% (#128) do 40,0% (rekord)** — pod polityką
rekordu większość (60,0%) zgonów miała niewybraną alternatywę, która przeżyłaby jeszcze jeden
pół-ruch, podczas gdy u #128 taka alternatywa była rzadkością. Okresowość z okresem 3 w
`forced_pct` na pozycjach 1–9 (ślad cyklu tacki, opisany w #128) jest widoczna w obu zbiorach.

## Co się zmieniło, a co zostało

Polityka rekordu przeżywa dłużej (mediana 87,5 → 243,5 postawień) i umiera na planszy z większym,
mniej pociętym wolnym miejscem (największy spójny region 20,5 → 28,0, największy prostokąt
10,0 → 14,0), ale zapełnienie planszy w chwili śmierci jest praktycznie takie samo (32,0 → 30,0 z
64). Klocek-zabójca wciąż jest niemal zawsze duży — `square3` dominuje jeszcze mocniej (54,7% →
61,2%) — ale drugi zabójca zmienia kształt: `rect23` (blok 2×3) ustępuje miejsca `beam5` (prosta
linia 1×5), zgodnie z większym, ale wciąż nie zawsze wystarczająco kwadratowym wolnym miejscem.
Najbardziej uderzająca różnica jest jednak w wymuszoności: pod starą `lookahead` 87,0% śmierci na
ostatniej turze nie dało się ominąć nawet o jeden pół-ruch, a pod polityką rekordu tylko 40,0% —
prawie dwie trzecie zgonów rekordu miało dostępną, niewybraną alternatywę na ostatniej turze, co
sugeruje, że przestrzeń, w której ocena mogła jeszcze wybrać lepiej, jest szersza niż u starej
polityki, nawet jeśli finalny typ klocka-zabójcy (`square3`) się nie zmienił.

## Czego nie wiem

- Jak w #128, (d) mierzy tylko jeden pół-ruch w przód — `policy_choice_pct=60,0%` na ostatniej
  turze rekordu mówi „istniała alternatywa przeżywająca jeszcze JEDNO postawienie", nie „istniała
  alternatywa przeżywająca dłużej o więcej niż jedno postawienie".
- 100 partii (te same seedy co #128, zgodnie z kryterium akceptacji) to mniej niż 300 użyte w
  `bench/record.json` do wyliczenia oficjalnej średniej rekordu — rzadkie typy klocków-zabójców
  (`square2`, `beam4`: po jednym wystąpieniu) mogą być szumem małej próby.
- Nie badano, czy okresowość 3-turowa w `forced_pct` odpowiada tej samej fazie cyklu tacki
  (`round_placement` w `game.py`) w obu zbiorach — przeniesiona bez weryfikacji obserwacja z #128.
