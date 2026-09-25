# Decyzja: kara terminalna w game.step (#56)

## Zmiana

`game.py:59` (gałąź `game_over`) zwraca teraz `gained` — przyrost punktów policzony w
`apply_placement` dla ostatniego, udanego postawienia partii — zamiast stałej `-5`.
Pozostałe trzy elementy krotki (`self.score`, `True`, `"game_over"`) bez zmian.

`game.py:52` (gałąź `wrong_placement`) zostaje merytorycznie bez zmian: nadal zwraca `-5`.
To zapora na wypadek błędu wywołującego, nie element kształtu nagrody — polityka wybiera
akcje wyłącznie z `available_actions()`, więc ta gałąź jest w praktyce nieosiągalna (#51:
zero wystąpień na 300 partii polityki zachłannej). Kontrakt jest teraz udokumentowany
komentarzem przy tej gałęzi w kodzie.

Sygnał przeżycia świadomie **nie** dostał własnego składnika nagrody — decyzja cyklu 3,
patrz sekcja (c) `docs/research/nagroda-terminalna-i-przezycie.md`: jedyny bezpośredni
precedens (Botkraker) deklaruje korzyść bez metodologii pomiaru, a literatura spoza tej gry
(lokomocja) pokazuje ryzyko lokalnego minimum przy zbyt dużym bonusie za trwanie.
`game.placements` zostaje miarą benchmarku, nie nagrodą.

## Dlaczego linia bazowa 704,79 / 34,99 się nie zmienia

`benchmark.py:119-125` (`play_game`) czyta `game.score` i `game.placements` na koniec
partii; wartości zwracanej przez `step()` (pierwszy element krotki) **nie używa wcale** —
zmienna `gained`/`reward` ze `step()` nie jest tam nawet przechwytywana. Zmiana tego, co
`step()` zwraca w kroku terminalnym, nie zmienia więc żadnej liczby czytanej przez
benchmark: `game.score` sumuje się identycznie jak przed zmianą (w `apply_placement`,
niezależnie od tego, co robi `step()` z `gained`), a `game.placements` liczy postawienia,
nie nagrody. Linia bazowa 704,79 (średni wynik) / 34,99 (średnie przeżycie) pozostaje
aktualna.
