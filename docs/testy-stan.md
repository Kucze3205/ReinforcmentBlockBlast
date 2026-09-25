# Stan testów

Stan na gałęzi `task/49`, po rebasie na domyślną, po jednej zmianie: usunięciu linii
`from turtle import done` z `model.py:1`.

## Ile i gdzie

`python -m unittest discover -s tests` uruchamia 30 testów z dwóch plików:

- `tests/test_engine.py` — 17 testów: silnik gry (`TestBenchmarkPrerequisites`,
  `TestComboMechanics`, `TestGenerator`, `TestPiecePool`, `TestScoreAccumulates`,
  `TestScoringFormula`). Pokrywa generator kawałków, punktację, combo, reprodukowalność
  seedów.
- `tests/test_loop.py` — 13 testów: logikę pętli/orchestratora (`ProfilTest`,
  `PrzyczynaTest`, `RaportTest`). Pokrywa parsowanie raportów, klasyfikację przyczyn
  błędów API/subskrypcji, zakazy profilu roli.

## Co było czerwone i dlaczego

Jeden test padał na starcie: `test_engine.TestBenchmarkPrerequisites.test_agent_accepts_epsilon_zero`.
Powód: `model.py:1` zawierał `from turtle import done`. `turtle` importuje `tkinter`,
którego na runnerze CI nie ma — import `agent` → `model` wywalał się na `ModuleNotFoundError`
zanim jakikolwiek test agenta zdążył się wykonać.

Nazwa `done` z tego importu nie była nigdzie w `model.py` używana — w pliku występuje
tylko lokalny parametr `done` w `QTrainer.train_step` (parametr funkcji, cieniuje
wcześniejszy import, nie odwołuje się do niego). Import był martwy, najpewniej
przypadkowy z podpowiedzi edytora. Usunięcie samej linii importu było całą poprawką.

## Wynik po poprawce

`python -m unittest discover -s tests` → kod wyjścia 0, 30/30 zielonych.

## Czego świadomie nie naprawiono

Nic — po usunięciu importu wszystkie 30 testów przechodzi bez dalszych zmian. Nie było
potrzeby ruszać silnika, agenta ani nagrody.
