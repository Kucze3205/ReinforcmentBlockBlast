# Wpisy `"ok": false` w materiale serii s1–s5 (#333)

Narzędzie: `python3 tools/ok_false.py --out ...` (`tools/ok_false.py`, testy w `tests/test_bridge_banner.py` i `tests/test_ok_false.py`).
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

## Pozostałe 2659 wpisów: mechanizmy i wpływ na decyzję (#335)

Zmierzone, nic nie naprawione (`bridge.py` bez zmian). `python3 tools/ok_false.py --podgrupy [--decyzje] [--przyklady]`;
testy na wpisach z prawdziwego materiału: `tests/test_ok_false.py`.

### Jak liczone

Każdy wpis z grup `nadmiar_gdzie_indziej`, `brak_pol` i `mieszane` dostaje nazwę z dwóch kroków.

1. Nazwa całego wpisu, gdy cały `observed` pasuje do wzorca: `plansza_bez_zmian` (`observed == board`), `odczyt_pusty` (pusta
   plansza przy niepustej), `klocek_obok_celu` (`observed` = `board` + ten sam klocek w innym miejscu), `inny_klocek`
   (`observed` = `board` + inny klocek z puli; tylko gdy odczyt ma pola poza klockiem z tacki).
2. Etykiety pól różnicy; nazwa podgrupy to rodzaje etykiet połączone `+`, pole bez etykiety daje `niewyjasnione`
   (przy >= 10 różniących się polach `niewyjasnione_duze`):
   - `dawny_duch` (brak): pole puste na ekranie, a `board` miał je jako klocek od wcześniejszego kroku, w którym
     `observed`=1, `expected`=0. Odczyt jest tu **prawdziwy**, błąd niósł `expected`;
   - `zakryte_wraca` (nadmiar): odbicie poprzedniego: pole puste w `board`, a wcześniej `observed`=0 przy `expected`=1
     (klocek był zakryty). Odczyt **prawdziwy**;
   - `napis` (nadmiar i brak): różnica w wierszach 3–5, gdy któreś pole różnicy leży w wierszu 4 (napis „Combo N" z „+N" albo
     „Perfect!" wisi na środku planszy i czytany jest jak klocki, albo zakrywa prawdziwe);
   - `serce` (nadmiar): >= 4 pola w wierszach i kolumnach 1–6, w >= 3 wierszach (różowe serce animacji „Combo N");
   - `baner` (nadmiar): w linii wyczyszczonej albo wiersz nad wyczyszczoną (hipoteza z #335);
   - `klocek_niepelny` (brak): pole brakujące jest polem postawionego klocka.

Etykiety `napis` i `serce` to **geometria**, nie kolor (zrzutów jest tylko 2090 z 79225 ruchów). Sprawdziłem je na zrzutach
w przykładach poniżej; przy wpisach bez zrzutu to przypisanie z wiersza, nie dowód.

`dotrwal` = pola różnicy w `board` następnego wpisu z ruchem mają wartość z `observed` (jak `duch_dotrwal`). Uwaga: to prawie
tautologia, bo pętla mostu podaje następnemu ruchowi ten sam odczyt (`grid` z `stable_state` po ruchu), a nie nowy;
`dotrwal` = fałsz, gdy następny wpis ma już inną planszę (np. po dodatkowym odczycie; w `niewyjasnione_duze` i `odczyt_pusty` zwykle jest to
plansza równa `expected`), i wtedy różnica nie dochodzi do decyzji.

### Podgrupy per seria

| grupa | podgrupa | s1 | s2 | s3 | s4 | s5 | suma | dotrwal | tacka_potwierdza |
|---|---|---|---|---|---|---|---|---|---|
| nadmiar_gdzie_indziej | napis | 13 | 72 | 68 | 86 | 64 | 303 | 300 | 301 |
| nadmiar_gdzie_indziej | zakryte_wraca | 29 | 28 | 35 | 63 | 37 | 192 | 190 | 185 |
| nadmiar_gdzie_indziej | napis+zakryte_wraca | 4 | 8 | 3 | 4 | 10 | 29 | 29 | 29 |
| nadmiar_gdzie_indziej | serce | 5 | 5 | 4 | 5 | 6 | 25 | 25 | 25 |
| nadmiar_gdzie_indziej | niewyjasnione_duze | 2 | 5 | 3 | 1 | 0 | 11 | 9 | 9 |
| nadmiar_gdzie_indziej | serce+zakryte_wraca | 1 | 2 | 1 | 1 | 2 | 7 | 7 | 7 |
| nadmiar_gdzie_indziej | inny_klocek | 3 | 2 | 0 | 1 | 0 | 6 | 6 | 1 |
| nadmiar_gdzie_indziej | baner | 1 | 0 | 1 | 0 | 1 | 3 | 3 | 3 |
| nadmiar_gdzie_indziej | baner+zakryte_wraca | 0 | 0 | 0 | 1 | 1 | 2 | 2 | 2 |
| nadmiar_gdzie_indziej | niewyjasnione | 0 | 1 | 1 | 0 | 0 | 2 | 2 | 2 |
| nadmiar_gdzie_indziej | baner+napis+zakryte_wraca | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
| brak_pol | dawny_duch | 118 | 175 | 266 | 299 | 279 | 1137 | 1129 | 1129 |
| brak_pol | plansza_bez_zmian | 29 | 17 | 32 | 59 | 32 | 169 | 166 | 161 |
| brak_pol | napis | 17 | 15 | 14 | 34 | 14 | 94 | 94 | 90 |
| brak_pol | odczyt_pusty | 13 | 24 | 17 | 26 | 7 | 87 | 18 | 72 |
| brak_pol | niewyjasnione_duze | 3 | 7 | 9 | 5 | 10 | 34 | 25 | 31 |
| brak_pol | niewyjasnione | 7 | 5 | 3 | 11 | 7 | 33 | 32 | 32 |
| brak_pol | klocek_niepelny | 2 | 15 | 2 | 4 | 1 | 24 | 22 | 16 |
| brak_pol | napis+klocek_niepelny | 0 | 3 | 1 | 2 | 1 | 7 | 7 | 6 |
| brak_pol | napis+dawny_duch+klocek_niepelny | 1 | 1 | 4 | 0 | 0 | 6 | 6 | 2 |
| brak_pol | napis+dawny_duch | 0 | 0 | 0 | 1 | 2 | 3 | 3 | 3 |
| brak_pol | dawny_duch+klocek_niepelny | 0 | 1 | 0 | 1 | 0 | 2 | 2 | 1 |
| mieszane | niewyjasnione_duze | 17 | 14 | 21 | 35 | 17 | 104 | 38 | 101 |
| mieszane | dawny_duch+zakryte_wraca | 16 | 11 | 26 | 23 | 17 | 93 | 93 | 92 |
| mieszane | napis | 10 | 10 | 28 | 26 | 18 | 92 | 90 | 90 |
| mieszane | inny_klocek | 8 | 9 | 4 | 11 | 11 | 43 | 43 | 22 |
| mieszane | baner+napis+dawny_duch | 2 | 8 | 6 | 11 | 6 | 33 | 33 | 33 |
| mieszane | napis+dawny_duch | 1 | 5 | 3 | 4 | 9 | 22 | 21 | 21 |
| mieszane | baner+dawny_duch | 0 | 1 | 6 | 5 | 7 | 19 | 18 | 18 |
| mieszane | napis+zakryte_wraca | 4 | 2 | 4 | 3 | 6 | 19 | 19 | 18 |
| mieszane | niewyjasnione | 3 | 0 | 6 | 4 | 5 | 18 | 18 | 18 |
| mieszane | baner+napis+dawny_duch+zakryte_wraca | 1 | 1 | 2 | 3 | 3 | 10 | 10 | 5 |
| mieszane | napis+dawny_duch+zakryte_wraca+klocek_niepelny | 0 | 1 | 4 | 2 | 1 | 8 | 8 | 5 |
| mieszane | napis+dawny_duch+zakryte_wraca | 1 | 0 | 0 | 1 | 2 | 4 | 4 | 3 |
| mieszane | klocek_obok_celu | 0 | 1 | 1 | 1 | 0 | 3 | 3 | 2 |
| mieszane | napis+zakryte_wraca+klocek_niepelny | 1 | 1 | 1 | 0 | 0 | 3 | 3 | 1 |
| mieszane | baner+klocek_niepelny | 1 | 0 | 0 | 0 | 1 | 2 | 2 | 2 |
| mieszane | baner+napis | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 1 |
| mieszane | baner+napis+dawny_duch+zakryte_wraca+klocek_niepelny | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 0 |
| mieszane | dawny_duch+zakryte_wraca+klocek_niepelny | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 |
| mieszane | napis+klocek_niepelny | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 |
| mieszane | serce+dawny_duch | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 1 |
| mieszane | serce+napis+klocek_niepelny | 0 | 0 | 1 | 0 | 0 | 1 | 0 | 1 |
| mieszane | serce+napis+zakryte_wraca | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| mieszane | serce+napis+zakryte_wraca+klocek_niepelny | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 1 |
| mieszane | zakryte_wraca+klocek_niepelny | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 |

### Wpływ na decyzję polityki rekordu

Polityka: `lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000` (`bench/record.json`,
`przegrana_serii.build_policy`). Dla wpisów z `dotrwal` liczone na planszy następnego wpisu (to widziała polityka), z tacką tego
wpisu: (a) jak w odczycie, (b) z polami różnicy podmienionymi na `expected`. Kolumny: `decyzja_inna` — wybrany ruch inny;
`odczyt_bez_ulozenia_a_expected_ma` — na planszy z odczytu nie da się ułożyć całej tacki, a na `expected` da się (tak wyglądał
s5 p.7: wpis 38 jest w pierwszym wierszu tabeli i jest tam jedynym takim przypadkiem); `ruch_odczytu_nielegalny_na_expected` — ruch
wybrany na odczycie jest nielegalny na `expected` (gra go odrzuci). Dwie ostatnie kolumny mają sens tylko tam, gdzie
`odczyt_bledny` = `tak`; gdy `nie`, to `expected` jest błędne, a odczyt trafny, więc liczby opisują ducha w `expected`, nie szkodę.
`decyzja_inna` nie znaczy „gorsza": nie oceniam ruchów (brak wartości na tej samej planszy), liczę tylko, czy się różnią.

| grupa | podgrupa | odczyt_bledny | wpisy | dotrwal | decyzja_inna | odczyt_bez_ulozenia_a_expected_ma | ruch_odczytu_nielegalny_na_expected |
|---|---|---|---|---|---|---|---|
| duchy_w_czyszczonych | duchy_w_czyszczonych | tak | 871 | 863 | 362 | 1 | 0 |
| nadmiar_gdzie_indziej | napis | tak | 303 | 300 | 169 | 2 | 0 |
| nadmiar_gdzie_indziej | zakryte_wraca | nie | 192 | 190 | 101 | 0 | 0 |
| nadmiar_gdzie_indziej | napis+zakryte_wraca | tak | 29 | 29 | 17 | 0 | 0 |
| nadmiar_gdzie_indziej | serce | tak | 25 | 25 | 23 | 0 | 0 |
| nadmiar_gdzie_indziej | niewyjasnione_duze | nieznane | 11 | 9 | 9 | 0 | 0 |
| nadmiar_gdzie_indziej | serce+zakryte_wraca | tak | 7 | 7 | 7 | 0 | 0 |
| nadmiar_gdzie_indziej | inny_klocek | nieznane | 6 | 6 | 4 | 0 | 0 |
| nadmiar_gdzie_indziej | baner | tak | 3 | 3 | 2 | 0 | 0 |
| nadmiar_gdzie_indziej | baner+zakryte_wraca | tak | 2 | 2 | 1 | 0 | 0 |
| nadmiar_gdzie_indziej | niewyjasnione | nieznane | 2 | 2 | 2 | 0 | 0 |
| nadmiar_gdzie_indziej | baner+napis+zakryte_wraca | tak | 1 | 1 | 1 | 0 | 0 |
| brak_pol | dawny_duch | nie | 1137 | 1129 | 465 | 1 | 153 |
| brak_pol | plansza_bez_zmian | tak | 169 | 166 | 124 | 0 | 35 |
| brak_pol | napis | tak | 94 | 94 | 38 | 1 | 9 |
| brak_pol | odczyt_pusty | tak | 87 | 18 | 12 | 0 | 3 |
| brak_pol | niewyjasnione_duze | nieznane | 34 | 25 | 15 | 0 | 9 |
| brak_pol | niewyjasnione | nieznane | 33 | 32 | 21 | 0 | 7 |
| brak_pol | klocek_niepelny | tak | 24 | 22 | 12 | 0 | 3 |
| brak_pol | napis+klocek_niepelny | tak | 7 | 7 | 7 | 0 | 6 |
| brak_pol | napis+dawny_duch+klocek_niepelny | tak | 6 | 6 | 3 | 0 | 2 |
| brak_pol | napis+dawny_duch | tak | 3 | 3 | 3 | 0 | 2 |
| brak_pol | dawny_duch+klocek_niepelny | tak | 2 | 2 | 2 | 0 | 0 |
| mieszane | niewyjasnione_duze | nieznane | 104 | 38 | 27 | 0 | 8 |
| mieszane | dawny_duch+zakryte_wraca | nie | 93 | 93 | 54 | 0 | 16 |
| mieszane | napis | tak | 92 | 90 | 58 | 2 | 13 |
| mieszane | inny_klocek | nieznane | 43 | 43 | 30 | 0 | 6 |
| mieszane | baner+napis+dawny_duch | tak | 33 | 33 | 26 | 0 | 7 |
| mieszane | napis+dawny_duch | tak | 22 | 21 | 14 | 0 | 5 |
| mieszane | baner+dawny_duch | tak | 19 | 18 | 11 | 0 | 4 |
| mieszane | napis+zakryte_wraca | tak | 19 | 19 | 14 | 0 | 2 |
| mieszane | niewyjasnione | nieznane | 18 | 18 | 13 | 0 | 6 |
| mieszane | baner+napis+dawny_duch+zakryte_wraca | tak | 10 | 10 | 9 | 1 | 4 |
| mieszane | napis+dawny_duch+zakryte_wraca+klocek_niepelny | tak | 8 | 8 | 7 | 0 | 3 |
| mieszane | napis+dawny_duch+zakryte_wraca | tak | 4 | 4 | 3 | 0 | 1 |
| mieszane | klocek_obok_celu | nie | 3 | 3 | 1 | 0 | 0 |
| mieszane | napis+zakryte_wraca+klocek_niepelny | tak | 3 | 3 | 3 | 0 | 1 |
| mieszane | baner+klocek_niepelny | tak | 2 | 2 | 2 | 0 | 0 |
| mieszane | baner+napis | tak | 1 | 1 | 1 | 0 | 0 |
| mieszane | baner+napis+dawny_duch+zakryte_wraca+klocek_niepelny | tak | 1 | 1 | 1 | 0 | 1 |
| mieszane | dawny_duch+zakryte_wraca+klocek_niepelny | tak | 1 | 1 | 1 | 0 | 1 |
| mieszane | napis+klocek_niepelny | tak | 1 | 1 | 0 | 0 | 0 |
| mieszane | serce+dawny_duch | tak | 1 | 1 | 1 | 0 | 0 |
| mieszane | serce+napis+klocek_niepelny | tak | 1 | 0 | 0 | 0 | 0 |
| mieszane | serce+napis+zakryte_wraca | tak | 1 | 0 | 0 | 0 | 0 |
| mieszane | serce+napis+zakryte_wraca+klocek_niepelny | tak | 1 | 0 | 0 | 0 | 0 |
| mieszane | zakryte_wraca+klocek_niepelny | tak | 1 | 1 | 1 | 0 | 0 |

Zbiorczo:

| grupa | odczyt | wpisy | dotrwal | decyzja_inna | odczyt_bez_ulozenia_a_expected_ma | ruch_odczytu_nielegalny_na_expected |
|---|---|---|---|---|---|---|
| duchy_w_czyszczonych | odczyt_bledny=tak | 871 | 863 | 362 | 1 | 0 |
| nadmiar_gdzie_indziej | odczyt_bledny=tak | 370 | 367 | 220 | 2 | 0 |
| nadmiar_gdzie_indziej | odczyt_bledny=nie | 192 | 190 | 101 | 0 | 0 |
| nadmiar_gdzie_indziej | odczyt_bledny=nieznane | 19 | 17 | 15 | 0 | 0 |
| brak_pol | odczyt_bledny=nie | 1137 | 1129 | 465 | 1 | 153 |
| brak_pol | odczyt_bledny=tak | 392 | 318 | 201 | 1 | 60 |
| brak_pol | odczyt_bledny=nieznane | 67 | 57 | 36 | 0 | 16 |
| mieszane | odczyt_bledny=tak | 221 | 214 | 152 | 3 | 42 |
| mieszane | odczyt_bledny=nieznane | 165 | 99 | 70 | 0 | 20 |
| mieszane | odczyt_bledny=nie | 96 | 96 | 55 | 0 | 16 |

### Przykłady (zrzut obejrzany; numer wpisu = `n` w `chunkK_moves.jsonl`, zrzut stanu po ruchu to `n+1`)

- `napis`, nadmiar: `docs/seria/s4/partia-1/kawalek_22/055_state.png`, wpis 54 — „Perfect!" na wierszu 4 zasłania środek planszy, odczyt dodaje (4,3).
- `napis`, brak: `docs/seria/s5/partia-2/kawalek_4/020_state.png`, wpis 19 — „+240 Combo 39" na wierszu 4 zakrywa klocek (4,3).
- `napis`, mieszane: `docs/seria/s1/partia-8/kawalek_1/015_state.png`, wpis 14 — „+90 Combo 5" na wierszach 3–4 i na klockach pod nim.
- `serce`: `docs/seria/s5/partia-8/kawalek_1/049_state.png`, wpis 48 — różowe serce „Combo 29" w środku planszy, odczyt dodaje 10 pól.
- `zakryte_wraca`: `docs/seria/s3/partia-4/kawalek_2/050_state.png`, wpis 49 — ekran bez nakładki, pole (4,5) jest klockiem; w poprzednim kroku (48) odczyt go nie widział.
- `dawny_duch`: `docs/seria/s1/partia-3/kawalek_54/100_state.png`, wpis 99 — pól (6,3),(6,4) na ekranie nie ma; `expected` dziedziczył je z wcześniejszego odczytu.
- `dawny_duch+zakryte_wraca` (mieszane): `docs/seria/s5/partia-5/kawalek_7/050_state.png`, wpis 49 — plansza bez nakładki, odczyt zgodny z ekranem, `expected` niesie stare błędy.
- `plansza_bez_zmian`: `docs/seria/s1/partia-2/kawalek_1/015_state.png`, wpis 14 (i `100_state.png`, wpis 99) — postawiony klocek jest na ekranie
  z ikonami kciuka (efekt nagrody), `is_block` ich nie czyta, odczyt = `board`; tacka potwierdza przyjęcie ruchu w 161 z 169 wpisów.
- `klocek_niepelny`: `docs/seria/s2/partia-2/kawalek_4/054_state.png`, wpis 53 — z klocka 2x3 widać tylko kształt S (4 z 6 pól), bez efektu na ekranie; przyczyna niewyjaśniona.
- `inny_klocek`, mieszane: `docs/seria/s1/partia-9/kawalek_1/015_state.png`, wpis 14 — na ekranie ikony kciuka na fioletowych polach (efekt nagrody); odczyt pasuje do innego klocka niż z tacki.
- `inny_klocek`, nadmiar: `docs/seria/s1/partia-5/kawalek_2/035_state.png`, wpis 34 — plansza bez nakładki, pola (0,2),(1,2) są klockami; klocek upadł inaczej niż w modelu.
- `klocek_obok_celu`: `docs/seria/s3/partia-7/kawalek_1/006_state.png`, wpis 5 — klocek 1x3 leży o wiersz niżej niż zamierzony (0,2)-(0,4).
- `baner+dawny_duch`: `docs/seria/s4/partia-4/kawalek_7/029_state.png`, wpis 28 — „+1800 Combo 89" na wierszach 1–3; pola różnicy (1,5),(1,6),(2,5),(2,6) leżą pod prawą częścią napisu.
- `baner+napis+dawny_duch`: `docs/seria/s3/partia-6/kawalek_4/050_state.png`, wpis 49 — brak widocznej nakładki, tylko konfetti; plansza zgodna z odczytem, więc etykiety `baner`/`napis` to tu zbieg z geometrią, a różnica to prawdopodobnie echo.
- `niewyjasnione_duze`: `docs/seria/s4/partia-4/kawalek_1/100_state.png`, wpis 99 — zwykła plansza bez nakładki, 11 pól różnicy bez wzorca. Przy wpisach bez `dotrwal` to
  także ekrany niebędące planszą (`s4/partia-4/kawalek_7/067_state.png`: reklama wideo; `s3/partia-3/kawalek_18/035_state.png`: koło fortuny), czytane jak plansza.
- Bez zrzutu w materiale: `odczyt_pusty` (18 wpisów z `dotrwal`), `baner` (samodzielny, 3) i `niewyjasnione` (małe). Dla nich brak dowodu na ekranie.

### Wnioski

- **`nadmiar_gdzie_indziej` (581):** hipoteza „glify baneru nad wierszem wyczyszczonym" nie trzyma się (`baner` w 6 wpisach). Główny mechanizm to napis albo serce
  animacji „Combo N" / „Perfect!" na środku planszy, nie w wierszu czyszczonym: 365 wpisów (333 `napis`, 32 `serce`). 231 wpisów zawiera echo (`zakryte_wraca`, z tego 192 samo):
  pole zakryte w poprzednim kroku, a odczyt jest już trafny.
- **`mieszane` (482):** hipoteza „klocek upadł o jedno pole obok celu" potwierdzona dla **3** wpisów. Reszta: napis zakrywający i dodający naraz (197 wpisów z `napis`),
  echo wcześniejszych błędów bez napisu (`dawny_duch+zakryte_wraca`, 93), `inny_klocek` (43) i `niewyjasnione` (122, z czego 104 duże).
- **`brak_pol` (1596):** hipoteza „animacja wejścia klocka" potwierdzona w mniejszości (`klocek_niepelny`: 24 samodzielnie, 39 z innymi rodzajami). 1137 (71%) to echo: duch
  z wcześniejszego kroku znika, a `expected` go dziedziczył. 169 to `plansza_bez_zmian`: ruch **przyjęty** (tacka potwierdza w 161), klocek na ekranie jest, ale ukryty pod ikonami kciuka;
  87 to klatki przejściowe (`odczyt_pusty`, w 69 leczy je następny odczyt); 110 wpisów z `napis` (baner zakrywa klocki).
- **Ruch nieprzyjęty (170, `observed == board`):** hipoteza odrzucona. To nie są ruchy odrzucone przez grę, tylko klocek nieczytelny w odczycie; 169 z nich jest w `brak_pol`, jeden w `duchy_w_czyszczonych`.
- **Echo to ta sama przyczyna, nie osobne błędy.** 1425 z 2659 wpisów (54%) to odczyt trafny w polach różnicy (echo wcześniejszego kroku albo klocek obok celu), a `expected` niesie stary błąd.
  Decyzje na nich zapadły na dobrym odczycie; liczby `decyzja_inna` w tych wierszach opisują ducha w `expected`, nie szkodę.
- **Wpływ na decyzję:** w trzech grupach z tego dokumentu 983 wpisy mają odczyt błędny (`tak`), 899 z nich dotrwało, a decyzja polityki jest inna w 573 (64%); w pierwszej grupie 863 dotrwałe
  i 362 inne (42%). Samo „inna" niczego nie ocenia. Plansza z odczytu bez układu całej tacki, przy układzie na `expected`, zdarzyła się w **8** wpisach: wpis 38 s5 p.7 (baner Combo),
  6 razy `napis` (`s3/partia-3/chunk18` n=33, `s4/partia-1/chunk22` n=54, `s4/partia-10/chunk8` n=45, `s4/partia-8/chunk7` n=123, `s5/partia-9/chunk10` n=65, `s5/partia-9/chunk13` n=44) i raz echo
  (`s4/partia-10/chunk16` n=27, odczyt trafny). Poza p.7 w żadnym z siedmiu nie ma wiersza `koniec_partii` w ciągu 7 następnych wpisów logu, więc przegranej z tego nie widać.
  W 102 wpisach z odczytem błędnym ruch polityki jest nielegalny na prawdziwej planszy (gra go odrzuca, most czyta ponownie: koszt czasu, nie partii).
- **Werdykt (propozycja):** poza duchami w czyszczonych liniach (#333) tylko podgrupa `napis` (640 wpisów w trzech grupach, 6 z 8 przypadków utraty układu tacki) może przegrać partię tak jak s5 p.7;
  naprawić ją tym samym narzędziem co #333: przy ruchu potwierdzonym przez tackę brać `expected` w polach różnicy leżących w wierszach 3–5 (i w środku planszy dla `serce`), a osobno
  `plansza_bez_zmian` (169 wpisów, 35 ruchów nielegalnych): gdy tacka potwierdza ruch, a `observed == board`, brać `expected`. Każdą regułę najpierw zmierzyć na zrzutach
  (`tools/porownanie_odczytu.py`) i na echu z tej tabeli, bo `klocek_obok_celu` i `inny_klocek` pokazują, że `expected` bywa błędne.
