# s7: niepotwierdzony `stop_prog` (p.2, p.4) — #356

Run 37046972994 @ `40137e2`. Odczyty odtworzone `bridge.read_score` na zapisanych zrzutach
(`partia-*/licznik_*.png`, `kawalek_*/final.png`).

| partia | kawałek | HUD w chwili stopu (`final.png`) | zrzut `licznik_k.png` (ostatnia klatka odczytu) | wynik |
|---|---|---|---|---|
| 2 | 7 | 1 000 888 | 1 001 782 | `stabilny: false`, brak celu |
| 4 | 8 | 1 002 693 | 1 004 232 | `stabilny: false`, brak celu |
| 9 | 7 | 1 013 223 | 1 013 223 | stabilny, `potwierdzony: true` |

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
