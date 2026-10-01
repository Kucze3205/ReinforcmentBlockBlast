# Tempo licznika apki na materiale s1/s2

Bilet: [#309](../../issues/309). **Zaraportowano, nie naprawiano** — bez zmian w polityce, moście, punktacji i `bench/`.
Narzędzie: `python3 tools/tempo_licznika.py docs/seria/s2/partia-8 [...]`, test: `tests/test_tempo_licznika.py`.

## Metoda

- Postawienie = unikalna para (kawałek, `n`); ponowione próby nie liczą się podwójnie (zgodnie z `postawienia` w `pomiar.json`).
- Licznik = pole `score` (HUD). Odczyt jest odrzucany, gdy cofa się względem ostatniego przyjętego albo rośnie o więcej niż
  100 tys. naraz (największy zmierzony przyrost sąsiednich wierszy: ~17 tys.). Odrzucone liczone osobno.
- Minuty = od pierwszego do ostatniego wiersza (`t`), bez startu apki; stąd ułamkowe różnice względem `pomiar.json`.
- „Po kawałkach” = licznik na końcu kolejnych kawałków po 150 postawień.

## Tabela

**s1 nie ma żadnego odczytu licznika** — w `chunk*_moves.jsonl` s1 pole `score` to wszędzie `null` (HUD nie był jeszcze czytany),
więc dla s1 są tylko postawienia i minuty, bez kolumny „1 mln”.

| partia | zakończenie | postawienia | minuty | licznik na końcu | postawień/min | 1 mln: postawienie, minuta | odrzucone | licznik po kawałkach (150) |
|---|---|---|---|---|---|---|---|---|
| s1/1 | przerwanie | 7950 | 303.3 | brak odczytów | 26.2 | brak danych | 0 | |
| s1/2 | przerwanie | 207 | 10.3 | brak odczytów | 20.1 | brak danych | 0 | |
| s1/3 | przerwanie | 8250 | 304.6 | brak odczytów | 27.1 | brak danych | 0 | |
| s1/4 | przerwanie | 37 | 2.2 | brak odczytów | 16.8 | brak danych | 0 | |
| s1/5 | przerwanie | 499 | 24.2 | brak odczytów | 20.6 | brak danych | 0 | |
| s1/6 | przerwanie | 149 | 8.0 | brak odczytów | 18.7 | brak danych | 0 | |
| s1/7 | przerwanie | 220 | 12.3 | brak odczytów | 17.9 | brak danych | 0 | |
| s1/8 | przerwanie | 222 | 12.2 | brak odczytów | 18.2 | brak danych | 0 | |
| s1/9 | przerwanie | 45 | 3.4 | brak odczytów | 13.2 | brak danych | 0 | |
| s1/10 | przerwanie | 49 | 2.0 | brak odczytów | 24.9 | brak danych | 0 | |
| s2/1 | przegrana | 209 | 11.7 | 59 932 | 17.8 | nie przekroczył | 0 | 38k 60k |
| s2/2 | przerwanie | 512 | 26.5 | 146 484 | 19.3 | nie przekroczył | 0 | 16k 62k 138k 146k |
| s2/3 | przegrana | 393 | 20.0 | 55 567 | 19.7 | nie przekroczył | 0 | 20k 35k 56k |
| s2/4 | przegrana | 197 | 12.7 | 32 690 | 15.5 | nie przekroczył | 0 | 21k 33k |
| s2/5 | cel | 1050 | 49.5 | 1 258 214 | 21.2 | 877, min 41.1 | 0 | 45k 68k 147k 336k 652k 1077k 1258k |
| s2/6 | cel | 1200 | 58.1 | 1 201 276 | 20.7 | 971, min 47.8 | 1 | 32k 96k 264k 555k 924k 957k 1092k 1201k |
| s2/7 | cel | 1350 | 64.4 | 1 222 688 | 21.0 | 1259, min 60.3 | 0 | 31k 81k 146k 334k 473k 519k 640k 880k 1223k |
| s2/8 | przerwanie (żywa) | 3300 | 152.8 | 694 797 | 21.6 | nie przekroczył | 0 | 24k 37k 51k 97k 176k 194k 230k 259k 317k 339k 361k 383k 414k 436k 457k 487k 519k 539k 558k 612k 664k 695k |
| s2/9 | przegrana | 214 | 12.9 | 31 319 | 16.6 | nie przekroczył | 1 | 21k 31k |
| s2/10 | przegrana | 211 | 12.6 | 89 137 | 16.8 | nie przekroczył | 0 | 42k 89k |

(s2/8: `pomiar.json` podaje 695 100 — ostatni odczyt ze zrzutu; tabela bierze ostatni odczyt z `jsonl`.)

## Odpowiedź

**Tempo gry:** ok. 21 postawień/min na długich partiach s2 (s1 miało 26–27), więc 337 min (340 − ~3 min startu apki)
to ok. 7000 postawień.

**Ile partii, które nie przegrały, dojdzie do 1 mln w 340 min.** Nieprzegrane s2 z odczytem licznika: 2, 5, 6, 7, 8.
- 5, 6, 7: **już doszły** (po 41, 48 i 60 min), 3 z 3.
- 8: nie doszła w 153 min (695 tys.), ale zostaje w trybie liniowym: ostatnie 12 kawałków dały średnio 29,6 tys./150
  postawień (cała partia: ~210/postawienie). Do 1 mln brakuje ok. 305 tys. → ok. 1550 postawień więcej, czyli 1 mln
  przy ok. 4850. postawieniu, **ok. 225 min (+3 min startu ≈ 228 min < 340)**. To ekstrapolacja liniowa, nie pomiar.
- 2: przerwana po 26 min przy 146 tys. (512 postawień, ~290/postawienie) — za krótka, by cokolwiek wnioskować.
- s1: bez odczytu licznika — nie da się ocenić; nie zgadujemy.

Wniosek: **w policzonym materiale limit 340 min nie odcina żadnej żywej partii przed 1 mln, nawet w trybie liniowym
partii 8** (zapas ok. 110 min). Ryzykiem zostaje przegrana (s2: 4 z 10 partii; to osobny temat), nie czas. Próbka to
4 żywe partie z długim materiałem, więc to nie jest rozkład, tylko brak kontrprzykładu.

**Czy są dwa tryby.** Średni przyrost na postawienie: partie 5–7 ~1000 (1,2 mln w 1050–1350), partia 8 ~210. Ale
nie ma czystego podziału na dwa tryby: przyrost na kawałek jest silnie zmienny w obrębie jednej partii (partia 6:
368 tys. w kawałku 5, potem 33 tys. w kawałku 6; partia 7: 46 tys. → 121 → 240 → 343 tys.; partia 8 też ma
kawałki 78 tys. i 57 tys. wśród ~20–30 tys.). Wygląda to raczej na skokowe okresy szybkiego wzrostu niż na stały
tryb partii; w partii 8 takich okresów było mało.

**Od czego zależy:** materiał **tego nie pokazuje**. Udział ruchów czyszczących (0,41–0,49), średnia długość serii
czyszczeń z rzędu (1,3–1,6) i najdłuższa seria (2–6, liczone z `board`/`observed`) są w kawałkach szybkich i wolnych
takie same, a średnie zapełnienie planszy też (≈15–24 komórek). Czyli to nie długość łańcuchów czyszczeń z rzędu.
Pomiar nie sprawdzał innych zmiennych (np. mnożnika serii w apce niewidocznego w `jsonl`).
