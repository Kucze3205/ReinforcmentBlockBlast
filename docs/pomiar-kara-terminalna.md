# Pomiar: ile sygnalu gubia obie kary -5 w game.step (#51)

Polecenie odtwarzajace: `python tools/measure_terminal_reward.py`

Polityka: `GreedyPolicy` z policies.py. Seedy: pierwsze 300 z bench/seeds_fixed.json (stale, powtarzalne). move_cap = 2000 (z bench/config.json).

## Suma nagrod z epizodu vs wynik partii

Srednia roznica (wynik_partii - suma_nagrod) na partie: **16.51** punktu.

Srednia z (roznica / wynik_partii) na partie: **4.12%**.

## `gained` wyrzucone w linii 59 (galaz game_over)

Partii, ktore zakonczyly sie galezia game_over (nie ucietych sufitem ruchow): 300 z 300.

- srednia: **11.51**
- mediana: **4.00**
- maksimum: **152.00**

## Galaz wrong_placement (linia 52)

Liczba wystapien galezi wrong_placement na 300 partii polityki zachlannej (ktora wybiera wylacznie z listy legalnych akcji): **0**.

