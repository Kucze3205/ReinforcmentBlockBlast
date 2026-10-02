# Raport pętli — raport końcowy

**2026-10-02 · cykl 60 · CEL OSIĄGNIĘTY**

**Czeka na ciebie:** [otwarte awarie](https://github.com/Kucze3205/ReinforcmentBlockBlast/labels/awaria) — żadnej.
Pętla stoi, bo w korzeniu leży `GOAL_REACHED`. Podsumowanie i rzeczy do decyzji są w przypiętym issue.

## Gdzie jesteśmy

Oba warunki celu „agent nie przegrywa” (`CONTEXT.md`, zasady zaliczania z #345) są spełnione i potwierdzone.

- **Symulator:** zero przegranych na 600 seedach (300 stałych i 300 rotowanych) przy ε = 0 i suficie 64 000 ruchów
  ([#279](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/279), cykl 34). Średnio 44,2 mln pkt na partię
  (tylko informacyjnie). Pliki, od których zależy wynik benchmarku, nie zmieniły się od tamtego pomiaru.
- **Prawdziwa apka (10.7.5):** seria **s7**
  ([run 37046972994](https://github.com/Kucze3205/ReinforcmentBlockBlast/actions/runs/37046972994), kod `40137e2`):
  **10 z 10 partii doszło do 1 mln na liczniku apki** w jednej serii. Zero przegranych, zero przerwań, zero powtórzonych
  jobów. Liczniki na końcu: od 1 001 477 do 1 282 497. Partie trwały od 44 do 156 minut (limit 340) i miały od 919 do
  3299 postawień. Każdy cel sprawdziłem na ostatnim zrzucie licznika: plansza żyje, HUD pokazuje ponad 1 mln.
  Materiał jest w `docs/seria/s7/`, a tabela w `docs/journal/cykl-0060.md`.

Bot: przeszukanie wiązką (128 najlepszych pierwszych ruchów, każdy dokończony do końca tacki). Planszę ocenia sieć
n-tuple trenowana na przeżycie, a dodatkowo bot dostaje dużą wagę za punkty z bieżącej tacki. Decyzja trwa 2–3 ms.
Ta polityka nie zmieniła się od cyklu 34.

## Co się wydarzyło

Od zmiany celu (30.09) bot nie przegrał żadnej partii z własnej winy. Wszystkie przegrane w seriach s3–s6 wynikały
z błędów mostu, czyli odczytu ekranu i sterowania emulatorem. Były to: napisy i „duchy” po czyszczeniu linii brane
za klocki, zbyt wczesny „stabilny” stan planszy i brak zatrzymania po milionie. Każdą serię dogrywaliśmy do końca,
przegrane odtwarzaliśmy, a most łataliśmy. Ostatnie poprawki przed s7 to:

- korekta duchów (#342),
- stop po 1 mln według HUD (#347),
- ponowny odczyt planszy, gdy ekran nie zgadza się z oczekiwanym stanem (#351/#353).

W s7 ponowny odczyt zadziałał na żywo 59 razy: 49 przypadków naprawił, 10 zostało rozbieżnych, ale żaden nie zakończył
partii.

Jedna usterka jest nadal otwarta. W 5 z 10 partii skrypt serii nie potwierdził przekroczenia miliona od razu, bo licznik
apki jeszcze się doliczał. Partia grała wtedy cały kawałek dłużej, maksymalnie o 280 tys. punktów ponad cel. Wszystkie
te partie przeżyły, ale według twoich zasad (#345) to wymaga naprawy. Zadanie
[#358](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/358) było już w toku, gdy kończyłem cykl.

## Co dalej

Pętla nie startuje nowych sesji. Zostały rzeczy, które możesz zrobić, ale nie musisz:

1. **#358.** Jeśli skończy się statusem `done`, poprawka wejdzie na `main` sama. Jeśli `partial`, praca zostanie na
   `task/358`.
2. **Wznowienie** (np. żeby powtórzyć serię albo podnieść poprzeczkę): skasuj `GOAL_REACHED`. Mapa
   [#359](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/359) czeka. Jej pierwsze zadania to raport #358,
   analiza s7 (10 nienaprawionych rozbieżności) i dopisanie s7 do testów detektorów.
3. Stare sprawy: dowody #262 na `task/262`, #237, 8 MB `ntuple-state.json` do sprzątnięcia.

**Rokowanie:** ta linia pracy dowiozła cel, czyli politykę z cyklu 34 i łatanie mostu po każdej serii. Siła bota nie
była wąskim gardłem. Po ewentualnym wznowieniu zostaje tylko utwardzanie mostu.
