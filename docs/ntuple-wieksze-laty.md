# Pilot: większe łaty N-tuple (układ `ADCE`, prostokąty 3×4/4×3) — czy pojemność przełamuje plateau (#222)

Pytanie: dalszy trening `ADC` (136 łat, 27 904 wagi) nic nie daje w skali 200k–500k (#194),
etapy nic (#213), a nawet kontrola trenowana zachłannie dalej od rekordu (800k → 895k) nie
poprawiła się (#216, `docs/uczenie-z-przeszukania-pilot.md`) — czy **większa pojemność oceny**
(więcej i większe łaty) przełamuje to plateau? Mierzone, nie wdrożone do benchmarku.

**Wynik jednym zdaniem**: przy tym samym budżecie odcinków `ADCE` bije `ADC` istotnie (+23,6%
przy 100k, 1,97 SE; +34,6% przy 200k, 2,69 SE) — pojemność pomaga i przełamuje plateau *przy
danym budżecie*, ale przy 200k `ADCE` nie bije jeszcze rekordu 800k-odcinkowego `ADC`
(+5,1%, 0,45 SE, w szumie) — potrzeba dalszego treningu, żeby rozstrzygnąć, czy dogoni i przebije
rekord.

## Układ `ADCE`

`ntuple.LAYOUTS["ADCE"]` (`ntuple.py`): `ADC` (136 łat: 16 wierszy/kolumn `A`, 36 kwadratów 3×3
`D`, 84 prostokąty 2×3/3×2 `C`) plus nowy wariant `E` — prostokąty 3×4 i 4×3 we wszystkich
położeniach lewego-górnego rogu na planszy 8×8: 3×4 (3 wiersze, 4 kolumny) daje
`(8-2)×(8-3) = 6×5 = 30` położeń, 4×3 (4 wiersze, 3 kolumny) daje `(8-3)×(8-2) = 5×6 = 30`
położeń — razem 60 łat, `k=12` komórek/łatę.

| układ | łaty | wagi | plik (JSON, indent=2) |
|---|---|---|---|
| `ADC` | 136 | 27 904 | ~0,78 MB |
| `ADCE` | 136 + 60 = **196** | 27 904 + 60·4096 = **273 664** | **~7,7 MB** (`ntuple/survival-adce-100k.json`: 7 691 141 B; `-200k.json`: 7 684 550 B) |

Plik wag `ADCE` (~7,7 MB) mieści się pod budżetem ~10 MB z zapasem — zapis JSON (`NTupleValue.save`,
nietknięty) nie musiał się zmienić dla nowego układu.

**Rdzeń natywny** (`ntuple_native.c`/`.py`, #184) obsługuje łaty `k=12` **bez żadnej zmiany**:
`run_dst`/`run_mask` już były na tyle szerokie (`uint8_t`/`uint32_t`), żeby pomieścić indeks i
maskę łaty 12-bitowej, a bufor wag jest adresowany 64-bitowymi przesunięciami niezależnie od
rozmiaru pojedynczej łaty. Test zgodności (`tests/test_ntuple_native.py`,
`TestValueEquivalence.test_value_on_1000_random_boards_equals_pure_python` rozszerzony o `"ADCE"`,
plus nowy `TestTrainingEquivalence.test_200_adce_survival_episodes_same_weights_and_log`) potwierdza
bitową zgodność rdzenia z Pythonem na tym układzie — 19/19 testów `test_ntuple_native.py` zielone.

## `alpha`

Konwencja repo (`docs/ntuple.md`): krok efektywny `alpha · N_łat` ma być równoważny `alpha=0,001`
dla wariantu `A` (16 łat) — `AD`/`ADC` przeliczały `alpha` tym wzorem. Dla `ADCE` (196 łat):

```
alpha = 0,001 · 16 / 196 = 8,163265306122449e-05
```

równoważnie: `alpha_ADC · 136/196 = 0,00011764705882352942 · 136/196 = 8,163265306122449e-05`
(ta sama wartość — skalowanie „ze 136 do 196 łat" z treści zadania i skalowanie od bazy `A` dają
identyczny wynik, bo `alpha_ADC` samo już było przeskalowane od `A`).

## Trening od zera: 0 → 200 000 odcinków

Dwa bloki na pierwszym planie, stan/wagi/krzywa/log commitowane po każdym (`--seed 3
--move-cap 2000`, jak wszystkie poprzednie przebiegi `survival` w tym repo, dla porównywalności):

```
python3 tools/train_ntuple.py --reward survival --alpha 8.163265306122449e-05 --seed 3 --move-cap 2000 \
    --layout ADCE \
    --state ntuple/survival-adce-state.json --out ntuple/survival-adce-weights.json \
    --best-out ntuple/survival-adce-best.json --curve-out docs/data/ntuple-survival-adce-krzywa.json \
    --eval-every 10000 --eval-episodes 50 --episodes <100000|200000> --episodes-per-run 100000
```

| blok | zakres odcinków | czas bloku (rzeczywisty) | s/odcinek (bloku) | migawka |
|---|---|---|---|---|
| 1 | 0 → 100 000 | 16m38,0s (998,0 s) | 0,00998 | `ntuple/survival-adce-100k.json` |
| 2 | 100 000 → 200 000 | 18m46,1s (1126,1 s) | 0,01126 | `ntuple/survival-adce-200k.json` |
| **razem** | 0 → 200 000 | **2 124,1 s** | 0,01062 śr. | — |

Oba bloki dobrze pod limitem 3400 s — pojemność `ADCE` (196 łat) nie spowolniła treningu wobec
`ADC` (136 łat) mimo prawie 10× więcej wag: rdzeń natywny liczy każdą łatę tym samym prostym
odczytem z LUT niezależnie od jej rozmiaru, więc koszt na odcinek rośnie przede wszystkim z
**długością partii** (rosnącą wraz z dojrzewaniem polityki), nie z liczbą/rozmiarem łat — to samo
zjawisko, co odnotowano dla `ADC` kontra `AD` w `docs/ntuple-survival-adc.md`. Dla porównania,
ciąg dalszy `ADC` na dojrzałych wagach z rdzeniem natywnym (`docs/ntuple-survival-adcg.md`, blok
100k→140k) mierzył **0,01412 s/odcinek** — `ADCE` (0,01062 śr. na całym przebiegu 0→200k, 0,01126
w drugiej połowie) jest w tym samym rzędzie wielkości, nawet nieco szybszy, mimo 60 dodatkowych,
większych łat.

Migawki: `ntuple/survival-adce-100k.json` sha256 `8a1afab58aa2a8c5`,
`ntuple/survival-adce-200k.json` sha256 `3b30d00f9d0ec288`.

Ewaluacja bez uczenia (polityka behawioralna, nie `beam=128` — patrz pomiar niżej): 100k
wynik_śr=8240,72 przeżycie_śr=137,14 (50 partii, najlepszy punkt całego przebiegu,
`ntuple/survival-adce-best.json`); 200k wynik_śr=5139,02 przeżycie_śr=104,06 (50 partii, słabiej —
pojedynczy zaszumiony punkt 50-partiowy, nie krzywa; `best` nadal wskazuje na 100k).

## Migawka `ADC` porównywalna liczbą odcinków od zera

`ntuple/survival-adc-100k.json` (sha256 `3e75cd9c41264fd5`, `docs/ntuple-survival-adc.md`): trening
`ADC` **od zera**, `--seed 3 --move-cap 2000`, trzy bloki 0→40k→70k→100k, ten sam wzór co `ADCE`
tutaj — bezpośrednio porównywalna z `ntuple/survival-adce-100k.json` (ten sam budżet odcinków, ta
sama metoda).

`ntuple/survival-adcg-200k.json` (`docs/ntuple-survival-adcg.md`) **nie** jest treningiem od zera
do 200k: to `ntuple/survival-adc-100k.json` skopiowane pod nową nazwą i trenowane **kolejne** 100k
odcinków (100k→200k) na generatorze skalibrowanym z mostu (#186) — czyli 100k odcinków starego
generatora plus 100k odcinków nowego, nie 200k jednym ciągiem od zera. Zostaje w tabeli niżej jako
najbliższy dostępny punkt odniesienia `ADC` przy ~200k odcinkach, z tym zastrzeżeniem — nie jest
tak czystym porównaniem jak para `adc-100k`/`adce-100k`.

## Pomiar, `beam=128` (`tools/measure_ntuple_search_grid.py`, bez zmian w narzędziu)

200 partii/wiersz, seedy rozłączne z `bench/seeds_fixed.json` (sól własna `pilot-222`, sprawdzona
jawnie przez narzędzie), sufit z `bench/config.json` (`move_cap=4000`).

Baza rekordu (`ntuple/survival-adcga16-800k.json`, 800 000 odcinków `ADC`, `docs/ntuple-survival-adcga16.md`):

```
python3 tools/measure_ntuple_search_grid.py --n-seeds 200 --jobs 4 \
    --seed-salt pilot-222 --search beam=128 \
    --weights ntuple/survival-adcga16-800k.json ntuple/survival-adce-100k.json ntuple/survival-adce-200k.json \
              ntuple/survival-adc-100k.json ntuple/survival-adcg-200k.json \
    --out docs/data/ntuple-wieksze-laty-pomiar.json
```

| wagi | odcinków treningu | wynik śr. | se | przeżycie śr. | vs rekord (`adcga16-800k`) |
|---|---|---|---|---|---|
| `ntuple/survival-adcga16-800k.json` (rekord) | 800 000 | 79 579,74 | 6 382,35 | 600,98 | baza |
| `ntuple/survival-adce-100k.json` | 100 000 | 76 802,51 | 6 145,12 | 635,31 | -3,49% (0,31 SE, bez zmian) |
| `ntuple/survival-adce-200k.json` | 200 000 | 83 651,08 | 6 692,11 | 667,66 | +5,12% (0,45 SE, bez zmian) |
| `ntuple/survival-adc-100k.json` | 100 000 | 62 154,42 | 4 458,51 | 461,45 | -21,90% (2,39 SE, regresja) |
| `ntuple/survival-adcg-200k.json` | ~200 000* | 66 287,43 | 5 329,74 | 563,12 | -16,70% (1,55 SE, bez zmian) |

Druga runda, ten sam pomiar, baza = `adc-100k` (żeby zobaczyć **wprost** efekt pojemności przy tym
samym budżecie odcinków, parowana ta sama pula 200 seedów):

```
python3 tools/measure_ntuple_search_grid.py --n-seeds 200 --jobs 4 \
    --seed-salt pilot-222 --search beam=128 \
    --weights ntuple/survival-adc-100k.json ntuple/survival-adce-100k.json \
              ntuple/survival-adcg-200k.json ntuple/survival-adce-200k.json \
    --out docs/data/ntuple-wieksze-laty-pomiar-parowany.json
```

| wagi | odcinków treningu | wynik śr. | przeżycie śr. | vs `adc-100k` (ten sam budżet) |
|---|---|---|---|---|
| `ntuple/survival-adc-100k.json` (baza) | 100 000 | 62 154,42 | 461,45 | baza |
| `ntuple/survival-adce-100k.json` | 100 000 | 76 802,51 | 635,31 | **+23,57% (1,97 SE, poprawa)** |
| `ntuple/survival-adcg-200k.json`* | ~200 000 | 66 287,43 | 563,12 | +6,65% (0,67 SE, bez zmian) |
| `ntuple/survival-adce-200k.json` | 200 000 | 83 651,08 | 667,66 | **+34,59% (2,69 SE, poprawa)** |

\* `adcg-200k` nie jest treningiem od zera do 200k — patrz zastrzeżenie wyżej; podane tylko jako
punkt odniesienia, nie jako czysta para z `adce-200k`.

## Wniosek

**Pojemność (więcej i większe łaty) przełamuje plateau `ADC` *przy danym budżecie odcinków***:
`ADCE` bije `ADC` trenowany od zera na tym samym budżecie istotnie i w tym samym kierunku na obu
punktach (100k: +23,6%, 1,97 SE; 200k: +34,6%, 2,69 SE) — sama zmiana układu łat robi więcej niż
dalsze trenowanie `ADC` w tym budżecie (`adcg-200k` nad `adc-100k`: tylko +6,7%, 0,67 SE,
nieistotne). Ale **`ADCE` przy 200k nie bije jeszcze rekordu** 800 000-odcinkowego `ADC`
(+5,1%, 0,45 SE — w szumie pomiaru 200 partii), więc pilot nie rozstrzyga, czy `ADCE` przy dalszym
treningu dogoni i przebije rekord, czy spłaszczy się wcześniej jak `ADC`/`AD` w #194/#213.

## Rekomendacja

Żadna migawka (`ntuple/survival-adce-100k.json`, `-200k.json`) nie idzie teraz do oficjalnego
benchmarku (#8) — żadna nie bije rekordu istotnie na tym pomiarze, więc bench (300 partii,
drożej) tylko potwierdziłby to, co pilot już pokazał na 200. **Trenować dalej** jest uzasadnione:
krzywa `ADCE` rośnie między 100k a 200k na pomiarze `beam=128` (76 802 → 83 651, +8,9%) w
przeciwieństwie do `ADC` przy analogicznym przyroście budżetu (`adc-100k` → `adcg-200k`: tylko
+6,7%, nieistotne) — i trening jest tani (0,01062 s/odcinek średnio, żaden blok blisko limitu
3400 s), więc kolejne 200k-400k odcinków to rozsądny następny krok przed decyzją o benchmarku.
