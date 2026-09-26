# Strojenie wag pod `LookaheadPolicy`

Zadanie: [#104](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/104).

`weights.json` powstało w CEM, który oceniał kandydatów grając `TrayPolicy`
([#81](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/81),
[#77](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/77)). Od
[#92](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/92) najlepszą polityką jest
`LookaheadPolicy` — inne przeszukanie, więc i inne optymalne wagi. Ten przebieg zmienia
**wyłącznie politykę oceniającą kandydatów**; funkcja celu zostaje ta sama co w #81 (średni
wynik partii), mimo że `docs/szum-oceny-kandydata.md` pokazuje przeżycie jako sygnał mniej
zaszumiony — dwie zmiany naraz znaczyłyby, że skutku nie da się przypisać.

Produktem jest **nowy** plik `weights-lookahead.json`. `weights.json` zostaje nietknięte: jest
ramieniem odniesienia następnego pomiaru.

## Parametry przebiegu

| parametr | wartość | skąd |
|---|---|---|
| polityka oceniająca | `lookahead` (`beam=8, samples=2, branch=2, inner_beam=1, inner_depth=1`) | parametry domyślne `LookaheadPolicy` z #92, czyli dokładnie to, co mierzy `benchmark.py` |
| funkcja celu | średni wynik partii | ta sama co #81, celowo niezmieniona |
| `games_per_candidate` | 32 | `docs/szum-oceny-kandydata.md` (#101) |
| `population` | 14 | jak #81 |
| `elite` | 4 | jak #81 |
| pokolenia | 6 | budżet, patrz niżej |
| `seed` | 104 | sól puli seedów treningowych i RNG pokoleń |
| środek rozkładu startowego | `weights.json` | „punkt wyjścia" z #104; 6 pokoleń to za mało, żeby startować z `DEFAULT_WEIGHTS` |
| `std` startowe | `max(1,0; |w|·0,5)` | wzór z #81, niezmieniony |

Polecenie (jedno wywołanie = jedno pokolenie, stan do pliku, commit, kolejne wywołanie
podejmuje z tego miejsca):

    python3 tools/tune_weights.py --policy lookahead \
        --state weights-lookahead.state.json --generations 6 --generations-per-run 1 \
        --games-per-candidate 32 --population 14 --elite 4 --seed 104 \
        --init-weights-file weights.json --out weights-lookahead.json

### Dlaczego 32 partie na kandydata

`docs/szum-oceny-kandydata.md` (#101) liczy, przy jakiej liczbie partii dwaj kandydaci o
tej samej sigmie są w ogóle rozróżnialni: przy 6 partiach (wartość z #81) próg wykrywalności
na wyniku to **147% średniej** dla `lookahead`, przy 16 partiach **90%**, a dopiero **32
partie** schodzą poniżej 65% średniej — i to jest jedyna liczba z tamtej tabeli, przy której
selekcja elity przestaje być w większości losowaniem zwycięzcy.

### Dlaczego 6 pokoleń, a nie więcej

`docs/lookahead.md`: `lookahead:weights.json` kosztuje ≈ 20,25 ms na decyzję przy ≈ 108
postawieniach, czyli ≈ 2,2 s na partię (#101 mierzy ≈ 2,0 s na partię na seedach
treningowych). Pokolenie to `14 × 32 × ≈ 2,0 s ≈ 900 s`, więc 6 pokoleń to **≈ 5400 s** —
powyżej progu ≈ 4000 s z #104. Reguła zadania jest jednoznaczna: przy przekroczeniu budżetu
zmniejsza się liczbę pokoleń, **nigdy** liczbę partii na kandydata, a dolna granica liczby
pokoleń to 6. Nie ma więc czego dalej ciąć — przebieg idzie na 6 pokoleniach i kosztuje tyle,
ile wynika z reguły.

### Jak przebieg przeżywa śmierć sesji

`tools/tune_weights.py --state` zapisuje po **każdym** pokoleniu pełny stan CEM (numer
pokolenia, `mean`, `std`, elita z wynikami, najlepszy dotąd kandydat, log) do
`weights-lookahead.state.json` i przepisuje `weights-lookahead.json`; każde pokolenie ma
osobny commit. RNG pokolenia jest wyprowadzony z pary `(seed, numer pokolenia)`, a nie
przeniesiony przez plik — dlatego wznowienie losuje **tę samą populację**, co przebieg
nieprzerwany. Sprawdza to `tests/test_tune_weights.py::TestGenerationalRunIsResumable`:
dwa wywołania po jednym pokoleniu dają bit w bit ten sam stan, co jedno wywołanie po dwa.
Powód tej konstrukcji: [#82](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/82)
kosztowało 59 minut policzonej pracy, bo przebieg nie zostawił niczego na dysku.

## Przebieg: pokolenie → średnia elity → wagi elity

<!-- TABELA-PRZEBIEGU -->

## Wagi końcowe wobec `weights.json`

<!-- TABELA-WAG -->

## Test dymny

<!-- TEST-DYMNY -->
