"""
Koszt decyzji `TrayPolicy` w funkcji `beam` i dobór wartości domyślnej (#79).

Dla każdej wartości `beam` gra ten sam, jawnie wypisany zbiór partii (seedy
rozłączne z `bench/seeds_fixed.json`, generowane deterministycznie z osobnej
soli) i mierzy per decyzję (`TrayPolicy.act`):

- czas decyzji (średni i 95. percentyl, ms),
- rozgałęzienie sekwencji faktycznie rozwiniętych (`TrayPolicy.last_expanded`,
  suma kandydatów przed przycięciem do `beam` na każdym poziomie) — do
  porównania z rozgałęzieniem pojedynczego ruchu z `docs/cechy-planszy.md`
  (śr. 39,66, mediana 32, max 170),

oraz per partia: wynik i przeżycie (liczba postawień).

    python3 tools/measure_tray_cost.py
"""
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from policies import TrayPolicy

BEAMS = (1, 2, 4, 8, 16)
N_GAMES = 40
MOVE_CAP = 2000
SEED_SALT = "tray-cost:79"


def measurement_seeds(n, salt=SEED_SALT, fixed_seed_file="bench/seeds_fixed.json"):
    """`n` seedów, deterministyczne, rozłączne z `bench/seeds_fixed.json`."""
    with open(fixed_seed_file, encoding="utf-8") as fh:
        fixed = set(json.load(fh))
    rng = random.Random(salt)
    out = []
    seen = set(fixed)
    while len(out) < n:
        candidate = rng.randrange(1, 2**31 - 1)
        if candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out


def percentile(values, pct):
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def measure(beam, seeds):
    policy = TrayPolicy(beam=beam)
    decision_times = []
    expanded = []
    scores = []
    survivals = []
    for seed in seeds:
        game = Game(seed=seed)
        policy.reset(seed)
        while not game.done:
            if game.placements >= MOVE_CAP:
                break
            actions = game.available_actions()
            if not actions:
                break
            start = time.perf_counter()
            action = policy.act(game, actions)
            decision_times.append(time.perf_counter() - start)
            expanded.append(policy.last_expanded)
            game.step(action)
        scores.append(game.score)
        survivals.append(game.placements)
    return {
        "beam": beam,
        "n_games": len(seeds),
        "n_decisions": len(decision_times),
        "mean_decision_ms": round(1000 * statistics.mean(decision_times), 3),
        "p95_decision_ms": round(1000 * percentile(decision_times, 95), 3),
        "mean_expanded": round(statistics.mean(expanded), 2),
        "median_expanded": round(statistics.median(expanded), 2),
        "max_expanded": max(expanded),
        "mean_score": round(statistics.mean(scores), 2),
        "mean_survival": round(statistics.mean(survivals), 2),
        "wall_s": round(sum(decision_times), 2),
    }


def main():
    seeds = measurement_seeds(N_GAMES)
    print("Seedy pomiaru (%d, rozłączne z bench/seeds_fixed.json):" % len(seeds))
    print(seeds)
    print()
    print(
        "{0:>5} {1:>10} {2:>9} {3:>9} {4:>12} {5:>10} {6:>10} {7:>10}".format(
            "beam", "śr.ms", "p95 ms", "rozgał.", "decyzji", "wynik", "przeżycie", "czas s"
        )
    )
    started = time.time()
    results = []
    for beam in BEAMS:
        r = measure(beam, seeds)
        results.append(r)
        print(
            "{0:>5} {1:>10} {2:>9} {3:>9} {4:>12} {5:>10} {6:>10} {7:>10}".format(
                r["beam"], r["mean_decision_ms"], r["p95_decision_ms"], r["mean_expanded"],
                r["n_decisions"], r["mean_score"], r["mean_survival"], r["wall_s"],
            )
        )
    total = round(time.time() - started, 1)
    print()
    print("N_GAMES=%d partii na wartość beam, %d wartości beam → %d partii łącznie." % (
        N_GAMES, len(BEAMS), N_GAMES * len(BEAMS)
    ))
    print("Całkowity czas pomiaru: %.1f s" % total)
    return results


if __name__ == "__main__":
    main()
