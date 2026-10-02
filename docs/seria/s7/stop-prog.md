# s7: niepotwierdzony `stop_prog` (p.2, p.4) — #356

Run 37046972994 @ `40137e2`. Odczyty odtworzone `bridge.read_score` na zapisanych zrzutach
(`partia-*/licznik_*.png`, `kawalek_*/final.png`).

| partia | kawałek | HUD w chwili stopu (`final.png`) | zrzut `licznik_k.png` (ostatnia klatka odczytu) | wynik |
|---|---|---|---|---|
| 2 | 7 | 1 000 888 | 1 001 782 | `stabilny: false`, brak celu |
| 4 | 8 | 1 002 693 | 1 004 232 | `stabilny: false`, brak celu |
| 9 | 7 | 1 013 223 | 1 013 223 | stabilny, `potwierdzony: true` |
| 5 | 11 | 1 003 568 | 1 005 197 | `stabilny: false`; cel dopiero kawałek później (1 277 590, `licznik_12.png`) |
| 10 | 10 | 1 004 546 | 1 006 670 | `stabilny: false`; cel dopiero kawałek później (1 109 502, `licznik_11.png`) |

Nowe przypadki p.5 i p.10 (#358, ta sama metoda: `bridge.read_score` na `kawalek_K/final.png` i `licznik_K.png`;
materiał z `task/357`): HUD w chwili stopu 1 003 568 / 1 004 546, ostatnia klatka odczytu 1 005 197 / 1 006 670, czyli
ekran wyższy od HUD o 1 629 / 2 124. Pasuje do hipotezy doliczania (jak p.2 i p.4: licznik apki rośnie po ostatnim
ruchu, a odczyty z kolejnych klatek się różnią). Nie dowodzi jej: ciągu odczytów nadal nie ma, bo pole `odczyty`
w `stop_prog` dochodzi dopiero w #358 — następna seria pokaże go wprost (lista list, po jednej na wywołanie
`read_stable_counter`).

Pełna lista odczytów z chwili stopu nie przetrwała: `pomiar.json` nadpisał `licznik_apki` odczytem z następnego
kawałka, a `licznik_odrzucone` jest puste (`counter_consistent` nie odrzucił niczego). `licznik_k.png` zapisuje się
tylko przy `value is not None`, więc odczyt był czytelny i spójny; `cel` wymaga `stable`, więc `stable` było `false`.

Hipoteza o żółtym diamencie nie potwierdza się: `read_hud_score` czyta poprawnie wszystkie zrzuty z diamentem
(p.4 `licznik_8.png`, 7 cyfr), a odczyt z diamentem w p.9 jest stabilny.

Przyczyna:
- **p.2:** po ostatnim ruchu licznik apki jeszcze się doliczał (HUD 1 000 888 → ekran 1 001 782), więc kolejne odczyty się różniły i dwa ostatnie nie były zgodne.
- **p.4:** to samo (HUD 1 002 693 → ekran 1 004 232); licznik rósł szybciej, niż odczyty następowały po sobie (6 prób bez przerwy).
- **p.9:** licznik zdążył się ustalić (ekran = HUD), więc dwa odczyty były zgodne.

Wniosek jest wyprowadzony z różnicy HUD vs zrzut i z tego, że odczyt jest czytelny; samego ciągu odczytów
nie da się już odtworzyć (patrz wyżej).

## Reguła

Po `stop_prog`, gdy odczyt jest czytelny, ≥ progu, ale niestabilny, `partia_serii.py` ponawia `read_stable_counter`
z przerwą `STOP_PRZERWA_S` = 1,5 s, najwyżej `STOP_PONOWIENIA` = 5 razy, do pierwszego stabilnego odczytu.
Licznik apki tylko rośnie, a doliczanie trwa krótko, więc po przerwie odczyty się ustalają. Odczyt końcowy przechodzi
dalej `counter_consistent` jak dotąd; stabilny ≥ progu → `cel` i `potwierdzony: true`. Odczyt < progu albo
nieczytelny, albo brak stabilizacji po limicie → zachowanie bez zmian (następny kawałek gra do końca).
Czas dodatkowy: najwyżej ok. 7,5 s plus odczyty, tylko przy stopie.
