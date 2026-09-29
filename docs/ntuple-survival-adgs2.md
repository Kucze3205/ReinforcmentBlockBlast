# Trening N-tuple etapowe, układ `AD`, sygnał survival: 200 000 -> 400 000 odcinków, 2 etapy (#209)

Pierwszy przebieg etapowy N-tuple (#203): dwa komplety wag układu `AD`, wybierane wg liczby
zajętych komórek planszy afterstate'u (`ntuple.occupied_count`) względem progu. Start z kopii
stanu i wag `ntuple/survival-adg-200k.json` (`docs/ntuple-survival-adg.md`) — oba etapy
zainicjowane tymi samymi wagami, bez starego logu i bez starej ewaluacji, wzorem
`docs/ntuple-survival-adcga4.md`. Parametry treningu (seed, alpha, move_cap, reward, layout)
identyczne z przebiegiem źródłowym `adg`.

## Próg etapu

Próg (`--thresholds`) wyznaczony `tools/measure_ntuple_stage_threshold.py` (#209, komentarz
raportu w `ca739e4`): mediana liczby zajętych komórek (`occupied_count`) afterstate'ów wybranych
zachłanną polityką treningu na wagach `ntuple/survival-adg-200k.json`, 200 partii ewaluacyjnych
(seedy `eval_seeds`, spoza `bench/config.json`), 22 947 afterstate'ów łącznie:

```
python3 tools/measure_ntuple_stage_threshold.py --weights ntuple/survival-adg-200k.json
```

Mediana: **21** zajętych komórek (na planszy 8x8, 64 pola). Etap 1 uczy się gry na planszy
względnie pustej (< 21 zajętych komórek), etap 2 — na planszy zapełnionej w drugiej połowie
partii, gdzie ryzyko przegranej rośnie i geometria dostępnych ruchów jest inna. Mediana (a nie
np. p25/p75) dzieli afterstate'y treningowe na dwie w przybliżeniu równe połowy, więc oba etapy
dostają porównywalną liczbę przykładów uczących.

## Stan startowy

`ntuple/survival-adgs2-state.json`: `episode = 200000`, `episodes_target = 400000`, układ `AD`,
`stages = 2`, `thresholds = [21]`, oba etapy zainicjowane kopią wag
`ntuple/survival-adg-200k.json`, `eval`/`windows`/log wyzerowane (nowy przebieg, ten sam wzór co
`docs/ntuple-survival-adcga4.md`). `ntuple/survival-adg-200k.json` (punkt startu) nietknięty:
sha256 `1fe18a4190e374ce`.

## Polecenie treningu

```
python3 tools/train_ntuple.py --reward survival --alpha 0.0003076923076923077 --seed 3 --move-cap 2000 \
    --layout AD --stages 2 --thresholds 21 \
    --state ntuple/survival-adgs2-state.json --out ntuple/survival-adgs2-weights.json \
    --best-out ntuple/survival-adgs2-best.json --curve-out docs/data/ntuple-survival-adgs2-krzywa.json \
    --eval-every 5000 --eval-episodes 200 --episodes 400000 --episodes-per-run 100000
```

## Bloki (pierwszy plan, każdy < 3600 s)

s/odcinek liczony z `ntuple/survival-adgs2-state.log.NNNN.jsonl` (suma `duration_s` wpisów bloku,
nie z zaokrąglanego pola stanu `duration_s`, ten sam powód co w `docs/ntuple-survival-adg.md`).

| blok | odcinki (od → do) | `--episodes-per-run` | czas bloku (rzeczywisty) | s/odcinek (log) |
|---|---|---|---|---|
| 1 | 200 000 → 300 000 | 100000 | 15m3,181s (903,181 s) | 0,00814 |
| 2 | 300 000 → 400 000 (KONIEC) | 100000 | 15m29,913s (929,913 s) | 0,00839 |

Oba bloki dobrze pod limitem 3600 s. Tempo (~0,0081-0,0084 s/odcinek) porównywalne z przebiegiem
jednoetapowym `adg` w tym samym zakresie (0,00949-0,00957 s/odcinek, `docs/ntuple-survival-adg.md`)
— dwa komplety wag nie podwajają kosztu kroku, bo każdy afterstate liczy tylko wagi swojego etapu.

## Zamrożone kopie wag

| plik | odcinek | sha256 (16 znaków) |
|---|---|---|
| `ntuple/survival-adgs2-300k.json` | 300 000 | `fdad4621b8a595b5` |
| `ntuple/survival-adgs2-400k.json` | 400 000 | `b1af6ffe7511d278` |

## Krzywa zachłanna (bez uczenia, 200 partii na punkt) co 25 000 odcinków

Te same seedy ewaluacji w każdym punkcie (`train_ntuple.eval_seeds`, niezależne od `--seed`).
Pierwszy punkt tego przebiegu to odcinek 205 000 (harmonogram zresetowany od kopii stanu przy
200 000); pełna lista w `docs/data/ntuple-survival-adgs2-krzywa.json`, tu punkty co 25 000:

| odcinki | wynik śr. | przeżycie śr. |
|---|---|---|
| 225 000 | 6557,81 | 123,57 |
| 250 000 | 6612,55 | 123,17 |
| 275 000 | 6538,89 | 123,39 |
| 300 000 | 6425,15 | 117,71 |
| 325 000 | 5990,26 | 116,61 |
| 350 000 | 6858,99 | 126,09 |
| 375 000 | 5815,49 | 113,06 |
| **400 000 (ostatnie)** | 5894,32 | 114,52 |

Najlepszy punkt ewaluacji całego przebiegu: odcinek **340 000** (wynik 7801,43, przeżycie 138,28,
200 partii) — `ntuple/survival-adgs2-best.json`.

## Odsetek postawień w każdym etapie

Z `stage_placements` każdego z 200 000 odcinków treningowych (`ntuple/survival-adgs2-state.log.0001.jsonl`
i `.0002.jsonl`), suma postawień na etap w całym przebiegu (24 305 017 postawień łącznie):

| etap | próg | postawienia | odsetek |
|---|---|---|---|
| 1 | zajęte komórki < 21 | 11 721 915 | 48,23% |
| 2 | zajęte komórki >= 21 | 12 583 102 | 51,77% |

Podział bliski połowie, zgodnie z medianą wybraną jako próg (patrz wyżej) — obie sieci uczą się
na porównywalnej liczbie przykładów przez cały przebieg 200k-400k, nie tylko w punkcie startowym.
