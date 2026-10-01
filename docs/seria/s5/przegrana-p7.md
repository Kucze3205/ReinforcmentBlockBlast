# Przegrana s5 p.7 (313 809) — diagnoza (#329)

Zaraportowano, nie naprawiono. Materiał: `docs/seria/s5/partia-7/` (z `origin/task/326`), werdykt narzędzia:
`przegrana-p7.json`, liczby: `przeglad-p7.json` (`tools/przeglad_p7.py`, powtarzalne).

## Werdykt: `rozjazd_mostu` — odczyt planszy czyta baner „Combo” jako klocki

Ani `tacka_nieukladalna`, ani `slepa_plamka`. Tacka z n = 38 była układalna w całości, a polityka rekordu **układa ją
w całości na prawdziwej planszy** — przegrała, bo most podał jej planszę z dwoma nieistniejącymi klockami.

- Po ruchu 38 (kreska w (5,1)) wiersz 1 jest pełny i znika. Zrzut `kawalek_9/039_state.png` (stan przed ruchem 39) ma
  nad nim baner „Combo 145”. Łaty komórek (1,6) i (1,7) mają tam kolory żółto-zielonych glifów (153,175,63) i
  (161,198,25), a `bridge.is_block` uznaje je za klocki (komórka (1,5) z (152,130,62) przechodzi jako pusta).
- To **nie** animacja czyszczenia i **nie** „n = 39 zgadza się z `expected` z n = 38”: `board` z n = 39 różni się od
  `expected` z n = 38 dokładnie w (1,6),(1,7), `ok` jest `false` zarówno przy n = 38, jak i n = 39. Po ruchu 39
  odczyt (`observed`) nie ma już tych pól, a wiersz okna po ostatnim ruchu (`brak_ruchu_ponowny_odczyt`) ma wiersz 1
  pusty. `przed_koncem` w logu dziedziczy duchy z łańcucha `expected`.
- Na planszy z duchami polityka rekordu gra (slot 1 = przekątna, (5,6)) — dokładnie jak most. Na planszy bez nich
  gra przekątną w **(6,1)** i S ma wtedy 9 legalnych miejsc; po (5,6) nie ma żadnego. Pełne ułożenie tej tacki
  przez politykę w symulatorze: kreska (5,1) → przekątna (6,1) → S (0,0).

## Liczby z kryteriów

- **`tools/porownanie_odczytu.py`, kawałek 9, n = 30–40:** odczyt tacki zgodny z obrazem we wszystkich stanach
  (`sloty_tacki_rozne: []`). Plansza: 0–2 różnic na n = 30–35 i 37, a na n = 36, 38, 39, 40 po 56–64 pól — to
  artefakt narzędzia, nie mostu: niezależny odczyt (najczęstszy kolor pustej komórki) gubi się na zrzutach z banerem
  i ekranem końca. Dla (1,6),(1,7) przy n = 39 dowodem są łaty koloru wyżej, nie to porównanie.
- **n = 38, przegląd wyczerpujący:** tak, układalna. 9 ułożeń, wszystkie zaczynają się od wybranego ruchu
  (slot 0, (5,1)); przykład: kreska (5,1), przekątna (6,1), S (0,0).
- **Przegląd wsteczny n = 35–37:** po każdym z 7 / 2 / 2 możliwych ułożeń reszty tacki (n = 35 / 36 / 37) tacka z
  n = 38 była układalna; ruch wybrany był też najwyżej ocenionym (ocena polityki 2345,4 / 1944,4 / 743,4).
  Nie było zatem ruchu, którego brakowało — wsteczne szukanie niczego nie zmienia.
- **Częstość w symulatorze** (1200 losowań ze ślepego `Generator`, po 300 na planszę z n = 35, 36, 37, 38): 23,6%
  tacek nieukładalnych (72 / 109 / 19 / 83); polityka z `complete=1` po pierwszym ruchu nie ułożyła tych samych 283,
  czyli żadnej układalnej. Dla planszy z n = 38: 27,7%. Tacka apki na tej planszy była układalna (generator apki
  nie faworyzuje tu nieukładalnych; jedna tacka to jednak za mało na rozstrzygnięcie, o to pytał #249).

## Co by zapobiegło

`read_board` nie może czytać baneru „Combo N” jako klocków (albo odczyt przed ruchem musi poczekać, aż baner zniknie);
`ok = false` przy dwóch kolejnych ruchach z tą samą różnicą pól to ten sam sygnał.
