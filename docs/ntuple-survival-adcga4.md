# Trening N-tuple, układ `ADC`, sygnał survival, krok TD 4x mniejszy: 500 000 -> 800 000 odcinków (#196)

Ciąg dalszy [`docs/ntuple-survival-adcg.md`](ntuple-survival-adcg.md) (500 000 odcinków, `alpha
0.00011764705882352942`): kopia stanu i wag `ntuple/survival-adcg-*` po 500 000 odcinkach, dalej
trenowana z krokiem TD **4x mniejszym** (`--alpha 0.000029411764705882354`), żeby sprawdzić, czy
krok był za duży do dostrojenia sieci — krzywa `adcg` stała od ~180k w paśmie 5 000–6 900 pkt i
skakała o ±700 między punktami ewaluacji. Pozostałe parametry niezmienione (`--seed 3 --move-cap
2000 --layout ADC --reward survival --eval-every 5000 --eval-episodes 200`). Werdykt o tym, czy
mniejszy krok wyciąga więcej z sieci, należy do benchmarku (#8) w następnym cyklu, nie do tego
dokumentu.

```
python3 tools/train_ntuple.py --reward survival --alpha 0.000029411764705882354 --seed 3 --move-cap 2000 \
    --layout ADC \
    --state ntuple/survival-adcga4-state.json --out ntuple/survival-adcga4-weights.json \
    --best-out ntuple/survival-adcga4-best.json --curve-out docs/data/ntuple-survival-adcga4-krzywa.json \
    --eval-every 5000 --eval-episodes 200 --episodes 800000 --episodes-per-run <K>
```

Start: `ntuple/survival-adcg-500k.json` (nietknięty, sha256 `0e97dde28c72ab25`) — a dokładniej
plik `ntuple/survival-adcg-weights.json`/`-state.json`/`-best.json` w chwili 500 000 odcinków —
skopiowany na `ntuple/survival-adcga4-weights.json`/`-state.json`/`-best.json`; w kopii stanu pole
`params.alpha` zmienione na `0.000029411764705882354` (bo `load_state` odrzuca wznowienie z innym
`alpha` niż zapisane), pole `eval` wyzerowane (nowy harmonogram punktów ewaluacji, zaczynający się
od odcinka 505 000), pole `windows` (krzywa treningu okien po 2000 odcinków) zachowane bez zmian z
przebiegu źródłowego. Bez kopii pliku logu (`ntuple/survival-adcg-state.log.*.jsonl`) — nowy
przebieg startuje z pustym logiem, tak jak zrobiło zadanie przebiegu `adcg`.

## Bloki (na pierwszym planie, commit po każdym)

**300 000 odcinków** (500 000 -> 800 000), trzy bloki po 100 000, stan/wagi/krzywa commitowane po
każdym; log rotowany co 150 000 odcinków ([#187](../../issues/187)):

| blok | zakres odcinków | `--episodes-per-run` | czas bloku (rzeczywisty) | s/odcinek (bloku) |
|---|---|---|---|---|
| 1 | 500 000 -> 600 000 | 100000 | 19m49,29s (1189,29 s) | 0,01189 |
| 2 | 600 000 -> 700 000 | 100000 | 19m43,84s (1183,84 s) | 0,01184 |
| 3 | 700 000 -> 800 000 (KONIEC) | 100000 | 19m50,54s (1190,54 s) | 0,01191 |

Wszystkie trzy pod limitem 3400 s, ze sporym zapasem — bloki po 100 000 odcinków dobrane od razu z
doświadczenia przebiegu `adcg` (~0,015 s/odcinek), a rdzeń natywny (#184) w tym zakresie okazał się
nawet nieco szybszy (~0,0119 s/odcinek). Żaden plik logu bloku nie przekroczył ~24,3 MB, pod
limitem 40 MB.

Migawki wag zamrożone natychmiast po bloku, który je osiągnął (kopia
`ntuple/survival-adcga4-weights.json` w chwili zapisu):

| plik | odcinki | sha256 (16 znaków) |
|---|---|---|
| `ntuple/survival-adcga4-600k.json` | 600 000 | `dade41c9da2ac82c` |
| `ntuple/survival-adcga4-700k.json` | 700 000 | `5cb9f92a806bb73c` |
| `ntuple/survival-adcga4-800k.json` | 800 000 | `3fe2efa5df60b144` |

## Punkty ewaluacji (bez uczenia, 200 partii na punkt) co 5000 odcinków

Te same seedy ewaluacji w każdym punkcie (`train_ntuple.eval_seeds`, niezależne od `--seed`).
Pierwszy punkt tego przebiegu to odcinek 505 000 (harmonogram zresetowany od kopii stanu przy
500 000); pełna lista w `docs/data/ntuple-survival-adcga4-krzywa.json`, tu punkty co 25 000:

| odcinki | wynik śr. | przeżycie śr. |
|---|---|---|
| 525 000 | 6394,15 | 120,08 |
| 550 000 | 6692,85 | 126,57 |
| 575 000 | 6391,84 | 119,44 |
| 600 000 | 6554,81 | 119,08 |
| 625 000 | 6218,48 | 117,17 |
| 650 000 | 6287,03 | 116,83 |
| 675 000 | 6990,54 | 127,03 |
| 700 000 | 7104,40 | 125,75 |
| 725 000 | 6902,01 | 128,12 |
| 750 000 | 5952,95 | 116,41 |
| 775 000 | 6180,82 | 117,77 |
| **800 000 (ostatnie)** | 6920,52 | 120,67 |

Najlepszy punkt ewaluacji całego przebiegu: odcinek **610 000** (wynik 7374,58, przeżycie 126,87,
200 partii) — `ntuple/survival-adcga4-best.json`.

## Średnia długość odcinka treningowego

Średnia liczba postawień na odcinek treningowy (nie ewaluacyjny), z plików bloków logu
(`train_ntuple.read_log`), po całym zakresie 500 001-800 000: **119,27 postawień/odcinek**.

Bez werdyktu tutaj — o tym, czy mniejszy krok TD wyciąga więcej z tej samej sieci, decyduje
benchmark (#8), nie ta krzywa.
