# Końce partii: cztery przerwania s4 i pozostałe przerwania s3–s6 (#344)

Pomiar, bez zmian w `bridge.py` ani `tools/partia_serii.py`. Zrzuty obejrzane wzrokowo; detektory z `main` uruchomione na zrzutach
(`bridge.is_*_screen`, skrypt jednorazowy, nie w repo). Pozycje ruchów: `tools/duchy_serii.py`.

## Wynik

**Wszystkie cztery partie s4 (p.1, p.4, p.6, p.10) to przegrane zapisane jako `przerwanie`.** Po ostatnim ruchu most dostał ciąg okien, który
w s6 poprzedza ekran końca u czterech zapisanych przegranych (s6 p.2, 3, 8, 10): `brak_ruchu_ponowny_odczyt` → `tacka_pusta_przejsciowo`
→ `reklama_wideo` → koło fortuny → `koniec_partii`. W s4 most nie znał koła (#317 powstało później), więc ciąg urwał się na kole.

Powód utknięcia: koło fortuny (ciemnoszare tło, „Go”, ✕ w rogu) mieści się w progu Ustawień, więc `is_settings_screen` → `press_back()`, a „wstecz”
kółka nie zamyka. 12 wpisów `ustawienia_wstecz` (`PROGRESS_SAFEGUARD_TRIES`), twardy restart, znów 12 → `petla_bez_postepu` → przerwanie.

| partia | werdykt | zrzut (obejrzany) | ostatnie okno w logu | `pomiar.json` | detektory `main` na tym zrzucie |
|---|---|---|---|---|---|
| s4/1 | **przegrana** (licznik 1 284 382 w ostatnim ruchu) | `partia-1/kawalek_22/057_state.png` (koło); `056_state.png`: plansza z jednym klockiem w tacce, który nie mieści się po ruchu n=56 (`ok: true`, przegląd wyczerpujący: nieukładalny) | n=57: `brak_ruchu_ponowny_odczyt`, `tacka_pusta_przejsciowo`, `reklama_wideo`, `reklama_wideo`, 8× `ustawienia_wstecz` | przerwanie / `petla_bez_postepu`, okno `ustawienia_wstecz` | `is_interactive_ad_screen` + `is_settings_screen`; pętla sprawdza interaktywną **przed** Ustawieniami → `reklama_interaktywna`, stuknięcie „>>/✕” (285,35) |
| s4/4 | **przegrana** (pewność niższa: pośrednio) | `partia-4/kawalek_7/068_state.png` (koło); `067_state.png`: reklama wideo bez wiersza `brak_ruchu_ponowny_odczyt`; `066_state.png`: plansza 436 318, dwa klocki w tacce | n=68: `reklama_wideo`, `reklama_wideo`, 10× `ustawienia_wstecz` | przerwanie / `petla_bez_postepu`, okno `ustawienia_wstecz` | jak wyżej: `reklama_interaktywna` |
| s4/6 | **przegrana** | `partia-6/kawalek_4/090_state.png` (koło); `089_state.png`: plansza 236 430 z animacją „+10” | n=90: `brak_ruchu_ponowny_odczyt`, `tacka_pusta_przejsciowo`, `reklama_wideo`, `reklama_wideo`, 8× `ustawienia_wstecz` | przerwanie / `petla_bez_postepu`, okno `ustawienia_wstecz` | jak wyżej |
| s4/10 | **przegrana** | `partia-10/kawalek_16/030_state.png`, `031_stuck.png`, `final.png`: reklama „Congrats! You’re seeing a test ad”, `029_state.png`: czarna reklama (`is_ad_screen`) | n=29: `brak_ruchu_ponowny_odczyt` (plansza 43 pola, tacka z pionową piątką), `tacka_pusta_przejsciowo`; potem ruchy n=29–31 na „pustej planszy” (odczyt reklamy, przeciągnięcia w reklamę), `plansza_zawieszona` | przerwanie / `plansza_zawieszona` | 029: `is_ad_screen` (czarna reklama, jak wtedy); 030, 031, `031_stuck`, `final`: **żaden** detektor → odczyt jako plansza pusta → `plansza_zawieszona`, jak w logu |

Uwagi do tabeli:

- „Przegrana” opieram na ciągu okien zakończonym kołem. Ciąg `brak_ruchu_ponowny_odczyt` → `tacka_pusta_przejsciowo` → reklama to ten sam, który
  s6 p.2/3/8/10 kończy `koniec_partii` z ekranem „Can you Top that?” (np. `s6/partia-2/kawalek_8/017_end.png`). W p.4 brak wiersza
  `brak_ruchu_ponowny_odczyt` (ostatni zrzut przed reklamą to plansza z ruchem, `ok: false`); stąd niższa pewność. Nie sprawdzałem, czy w partiach, które trwały, reklama
  bywa wyświetlana zaraz po ruchu; to jedyna luka w werdykcie p.4.
- Przy `ok: false` w ostatnim ruchu (p.4, p.6) `expected` jest niepewne (duchy baneru), więc nie rozstrzygam „ułożyłoby się” z logu.
- Wszystkie cztery miały szkodliwą decyzję na duchu 0–4 ruchów przed końcem logu (`python3 tools/duchy_serii.py`): p.1 n=55 (1), p.4 n=66 (1), p.6 n=89 (0), p.10 n=27 (4).
- s4/1: licznik przekroczył 1 mln w kawałku 18 (patrz `docs/seria/licznik-ponownie.md`), a partia i tak skończyła się przegraną: cel osiągnięty, więc rozjazd
  `przerwanie`/`cel` tam zostaje; na końcu to jednak przegrana po osiągnięciu celu.
- Okno, które widział most po końcu gry, to w p.1/4/6 koło fortuny (`okno: ustawienia_wstecz`), w p.10 reklama bez przycisku zamknięcia rozpoznanego przez
  detektory (`plansza_zawieszona`). Most z `main` rozpoznałby koło jako `reklama_interaktywna`, stuknąłby (285,35) i, jak w s6 p.2/3/8/10, doszedł do
  `koniec_partii`; **tego nie sprawdzam na emulatorze** (czy ✕ w rogu (288,32) zamyka koło z s4, rozstrzygnie verifier). Reklama z p.10 pozostaje bez detektora.

## Pozostałe przerwania s3–s6 (czy ten sam wzór)

Kryteria wzoru: (a) szkodliwa decyzja wg `tools/duchy_serii.py` w ostatnich ruchach, (b) ekran po grze (koło, reklama po `tacka_pusta_przejsciowo`) w ostatnim kawałku.
`duchy_serii` wskazuje szkodliwe decyzje tylko w s4 p.1/4/6/10 spośród przerwań (poza nimi: s5 p.7, s6 p.2/3/8/10, wszystkie `przegrana`).

| partia | klasyfikacja | werdykt | podstawa |
|---|---|---|---|
| s3/1 | przerwanie / `petla_bez_postepu` (`ekran_startowy`) | przerwanie (gra trwa) | `kawalek_1/135_state.png`: plansza 18 893 z dwoma klockami do ułożenia; most wziął ją za ekran startowy (12× `ekran_startowy`); bez szkodliwej decyzji |
| s3/2 | przerwanie / `petla_bez_postepu` (`ekran_startowy`) | przerwanie | `kawalek_1/091_state.png`: plansza 13 218, dwa ułożone klocki; ten sam ciąg `ekran_startowy` |
| s3/3 | przerwanie / `petla_bez_postepu` (`ustawienia_wstecz`) | **przegrana** (ten sam wzór co s4) | `kawalek_18/035_state.png`: koło fortuny (to ono dało #317); po ostatnim ruchu `tacka_pusta_przejsciowo`, `reklama_wideo`, 9× `ustawienia_wstecz`. Bez szkodliwej decyzji wg `duchy_serii` (ruch n=34 miał `ok: false`, baza nieczysta, nie oceniono) |
| s3/7 | przerwanie / `plansza_zawieszona` | przerwanie | `kawalek_1/008_state.png`: żywa plansza 162 z klockiem w tacce; baner InMobi u dołu, brak okna po grze |
| s3/8 | przerwanie / `petla_bez_postepu` (`ekran_startowy`) | przerwanie | `kawalek_3/009_state.png`: plansza 215 156 z klockiem w tacce |
| s3/10 | przerwanie / `petla_bez_postepu` (`ekran_startowy`) | przerwanie | `kawalek_1/028_state.png`: plansza 1 972 z trzema klockami w tacce |
| s4/8 | przerwanie / `limit_minut` | przerwanie (partia trwała; cel, patrz `licznik-ponownie.md`) | `kawalek_57/final.png`: plansza 3 172 913 z klockiem w tacce |
| s5/2 | przerwanie / `petla_bez_postepu` (`nakladka_better_than`) | przerwanie | `kawalek_4/071_state.png`: żywa plansza 48 988, klocek mieści się; tail 11+12× `nakladka_better_than` (zła klasyfikacja planszy jako nakładki) |
| s5/8 | przerwanie / `petla_bez_postepu` (`nakladka_better_than`) | przerwanie | `kawalek_1/110_state.png`: plansza 14 244 z trzema klockami |
| s6/1 | przerwanie / `petla_bez_postepu` (`nakladka_better_than`) | przerwanie | `kawalek_6/041_state.png`: plansza 816 474 z dwoma klockami; `is_trophy_overlay_screen` na `main` rozpoznaje ten zrzut jako nakładkę pucharu |
| s6/5 | przerwanie / `petla_bez_postepu` (`tacka_pusta_przejsciowo`) | przerwanie | `kawalek_3/106_state.png`: plansza 61 352, tacka z jednym klockiem (2×3) |

Wniosek: poza czterema partiami s4 wzór (ekran po grze w ostatnim kawałku) ma jeszcze **s3/3**; reszta to przerwania na żywej planszy
(błędna klasyfikacja ekranu: `ekran_startowy`, `nakladka_better_than`, `tacka_pusta_przejsciowo`, albo limit czasu). Zatem przegranych zapisanych jako przerwanie jest
**5** (s3/3, s4/1, s4/4, s4/6, s4/10). Dla s3/3 i s4/4 werdykt jest pośredni (patrz uwagi wyżej).

## Propozycja zmiany klasyfikacji końca partii (opis, nie kod)

Werdykt „przegrana” padł, więc:

1. **Okno po grze nie powinno być końcem „przerwanie”.** W `tools/partia_serii.py` (`classify_end`) końce `petla_bez_postepu` i `plansza_zawieszona`, po których w ostatnich
   wpisach logu stoi `brak_ruchu_ponowny_odczyt` albo `tacka_pusta_przejsciowo`, a po nich okno reklamowe (`reklama_wideo`, koło), klasyfikować jako
   `przegrana` z `przyczyna: koniec_po_oknach` (albo osobną wartością), a nie `przerwanie`. Przerwanie nie liczy się do serii, a przegrana tak.
2. **Reguła minimalna, bez ekranu:** ostatni wiersz z ruchem + ciąg okien zaczynający się od `brak_ruchu_ponowny_odczyt`/`tacka_pusta_przejsciowo` i zawierający
   reklamę → „przegrana (wnioskowana)”. W s4 p.4 brak wiersza `brak_ruchu_ponowny_odczyt`; tam ciągiem jest sama reklama zaraz po ruchu, więc reguła musi
   dopuszczać `reklama_*` bezpośrednio po ruchu.
3. **Most (`bridge.py`):** (a) koło fortuny z `main` (#317) już zamyka się ✕/„>>”; sprawdzić na emulatorze, że ✕ (288,32) trafia w zasięg stuknięcia (285,35);
   (b) dla reklamy z p.10 („Congrats! You’re seeing a test ad”, odliczanie, bez ✕ w detektorach) potrzebny detektor albo zasada: dowolny ekran bez planszy po
   `tacka_pusta_przejsciowo` to okno po grze, nie plansza pusta (zapobiega przeciągnięciom w reklamę, n=29–31 w p.10).
4. **Seria:** przeliczyć wsteczne serie s3–s4 z przegranymi (5 partii) — w s4 mogły to być jedyne przegrane, więc założenie „w s4 nie było przegranych” jest fałszywe.
5. Zatrzymanie przy `petla_bez_postepu` na ekranie koła powinno być twardym restartem + ponownym sprawdzeniem końca gry, nie `przerwanie`.

## Powtórzenie

```
git checkout origin/task/340 -- docs/seria/s6      # tylko do odczytu (niecommitowane)
python3 tools/duchy_serii.py
python3 tools/licznik_ponownie.py --tabela docs/seria/s6/partia-4 docs/seria/s6/partia-6 docs/seria/s6/partia-7 docs/seria/s6/partia-9
```

## Wdrożone w #347
Propozycje 1–2 weszły do `tools/partia_serii.py` (`koniec_po_oknach`, `przyczyna: koniec_po_oknach`, kod 1); opis i test na logach: `docs/seria-skrypt.md`. Wyjątek: sama
`tacka_pusta_przejsciowo` nie wystarcza (s6/5), potrzebna `reklama_*` albo `brak_ruchu_ponowny_odczyt`. Propozycje 3–5 (most, przeliczenie serii) bez zmian.
