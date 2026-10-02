# s6: cztery przegrane na oryginale — przyczyny (#341)

Zaraportowano, nie naprawiono. Materiał: `docs/seria/s6/` (z `origin/task/337`, scommitowany bez zmian). Narzędzia, wszystkie
powtarzalne i z testami w `tests/`: `tools/przegrana_serii.py` (werdykt), `tools/przeglad_s6.py` (przegląd wsteczny),
`tools/duchy_serii.py` (częstość w s3–s6), `tools/rozklad_tacek.py` (rozkład tacek). `bridge.py` i pliki odcisku
benchmarku są nietknięte.

## Werdykt w skrócie

**Wszystkie cztery przegrane mają jedną przyczynę: most.** W każdej partii decyzja przy pierwszej (p.3: przy pierwszej
z dwóch) tacce, która dała przegraną, zapadła na planszy z duchami baneru („Perfect!” albo „Combo 5”) w wierszach 3–4. Na
planszy prawdziwej polityka rekordu gra inaczej i **układa ostatnią tackę w całości**; ruch mostu to uniemożliwił.
To nie jest generator apki (ostatnie tacki były układalne) ani ślepa plamka polityki (polityka znajduje układ, gdy widzi
prawdziwą planszę). Naprawa z #333 (`drop_banner_ghosts`) tu nie zadziałała: zdejmuje tylko nadmiar pól leżący
w liniach wyczyszczonych ruchem, a tutaj duch leży poza nimi (p.2, p.8, p.10) albo odczyt gubi też klocek zasłonięty
przez glif (p.3).

| partia | wynik z ekranu | `przegrana_serii` | ruch decydujący | duch w `board` (kolor łaty z `NNN_state.png`) | most zagrał | polityka na prawdziwej planszy | legalnych / z układem po ruchu |
|---|---|---|---|---|---|---|---|
| p.2 | 289 145 | `rozjazd_mostu` (`ok_false_przed_ostatnim_ruchem`, n=14, 15) | n=15 | (4,4), „Perfect!” (238,113,76) | slot 1 → (3,0) | slot 0 → (4,0) | 6 / 1 (tylko ruch polityki) |
| p.3 | 407 069 | `rozjazd_mostu` (n=13, 14) | n=14 | (4,3),(4,4),(4,5) nadmiar i (3,2) brak, „Perfect!” (190,76,48), (238,113,75), (250,140,111); (3,2) = (98,125,66) czytane jako puste | slot 1 → (5,1) | slot 2 → (3,4) | 2 / 1 |
| p.8 | 384 087 | `rozjazd_mostu` (n=31, 32) | n=32 | (4,5), „Perfect!” (250,140,111) | slot 0 → (1,6) | slot 0 → (5,2) | 10 / 1 |
| p.10 | 15 871 | `rozjazd_mostu` (n=43) | n=44 | (4,2),(4,3), „Combo 5” (60,160,148), (64,173,160) | slot 0 → (1,2) | slot 0 → (3,6) | 3 / 1 |

Kontrfaktyk (`przeglad_s6`, polityka od ruchu z duchem na prawdziwej planszy, na zalogowanych tackach): w każdej
z czterech partii **układa wszystkie zalogowane tacki, ostatnią włącznie**. Ostatnia tacka była rozdana, zanim zapadła
decyzja z duchem, więc dla niej kontrfaktyk jest dokładny; dalszych tacek apka po innej grze mogłaby nie rozdać tak samo.

## Co mówi `tools/przegrana_serii.py`

Dla każdej partii: `rozjazd_mostu`, powód `ok_false_przed_ostatnim_ruchem` (p.2: n=14, 15; p.3: n=13, 14; p.8: n=31, 32;
p.10: n=43). To werdykt mechaniczny: każdy `ok: false` w dwóch ostatnich tackach daje „rozjazd”, bez rozróżnienia
echa od błędu odczytu (`docs/seria/ok-false.md`). Przegląd niżej rozstrzyga, że tu był to błąd odczytu, który zmienił
decyzję. Ani razu nie wyszedł `tacka_nieukladalna` ani `slepa_plamka`.

## Przegląd wsteczny (`tools/przeglad_s6.py`)

Ogon każdej partii: całe tacki, razem co najmniej 10 ruchów. Kolumny:

