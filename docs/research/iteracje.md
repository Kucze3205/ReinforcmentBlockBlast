# Iteracje pętli: co robił każdy cykl, ile trwał, ile dał

Odpowiedź na #367 (mapa #361). Dane maszynowe: [`iteracje.json`](iteracje.json) (60 wpisów; cykle 11-13 bez dziennika).
Przegląd półautomatyczny: czasy, commity, issues i zmiany rekordu ze skryptu (git, `gh`, historia `bench/record.json`); cel i werdykt ręcznie z dzienników `docs/journal/cykl-*.md`.

## Definicje

- **Okno cyklu N** = od commita dziennika N do commita dziennika N+1. Dziennik N powstaje na początku cyklu (zlecenia), wyniki wracają w oknie N i w dzienniku N+1. Cykle 1-2: okna z dat issues (#43-#55; dzienniki odzyskane dopiero w c.3). Cykl 10 sięga do dziennika 14 (11-13 padły). Cykl 60: do ostatniego commitu #358.
- **Godziny** = czas między dziennikami: wliczone kolejki, serie na emulatorze (3-5 h), przestoje. To nie czas pracy sesji.
- **Issues** = etykieta `loop:iteration N` (z zadaniem złączeniowym); serie nie są issues. **Commity** = wszystkie w oknie na `main`.
- **Rekord** = średnia fixed z `bench/record.json`, jeśli w oknie była jej zmiana. Liczby nie są porównywalne między zmianami sufitu, generatora lub odcisku (c.20, 23, 26, 29, 30, 33); `uwaga` w JSON podaje przyrost i zastrzeżenia.
- **Werdykt**: `promocja` (zmiana rekordu), `bez efektu`, `cofnięte`; dodatkowo `awaria`, `infrastruktura` (most/seria/narzędzia, rekord nietknięty) i `cel`. Trzy zadane kategorie nie pokrywają 24 cykli po c.33, stąd `infrastruktura`.

## Wnioski

- 60 cykli, 57 z dziennikiem; suma okien ok. 195 h (24.09 18:29 -> 02.10 21:34 UTC), 689 commitów, 283 issues w oknach.
- Werdykty: 24 infrastruktura, 14 bez efektu, 13 promocja, 5 awaria, 2 cel, 2 cofnięte (c.32 cel odwołany przez właściciela, c.51 niezaliczone ogłoszenie).
- Rekord: 4 510 (c.5) -> 6 171 (c.7) -> 14 792 (c.17) -> 34 658 (c.21) -> 83 866 (c.22) -> 123 077 (c.27) -> 560 859 (c.28, `complete=1`) -> 11,03 mln (c.30, `gain_weight`) -> 44,16 mln (c.33, sufit 64 000 = linia bazowa, nie nowa polityka).
- Największe skoki z jednej zmiany: gwarancja tacki (c.28, +356%) i `gain_weight` (c.30, +387%); przeszukanie z szerokim beamem (c.22, +142%). Po dwa cykle bez ruchu rekordu: c.18-19 i c.24-25.
- Od c.33 polityka stoi; 24 z 27 cykli (34-60) to naprawy mostu i serie na oryginale (s1-s7), cel 10/10 w c.60.
- Awarie: c.1-2 (zamek, brak `GH_TOKEN`), c.11-13 (API 400, #137); c.2 (12,7 h) i okno c.10-13 (22,4 h) to w dużej części przestój.

## Tabela

| cykl | start UTC | h | commity | issues | rekord (śr. fixed) | werdykt | cel |
|---|---|---|---|---|---|---|---|
| 1 | 09-24 18:29 | 1.6 | 1 | 5 |  | awaria | Bieg na sucho: research kar terminalnych (#43), testy (#44), pomiar sygnalu (#45) |
| 2 | 09-24 20:05 | 12.7 | 9 | 8 |  | awaria | Puste zadanie domykajace cykl; zadania zablokowane awaria #48 |
| 3 | 09-25 08:46 | 6.5 | 15 | 4 |  | bez efektu | Zmiana kierunku: DQN -> funkcja oceny planszy + przeszukanie tacki + CEM (#56-#61) |
| 4 | 09-25 15:15 | 3.8 | 19 | 7 |  | bez efektu | Odzysk dorobku (#77), koszt TrayPolicy (#79), benchmark ze strojonymi wagami (#80), pierwsze wagi CEM (#81), pomiar #82 |
| 5 | 09-25 19:05 | 1.0 | 7 | 4 | 4 510.24 | promocja | Powtorka pomiaru #87 (tray:weights vs greedy), przyspieszenie TrayPolicy 3,14x (#88) |
| 6 | 09-25 20:03 | 8.3 | 10 | 7 |  | bez efektu | Kierunek: glebokosc przeszukania, lookahead (#92), pomiar #97 |
| 7 | 09-26 04:23 | 6.1 | 11 | 8 | 6 171.04 | promocja | Ratunek wyniku #97 (#100), sigma wyniku (#101), source_hashes (#102), start CEM pod lookahead (#104) |
| 8 | 09-26 10:32 | 2.2 | 12 | 5 |  | bez efektu | Dokonczenie CEM (#110), pomiar wag lookahead vs rekord (#111) |
| 9 | 09-26 12:41 | 3.6 | 18 | 7 |  | bez efektu | Combo w ocenie liscia (#118), ile do 10 mln (#119), budzet wyuczonej oceny (#120), Z-6 na oryginale (#121) |
| 10 | 09-26 16:16 | 22.4 | 16 | 8 |  | bez efektu | Wyuczona ocena N-tuple/TD (#123), hak liscia (#125), pomiar #127 |
| 11 | - | - | - | - | | awaria | brak dziennika (sesja padla, API 400, #137) |
| 12 | - | - | - | - | | awaria | brak dziennika (sesja padla, API 400, #137) |
| 13 | - | - | - | - | | awaria | brak dziennika (sesja padla, API 400, #137) |
| 14 | 09-27 14:40 | 3.2 | 24 | 8 |  | bez efektu | Eksperyment sygnal/krok z uczciwym narzedziem; mapa #140-#146 |
| 15 | 09-27 17:52 | 2.6 | 17 | 9 |  | bez efektu | Dluzszy trening A (#147->#151) i bogatszy uklad AD z kwadratami 3x3 (#149->#156) rownolegle |
| 16 | 09-27 20:29 | 2.1 | 13 | 5 | 10 584.01 | promocja | Bench AD 40k (#156), trening AD do 70k (#157) |
| 17 | 09-27 22:35 | 2.4 | 27 | 5 | 14 791.52 | promocja | Bench AD 50k i 70k (#161) |
| 18 | 09-28 00:57 | 5.7 | 28 | 9 |  | bez efektu | ADC do 70k vs AD (#166->#171), bench w kawalkach (#167) |
| 19 | 09-28 06:37 | 4.2 | 37 | 11 |  | bez efektu | Dokonczyc #171, starty z pozdniej gry (#177), ADC/ADC-SS do 100k, przepustowosc treningu |
| 20 | 09-28 10:51 | 8.0 | 30 | 8 | 25 946.36 | promocja | Kalibracja generatora (#186), trening 500k, nowa linia bazowa (#192) |
| 21 | 09-28 18:49 | 1.6 | 24 | 7 | 34 657.70 | promocja | Skala 180k-500k, bench migawek (#194), test hipotezy kroku alpha/4, /16 (#196, #197) |
| 22 | 09-28 20:22 | 5.4 | 36 | 7 | 83 865.64 | promocja | Przeszukanie przed wagami: szeroki beam (#201), diagnoza drugiego poziomu (#202) |
| 23 | 09-29 01:49 | 5.3 | 20 | 8 | 88 133.50 | bez efektu | Zmiana sposobu uczenia: research #208, pilot TD na stanach z przeszukania (#214), sufit 4000 |
| 24 | 09-29 07:04 | 4.2 | 8 | 5 |  | bez efektu | Srodowisko przed ocena: generator swiadomy planszy (#217) (#216-#219) |
| 25 | 09-29 11:18 | 3.6 | 16 | 5 |  | bez efektu | Os pojemnosci: ADCE (#222), pilot #216 |
| 26 | 09-29 14:52 | 4.5 | 9 | 7 | 92 772.85 | promocja | ADCE 200k->600k (#228), bench 400k/600k (#229), port #221 |
| 27 | 09-29 19:20 | 2.3 | 12 | 6 | 123 077.03 | promocja | Dokonczenie ADCE, bench, pomiar unikalnosci smierci (#236) |
| 28 | 09-29 21:40 | 2.6 | 15 | 4 | 560 858.53 | promocja | Gwarancja ulozenia tacki complete=1 (#240), smierc = chybienie wiazki |
| 29 | 09-30 00:14 | 1.7 | 20 | 8 | 1 126 300.71 | promocja | Sufit x2 4000->8000 (#243), pomiar gain_weight (#248), ukladalnosc tacek w apce (#249) |
| 30 | 09-30 01:57 | 2.5 | 29 | 11 | 11 034 218.30 | promocja | Sufit x2 ->16000, bench gain_weight=100000 (#251-#259), gotowosc mostu (#260) |
| 31 | 09-30 04:24 | 3.8 | 2 | 2 |  | cel | Weryfikacja na oryginale (#262): partia >= 1 mln w apce |
| 32 | 09-30 08:13 | 2.3 | 4 | 1 |  | cel / cofniete | Cel osiagniety - GOAL_REACHED (#259 11,03 mln + #262 1 004 153) |
| 33 | 09-30 10:33 | 6.9 | 52 | 17 | 44 163 856.20 | promocja | Nowy cel: nieprzegrywanie. Bench przy suficie 64000 (#265-#279), tempo mostu, skrypt serii |
| 34 | 09-30 17:29 | 0.6 | 2 | 4 |  | infrastruktura | Warunek 1 potwierdzony (#279); #282-#284: domkniecie #266, skrypt serii, pomiar |
| 35 | 09-30 18:08 | 3.1 | 22 | 3 |  | infrastruktura | Pomiar tempa (#286) + proba skryptu serii na emulatorze |
| 36 | 09-30 21:14 | 0.5 | 5 | 2 |  | infrastruktura | Pewny licznik apki: OCR 7 cyfr (#290) |
| 37 | 09-30 21:42 | 1.6 | 13 | 2 |  | infrastruktura | Start serii s1, narzedzie diagnozy przegranej (#292) |
| 38 | 09-30 23:21 | 0.4 | 2 | 3 |  | infrastruktura | Naprawa mostu po przerwaniach s1 (#294) |
| 39 | 09-30 23:44 | 0.5 | 2 | 2 |  | infrastruktura | s2 zakolejkowana, HUD na zlotym rombie (#297) |
| 40 | 10-01 00:17 | 1.4 | 2 | 2 |  | infrastruktura | s2 na 8fde499, diagnoza nowej tacki (#299) |
| 41 | 10-01 01:40 | 1.4 | 2 | 1 |  | bez efektu | Bez zadan - czeka na artefakty s1 |
| 42 | 10-01 03:04 | 0.4 | 3 | 2 |  | infrastruktura | Test read_hud_score na 7 cyfrach (#302) |
| 43 | 10-01 03:29 | 0.7 | 4 | 3 |  | infrastruktura | Naprawa infrastruktury mostu (#304), diagnoza przegranych (#305) |
| 44 | 10-01 04:13 | 1.4 | 5 | 2 |  | infrastruktura | Naprawa read_tray (#307) |
| 45 | 10-01 05:35 | 0.3 | 3 | 2 |  | infrastruktura | s2 anulowana, s3 z limitem 340 min (#308) |
| 46 | 10-01 05:56 | 1.3 | 8 | 3 |  | infrastruktura | Dwie poprawki mostu lancuchem (#311 ekran startowy, #312 read_tray z banerem) |
| 47 | 10-01 07:15 | 2.4 | 9 | 4 |  | infrastruktura | s4 w kolejce; detektory (#314), roznice planszy (#315) |
| 48 | 10-01 09:37 | 1.1 | 4 | 3 |  | infrastruktura | Regula ostatniej deski: twardy restart (#318), pomiar force-stop (#319) |
| 49 | 10-01 10:43 | 4.2 | 6 | 4 |  | infrastruktura | s5 w kolejce, test wariantu X kola fortuny (#321) |
| 50 | 10-01 14:56 | 3.2 | 3 | 2 |  | infrastruktura | Zadanie scalajace poprawki (#325) |
| 51 | 10-01 18:11 | 4.1 | 4 | 5 |  | cofniete | Rozliczenie s4/s5, #326 |
| 52 | 10-01 22:15 | 2.5 | 4 | 2 |  | infrastruktura | Naprawa mostu: baner Combo w odczycie (#333) |
| 53 | 10-02 00:46 | 1.6 | 6 | 3 |  | infrastruktura | s6 start @6c4c88b, pomiar pozostalych ok:false (#335), test licznika s4 p.8 (#336) |
| 54 | 10-02 02:23 | 4.2 | 8 | 4 |  | infrastruktura | Przyczyna przegranych s6 (#341), domkniecie #335 (#338), napis w moscie (#339) |
| 55 | 10-02 06:33 | 3.3 | 6 | 4 |  | infrastruktura | Naprawa duchow baneru (#342), przerwania s6 (#343), konce partii s4 (#344) |
| 56 | 10-02 09:52 | 2.2 | 4 | 4 |  | infrastruktura | Nowe zasady serii 10/10 (#345): czas napisu (#346), koniec przy 1 mln (#347), ponowny odczyt (#348) |
| 57 | 10-02 12:04 | 3.7 | 8 | 3 |  | infrastruktura | Pomiar napisu (#350) i ponowny odczyt z limitem 5 s (#351) rownolegle |
| 58 | 10-02 15:46 | 2.6 | 3 | 2 |  | infrastruktura | Domkniecie #351 pelnym zestawem testow (#353) |
| 59 | 10-02 18:25 | 2.1 | 6 | 3 |  | infrastruktura | s7 na 40137e2 (limit 340), analiza ok_false --ponowny (#355) |
| 60 | 10-02 20:30 | 1.1 | 4 | 3 |  | cel | s7 10/10, GOAL_REACHED, domkniecie #356 (#358) |


