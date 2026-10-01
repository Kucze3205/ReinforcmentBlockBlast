# Różnice planszy most vs odczyt niezależny w seriach s1–s3 — diagnoza #315

Zaraportowano, nie naprawiano: `bridge.py` i `tools/porownanie_odczytu.py` bez zmian. Tabelę generuje
`python3 tools/plansza_roznice.py` (nowe narzędzie, tylko czyta zrzuty i logi); werdykty „kto ma rację” i kategorie
są rozstrzygnięte wzrokowo (niżej) i wpisane w słownikach tego narzędzia.

## Wniosek

- **100 klatek** z różnicą planszy (96 z #312 plus 4 z partii 4, 6, 8 serii s3 dodanych w cyklu 47: s3/4/2/100,
  s3/6/11/50, s3/6/8/100, s3/8/3/5). 92 mają wpis `move` w `chunkK_moves.jsonl`, 8 nie.
- **Większość to wina odczytu niezależnego, nie mostu** (81 klatek „most ma rację”): nakładki (napis Combo, pochwała,
  +N, błysk wybuchu, ikony kciuka, dłoń i duch samouczka) leżą na pustych polach, a odczyt niezależny liczy każdą
  łatę różną od „najczęstszego koloru” jako klocek. Do tego 10 klatek z odwróconym odczytem niezależnym: gdy
  zajętych jest ponad 32 pola, najczęstszy kolor łaty to klocek i `board_independent` zamienia plansze (64 różne pola).
- **Most odczytał planszę źle w 11 klatkach z ruchem** (tabela, kolumna „most źle i ruch”) i w 1 klatce bez ruchu
  (s1/5/4/48, niżej). Mierzone ciągłością (plansza z klatki n musi równać się `expected` z wpisu n-1) i zrzutem.
- **Żaden z tych 11 ruchów nie był nielegalny na prawdziwej planszy**: ruch nie pokrywa się z żadnym polem, które most
  pominął (narzędzie to liczy), a gra przyjęła każdy z nich (następny wpis ma ten slot pusty albo nową tackę;
  dla s1/7/1/15 itd. `accepted=True`). Błąd mostu groził więc nie nielegalnym ruchem, lecz **złą decyzją przy planszy
  z fantomami lub bez części klocków**, a w jednym przypadku fałszywym końcem partii.
- **Groziło przegraną raz, bez ruchu**: s1/5/4/48 (`end: brak legalnego ruchu wg odczytu`). Plansza z mostu ma fantom
  w polu (4,5) (poświata cyfry „3” z napisu Combo 38), a na prawdziwej planszy (oraz wg `expected` z n=47) istnieje
  legalne ułożenie S w (3,4). Most uznał partię za skończoną, choć gra trwała (`final.png`: licznik 169 560, tacka z S,
  animacja Combo). To jedyna klatka w materiale, w której błąd odczytu planszy zakończył przebieg.
- **Przyczyna wspólna po stronie mostu** (11 klatek + s1/5/4/48): `bridge.read_board` (`bridge.py:560`) klasyfikuje
  łatę 11×11 przez `is_block`, nie odróżniając nakładki od klocka, a `fast_stable_state` (`bridge.py:498`) przyjmuje
  stan po dwóch **identycznych** klatkach, więc nakładka trzymająca się przez dwie klatki (kciuki na świeżo położonym
  klocku, napis Combo, poświata) przechodzi jako stan stabilny. Kciuki zasłaniają prawdziwe klocki (most czyta je
  jako puste: 4 klatki, 22 pola), napis zasłania klocek (3 klatki, 4 pola), poświata, cyfry, serce i kciuki dają fantomy (6 klatek).

## Metoda i jej granice

1. `bridge.read_board` vs `porownanie_odczytu.board_independent` na każdym `NNN_state.png` w `docs/seria/s*/`
   (774 zrzuty, 100 z różnicą).