- **pola board≠prawda**: różnica między `board` (to, co zobaczyła polityka) a planszą prawdziwą. Prawdę liczymy
  łańcuchem symulacji od początku ogona (ruch przyjęty przez grę wg `bridge.tray_consumed` jest stawiany tam, gdzie chciał
  most), nie z `expected` mostu: ten rośnie z odczytanej planszy i dziedziczy duchy (jak w `docs/seria/s5/przegrana-p7.md`).
- **ok**, **klasa** (`tools/ok_false.py`), **duchy zdjęte** (pole `duchy` z #333): w żadnym z ruchów ogona most nie zdjął
  duchów, bo reguła #333 nie pasowała do tych różnic.
- **polityka na prawdzie**: ruch polityki rekordu (spec z `pomiar.json`) na prawdziwej planszy i tej samej tacce.
- **legalnych / z ułożeniem**: spośród legalnych ruchów, po ilu reszta bieżącej tacki i wszystkie późniejsze zalogowane
  tacki (z ostatnią) dają się ułożyć w całości (przegląd wyczerpujący, bez limitu głębokości, z pamięcią stanów).
- **most→ułożenie**, **polityka→ułożenie**: to samo kryterium dla ruchu mostu i ruchu polityki. `False` = po tym ruchu
  gra jest przegrana najpóźniej przy tej tacce.

Odpowiedź na pytanie z kryteriów: **tak, w każdej partii polityka na prawdziwej planszy miała ruch, po którym ostatnia
tacka dawała się ułożyć, i był to jej własny wybór** (kolumna „polityka→ułożenie” = `True` w pierwszym ruchu z duchem).
W żadnym wcześniejszym ruchu ogona (co najmniej 8 ruchów przed tym) most i polityka nie różnią się, a ruch mostu zachowuje
układ.

### p.2 (288 767, 1067 postawień, ostatni `kawalek_8`)

| n | tacka | ok | klasa | duchy zdjęte | pola board≠prawda | most | polityka na prawdzie | legalnych | z ułożeniem | most→ułożenie | polityka→ułożenie |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 6 | -3 | True | - | 0 | - | (0, 0, 3) | (0, 0, 3) | 9 | 1 | True | True |
| 7 | -3 | True | - | 0 | - | (2, 0, 1) | (2, 0, 1) | 3 | 1 | True | True |
| 8 | -3 | True | - | 0 | - | (1, 1, 1) | (1, 1, 1) | 1 | 1 | True | True |
| 9 | -2 | True | - | 0 | - | (0, 1, 3) | (0, 1, 3) | 13 | 5 | True | True |
| 10 | -2 | True | - | 0 | - | (2, 0, 6) | (2, 0, 6) | 8 | 4 | True | True |
| 11 | -2 | True | - | 0 | - | (1, 3, 5) | (1, 3, 5) | 5 | 1 | True | True |
| 12 | -1 | True | - | 0 | - | (0, 4, 2) | (0, 4, 2) | 18 | 2 | True | True |
| 13 | -1 | True | - | 0 | - | (2, 3, 2) | (2, 3, 2) | 7 | 1 | True | True |
| 14 | -1 | False | nadmiar_gdzie_indziej | 0 | - | (1, 3, 5) | (1, 3, 5) | 2 | 2 | True | True |
| 15 | 0 | False | brak_pol | 0 | 1: [(4, 4)] | (1, 3, 0) | (0, 4, 0) | 6 | 1 | False | True |
| 16 | 0 | True | - | 0 | - | (0, 2, 0) | (0, 2, 0) | 8 | 0 | False | False |

Ruch n=14 (kwadrat 3×3 w (3,5)) dał `observed` z nadmiarem w (4,4): poza liniami wyczyszczonymi, więc `drop_banner_ghosts`
go nie zdjął. Zrzut `015_state.png` ma na wysokości wierszy 3–4 baner „Perfect!”, a łata (4,4) to (238,113,76), czyli
różowo-pomarańczowy glif, który `is_block` czyta jako klocek. Na tej planszy most zagrał esowaty klocek (slot 1) w (3,0),
polityka na prawdziwej planszy zagrałaby kreskę 1×5 (slot 0) w (4,0): jedyny z 6 legalnych ruchów z układem. Po ruchu
mostu (ruch 16) żaden z 8 legalnych ruchów nie pozwala dołożyć obu pozostałych klocków: kolumny 2–3 są puste, ale tylko dwie
szerokie, więc 3×3 nie ma gdzie wejść. Wynik końcowy 289 145 z ekranu (licznik apki
288 767).

### p.3 (406 548, 766 postawień, ostatni `kawalek_6`)

| n | tacka | ok | klasa | duchy zdjęte | pola board≠prawda | most | polityka na prawdzie | legalnych | z ułożeniem | most→ułożenie | polityka→ułożenie |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | -3 | True | - | 0 | - | (1, 3, 1) | (1, 3, 1) | 26 | 25 | True | True |
| 6 | -3 | True | - | 0 | - | (0, 4, 3) | (0, 4, 3) | 14 | 11 | True | True |
| 7 | -3 | True | - | 0 | - | (2, 6, 1) | (2, 6, 1) | 3 | 3 | True | True |
| 8 | -2 | True | - | 0 | - | (2, 0, 4) | (2, 0, 4) | 22 | 14 | True | True |
| 9 | -2 | True | - | 0 | - | (0, 5, 4) | (0, 5, 4) | 11 | 6 | True | True |
| 10 | -2 | True | - | 0 | - | (1, 4, 4) | (1, 4, 4) | 2 | 2 | True | True |
| 11 | -1 | True | - | 0 | - | (1, 0, 0) | (1, 0, 0) | 11 | 2 | True | True |
| 12 | -1 | True | - | 0 | - | (2, 4, 2) | (2, 4, 2) | 7 | 1 | True | True |
| 13 | -1 | False | mieszane | 0 | - | (0, 2, 0) | (0, 2, 0) | 1 | 1 | True | True |
| 14 | 0 | False | mieszane | 0 | 4: [(3, 2), (4, 3), (4, 4), (4, 5)] | (1, 5, 1) | (2, 3, 4) | 2 | 1 | False | True |
| 15 | 0 | False | nadmiar_gdzie_indziej | 0 | - | (2, 3, 4) | (2, 3, 4) | 1 | 0 | False | False |

Ruch n=13 (3×3 w (2,0)) dał `observed` z trzema nadmiarowymi polami w wierszu 4 i brakującym (3,2): „Perfect!” zakrył
zielony klocek, a jego glify (190,76,48), (238,113,75), (250,140,111) wyglądają jak klocki. Różnica jest „mieszana”,
więc reguła #333 (tylko nadmiar w liniach wyczyszczonych) jej nie ruszyła. Na prawdziwej planszy polityka zagrałaby
klocek `11/10/10` (slot 2) w (3,4); z dwóch legalnych ruchów tylko ten układa tackę. Wiersz `n=15` ma `most→ułożenie` `False`
i `polityka→ułożenie` `False`: przy ruchu 15 było już po wszystkim, przegrana zapadła ruchem 14.

### p.8 (351 960, 784 postawienia, ostatni `kawalek_6`)

| n | tacka | ok | klasa | duchy zdjęte | pola board≠prawda | most | polityka na prawdzie | legalnych | z ułożeniem | most→ułożenie | polityka→ułożenie |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 23 | -3 | True | - | 0 | - | (2, 1, 1) | (2, 1, 1) | 41 | 41 | True | True |
| 24 | -3 | True | - | 0 | - | (0, 5, 3) | (0, 5, 3) | 19 | 15 | True | True |
| 25 | -3 | True | - | 0 | - | (1, 5, 0) | (1, 5, 0) | 3 | 3 | True | True |
| 26 | -2 | True | - | 0 | - | (1, 5, 0) | (1, 5, 0) | 29 | 20 | True | True |
| 27 | -2 | True | - | 0 | - | (2, 5, 1) | (2, 5, 1) | 13 | 5 | True | True |
| 28 | -2 | True | - | 0 | - | (0, 4, 6) | (0, 4, 6) | 5 | 3 | True | True |
| 29 | -1 | True | - | 0 | - | (0, 0, 5) | (0, 0, 5) | 18 | 2 | True | True |
| 30 | -1 | True | - | 0 | - | (2, 1, 0) | (2, 1, 0) | 7 | 1 | True | True |
| 31 | -1 | False | nadmiar_gdzie_indziej | 0 | - | (1, 0, 3) | (1, 0, 3) | 1 | 1 | True | True |
| 32 | 0 | False | brak_pol | 0 | 1: [(4, 5)] | (0, 1, 6) | (0, 5, 2) | 10 | 1 | False | True |
| 33 | 0 | False | nadmiar_gdzie_indziej | 0 | - | (1, 0, 0) | (1, 0, 0) | 5 | 0 | False | False |

Ruch n=31 dał `observed` z nadmiarem poza liniami wyczyszczonymi, `032_state.png` ma baner „Perfect!” nad wierszami 3–4,
łata (4,5) to (250,140,111). Z dziesięciu legalnych ruchów układ ma tylko wybór polityki, (0,5,2); most zagrał (0,1,6).
Ruch 33 nie ma już ratunku.

### p.10 (12 822, 195 postawień, ostatni `kawalek_2`)

| n | tacka | ok | klasa | duchy zdjęte | pola board≠prawda | most | polityka na prawdzie | legalnych | z ułożeniem | most→ułożenie | polityka→ułożenie |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 34 | -3 | True | - | 0 | - | (0, 5, 0) | (0, 5, 0) | 4 | 3 | True | True |
| 35 | -3 | True | - | 0 | - | (1, 1, 4) | (1, 1, 4) | 2 | 2 | True | True |
| 36 | -3 | True | - | 0 | - | (2, 1, 0) | (2, 1, 0) | 1 | 1 | True | True |
| 37 | -2 | True | - | 0 | - | (2, 3, 3) | (2, 3, 3) | 2 | 1 | True | True |
| 38 | -2 | True | - | 0 | - | (1, 6, 3) | (1, 6, 3) | 4 | 1 | True | True |
| 39 | -2 | True | - | 0 | - | (0, 6, 4) | (0, 6, 4) | 1 | 1 | True | True |
| 40 | -1 | True | - | 0 | - | (0, 3, 6) | (0, 3, 6) | 8 | 1 | True | True |
| 41 | -1 | True | - | 0 | - | (1, 4, 5) | (1, 4, 5) | 2 | 1 | True | True |
| 42 | -1 | True | - | 0 | - | (2, 1, 5) | (2, 1, 5) | 2 | 2 | True | True |
| 43 | 0 | False | nadmiar_gdzie_indziej | 0 | - | (1, 3, 3) | (1, 3, 3) | 7 | 2 | True | True |
| 44 | 0 | False | mieszane | 0 | 2: [(4, 2), (4, 3)] | (0, 1, 2) | (0, 3, 6) | 3 | 1 | False | True |

Ruch 44 trafił tam, gdzie chciał most (L w (1,2): `observed` ma (2,3) i (3,1)–(3,3)), więc to nie przeciągnięcie.
Po ruchu 43 `observed` miał nadmiar w (4,2) i (4,3); `(4,3)` leży w wyczyszczonej kolumnie 3, `(4,2)` nie, więc cała różnica
nie spełniła reguły #333. `044_state.png` ma baner „Combo 5 +27” nad wierszami 3–4, łaty to teal (60,160,148) i (64,173,160),
kolor klocków tej skórki. Polityka na planszy z duchami zobaczyła kolumnę 2 jako pełną po L i oczekiwała jej wyczyszczenia;
gra jej nie wyczyściła, bo (4,2) jest naprawdę puste (`observed` ruchu 44 ma ją niewyczyszczoną). Na prawdziwej planszy
polityka gra (0,3,6): z trzech legalnych ruchów tylko ten układa resztę tacki. Dalej: plansza z okna
`brak_ruchu_ponowny_odczyt` jest równa prawdziwej planszy po ruchu 44, a 2×3 **nie mieści się na niej** (0 legalnych ruchów).
Mieści się natomiast na `expected` mostu (kolumny 2–3, wiersze 5–7, ruch (2,2,5)), bo `expected` dziedziczy kolumnę 2 wyczyszczoną
przez ducha. Brak ruchu w oknie był więc prawdziwy, a rozjazd powstał dwa ruchy wcześniej.

## Ostatni `*_state.png` przed końcem

| partia | plik | opis |
|---|---|---|
| p.2 | `kawalek_8/016_state.png` | plansza z dwiema pustymi kolumnami 2–3 przez całą wysokość i klockami po bokach, tacka: pionowa kreska 1×5 i 3×3, bez nakładki; `017_state.png` to już ekran „Can you Top that?” 289 145 |
| p.3 | `kawalek_6/015_state.png` | zielona plansza z pustym wierszem 4 i dziurami w lewej połowie, tacka: pionowy prostokąt 3×2 i J-klocek, konfetti, bez baneru; `016_state.png` to „Can you Top that?” 407 069 |
| p.8 | `kawalek_6/033_state.png` | plansza z klockami po bokach i środkowymi kolumnami prawie pustymi, tacka: T-klocek i niebieski 3×3, bez nakładki; `034_state.png` to „Can you Top that?” 384 087 |
| p.10 | `kawalek_2/044_state.png` | plansza z banerem „Combo 5 +27” na wierszach 3–4, tacka: L-klocek i 2×3; `045_state.png` to fioletowy ekran końca z konfetti, bez wyniku |

## Rozkład tacek (`tools/rozklad_tacek.py`, testy `tests/test_rozklad_tacek.py`)

Udział klocków w tackach z pola `tray` pierwszego wiersza każdej tacki w `chunk*_moves.jsonl`. „3×3” to pełny kwadrat,
„2×3/3×2” pełny prostokąt, „1×5/5×1” kreska, „≥6 pól” to w puli dokładnie kwadrat i prostokąty (kreska i L 3×3 mają
5 pól). Tacki z nierozpoznanym kształtem są pominięte (s3: 9, s4: 1, s5: 3, s6: 4; to błędne odczyty tacki w środku partii,
np. kształt 5×7 przy `ok: false`, nie badałem ich).

| seria | tacek | klocków | 3×3 | 2×3/3×2 | 1×5/5×1 | ≥6 pól | tacki z ≥6 pól | pól na klocek |
|---|---|---|---|---|---|---|---|---|
| s3 | 5094 | 15282 | 0.6% | 3.9% | 0.5% | 4.4% | 10.4% | 4.10 |
| s4 | 8425 | 25275 | 0.5% | 3.9% | 0.5% | 4.4% | 10.5% | 4.09 |
| s5 | 4118 | 12354 | 0.7% | 4.0% | 0.6% | 4.7% | 10.9% | 4.09 |
| s6 | 1328 | 3984 | 1.7% | 5.9% | 1.4% | 7.6% | 17.7% | 4.15 |

Pierwsze 60 tacek każdej partii (partie z co najmniej 60 tackami):

| seria | tacek | klocków | 3×3 | 2×3/3×2 | 1×5/5×1 | ≥6 pól | tacki z ≥6 pól | pól na klocek |
|---|---|---|---|---|---|---|---|---|
| s3 (6 partii) | 359 | 1077 | 3.1% | 10.8% | 3.0% | 13.8% | 27.3% | 4.29 |
| s4 (9 partii) | 540 | 1620 | 4.5% | 13.1% | 4.8% | 17.6% | 35.0% | 4.41 |
| s5 (7 partii) | 417 | 1251 | 3.0% | 9.4% | 2.9% | 12.4% | 24.5% | 4.20 |
| s6 (6 partii) | 359 | 1077 | 3.2% | 10.9% | 2.9% | 14.1% | 29.5% | 4.26 |

Pierwsze 120 tacek każdej partii (partie z co najmniej 120 tackami):

| seria | tacek | klocków | 3×3 | 2×3/3×2 | 1×5/5×1 | ≥6 pól | tacki z ≥6 pól | pól na klocek |
|---|---|---|---|---|---|---|---|---|
| s3 (5 partii) | 595 | 1785 | 1.9% | 7.7% | 1.8% | 9.6% | 18.8% | 4.20 |
| s4 (9 partii) | 1079 | 3237 | 2.7% | 8.5% | 3.1% | 11.2% | 23.0% | 4.26 |
| s5 (7 partii) | 837 | 2511 | 1.9% | 6.7% | 1.8% | 8.6% | 17.2% | 4.14 |
| s6 (5 partii) | 598 | 1794 | 2.0% | 7.8% | 1.9% | 9.8% | 21.4% | 4.18 |

Pierwsze 250 tacek każdej partii (partie z co najmniej 250 tackami):

| seria | tacek | klocków | 3×3 | 2×3/3×2 | 1×5/5×1 | ≥6 pól | tacki z ≥6 pól | pól na klocek |
|---|---|---|---|---|---|---|---|---|
| s3 (5 partii) | 1244 | 3732 | 1.0% | 5.1% | 0.9% | 6.1% | 12.5% | 4.13 |
| s4 (8 partii) | 1999 | 5997 | 1.7% | 6.0% | 1.8% | 7.7% | 16.2% | 4.18 |
| s5 (6 partii) | 1498 | 4494 | 1.0% | 4.5% | 1.0% | 5.6% | 11.7% | 4.10 |
| s6 (4 partii) | 997 | 2991 | 1.3% | 5.8% | 1.2% | 7.1% | 16.6% | 4.13 |

**Sumarycznie s6 odstaje** (7,6% klocków z ≥6 polami wobec 4,4–4,7% w s3–s5; test z: z=9), ale to artefakt składu
partii: udział dużych klocków **maleje z postępem partii w każdej serii** (pierwsze 60 tacek: 12–18%, pierwsze 250:
6–8%), a s6 to prawie same krótkie partie (1328 tacek w 6 partiach wobec 4118–8425 w s3–s5). **Po tym samym odcinku
partii s6 nie odstaje** (np. pierwsze 120 tacek: 9,8% ≥6 pól wobec 8,6–11,2%; średnia liczby pól 4,18 wobec 4,14–4,26).
Wersja apki jest ta sama we wszystkich seriach (`version.txt`: 10.7.5). Na generator apki nie ma tu dowodu.

## Czy to wspólne i jak często (`tools/duchy_serii.py`, testy `tests/test_duchy_serii.py`)

Dla wpisu, którego poprzednik miał `ok: false` (a przed nim stał `ok: true`, więc plansza sprzed poprzednika była dobra),
prawdą jest `expected` poprzednika. „Inaczej” = polityka rekordu na prawdziwej planszy gra inaczej niż most;
„szkodliwe” = jej ruch pozwala ułożyć resztę tacki, ruch mostu nie.

| seria | ruchów | ok:false | w wierszach 3–4 | baza czysta | inaczej | szkodliwe | nieoceniane | szkodliwe /1000 ruchów |
|---|---|---|---|---|---|---|---|---|
| s3 | 15307 | 786 | 383 | 378 | 167 | 0 | 0 | 0.00 |
| s4 | 25297 | 967 | 465 | 475 | 203 | 4 | 0 | 0.16 |
| s5 | 12371 | 792 | 385 | 379 | 177 | 1 | 0 | 0.08 |
| s6 | 4009 | 191 | 108 | 101 | 49 | 4 | 0 | 1.00 |

- Decyzje zmienione przez błąd odczytu zdarzają się w każdej serii z podobną częstością: 8–14 na 1000 ruchów (s6: 12). Nie
  jest to więc nowy rodzaj błędu w s6, a `ok: false` w s6 (4,8%) nie jest częstszy niż w s5 (6,4%).
- **Każda szkodliwa decyzja kończy partię**, we wszystkich seriach: 9 szkodliwych decyzji, 9 końców partii w ostatnich
  0–4 ruchach logu. Rozkład: s4 cztery (wszystkie zapisane jako `przerwanie`), s5 jedna (p.7, #329), s6 cztery.
- Częstość szkodliwych na 1000 ruchów rośnie z 0,08–0,16 (s4, s5) do 1,00 (s6): przy tej samej polityce, tej samej liczbie
  zmienionych decyzji i **nie ciaśniejszych** planszach (s6: średnio 15,7 zajętych pól i 39,7 legalnych ruchów w pierwszych 120
  tackach wobec 16,9–17,8 i 35,5–37,0 w s3–s5). Naiwny test Poissona (oczekiwane 0,5 zdarzenia na 4009 ruchów, obserwowane 4)
  daje p ≈ 0,002. **Dlaczego s6 ma wyższe ryzyko, nieustalone**: pomiar wyklucza zmianę polityki, mostu poza #333,
  generatora (rozkład tacek) i ciasnoty planszy; nie wyklucza pecha ani różnicy w czasie życia baneru względem odczytu.
- Połowa `ok: false` ma różnicę wyłącznie w wierszach 3–4 (s3: 49%, s4: 48%, s5: 49%, s6: 57%), czyli tam, gdzie wiszą
  banery „Perfect!” i „Combo”; baner z s5 p.7 wisiał w wierszu 1, więc pas nie jest stały.

## Werdykt

| partia | przyczyna | wspólna z pozostałymi |
|---|---|---|
| p.2 | **most** (duch baneru poza liniami wyczyszczonymi) | tak |
| p.3 | **most** (duch baneru, mieszana różnica: nadmiar i zasłonięty klocek) | tak |
| p.8 | **most** (duch baneru poza liniami wyczyszczonymi) | tak |
| p.10 | **most** (duch baneru „Combo 5” w (4,2),(4,3)) | tak |

**Przyczyna wspólna: odczyt planszy czyta glify baneru („Perfect!”, „Combo N”) jako klocki, a #333 zdejmuje tylko nadmiar
leżący w liniach wyczyszczonych ruchem.** To ten sam mechanizm co s5 p.7 (#329), w innej postaci. Nie polityka (na
prawdziwej planszy gra dobrze we wszystkich czterech), nie generator apki (ostatnie tacki układalne, rozkład tacek po tym
samym postępie partii bez różnicy). Przeciągnięcie nie zawiodło (p.10: klocek wylądował tam, gdzie chciał most).

Nieustalone: dlaczego s6 ma około sześciokrotnie wyższe ryzyko takiej decyzji niż s4–s5 (patrz wyżej).

### Propozycje (nie wdrożone; to poprawka mostu, więc osobne zadanie z testem na tych czterech zrzutach)

1. **Nie decydować na ekranie, gdy różnica `observed` wobec `expected` nie jest ani echem, ani nadmiarem w liniach
   wyczyszczonych**, tylko odczytać planszę ponownie po zniknięciu baneru. We wszystkich czterech partiach odczyt w następnym
   wpisie (p.2: n=16, p.3: n=15, p.8: n=33, p.10: okno po ruchu 44) jest już zgodny z prawdą, czyli duch znika. Koszt:
   dodatkowe opóźnienie tylko we wpisach z `ok: false` (4–6% ruchów).
2. Alternatywnie rozszerzyć `drop_banner_ghosts` o różnice z łatami o kolorze spoza klocków skórki (glify
   „Perfect!” (238,113,76), (250,140,111) różnią się od klocków; teal „Combo” w p.10 jest bliski klockom, więc to nie wystarczy
   samo) i o brakujące pola zakryte przez glif (p.3, (3,2)); do sprawdzenia `tools/porownanie_odczytu.py` na ok. 3000 zrzutach
   z całego `docs/seria` (pułapka 28).
3. Test regresji na `s6/partia-{2,3,8,10}/kawalek_*/NNN_state.png` z polami z tabeli „duch w `board`”.

## Poza zadaniem (odkrycia)

- **W s4 były cztery prawdopodobne przegrane zapisane jako `przerwanie`**: p.1, p.4, p.6 i p.10 kończą się dokładnie po
  szkodliwej decyzji na duchu w ostatnich 0–4 ruchach logu (`tools/duchy_serii.py`), a `pomiar.json` ma
  `przyczyna: petla_bez_postepu`/`plansza_zawieszona`. Zrzut `s4/partia-4/kawalek_7/068_state.png` to koło nagród po grze, nie
  plansza. Założenie „w s4 nie było żadnej przegranej” jest więc najpewniej błędne (potwierdzenie na ekranie wykonałem tylko
  dla p.4); `tools/partia_serii.py` nie rozpoznaje tego okna jako końca gry.
- `tools/przegrana_serii.py` dla partii z `ok: false` w dwóch ostatnich tackach zawsze zwraca `rozjazd_mostu`, także gdy
  `ok: false` było echem; werdykt mówi „sprawdź”, nie „błąd odczytu”.

## Powtórzenie

```
git checkout origin/task/337 -- docs/seria/s6
python3 tools/przegrana_serii.py docs/seria/s6/partia-K          # K = 2, 3, 8, 10
python3 tools/przeglad_s6.py docs/seria/s6/partia-K --md          # tabele wyżej
python3 tools/rozklad_tacek.py                                   # rozkład tacek, s3–s6
python3 tools/duchy_serii.py                                     # częstość, s3–s6
python3 -m unittest tests.test_przeglad_s6 tests.test_rozklad_tacek tests.test_duchy_serii
```
