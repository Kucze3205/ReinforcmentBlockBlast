# Wpisy `"ok": false` w materiale serii s1–s5 (#333)

Narzędzie: `python3 tools/ok_false.py --out ...` (`tools/ok_false.py`, testy w `tests/test_bridge_banner.py`).
Każdy wpis z ruchem i `"ok": false` z `docs/seria/s*/partia-*/chunk*_moves.jsonl` trafia do jednej grupy wg różnicy
`observed` vs `expected` pole po polu (linie wyczyszczone ruchem liczone z `board` + klocka + `move`, tak jak robi to most
(`bridge.cleared_cells`)):

- `duchy_w_czyszczonych` — tylko nadmiar pól (observed=1, expected=0), wszystkie w liniach wyczyszczonych tym ruchem
  (baner „Combo N” czytany jako klocki, przyczyna przegranej s5 p.7);
- `nadmiar_gdzie_indziej` — tylko nadmiar, przynajmniej jedno pole poza liniami wyczyszczonymi;
- `brak_pol` — tylko brak (observed=0, expected=1);
- `mieszane` — nadmiar i brak.

`ruch_nieprzyjety` = wpisy, w których `observed` == `board` (plansza nie ruszyła się; podzbiór wszystkich grup).
`duch_dotrwal` = duch z pierwszej grupy jest w `board` następnego wpisu z ruchem, czyli polityka podjęła na nim
decyzję. `tacka_potwierdza` = tacka następnego wpisu potwierdza, że gra przyjęła klocek (`bridge.tray_consumed`) —
warunek, od którego poprawka zależy. `bez_nastepnego` = koniec pliku, brak wpisu do sprawdzenia.

| seria | ruchow | ok_false | duchy_w_czyszczonych | nadmiar_gdzie_indziej | brak_pol | mieszane | ruch_nieprzyjety | duch_dotrwal | tacka_potwierdza | bez_nastepnego |
|---|---|---|---|---|---|---|---|---|---|---|
| s1 | 17620 | 416 | 101 | 58 | 190 | 67 | 30 | 100 | 99 | 1 |
| s2 | 8630 | 569 | 117 | 123 | 263 | 66 | 17 | 116 | 116 | 1 |
| s3 | 15307 | 786 | 207 | 116 | 348 | 115 | 32 | 204 | 205 | 1 |
| s4 | 25297 | 967 | 232 | 162 | 442 | 131 | 59 | 231 | 230 | 1 |
| s5 | 12371 | 792 | 214 | 122 | 353 | 103 | 32 | 212 | 213 | 1 |
| **suma** | 79225 | 3530 | 871 | 581 | 1596 | 482 | 170 | 863 | 863 | 5 |

**Pierwsza grupa nie wyczerpuje problemu:** 871 z 3530 wpisów (25%) to duchy w liniach wyczyszczonych, a pozostałe
~75% (`brak_pol` 1596, `nadmiar_gdzie_indziej` 581, `mieszane` 482) to inne zjawiska (przyczyn nie rozstrzygałem; 170 wpisów to ruch nieprzyjęty, reszta
to plansza różna od `expected` w innych miejscach) i **ta zmiana ich nie rusza** (most nadal bierze
wtedy ekran).

## Co się zmieniło w moście

`bridge.drop_banner_ghosts` (pętla ruchu): gdy tacka potwierdza przyjęcie ruchu (`tray_consumed`) i `observed` różni
się od `expected` **wyłącznie** nadmiarem pól w liniach wyczyszczonych tym ruchem, te pola są puste (gra zawsze czyści
pełną linię), więc do następnej decyzji idzie `expected`. Każda inna różnica zostawia odczyt z ekranu. Wpis w logu ma
dalej surowe `observed`, a `ok` i lista `duchy` mówią, co poprawiono. Odczyt (`read_board`, `is_block`) bez zmian,
progi koloru nietknięte (#169).

Dlaczego nie czekanie z ponownym odczytem: nie da się go sprawdzić bez emulatora, a poprawka na samym stanie jest
deterministyczna i testowalna na zrzucie `s5/partia-7/kawalek_9/039_state.png`.

## Regresja odczytu (pułapka 28)

`tools/porownanie_odczytu.py` (`compare_state`) na **2090** stanach `*_state.png` z całego `docs/seria`
(s1–s5): przed zmianą (merge-base `24b6d69`) i po niej to **te same** 279 stanów z różnicą, z identycznymi listami
pól i slotów (porównanie plik do pliku). `read_board`/`read_tray` nie były zmieniane, więc nowych różnic nie ma.
