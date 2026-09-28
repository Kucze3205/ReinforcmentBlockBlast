# Trening N-tuple, układ `ADC`, sygnał survival, krok TD 16x mniejszy: 500 000 -> 800 000 odcinków (#197)

Ciąg dalszy [`docs/ntuple-survival-adcg.md`](ntuple-survival-adcg.md) (100 000 -> 500 000
odcinków, `--alpha 0.00011764705882352942`): kopia stanu i wag `ntuple/survival-adcg-*` po
500 000 odcinkach (bez starego logu), dalej trenowana z krokiem TD **16x mniejszym**
(`--alpha 0.000007352941176470588`). Cel: sprawdzić, czy mniejszy krok wyciąga więcej z tej
samej sieci — krzywa przebiegu źródłowego stała od ~180k w paśmie 5 000-6 900 pkt ze skokami
±700 między punktami ewaluacji. Werdykt (czy skala jest dźwignią) należy do benchmarku (#8), nie
do tego dokumentu.

```
python3 tools/train_ntuple.py --reward survival --alpha 0.000007352941176470588 --seed 3 --move-cap 2000 \
    --layout ADC \
    --state ntuple/survival-adcga16-state.json --out ntuple/survival-adcga16-weights.json \
    --best-out ntuple/survival-adcga16-best.json --curve-out docs/data/ntuple-survival-adcga16-krzywa.json \
    --eval-every 5000 --eval-episodes 200 --episodes 800000 --episodes-per-run <K>
```

Start: `ntuple/survival-adcg-500k.json` (nietknięty, sha256 `0e97dde28c72ab25`) skopiowany na
`ntuple/survival-adcga16-weights.json`/`-state.json`/`-best.json`; w skopiowanym stanie pole
`params.alpha` zmienione na `0.000007352941176470588` (wznowienie z innym `alpha` niż zapisane
odrzuca `load_state`, tak samo jak zmiana `--reward`/`--layout`), pole `eval` wyzerowane (nowy
harmonogram punktów ewaluacji liczony od 500 000, nie kontynuacja punktów `adcg`), pole `windows`
(krzywa treningu okien po 2000 odcinków) zachowane bez zmian z przebiegu źródłowego. Bez kopii
pliku `ntuple/survival-adcg-state.log.jsonl` (zgodnie z zadaniem — "bez starego logu"); log tego
przebiegu zaczyna się od pustego bloku aktywnego w chwili kopii (blok wg numeru odcinka, #187).

## Bloki (na pierwszym planie, commit po każdym)

**300 000 odcinków** (500 000 -> 800 000), trzy bloki po 100 000, stan/wagi/krzywa commitowane po
każdym; log rotowany co 150 000 odcinków ([#187](../../issues/187) — żaden plik logu nie
przekracza ~24,3 MB, pod limitem 40 MB), numeracja bloków logu ciągła z przebiegu źródłowego
(bloki 3-5, bo licząc od odcinka 1 500 000 to blok `(500000-1)//150000 = 3`):

| blok | zakres odcinków | `--episodes-per-run` | czas bloku (rzeczywisty) | s/odcinek (bloku) |
|---|---|---|---|---|
| 1 | 500 000 -> 600 000 | 100000 | 19m44,37s (1184,37 s) | 0,01184 |
| 2 | 600 000 -> 700 000 | 100000 | 19m29,25s (1169,25 s) | 0,01169 |
| 3 | 700 000 -> 800 000 (KONIEC) | 100000 | 19m27,62s (1167,62 s) | 0,01168 |

Wszystkie trzy poniżej limitu 3400 s, ze sporym zapasem (rdzeń natywny #184, ~0,012 s/odcinek w
tym zakresie, zgodnie z pomiarami `docs/ntuple-survival-adcg.md`). Każdy blok zatrzymany dokładnie
na wielokrotności 100 000, żeby zamrożenie migawki (`ntuple/survival-adcga16-<N>k.json`) trafiało
dokładnie w wymaganą liczbę odcinków.

Migawki wag zamrożone natychmiast po bloku, który je osiągnął (kopia
`ntuple/survival-adcga16-weights.json` w chwili zapisu):

| plik | odcinki | sha256 (16 znaków) |
|---|---|---|
| `ntuple/survival-adcga16-600k.json` | 600 000 | `b9298b0c37723f0e` |
| `ntuple/survival-adcga16-700k.json` | 700 000 | `e8f87872b84c5e5e` |
| `ntuple/survival-adcga16-800k.json` | 800 000 | `0ca43a9190d1f1e3` |

## Punkty ewaluacji (bez uczenia, 200 partii na punkt) co 5000 odcinków

Te same seedy ewaluacji w każdym punkcie (`train_ntuple.eval_seeds`, niezależne od `--seed`).
Pierwszy punkt tego przebiegu to odcinek 505 000 (harmonogram zresetowany od kopii stanu przy
500 000); pełna lista w `docs/data/ntuple-survival-adcga16-krzywa.json`, tu punkty co 25 000:

| odcinki | wynik śr. | przeżycie śr. |
|---|---|---|
| 505 000 | 5657,15 | 109,33 |
| 530 000 | 6045,86 | 114,41 |
| 555 000 | 7321,97 | 128,53 |
| 580 000 | 6926,56 | 125,81 |
| 605 000 | 6837,89 | 127,34 |
| 630 000 | 6335,02 | 119,50 |
| 655 000 | 7992,85 | 142,25 |
| 680 000 | 7506,90 | 137,81 |
| 705 000 | 5677,87 | 110,28 |
| 730 000 | 5912,82 | 112,72 |
| 755 000 | 6281,95 | 114,92 |
| 780 000 | 7229,87 | 125,29 |
| **800 000 (ostatnie)** | 7259,57 | 127,82 |

Najlepszy punkt ewaluacji całego przebiegu: odcinek **775 000** (wynik 8322,39, przeżycie 138,94,
200 partii) — `ntuple/survival-adcga16-best.json`.

## Średnia długość odcinka treningowego

Średnia liczba postawień na odcinek treningowy (nie ewaluacyjny), z `<stan>.log.jsonl`/bloków i
plików bloków (`train_ntuple.read_log`), po całym zakresie 500 001-800 000: **121,06
postawień/odcinek**.

Bez werdyktu tutaj — o tym, czy mniejszy krok TD wyciąga więcej z tej samej sieci, decyduje
benchmark (#8), nie ta krzywa.