2. Kategoria i „kto ma rację”: wzrokowo, na arkuszach zrzutów z zaznaczonymi spornymi polami, dla **wszystkich** 100
   klatek (nie tylko przedstawicieli): napisy i błyski — pola puste (most ma rację); kciuki, duch i dłoń samouczka
   — pola puste (most) albo świeżo położony klocek (niezależny); ekran startowy, reklama i ekran końca — to nie plansza.
3. Ciągłość: plansza klatki n vs `expected` z n-1 (ta sama partia i kawałek; numeracja `n` zaczyna się od 0 w każdym
   kawałku). Różni się w 13 klatkach; w 2 z nich (s2/6/7/50, s2/8/10/100) zrzut pokazuje, że pomylił się `expected`
   (efekt wcześniejszego odczytu), most ma rację. Pozostałe 11 to tabela „most źle”.
4. Ruch przyjęty przez grę: `ok` z logu, a gdy `ok=false` — następny wpis ma o jeden klocek mniej w slocie ruchu
   albo nową tackę. Klatki z `ok=false` (15) mają `observed` zepsuty tą samą nakładką, więc `ok` sam nie dowodzi
   błędu odczytu w klatce n.
5. Czego nie wiemy: klatki, w których most i odczyt niezależny **zgadzają się**, a oba się mylą, nie wchodzą
   do tego zbioru; zrzuty są próbką (co 5–50 ruchów), nie każdym ruchem. s1/7/1/15 i s1/5/2/10 rozstrzygnięte
   słabiej (serce zasłania planszę; kciuki bez widocznego klocka pod spodem) — stąd „oba źle”.

## Klatki z błędem mostu i ruchem (11)

| klatka | pola, w których most się myli | skutek |
|---|---|---|
| s1/2/1/15 | 5 klocków pod kciukami czytane jako puste | ruch (3,0) legalny, przyjęty |
| s1/2/1/100 | 4 klocki pod kciukami (kolumna 7) | ruch (3,0) legalny, przyjęty |
| s1/6/1/45 | 9 klocków (3×3) pod kciukami | ruch (3,5) legalny, przyjęty |
| s1/9/1/15 | 4 klocki pod kciukami | ruch (0,4) legalny, przyjęty |
| s1/10/1/40 | 1 klocek pod napisem „6000”, 2 fantomy | ruch (2,0) legalny, przyjęty |
| s1/6/1/110 | 1 klocek pod napisem Combo | ruch (5,2) legalny, przyjęty |
| s1/8/1/15 | 2 klocki pod napisem Combo, 2 fantomy | ruch (1,3) legalny, przyjęty |
| s1/1/9/100 | 2 fantomy (poświata cyfry) | ruch (1,5) legalny, przyjęty |
| s1/5/2/120 | 2 fantomy (cyfry „12”) | ruch (2,2) legalny, przyjęty |
| s1/5/2/10 | 11 fantomów (serce) | ruch (4,5) legalny, przyjęty |
| s1/7/1/15 | 2 fantomy (kciuki) | ruch (0,0) legalny, przyjęty |

Grup jest kilka (kciuki 4, napis na klocku 3, poświata/serce/fantomy 4), przyczyna wspólna jedna (wyżej). Fantomy
są bezpieczne dla legalności ruchu (zawężają wybór), ale mogą zadecydować o końcu partii jak w s1/5/4/48.

## `tools/porownanie_odczytu.py --rozdanie N` dla przedstawicieli grup

Rozdanie liczy się na odczycie niezależnym (nakładki są w nim klockami), więc jest orientacyjne; polityka „przeżyła”
we wszystkich, bo nakładki zwykle tylko zawężają planszę:

