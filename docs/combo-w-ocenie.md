# Combo w ocenie liścia: skąd biorą się wagi

Dokument odpowiada na jedno pytanie: **skąd wzięła się liczba `2.0`** przy składniku
`combo_x_counter` w `weights-combo.json`. Wagi combo nie są strojone i nie są zgadnięte —
wychodzą z arytmetyki `scoring.py`. To rozróżnienie jest tu najważniejsze, bo bez niego
następny cykl nie odróżni wyprowadzenia od wolnego wyboru i zacznie tę liczbę „poprawiać".

## Dlaczego ocena w ogóle musi widzieć combo

`scoring.py` liczy czyszczenie jako

    punkty = combo * B(l),    B(1) = 10,  B(l>=2) = 10*l*(l-1)

gdzie `combo` jest wartością **po** inkrementacji. `game.py:81-89` podnosi `combo` przy każdym
czyszczeniu, bez ograniczenia z góry, a zeruje je dopiero wtedy, gdy przez
`COMBO_COUNTER_BASE + remaining` postawień nie padło żadne czyszczenie. Combo jest więc
**nieograniczonym mnożnikiem**, nie stałą premią: partia czyszcząca linię co postawienie ma
po `n` postawieniach około `5n²` punktów, podczas gdy rekord (6171 pkt na 110,5 postawienia)
siedzi na `0,51n²`.

Ocena liścia tego nie widziała. `features(board)` (`features.py`) zależy wyłącznie od planszy,
więc liść ze stanem „combo 40, licznik 4" był wart dokładnie tyle samo, co „combo 0, licznik 3"
na tej samej planszy. Combo wchodziło do liczby tylko przez `gain` naliczony **wewnątrz**
horyzontu (2–3 pół-ruchy). Przeszukanie chętnie zrywało łańcuch wart setki punktów dla planszy
minimalnie ładniejszej według sześciu cech — bo za horyzontem łańcuch nie był wart nic.

Człon combo w ocenie liścia jest **estymatorem punktów za horyzontem**, w tych samych
jednostkach co `gain`. Dzięki temu suma `gain + w·cechy` pozostaje wielkością punktową i nie
ma w niej miejsca na swobodną skalę.

## Wyprowadzenie

Oznaczenia: `c` = `combo` w liściu, `k` = `combo_counter` w liściu.

**Krok 1 — ile warta jest jedna jednostka combo.** Porównujemy ten sam liść, raz ze stanem
`combo = c`, raz ze stanem `combo = 0`. Następne czyszczenie `l` linii zapłaci w pierwszym
przypadku `(c+1)·B(l)`, w drugim `1·B(l)`. Różnica:

    (c+1)*B(l) - 1*B(l) = c * B(l)

Wartość stanu combo jest więc **liniowa w `c`**, ze współczynnikiem `B(l)` — wprost z
`scoring.clear_points`.

**Krok 2 — które `B(l)`.** Przyjmujemy `l = 1`, czyli `B = 10`. To jest **najniższa** możliwa
wartość bonusu bazowego (`B(2) = 20`, `B(3) = 60`, `B(4) = 120`), więc przybliżenie zaniża
wartość combo, nigdy jej nie zawyża.

**Krok 3 — czy łańcuch dożyje tego czyszczenia.** Różnica z kroku 1 realizuje się tylko wtedy,
gdy łańcuch przetrwa do następnego czyszczenia. Pilnuje tego `combo_counter`: `game.py:83`
ustawia go na `COMBO_COUNTER_BASE + remaining`, a `remaining` (liczba klocków zostających w
tacce) należy do `{0, 1, 2}`, więc licznik startuje z `{3, 4, 5}` i schodzi o 1 na każde
postawienie bez czyszczenia. Maksymalny zapas to

    K_max = COMBO_COUNTER_BASE + 2 = 5

Przyjmujemy przybliżenie **liniowe**: szansa dotrwania do następnego czyszczenia jest
proporcjonalna do pozostałego zapasu,

    P_przetrwania(k) ~ k / K_max = k / 5

**Krok 4 — ile czyszczeń liczymy.** Liczymy **jedno**. Stan „combo 40" w realnej partii
zapłaci wielokrotnie, ale każde następne czyszczenie wymaga własnego założenia o przetrwaniu,
a tych nie da się wyprowadzić ze wzoru — trzeba by je zmierzyć. Zatrzymujemy się na pierwszym.

**Złożenie.**

    V(c, k) = P_przetrwania(k) * c * B(1)
            = (k / 5) * c * 10
            = 2 * c * k

## Wagi

Wyprowadzenie daje funkcję `V(c, k) = 2·c·k`, czyli **iloczyn**. Stąd trzy składniki w
`features.COMBO_FEATURE_NAMES` i ich wagi:

| składnik | co liczy | waga | z czego wynika |
|---|---|---|---|
| `combo` | `c` | **0.0** | wyprowadzenie nie daje członu liniowego w samym `c` |
| `combo_counter` | `k` | **0.0** | wyprowadzenie nie daje członu liniowego w samym `k` |
| `combo_x_counter` | `c · k` | **2.0** | `B(1) / (COMBO_COUNTER_BASE + 2)` = `10 / 5` |

Dwa zera nie są zaniedbaniem — są wynikiem. Waga przy samym `c` twierdziłaby, że combo jest
coś warte także wtedy, gdy licznik właśnie wygasa, a `game.py:85-87` kasuje wtedy całe combo
niezależnie od tego, jak urosło. Waga przy samym `k` twierdziłaby, że zapas licznika jest coś
wart także przy `combo = 0`, a wtedy nie chroni niczego: `V(0, k) = 0` dla każdego `k`.
Oba składniki zostają w wektorze jako **nazwane miejsca**, żeby przyszły pomiar mógł je
sprawdzić, nie przebudowując formatu pliku wag.

### Rząd wielkości — czy to nie za dużo

Przy `c = 40` i świeżym liczniku `k = 5` człon daje 400 punktów. Tyle właśnie zapłaci jedno
czyszczenie pojedynczej linii przy combo 40 (`clear_points(41, 1) = 410`), więc skala się
zgadza. Wagi planszowe z `weights.json` na typowej planszy sumują się do kilkudziesięciu
punktów, więc człon combo zaczyna przeważać nad kosmetyką planszy w okolicach `c·k ≈ 25`, czyli
przy combo 5–8 ze świeżym licznikiem. To jest dokładnie intencja: łańcuch wart setki punktów ma
wygrywać z planszą „nieco ładniejszą według sześciu cech".

## Przyjęte przybliżenia

Wszystkie cztery **zaniżają** wartość combo. `2.0` jest podłogą, nie środkiem przedziału.

1. `l = 1`, czyli `B = 10` — najniższy możliwy bonus bazowy.
2. Liczone jest **jedno** następne czyszczenie, nie cały łańcuch.
3. `P_przetrwania(k) = k/5` zamiast modelu geometrycznego `1 − q^k`. Przy typowym udziale
   postawień czyszczących model liniowy jest ostrożniejszy dla małych `k` i optymistyczny
   dopiero przy `k = 5`, gdzie daje pewność 1.
4. Combo nie rośnie za liściem — wyceniamy `c`, a nie łańcuch, w który `c` się rozwinie.

Gdyby pomiar pokazał, że kandydat wygrywa, naturalnym następnym krokiem jest **zdjęcie
przybliżenia 2** (policzyć `m` oczekiwanych czyszczeń w łańcuchu), a nie mnożenie `2.0` przez
dobraną z ręki stałą.

## Czego tu nie ma: strojenia

Wag combo nie wolno stroić CEM-em z `tools/tune_weights.py`. W cyklu 9 (#111) sześć pokoleń CEM
na sześciu wagach planszowych dało wynik **gorszy** od punktu startowego: 5772,95 wobec 6171,04
(`bench/111-cem.json`, `mean_diff_over_se = −0,76`, etykieta „bez zmian"). Przyczyna jest
policzalna, nie pechowa: przy 32 partiach na kandydata błąd standardowy oceny kandydata jest
większy niż różnice, które CEM ma rozstrzygać. Dołożenie trzech wymiarów tej sytuacji nie
poprawia.

## Zgodność wstecz

`features.ALL_FEATURE_NAMES` to `FEATURE_NAMES + COMBO_FEATURE_NAMES` — sześć wag planszowych,
potem trzy combo. `benchmark.load_tuned_weights` przyjmuje wektory długości 6–9 i **dopełnia
brakujący ogon zerami**. Przy zerowych wagach combo `policies._weighted_features` dokłada do
sumy dokładne `0.0`, a `x + 0.0 == x` dla każdej skończonej liczby zmiennoprzecinkowej — ocena
liścia jest więc **bit w bit** ta sama co przed zmianą.

Dlatego `weights.json` i `weights-lookahead.json` opisują po zmianie **tę samą politykę** co
przed nią. Pilnuje tego `tests/test_lookahead_regression.py`: 24 pełne partie
`lookahead:weights.json` porównywane ruch po ruchu ze złotym zapisem sprzed zmiany. Ten test
chroni `bench/record.json` — gdyby ramię odniesienia drgnęło, każdy przyszły pomiar mierzyłby
od ruchomego punktu.
