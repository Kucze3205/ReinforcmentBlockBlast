# Raport tygodniowy

**2026-09-24 · cykl 1**

**Czeka na ciebie:** [otwarte awarie](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues?q=is%3Aissue+is%3Aopen+label%3Aawaria) — dziś pusto, pętla nie potrzebuje twojej ręki.

## Gdzie jesteśmy

Rekordu nie ma. `bench/record.json` nie istnieje i nie ma ani jednych wytrenowanych wag, więc
najlepsze, co repo umie, to zachłanna heurystyka na jeden pół-ruch w przód: **704,79 punktu
średnio i 34,99 postawień** na 300 stałych seedach. Losowa gra daje 59,15. Cel to 10 000 000 —
cztery rzędy wielkości wyżej.

Sufit ruchów w benchmarku stoi na 2000 i żadna partia go nie dotknęła, więc nie ma czego
podnosić.

## Co się wydarzyło

To był pierwszy cykl pętli i z twojego biletu #42 wynikało wprost, że ma być biegiem na sucho:
sprawdzamy, czy maszyneria się domyka, nie czy bot się poprawia. Zlecone są trzy tanie zadania
i jedno issue złączeniowe, które obudzi cykl 2 — #43 (researcher: co wiadomo spoza repo o karze
terminalnej i o nagradzaniu przeżycia), #44 (implementer: przebieg testów i naprawa tego, co
czerwone, byle poza silnikiem), #45 (implementer: pomiar, ile sygnału gubi gałąź końca partii
w `game.step`) i #46 (domknięcie cyklu). #43 i #44 ruszyły, #45 czeka na #44, #46 czeka na
całą trójkę.

Przy okazji czytania repo wyszła rzecz poważniejsza niż cokolwiek zleconego. **`scoring.py`
nigdy nie dostało poprawek, które pętla sama zmierzyła.** Bilety #30 i #33 ustaliły, że bonus
za wyczyszczenie całej planszy wynosi 0, a nie 300, i że bonus za linię rośnie schodkami wraz
z combo — oba są zamknięte, ale kod leży na niescalonych gałęziach. Skutek: symulator zaniża
grę tym bardziej, im wyższe combo, czyli dokładnie w reżimie, do którego zmierzamy. To samo
dotyczy filtra grywalności tacki z #37.

Nie zleciłem tego w tym cyklu, bo twój bilet zabronił w biegu na sucho zadań ruszających
kalibrację symulatora. Wątek jest zapisany w dzienniku jako pierwsza pozycja na cykl 2.

## Co dalej

Linia pracy: najpierw uczciwy sygnał nagrody, potem wybór metody. Decyzja o obu karach `-5`
w `game.step` i o tym, czy przeżycie dostanie własny sygnał, zapada w cyklu 2 — materiał na
nią dowożą właśnie #43 i #45.

Rokuje, ale nie dlatego, że cokolwiek urosło; w tym cyklu nie urosło nic i nie miało.
Rokuje dlatego, że pomiar #40 już pokazał, gdzie obecny DQN się kończy, a symulator bez sieci
chodzi jakieś dwieście razy szybciej niż uczenie — to przesuwa ciężar dowodu w stronę
przeszukiwania. Jeśli cykl 2 skończy się bez decyzji o kierunku algorytmicznym, uznam to za
pierwszy sygnał stagnacji i zmienię linię pracy, zamiast dokładać kolejne zadanie w tej samej.

Dziennik cyklu: `docs/journal/cykl-0001.md`.