| klatka (grupa) | wynik |
|---|---|
| s1/5/2/10 (serce, most źle) | tacka `[None, [[1]], None]`, `przezyla: True`, ruch slot 1 → (2,5) |
| s1/1/30/100 (napis) | tacka I4 + T, `przezyla: True`, ruchy slot 0 → (0,1), slot 1 → (4,3) |
| s1/1/28/50 (błysk) | tacka T, `przezyla: True`, slot 2 → (4,3) |
| s1/2/1/100 (kciuki, most źle) | tacka I3, `przezyla: True`, slot 2 → (7,5) |
| s1/2/1/0 (duch samouczka) | tacka O, `przezyla: True`, slot 1 → (6,5) |
| s1/5/1/15 (czyszczenie) | tacka I3 poziome, `przezyla: True`, slot 0 → (3,2) |
| s1/1/12/50 (odwrócony odczyt) | tacka L + S + 2×3, `ukladalna: True`, `przezyla: True`, trzy ruchy |
| s2/5/6/50 (napis, s2) | tacka T pionowe, `przezyla: True`, slot 1 → (4,3) |
| s3/8/3/5 (napis, s3) | tacka T + O1, `przezyla: True`, dwa ruchy |

## Tabela wszystkich 100 klatek

„kto ma rację” dotyczy pól spornych; „gra przyjęła ruch” — `ok` z logu albo następny wpis (tacka o jeden klocek
mniejsza w slocie ruchu albo nowa tacka).

