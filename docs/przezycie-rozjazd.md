# Rozjazd 34,99 vs 57,3: dwie różne miary, nie dwa pomiary tego samego

Issue #52. Odpowiedź: **34,99 jest miarą przeżycia w sensie benchmarku #8. 57,3 mierzy
coś innego — przeżycie polityki wytrenowanej sieci (`ModelPolicy`) w trakcie treningu,
a nie polityki zachłannej (`GreedyPolicy`).** Dwie liczby nigdy nie opisywały tej samej
polityki.

## Skąd bierze się 34,99

- `benchmark.py:296` (`measure_arm`) → `benchmark.py:128-134` (`run_set`/`play_game`) →
  pole `survival_mean` = `statistics.mean(survivals)`, gdzie `survivals` to
  `game.placements` po zakończeniu partii (`benchmark.py:120-125`).
- Polityka: `GreedyPolicy` z `policies.py:28-42` — maksymalizuje natychmiastowy zysk
  punktowy z bieżącego postawienia (jeden pół-ruch w przód, `_immediate_gain`,
  `policies.py:61-76`). Sieć neuronowa nie bierze w tym udziału.
- Warunki: `bench/43d1e7cf8035132ea52f67865c3473aefeda8741.json` — zestaw **fixed**,
  `n_seeds = 300` z `bench/seeds_fixed.json`, `move_cap = 2000`, `epsilon = 0.0`,
  `issue = 17` (rekord zapisany w benchmarku #17). Wartość `survival_mean` dla ramienia
  `candidate` (greedy) w zestawie fixed = **34.99**.
- Koniec partii: `game.done` w naturalnym przebiegu gry (plansza bez ruchów) albo
  ucięcie po `move_cap = 2000` postawieniach (`was_capped`); dla tego pomiaru
  `capped_pct = 0.0%`, więc żadna z 300 partii nie została ucięta sufitem — 34,99 to
  naturalne przeżycia, nie efekt limitu.
- „Postawienie" = jedno wywołanie `game.step(...)` liczone jako `game.placements`
  (inkrementowane wewnątrz silnika gry przy każdym udanym postawieniu klocka).

## Skąd bierze się 57,3

- Kod pochodzi z `tools/rl_measure.py`, dodanego w commicie `06b7b36` („Zmierz trening RL
  na runnerze Actions (#40)"). **Ten plik nie istnieje na żadnej gałęzi historii bieżącego
  HEAD** (`git merge-base --is-ancestor 06b7b36 HEAD` → `NOT ancestor`) — żyje wyłącznie
  na `origin/wayfinder/40-rl-measure`, gałęzi feature'owej z #40, która nigdy nie została
  scalona do `main`. `tools/` w obecnym repo zawiera tylko `bridge.sh` i
  `emulator_probe.sh`.
- Funkcja `evaluate()` (`tools/rl_measure.py:45-49` na gałęzi 40) woła:
  `run_set(ModelPolicy(agent, "rl"), seeds, cap)` — **to jest ta sama funkcja `run_set`
  co w benchmarku**, ale karmiona `ModelPolicy`, czyli aktualnie trenowaną siecią
  (`agent.model`, tryb `eval()`, ε = 0 tylko na czas ewaluacji), **nie `GreedyPolicy`**.
  Zero odniesienia do `policies.GreedyPolicy` w całym pliku.
- Pętla `train()` (`tools/rl_measure.py:52-...`) trenuje agenta czasowo:
  `--train-seconds 1500 --eval-every 300` (`.github/workflows/rl-measure.yml`), partie
  losowane `Game(seed=rng.randrange(2**31))` z `random.Random(1)` — **inny generator
  seedów** niż `fixed_seeds`/`rotated_seeds` benchmarku. Co 300 s treningu wywoływana jest
  `evaluate()` na `seeds = fixed_seeds(cfg)[:eval_seeds]`, `eval_seeds = 50` (domyślne,
  workflow go nie nadpisuje) — **50 seedów, nie 300**, choć to prefiks tej samej listy
  `bench/seeds_fixed.json`.
- Liczba 300-sekundowych okien w 1500 s treningu zależy od realnej prędkości runnera
  (`train_time < seconds` mierzone `time.perf_counter()`), więc to, ile kroków/gier agent
  zdążył rozegrać do danego punktu krzywej, jest niedeterministyczne między przebiegami.
  57,3 to `survival_mean` z jednego z punktów krzywej `curve` w artefakcie
  `rl-out/result.json` z workflow `rl-measure` — **artefakt nie jest częścią repo**
  (GH Actions artifact, wygasa, wymaga `gh`/internetu, których ta rola nie ma).

## Różnice w warunkach pomiaru

| | 34,99 (benchmark #17) | 57,3 (pomiar RL #40) |
|---|---|---|
| Polityka | `GreedyPolicy` (heurystyka, bez sieci) | `ModelPolicy` = aktualnie trenowana sieć w danym punkcie treningu |
| Plik/funkcja | `benchmark.py:296` `measure_arm` → `run_set` | `tools/rl_measure.py:45` `evaluate` → ta sama `run_set` |
| Obecność w repo | tak, `main`/HEAD | **nie** — tylko `origin/wayfinder/40-rl-measure`, niescalone |
| Zestaw seedów | `fixed_seeds`, N = 300, z `bench/seeds_fixed.json` | pierwsze 50 z tej samej listy (`eval_seeds=50`) |
| Generator partii treningowych (nie ewaluacyjnych) | n/d (benchmark nie trenuje) | `random.Random(1).randrange(2**31)`, inny niż fixed/rotated |
| `move_cap` | 2000 | 2000 (to samo `cfg["move_cap"]`, przez ten sam `load_config`) |
| Warunek końca partii | `game.done` albo ucięcie `move_cap` — identyczny mechanizm, bo obie ścieżki wołają `run_set`/`play_game` z `benchmark.py` | identyczny (patrz wyżej) |
| Definicja „postawienia" | `game.placements`, z `run_set` | identyczna (ten sam `run_set`) |
| ε podczas pomiaru | 0.0 zawsze | 0.0 tylko na czas `evaluate()` (agent poza tym trenuje z eksploracją) |
| Determinizm | w pełni odtwarzalny (stały kod + stałe seedy) | zależny od czasu ściany zegara runnera → punkt krzywej, do którego agent doszedł, jest za każdym razem inny |

Mechanizm liczenia „postawienia" i warunek końca partii są identyczne (obie ścieżki
przechodzą przez `benchmark.run_set`/`play_game`) — rozjazd nie bierze się stąd. Bierze
się z tego, **jaka polityka** jest mierzona (heurystyka kontra sieć w trakcie nauki),
z ilu seedów (300 vs 50) i z niedeterministycznego czasu treningu.

## Jedno zdanie odpowiedzi

34,99 to miara przeżycia polityki zachłannej w sensie benchmarku #8 (pełny zestaw fixed,
eps=0, ten sam symulator, zapisany rekord); 57,3 to przeżycie zupełnie innej polityki —
niewymienionej z `main` sieci neuronowej w trakcie treningu, na mniejszym podzbiorze
seedów, z kodu pomiarowego, który nigdy nie trafił na `main`.

## Odtworzenie

### 34,99 — odtworzone

```
python benchmark.py --candidate greedy --previous random --issue 17 --out /tmp/repro_17.json
```

Na obecnym HEAD (`ae258b0`) daje `survival_mean = 34.99` dla ramienia `candidate` (greedy),
zestaw fixed — identycznie jak w `bench/43d1e7cf8035132ea52f67865c3473aefeda8741.json`.
(Hash `pieces.py` w nowym przebiegu różni się od zapisanego w tamtym rekordzie — plik
zmienił się od #17 — ale wynik liczbowy `greedy` jest identyczny, więc na wynik przeżycia
to nie wpłynęło.)

### 57,3 — nieodtwarzalne z tego stanowiska

```
git checkout origin/wayfinder/40-rl-measure -- tools/rl_measure.py .github/workflows/rl-measure.yml
python tools/rl_measure.py --train-seconds 1500 --eval-every 300 --out rl-out/result.json
```

Polecenie odtwarza **metodę**, nie liczbę. Powody, dla których 57,3 nie da się odtworzyć
bit w bit z tej roli:

1. Kod mierzący (`tools/rl_measure.py`) nie jest częścią `main`/tej gałęzi — trzeba go
   ręcznie wyciągnąć z niescalonej gałęzi, więc "ten sam pomiar" wymaga już ingerencji
   poza zakresem zadania (bez naprawiania czegokolwiek — patrz `## Odkrycia`).
2. Pomiar trenuje sieć przez czas ścienny (1500 s), a liczba rozegranych partii/kroków do
   danego punktu krzywej zależy od prędkości maszyny — implementer nie ma dostępu do
   uczenia (brak wagi/emulatora nie jest tu problemem, ale powtarzalność sprzętowa już
   tak) i nie uruchamia treningu jako część tego zadania.
3. Artefakt `rl-out/result.json` z oryginalnego przebiegu #40 to artefakt GitHub Actions,
   nie plik w repo — bez `gh`/internetu (czego ta rola nie ma) nie da się go pobrać, żeby
   zweryfikować, któremu dokładnie punktowi krzywej `curve` odpowiada 57,3.

## Odkrycia

- `tools/rl_measure.py` z #40 nigdy nie trafiło na `main` (żyje tylko na
  `origin/wayfinder/40-rl-measure`) — jeśli #40 miało dać trwałe narzędzie pomiarowe, PR
  z tej gałęzi nie został scalony; jeśli miało być jednorazowe, warto to zapisać w #40,
  żeby nikt więcej nie próbował go tam szukać na `main`.
