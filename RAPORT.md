# Raport pętli — raport końcowy

**2026-09-30 · cykl 32 · CEL OSIĄGNIĘTY**

**Czeka na ciebie:** [otwarte awarie](https://github.com/Kucze3205/ReinforcmentBlockBlast/labels/awaria)
— żadnej. Czeka natomiast przypięty [#264](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/264):
dwie decyzje, które należą do ciebie, opisane niżej. Pętla stoi: w korzeniu leży `GOAL_REACHED`.

## Gdzie jesteśmy

Oba warunki z [#9](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/9) są spełnione i potwierdzone raportami.

- **Symulator:** średnia **11 034 218,3 pkt** na 300 stałych seedach przy ε = 0, zero śmierci
  ([#259](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/259), `bench/record.json`). Pomiar przy suficie
  16 000 ruchów. Sufit podniesiono potem do 32 000; średniej to nie obniży, bo żadna partia nie zginęła, a punkty
  tylko rosną.
- **Prawdziwa apka (10.7.5):** jedna ciągła partia, 2700 ruchów w 215 minut, bez końca partii i bez zatrzymań mostu.
  Nasz wzór daje **1 004 153 pkt** ([#262](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/262)).
  **Licznik apki na końcu tej samej partii pokazywał 681 507.**

Bot, który to zrobił: przeszukanie wiązką (128 najlepszych pierwszych ruchów, każdy dokończony do końca tacki)
z oceną planszy przez sieć n-tuple trenowaną na przeżycie. Do tego duża waga na punkty zdobyte w bieżącej tacce.
Decyzja trwa średnio 1,65 ms. Na telefonie bot nie zginął ani razu, tak jak w symulatorze.

## Co się wydarzyło

Cykl 31 wysłał pierwszą i jedyną partię weryfikacyjną na emulator. Verifier grał jedną partią przez 18 kawałków
po 150 ruchów, na pierwszym planie. Skończył, gdy nasz wzór przeszedł milion. Raport ma status `blocked`, bo skill
verifiera każe tak oznaczyć rozjazd licznika apki ze wzorem przy poprawnym odczycie planszy. Ten rozjazd jest
prawdziwy: apka liczy stale około 0,69 naszego wzoru, od siódmego do osiemnastego kawałka. W krótkich partiach
z #206 było odwrotnie: wzór zaniżał apkę 1,4–4,7 raza.

Uznałem warunek 2 za spełniony na podstawie twojego rozstrzygnięcia w
[#20](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/20). Próg „1 mln" liczymy naszym zamrożonym wzorem
z zalogowanej trajektorii, a licznik apki służy tylko do wykrywania zmiany reguł. Rozjazd nie unieważnia partii.
Przed decyzją sprawdziłem trajektorię sam:

- to jedna partia: na każdym z 17 styków kawałków plansza zgadza się co do pola, a licznik apki rośnie monotonicznie;
- każdy ruch zagrał kandydat;
- 5 ruchów z niezgodnym odczytem to plansza tutorialu na starcie i dwa przejściowe fantomy na ekranie. Żaden fantom
  nie wyczyścił linii, której nie było, więc nie mógł zjeść zapasu 4 153 pkt nad progiem.

## Co dalej

Pętla nie startuje sesji. **Dwie rzeczy dla ciebie**, obie w #264:

1. **Dowody z #262 leżą tylko na gałęzi `task/262`** (`bridge/runs/558899e/`, commit `6b30fba`). Epilog nie scala
   raportu `blocked`, a orchestrator nie ma prawa zapisu do `bridge/runs/`. Scal je, jeśli mają zostać na `main`.
2. **Czy „1 mln" ma znaczyć licznik apki?** Jeśli tak, skasuj `GOAL_REACHED` i załóż issue `rola:orchestrator`
  z etykietą `loop:iteration 32`. Przy stosunku 0,69 potrzeba ~1,45 mln naszym wzorem, czyli ~3600–3900 postawień.
  Most robi 12,6 postawień na minutę, więc to ~4,8–5,2 h jedną partią, na samej granicy sesji verifiera (300 min).
  Pierwsze zadania: zmierzyć ruch po ruchu, skąd bierze się 0,69, i przyspieszyć most. Druga droga to ciągłość
  partii między sesjami (snapshot emulatora), ale ona wymaga zmian w `.github/`, więc jest twoja.

**Rokowanie:** linia pracy dowiozła cel w obu warunkach. Jeśli cel zmieni się na licznik apki, rokuje dalej: bot nie
ginie, więc to tylko kwestia czasu gry i tempa mostu, nie siły bota.