| seria | partia | kawałek | n | różnych pól | kto ma rację | kategoria | ruch | ok (log) | gra przyjęła ruch | most źle i ruch |
|---|---|---|---|---|---|---|---|---|---|---|
| s1 | 1 | 12 | 50 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s1 | 1 | 23 | 100 | 3 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 27 | 50 | 3 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 28 | 50 | 1 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 1 | 30 | 50 | 3 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 30 | 100 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 1 | 32 | 100 | 1 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 1 | 38 | 50 | 2 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 38 | 100 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s1 | 1 | 40 | 100 | 2 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 41 | 50 | 1 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 1 | 42 | 100 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s1 | 1 | 44 | 50 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 1 | 47 | 50 | 2 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 1 | 48 | 50 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 1 | 49 | 50 | 2 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 50 | 50 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 1 | 50 | 100 | 2 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 53 | 50 | 2 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 1 | 9 | 100 | 5 | most w polach spornych; oba źle w 2 polach | napis (Combo / pochwała / +N) nad polami | tak | False | tak | **tak** |
| s1 | 10 | 1 | 0 | 5 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s1 | 10 | 1 | 25 | 1 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 10 | 1 | 40 | 7 | niezależny (+ oba w 2 polach) | napis (Combo / pochwała / +N) nad polami | tak | False | tak | **tak** |
| s1 | 10 | 1 | 48 | 15 | oba (to nie plansza) | ekran końca partii, nie plansza | nie | - | - | nie |
| s1 | 2 | 1 | 0 | 7 | most | dłoń / duch podpowiedzi samouczka | tak | False | tak | nie |
| s1 | 2 | 1 | 15 | 5 | niezależny | ikony kciuka na polach | tak | False | tak | **tak** |
| s1 | 2 | 1 | 60 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | False | tak | nie |
| s1 | 2 | 1 | 100 | 4 | niezależny | ikony kciuka na polach | tak | False | tak | **tak** |
| s1 | 2 | 2 | 10 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 2 | 2 | 25 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 2 | 2 | 45 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 3 | 10 | 100 | 9 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 3 | 11 | 100 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 3 | 12 | 100 | 1 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 3 | 13 | 100 | 2 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 3 | 15 | 100 | 1 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 3 | 19 | 100 | 5 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 3 | 23 | 100 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 3 | 27 | 100 | 3 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 3 | 3 | 100 | 2 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 3 | 31 | 100 | 7 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 3 | 42 | 100 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 3 | 45 | 50 | 2 | most | błysk wybuchu / iskry w komórce | tak | True | tak | nie |
| s1 | 3 | 54 | 50 | 2 | most | napis + błysk wybuchu w komórce | tak | True | tak | nie |
| s1 | 3 | 7 | 100 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 4 | 1 | 0 | 6 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s1 | 4 | 1 | 10 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 1 | 0 | 2 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s1 | 5 | 1 | 15 | 7 | most | animacja czyszczenia wiersza | tak | False | tak | nie |
| s1 | 5 | 1 | 20 | 1 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 1 | 25 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 1 | 35 | 3 | most | ikony kciuka na polach | tak | True | tak | nie |
| s1 | 5 | 1 | 85 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 2 | 10 | 5 | oba źle | serce (efekt pełnoekranowy) | tak | False | tak | **tak** |
| s1 | 5 | 2 | 30 | 4 | most | ikony kciuka na polach | tak | True | tak | nie |
| s1 | 5 | 2 | 100 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s1 | 5 | 2 | 120 | 5 | most w polach spornych; oba źle w 2 polach | napis (Combo / pochwała / +N) nad polami | tak | False | tak | **tak** |
| s1 | 5 | 3 | 95 | 7 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 3 | 140 | 1 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 4 | 5 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 4 | 25 | 6 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 5 | 4 | 47 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | False | tak | nie |
| s1 | 5 | 4 | 48 | 3 | niezależny (duch w polu (4,5)) | napis (Combo / pochwała / +N) nad polami | nie | - | - | nie |
| s1 | 6 | 1 | 0 | 6 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s1 | 6 | 1 | 40 | 7 | most | ikony kciuka na polach | tak | True | tak | nie |
| s1 | 6 | 1 | 45 | 9 | niezależny | ikony kciuka na polach | tak | False | tak | **tak** |
| s1 | 6 | 1 | 110 | 4 | niezależny | napis (Combo / pochwała / +N) nad polami | tak | False | tak | **tak** |
| s1 | 6 | 1 | 147 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s1 | 7 | 1 | 0 | 6 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s1 | 7 | 1 | 15 | 1 | oba źle | ikony kciuka na polach | tak | False | tak | **tak** |
| s1 | 7 | 1 | 125 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s1 | 8 | 1 | 0 | 6 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s1 | 8 | 1 | 15 | 5 | niezależny (+ oba w 2 polach) | napis (Combo / pochwała / +N) nad polami | tak | False | tak | **tak** |
| s1 | 8 | 2 | 45 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s1 | 9 | 1 | 0 | 6 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s1 | 9 | 1 | 15 | 4 | niezależny | ikony kciuka na polach | tak | False | tak | **tak** |
| s2 | 1 | 2 | 58 | 57 | oba (to nie plansza) | ekran startowy, nie plansza | nie | - | - | nie |
| s2 | 10 | 2 | 60 | 57 | oba (to nie plansza) | ekran startowy, nie plansza | nie | - | - | nie |
| s2 | 2 | 1 | 100 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 2 | 2 | 79 | 3 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 2 | 4 | 61 | 31 | oba (to nie plansza) | reklama wideo, nie plansza | nie | - | - | nie |
| s2 | 3 | 3 | 92 | 56 | oba (to nie plansza) | ekran startowy, nie plansza | nie | - | - | nie |
| s2 | 4 | 2 | 46 | 56 | oba (to nie plansza) | ekran startowy, nie plansza | nie | - | - | nie |
| s2 | 5 | 4 | 100 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 5 | 5 | 100 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 5 | 6 | 50 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 5 | 7 | 50 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s2 | 6 | 6 | 50 | 6 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 6 | 7 | 50 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s2 | 6 | 7 | 100 | 5 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 6 | 8 | 100 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 8 | 10 | 100 | 3 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 8 | 13 | 100 | 3 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 8 | 17 | 50 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s2 | 9 | 2 | 63 | 57 | oba (to nie plansza) | ekran startowy, nie plansza | nie | - | - | nie |
| s3 | 4 | 2 | 100 | 4 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s3 | 6 | 11 | 50 | 2 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
| s3 | 6 | 8 | 100 | 64 | most | odczyt niezależny odwrócony (ponad 32 pola zajęte) | tak | True | tak | nie |
| s3 | 7 | 1 | 0 | 6 | most | dłoń / duch podpowiedzi samouczka | tak | True | tak | nie |
| s3 | 8 | 3 | 5 | 3 | most | napis (Combo / pochwała / +N) nad polami | tak | True | tak | nie |
