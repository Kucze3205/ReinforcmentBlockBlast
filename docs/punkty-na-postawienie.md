# Punkty na postawienie przy gwarancji tacki (#248)

Przy `complete=1` partie nie umierają ([dlugie-partie-gwarancja.md](dlugie-partie-gwarancja.md), #241), więc średnia
benchmarku = sufit × punkty na postawienie. Składnik ścieżki w `NTupleLookaheadPolicy` dla wag `survival` to liczba
postawień (`placed`) i nie patrzy na punkty; wybór między kompletnymi ułożeniami tacki szedł więc wyłącznie za oceną
N-tuple.

## Parametr `gain_weight`

Nowy całkowitoliczbowy parametr wyszukiwania `NTupleLookaheadPolicy(..., gain_weight=w)` (także
`benchmark.NTUPLE_SEARCH_PARAMS`, np. `lookahead-ntuple:<wagi>@beam=8,samples=0,complete=1,gain_weight=100000`).
Składnik ścieżki staje się

```
placed + w/1000 · gain          (gain = punkty z gry wzdłuż ścieżki)
```

a wartość liścia (`ntuple.value`) i reszta wyszukiwania są bez zmian. `w` to tysięczne części postawienia na punkt:
`w = 1000` waży punkt tak jak postawienie, `w = 100000` — tak, że ocena N-tuple rozstrzyga w praktyce tylko remisy
punktowe. `gain_weight = 0` (domyślnie) nie wykonuje żadnego nowego kroku: decyzje bit w bit jak przed #248.

- Tylko wagi `survival` (dla wag `score` ścieżką są już punkty): `gain_weight != 0` z wagami `score` → `ValueError`.
- Rdzeń natywny sumuje ścieżkę jako liczbę całkowitą, więc liczy w skali ×1000: `1000·placed + w·gain` przez tabele
  punktów podane z Pythona (`pp`, `cp_lo`, `cp_hi`, `fcb`) i kopię wag N-tuple przemnożoną przez 1000
  (`NTupleLookaheadPolicy._scaled_core`). `ntuple_native.c/.py` i `ntuple.py` bez zmian. Test
  `test_native_matches_python_search` porównuje stany wiązki natywnej i czystego Pythona (te same akcje, `gain`, `placed`,
  `score` do 1e-6).
- Przegląd wyczerpujący gwarancji (`_tray_complete_search`) używa tego samego składnika; przy `gain_weight != 0` klucz
  scalania stanów zawiera combo i licznik (jak dla `gain`), bo od nich zależą przyszłe punkty.
- `reward_shape_changed: no` — `game.step`, kary i punktacja nietknięte; zmienia się tylko to, co przeszukanie
  maksymalizuje przy wyborze ruchu.

**Wartość domyślna = zachowanie sprzed zmiany.** `bench/240-complete.json` nie niesie wyników per seed, więc porównanie
jest z przebiegiem sprzed zmiany na tych samych seedach (5 pierwszych stałych, sufit 4000, `complete=1`, `samples=0`,
wagi `survival-adce-400k`):

| B | wyniki (sprzed zmiany = `gain_weight=0`) |
|---|---|
| 8 | 478518, 411769, 413278, 372386, 495054 (test `test_default_reproduces_pre_change_scores_beam8`) |
| 128 | 568704, 587729, 575926, 527261, 630016 (jednorazowo sprawdzone, nie w teście — ~50 s) |

Ponadto `gain_weight=0` na 16 seedach do 20000 odtwarza średnie z #241 co do punktu (2 109 700 dla B=8, 2 603 193 dla B=32).

## Pomiar

Jak w #241: 16 pierwszych seedów stałych, sufit 20000, `complete=1`, `samples=0`, wagi `ntuple/survival-adce-400k.json`,
`--jobs 4`. Narzędzie: `tools/measure_gain_weight.py` (opakowanie na `tools/measure_death_avoidability.py`, konfiguracja
`docs/data/241-config-20k.json`). Dane: `docs/data/248-beam<B>-gw<W>.json`; wiersz `B=128, gw=0` pochodzi z
`docs/data/241-long-beam128.json`. Postawień/s = suma postawień / `elapsed_s` (wall, 4 procesy, runner CI — czasy nie
są porównywalne 1:1 z tabelą #241: `gw=0` dla B=8 wyszło tu 71 s wobec 84 s wtedy).

| B | `gain_weight` | śmierci | średnia pkt | mediana | min–max | pkt/postawienie | postawień/s |
|---|---|---|---|---|---|---|---|
| 8 | 0 | 0/16 | 2 109 700 | 2 123 984 | 1 972 675 – 2 291 510 | 105,5 | 4488 |
| 8 | 2 | 0/16 | 2 456 349 | 2 455 716 | 2 031 349 – 2 816 404 | 122,8 | 4414 |
| 8 | 5 | 0/16 | 2 870 912 | 2 900 248 | 2 451 592 – 3 503 236 | 143,5 | 4420 |
| 8 | 10 | 0/16 | 3 493 265 | 3 487 554 | 3 128 500 – 4 369 119 | 174,7 | 4444 |
| 8 | 20 | 0/16 | 3 958 791 | 3 970 366 | 3 348 364 – 4 712 675 | 197,9 | 4408 |
| 8 | 50 | 0/16 | 4 267 453 | 4 242 140 | 3 758 499 – 5 087 517 | 213,4 | 4526 |
| 8 | 100 | 0/16 | 4 354 212 | 4 366 926 | 3 919 704 – 4 753 416 | 217,7 | 4444 |
| 8 | 200 | 0/16 | 4 389 588 | 4 435 402 | 3 854 948 – 4 968 424 | 219,5 | 4426 |
| 8 | 500 | 0/16 | 4 482 236 | 4 441 364 | 3 696 061 – 5 442 484 | 224,1 | 4342 |
| 8 | 1000 | 0/16 | 4 332 901 | 4 364 404 | 3 882 872 – 5 034 486 | 216,6 | 4378 |
| 8 | 3000 | 0/16 | 4 895 460 | 4 870 472 | 4 247 866 – 5 831 979 | 244,8 | 4318 |
| 8 | 10000 | 0/16 | 5 495 764 | 5 513 402 | 4 653 579 – 6 373 077 | 274,8 | 4227 |
| 8 | 100000 | 0/16 | 5 809 088 | 5 768 216 | 4 844 685 – 6 654 727 | 290,5 | 4233 |
| 8 | 1000000 | 0/16 | 5 809 088 | 5 768 216 | 4 844 685 – 6 654 727 | 290,5 | 4233 |
| 32 | 0 | 0/16 | 2 603 193 | 2 606 986 | 2 391 242 – 2 917 115 | 130,2 | 2097 |
| 32 | 20 | 0/16 | 7 447 429 | 7 263 102 | 6 489 863 – 9 093 298 | 372,4 | 2116 |
| 32 | 500 | 0/16 | 7 486 152 | 7 648 052 | 5 921 983 – 9 306 679 | 374,3 | 2114 |
| 32 | 3000 | 0/16 | 7 997 041 | 7 958 874 | 6 154 144 – 9 280 794 | 399,9 | 2066 |
| 32 | 10000 | 0/16 | 8 663 688 | 8 625 996 | 7 241 840 – 10 916 318 | 433,2 | 1996 |
| 32 | 100000 | 0/16 | 9 067 867 | 9 152 824 | 7 307 489 – 10 778 582 | 453,4 | 2028 |
| 128 | 0 (#241) | 0/16 | 2 818 480 | 2 821 041 | 2 531 350 – 3 335 579 | 140,9 | 445 |
| 128 | 100000 | 0/16 | 13 692 823 | 13 027 562 | 11 454 940 – 18 872 237 | 684,6 | 557 |

**Śmierci: zero na wszystkich 22 konfiguracjach × 16 partii** (`n_capped = 16` w każdym pliku) — gwarancja tacki nadal
trzyma, także gdy waga punktów wypiera z ścieżki niemal całą ocenę N-tuple.

Uwagi do liczb:

- Zależność od `gain_weight` jest rosnąca i nasyca się dopiero przy `w ≈ 1e5`: dla B=8 `w=1e5` i `w=1e6` dają
  identyczne partie (ocena N-tuple przestaje rozstrzygać cokolwiek poza remisami punktowymi). Mała waga (`w ≤ 5`)
  pokrywa się rzędem wielkości z jednym postawieniem na ~140 pkt i daje tylko część zysku.
- Rozrzut między seedami jest duży (min–max ±15–25%), a przy B=8 zależność bywa nierówna (`w=1000` < `w=500`,
  `w=100` ≈ `w=200`); 16 partii wystarcza dla różnic ≥ ~5%, nie dla drobnych.
- Prędkość (postawień/s) nie zależy od `gain_weight` w granicach szumu — tabele ×1000 policzone raz na tackę, kopia
  wag raz na politykę. Dla B=128 wyższe postawień/s niż w #241 (557 vs 445) wynika z innego runnera.
- Wartość pkt/postawienie dla B=128 wyszła 684,6, ~5× więcej niż 140,9; dla B=32 — 3,5×; dla B=8 — 2,75×. Dlaczego
  szerokość wiązki tak silnie wzmacnia wagę punktów, nie badałem.

## Wniosek

**Najwięcej pkt/postawienie bez śmierci: `beam=128, gain_weight=100000` — 684,6** (0 śmierci w 16 × 20000 postawień).
Przy `beam=32` najlepsze jest `w=100000` (453,4), przy `beam=8` `w=100000` (290,5). Cel z issue (≥ 160 pkt/postawienie)
przy `beam=8` osiąga się od `w=10` (174,7); `w=5` daje 143,5.

Sufit 4000·2^k wystarczający na średnią 10 mln (zakładam stałe pkt/postawienie z pierwszych 20000 postawień — to
założenie, nie pomiar):

| konfiguracja | pkt/postawienie | potrzebne postawienia | najmniejszy sufit 4000·2^k | k | średnia przy tym suficie (szac.) | koszt 2×300 partii (wg zmierzonej prędkości, 4 procesy) |
|---|---|---|---|---|---|---|
| B=8, w=1e5 | 290,5 | ~34 400 | 64 000 | 4 | ~18,6 mln | 600 × 64 000 / 4233 ≈ 9 070 s ≈ 2,5 h |
| B=32, w=1e5 | 453,4 | ~22 100 | 32 000 | 3 | ~14,5 mln | 600 × 32 000 / 2028 ≈ 9 470 s ≈ 2,6 h |
| B=128, w=1e5 | 684,6 | ~14 600 | 16 000 | 2 | ~11,0 mln | 600 × 16 000 / 557 ≈ 17 200 s ≈ 4,8 h |

Sufit 16 000 przy B=128 daje zapas tylko ~10% nad 10 mln (rozrzut między seedami: min 11,45 mln, max 18,87 mln przy 20000,
czyli min ~9,2 mln przy 16000) — B=32 przy 32 000 ma zapas ~45% za zbliżony czas. Wybór pomiędzy nimi
i weryfikacja założenia stałych pkt/postawienie na sufitach 16 000–64 000 należą do orchestratora (osobny pomiar
`rola:bench`). Poprzednie wyliczenie z #241 (128 000 przy 141 pkt/postawienie) traci rację: przy `gain_weight=100000`
wystarcza sufit od 2 do 5 razy mniejszy.

## Czego nie sprawdzałem

- Benchmarku (`bench/` nietknięty). `policies.py` i `benchmark.py` są w `HASHED_SOURCES`, więc hash rekordu się zmienił
  (zmiana czysto addytywna: `gain_weight=0` nie zmienia decyzji, patrz wyżej); pomiar zleca orchestrator.
- Pkt/postawienie po 20000 postawieniach (możliwy wzrost combo albo spadek przy gęstej planszy).
- Partie z `samples > 0` z `gain_weight` (ścieżka działa i ma test na legalność akcji, jakości nie mierzyłem).
- Wpływu na apkę (krótsza partia do 1 mln): to pomiar verifiera.
