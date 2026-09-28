# Trening N-tuple, układ `ADC`, sygnał survival, na skalibrowanym generatorze: 100 000 -> 500 000 odcinków (#188)

Ciąg dalszy [`docs/ntuple-survival-adc.md`](ntuple-survival-adc.md) (100 000 odcinków, generator
sprzed kalibracji): kopia stanu i wag `ntuple/survival-adc-*` po 100 000 odcinkach (bez starego
logu), dalej trenowana na generatorze, którego wagi typów klocków zostały przeliczone z danych
mostu ([#186](../../issues/186), [`docs/generator-wagi-typow.md`](generator-wagi-typow.md) —
`generator.py` losuje typ klocka wg wag zmierzonych z mostu, nie 1/15 jak wcześniej). Parametry
niezmienione względem `ADC` (`--alpha` przeliczone dla 136 łat, `--seed 3`, `--move-cap 2000`,
`--layout ADC`), zmienione tylko ścieżki, `--episodes`/`--episodes-per-run` i ewaluacja
(`--eval-every 5000 --eval-episodes 200`, gęstsza niż `--eval-every 1000 --eval-episodes 100`
przebiegu źródłowego — harmonogram ewaluacji przebiegu skopiowanego stanu zresetowany na nowy,
bo `tools/train_ntuple.load_state` odrzuca wznowienie z inną konfiguracją ewaluacji niż
zapisana). Rdzeń natywny [#184](../../issues/184) przyspiesza trening ~13× względem czystego
Pythona.

```
python3 tools/train_ntuple.py --reward survival --alpha 0.00011764705882352942 --seed 3 --move-cap 2000 \
    --layout ADC \
    --state ntuple/survival-adcg-state.json --out ntuple/survival-adcg-weights.json \
    --best-out ntuple/survival-adcg-best.json --curve-out docs/data/ntuple-survival-adcg-krzywa.json \
    --eval-every 5000 --eval-episodes 200 --episodes 500000 --episodes-per-run <K>
```

Start: `ntuple/survival-adc-100k.json` (nietknięty, sha256 `3e75cd9c41264fd5`) skopiowany na
`ntuple/survival-adcg-weights.json`/`-state.json`/`-best.json`; pole `eval` stanu wyzerowane
(nowy harmonogram co 5000/200 partii, nie co 1000/100), pole `windows` (krzywa treningu okien
po 2000 odcinków) zachowane bez zmian z przebiegu źródłowego. Bez kopii pliku
`ntuple/survival-adc-state.log.jsonl` (zgodnie z zadaniem — "bez starego logu").

## Bloki (na pierwszym planie, commit po każdym)

**500 000 odcinków**, pięć bloków, stan/wagi/krzywa commitowane po każdym; log rotowany co
150 000 odcinków ([#187](../../issues/187) — żaden plik logu nie przekracza ~24,3 MB, pod
limitem 40 MB):

| blok | zakres odcinków | `--episodes-per-run` | czas bloku (rzeczywisty) | s/odcinek (bloku) |
|---|---|---|---|---|
| 1 | 100 000 -> 140 000 | 40000 | 9m24,95s (564,95 s) | 0,01412 |
| 2 | 140 000 -> 200 000 | 60000 | 14m48,42s (888,42 s) | 0,01481 |
| 3 | 200 000 -> 300 000 | 100000 | 24m37,61s (1477,61 s) | 0,01478 |
| 4 | 300 000 -> 400 000 | 100000 | 24m56,90s (1496,90 s) | 0,01497 |
| 5 | 400 000 -> 500 000 (KONIEC) | 100000 | 25m18,02s (1518,02 s) | 0,01518 |

Wszystkie pięć poniżej limitu 3400 s, ze sporym zapasem: rdzeń natywny (#184) daje
`s/odcinek` rzędu 0,013-0,015 w tym zakresie odcinków, ~13× mniej niż `ADC` bez rdzenia
natywnego (0,177 s/odcinek pod koniec przebiegu 70 001-100 000, `docs/ntuple-survival-adc.md`).
Blok 1 dobrany z dymnego pomiaru (300 odcinków na skopiowanym stanie, `≈0,013 s/odcinek`);
bloki 2-5 rozszerzane stopniowo, każdy zatrzymany dokładnie na wielokrotności 100 000, żeby
zamrożenie migawki (`ntuple/survival-adcg-<N>k.json`) trafiało dokładnie w wymaganą liczbę
odcinków, nie w środek biegnącego bloku.

Migawki wag zamrożone natychmiast po bloku, który je osiągnął (kopia
`ntuple/survival-adcg-weights.json` w chwili zapisu):

| plik | odcinki | sha256 (16 znaków) |
|---|---|---|
| `ntuple/survival-adcg-200k.json` | 200 000 | `090a532ce4a05259` |
| `ntuple/survival-adcg-300k.json` | 300 000 | `47d5244d1712e5e7` |
| `ntuple/survival-adcg-400k.json` | 400 000 | `2f713f11e7f0ee34` |
| `ntuple/survival-adcg-500k.json` | 500 000 | `0e97dde28c72ab25` |

## Punkty ewaluacji (bez uczenia, 200 partii na punkt) co 5000 odcinków

Te same seedy ewaluacji w każdym punkcie (`train_ntuple.eval_seeds`, niezależne od `--seed`).
Pierwszy punkt tego przebiegu to odcinek 105 000 (harmonogram zresetowany od kopii stanu przy
100 000); pełna lista w `docs/data/ntuple-survival-adcg-krzywa.json`, tu punkty co 25 000:

| odcinki | wynik śr. | przeżycie śr. |
|---|---|---|
| 105 000 | 5655,65 | 110,78 |
| 130 000 | 5087,19 | 104,92 |
| 155 000 | 5555,51 | 109,72 |
| 180 000 | 6532,26 | 122,68 |
| 205 000 | 5631,31 | 106,66 |
| 230 000 | 5639,56 | 112,47 |
| 255 000 | 6327,82 | 115,86 |
| 280 000 | 6252,10 | 120,83 |
| 305 000 | 6140,11 | 119,05 |
| 330 000 | 6336,27 | 118,42 |
| 355 000 | 6105,97 | 114,79 |
| 380 000 | 6192,60 | 115,73 |
| 405 000 | 5318,20 | 106,58 |
| 430 000 | 6303,32 | 120,48 |
| 455 000 | 6032,27 | 109,69 |
| 480 000 | 6538,57 | 118,01 |
| **500 000 (ostatnie)** | 5970,62 | 113,00 |

Najlepszy punkt ewaluacji całego przebiegu: odcinek **390 000** (wynik 6882,47, przeżycie
119,39, 200 partii) — `ntuple/survival-adcg-best.json`.

## Średnia długość odcinka treningowego

Średnia liczba postawień na odcinek treningowy (nie ewaluacyjny), z `<stan>.log.jsonl` i
plików bloków (`train_ntuple.read_log`), po całym zakresie 100 001-500 000: **110,87
postawień/odcinek**.

Bez werdyktu tutaj — o zakończeniu treningu i o tym, czy skala jest dźwignią, decyduje
benchmark (#8), nie ta krzywa.
