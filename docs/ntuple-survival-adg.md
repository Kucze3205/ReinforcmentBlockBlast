# Trening N-tuple, układ `AD`, sygnał survival: 70 000 -> 500 000 odcinków na skalibrowanym generatorze (#189)

Bliźniak treningu na dużą skalę na układzie `AD` (52 łaty, linia rekordu #157), startujący z kopii
stanu i wag `ntuple/survival-ad-70k.json` (`docs/ntuple-survival-ad.md`), bez starego logu i bez
starej ewaluacji (schemat ewaluacji się zmienia: 1000/100 -> 5000/200). Parametry treningu (seed,
alpha, move_cap, reward, layout) identyczne z przebiegiem źródłowym — zmienione tylko ścieżki,
`--episodes`/`--episodes-per-run` i ewaluacja. Rdzeń natywny (#184) jest dostępny na tej maszynie,
więc trening jest dużo szybszy niż sugerowałby czysty Python z `docs/ntuple-survival-ad.md`.

```
python3 tools/train_ntuple.py --reward survival --alpha 0.0003076923076923077 --seed 3 --move-cap 2000 \
    --layout AD \
    --state ntuple/survival-adg-state.json --out ntuple/survival-adg-weights.json \
    --best-out ntuple/survival-adg-best.json --curve-out docs/data/ntuple-survival-adg-krzywa.json \
    --eval-every 5000 --eval-episodes 200 --episodes 500000 --episodes-per-run <K>
```

## Bloki (pierwszy plan, każdy < 3400 s)

s/odcinek liczony z `ntuple/survival-adg-state.log*.jsonl` (suma `duration_s` wpisów bloku, nie z
zaokrąglanego pola stanu `duration_s`, ten sam powód co w `docs/ntuple.md`/`docs/ntuple-survival-ad.md`).

| blok | odcinki (od → do) | `--episodes-per-run` | czas bloku (rzeczywisty) | s/odcinek (log) |
|---|---|---|---|---|
| 1 | 70 000 → 130 000 | 60000 | 9m24,2s (564,2 s) | 0,00868 |
| 2 | 130 000 → 200 000 | 70000 | 11m44,7s (704,7 s) | 0,00931 |
| 3 | 200 000 → 300 000 | 100000 | 17m6,3s (1026,3 s) | 0,00949 |
| 4 | 300 000 → 400 000 | 100000 | 17m15,0s (1035,0 s) | 0,00957 |
| 5 | 400 000 → 500 000 (KONIEC) | 100000 | 17m8,3s (1028,3 s) | 0,00950 |

Wszystkie pięć bloków poniżej limitu 3400 s, z dużym zapasem (rdzeń natywny, #184): tempo
mieści się w 0,0087-0,0096 s/odcinek na całym zakresie 70 000-500 000, rosnące bardzo powoli
mimo 6,4× więcej odcinków niż w `docs/ntuple-survival-ad.md` (tam, jeszcze bez rdzenia natywnego,
0,197 s/odcinek w zakresie 40 001-70 000).

## Zamrożone kopie wag

| plik | odcinek | sha256 (16 znaków) |
|---|---|---|
| `ntuple/survival-adg-200k.json` | 200 000 | `1fe18a4190e374ce` |
| `ntuple/survival-adg-300k.json` | 300 000 | `3ea1a3393ee14212` |
| `ntuple/survival-adg-400k.json` | 400 000 | `70687363f10b592b` |
| `ntuple/survival-adg-500k.json` | 500 000 | `ebcd10f3043a7e7b` |

`ntuple/survival-ad-70k.json` (punkt startu) nietknięty: sha256 `58d1c5f997fa6f55`.

## Punkty ewaluacji (bez uczenia, 200 partii na punkt) co 5000 odcinków

| odcinki | wynik | przeżycie |
|---|---|---|
| 75 000 | 4434,78 | 95,07 |
| 80 000 | 4481,19 | 95,45 |
| 85 000 | 4545,82 | 94,71 |
| 90 000 | 4412,30 | 92,58 |
| 95 000 | 5592,97 | 107,73 |
| 100 000 | 5669,05 | 110,67 |
| 105 000 | 4266,41 | 89,67 |
| 110 000 | 5693,78 | 106,75 |
| 115 000 | 5238,40 | 108,59 |
| 120 000 | 5749,03 | 111,78 |
| 125 000 | 5503,92 | 109,81 |
| 130 000 | 5857,41 | 116,20 |
| 135 000 | 5397,27 | 111,78 |
| 140 000 | 6051,49 | 115,28 |
| 145 000 | 5618,47 | 114,47 |
| 150 000 | 6214,98 | 111,66 |
| 155 000 | 5522,69 | 105,11 |
| 160 000 | 5219,96 | 102,42 |
| 165 000 | 6277,80 | 112,08 |
| 170 000 | 5526,64 | 106,95 |
| 175 000 | 6363,62 | 116,34 |
| 180 000 | 5903,45 | 113,47 |
| 185 000 | 4490,05 | 93,11 |
| 190 000 | 5851,67 | 109,46 |
| 195 000 | 4981,60 | 94,29 |
| 200 000 | 6124,34 | 114,73 |
| 205 000 | 4914,76 | 98,97 |
| 210 000 | 5506,29 | 107,44 |
| 215 000 | 6233,34 | 114,91 |
| 220 000 | 6241,33 | 114,12 |
| 225 000 | 6345,50 | 115,38 |
| 230 000 | 5300,44 | 104,97 |
| 235 000 | 5511,21 | 110,80 |
| 240 000 | 5492,93 | 108,27 |
| 245 000 | 6039,35 | 114,14 |
| 250 000 | 6732,72 | 127,64 |
| 255 000 | 5920,33 | 116,40 |
| 260 000 | 4741,30 | 101,19 |
| 265 000 | 5823,01 | 109,74 |
| 270 000 | 5470,34 | 105,47 |
| 275 000 | 5977,61 | 112,61 |
| 280 000 | 6197,26 | 109,38 |
| 285 000 | 5777,83 | 110,36 |
| 290 000 | 5876,90 | 113,19 |
| 295 000 | 6071,10 | 124,22 |
| 300 000 | 5519,04 | 106,94 |
| 305 000 | 5725,51 | 106,17 |
| 310 000 | 5928,95 | 115,73 |
| 315 000 | 6047,81 | 111,81 |
| 320 000 | 6018,70 | 117,32 |
| 325 000 | 6314,74 | 117,03 |
| 330 000 | 6023,11 | 112,24 |
| 335 000 | 5728,56 | 111,61 |
| 340 000 | 5081,31 | 101,55 |
| 345 000 | 5209,48 | 97,75 |
| 350 000 | 6357,07 | 114,34 |
| 355 000 | 5882,66 | 111,91 |
| 360 000 | 4735,40 | 96,70 |
| 365 000 | 5313,15 | 102,31 |
| 370 000 | 6260,77 | 121,52 |
| 375 000 | 6592,06 | 121,40 |
| 380 000 | 6216,44 | 118,43 |
| 385 000 | 5331,81 | 107,84 |
| 390 000 | 5516,70 | 108,85 |
| 395 000 | 5464,77 | 107,12 |
| 400 000 | 6210,52 | 115,22 |
| 405 000 | 6085,71 | 113,54 |
| 410 000 | 5557,29 | 105,86 |
| 415 000 | 5579,31 | 103,23 |
| 420 000 | 6117,02 | 113,95 |
| 425 000 | 5350,97 | 103,60 |
| 430 000 | 5465,56 | 104,69 |
| 435 000 | 5839,13 | 116,19 |
| 440 000 | 6720,34 | 116,83 |
| 445 000 | 6195,31 | 115,43 |
| 450 000 | 4959,78 | 97,38 |
| 455 000 | 6115,61 | 115,33 |
| 460 000 | 5956,98 | 112,00 |
| 465 000 | 5858,93 | 108,01 |
| 470 000 | 6270,23 | 113,82 |
| 475 000 | 6352,20 | 119,62 |
| **480 000 (najlepsze)** | **6885,05** | **122,94** |
| 485 000 | 5992,13 | 112,06 |
| 490 000 | 5720,36 | 109,09 |
| 495 000 | 5952,10 | 112,84 |
| 500 000 (ostatnie) | 5570,66 | 109,25 |

`ntuple/survival-adg-best.json` nadpisano przy odcinku **480 000**: wynik 6885,05, przeżycie
122,94 (200 partii).

## Średnia długość odcinka treningowego

Liczona z `postawienia` (pole `placements`) wszystkich 430 000 wpisów logu (odcinki 70 001-500 000,
wszystkie cztery bloki rotacji: `.log.jsonl`, `.log.0001.jsonl`, `.log.0002.jsonl`, `.log.0003.jsonl`):

**108,06 postawień/odcinek** średnio na całym dopisanym zakresie (70 001-500 000).
