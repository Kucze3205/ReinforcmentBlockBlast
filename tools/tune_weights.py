"""
CEM (cross-entropy method) do strojenia wag `features.FEATURE_NAMES` (#59).

Populacja wektorów wag losowana z N(mean, std) niezależnie na cechę, elita
wybierana po średnim wyniku z `--games-per-candidate` gier, mean/std
aktualizowane z elity na następną iterację. Bez GPU, bez sieci — sam
symulator (`docs/research/kierunek-algorytmiczny.md`, sekcja (a)).

    python tools/tune_weights.py --policy heuristic --minutes 10
    python tools/tune_weights.py --policy tray --minutes 10 --games-per-candidate 8

Seedy treningowe są losowane rozłącznie z `bench/seeds_fixed.json` (300 seedów
benchmarku, #8) i sprawdzone asercją w `training_seeds()` — pokrywanie się
zbiorów zamieniłoby pomiar `benchmark.py` na pomiar przeuczenia.

Ten sam wektor wag ocenia dwie polityki:

- `heuristic` — `policies.HeuristicPolicy`, jeden pół-ruch w przód.
- `tray` — `policies.TrayPolicy`, wyczerpujące przeszukanie z wiązką całej
  bieżącej tacki (#58). Strojenie musi oceniać kandydatów tą samą polityką,
  którą potem mierzy `benchmark.py` (`--candidate tray`) — inna implementacja
  tacki na czas strojenia dałaby fałszywy wynik (patrz `docs/odzyskanie-cyklu-3.md`).

Job ma limit czasu: pętla CEM sprawdza deadline przed każdym kandydatem (nie
tylko między iteracjami), więc przerwanie w połowie iteracji nie gubi
najlepszego dotychczasowego wyniku — ten jest śledzony per-kandydat, nie
per-iteracja.
"""
import argparse
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import play_game
from features import FEATURE_NAMES
from policies import HeuristicPolicy, TrayPolicy

BENCH_CONFIG = "bench/config.json"
DEFAULT_OUT = "weights.json"
MIN_STD = 0.05


def build_policy(policy_name, weights):
    if policy_name == "heuristic":
        return HeuristicPolicy(weights=weights)
    if policy_name == "tray":
        return TrayPolicy(weights=weights)
    raise ValueError("nieznana polityka: " + policy_name)


def training_seeds(n, bench_seeds, salt=0):
    """`n` seedów, rozłącznych z `bench_seeds` (bench/seeds_fixed.json).

    Rozłączność jest gwarantowana konstrukcją (pomijanie trafień) i dodatkowo
    sprawdzona asercją — #59 wprost tego wymaga, bo pokrywanie się zbiorów
    zamieniłoby pomiar `benchmark.py` w pomiar przeuczenia."""
    forbidden = set(bench_seeds)
    rng = random.Random("tune_weights:{}".format(salt))
    seen, seeds = set(), []
    while len(seeds) < n:
        candidate = rng.randrange(1, 2**31 - 1)
        if candidate in forbidden or candidate in seen:
            continue
        seen.add(candidate)
        seeds.append(candidate)
    assert not (set(seeds) & forbidden), "seedy treningowe pokrywaja sie z bench/seeds_fixed.json"
    return seeds


def evaluate_candidate(policy_name, weights, seeds, move_cap):
    policy = build_policy(policy_name, weights)
    scores = []
    for seed in seeds:
        policy.reset(seed)
        score, _placements, _capped = play_game(policy, seed, move_cap)
        scores.append(score)
    return statistics.mean(scores)


def sample_population(mean, std, size, rng):
    return [tuple(rng.gauss(m, s) for m, s in zip(mean, std)) for _ in range(size)]


def update_distribution(elite_weights):
    n = len(elite_weights[0])
    mean = tuple(statistics.mean(w[i] for w in elite_weights) for i in range(n))
    if len(elite_weights) > 1:
        std = tuple(max(MIN_STD, statistics.pstdev([w[i] for w in elite_weights])) for i in range(n))
    else:
        std = tuple(MIN_STD for _ in range(n))
    return mean, std


def run_cem(policy_name, minutes, games_per_candidate, population_size, elite_n,
            seeds, move_cap, init_mean, init_std, rng, log_fn=None):
    """Zwraca `(best_weights, best_score, log, iteracje, gry_rozegrane)`.

    `best_weights`/`best_score` są aktualizowane po KAŻDYM kandydacie, nie
    dopiero po iteracji — przerwanie deadline'em w połowie iteracji nie gubi
    najlepszego dotychczasowego wyniku (kryterium akceptacji #59)."""
    mean, std = tuple(init_mean), tuple(init_std)
    best_weights, best_score = mean, None
    log = []
    games_played = 0
    deadline = time.monotonic() + minutes * 60.0
    iteration = 0
    while time.monotonic() < deadline:
        iteration += 1
        population = sample_population(mean, std, population_size, rng)
        scored = []
        for candidate in population:
            if time.monotonic() >= deadline:
                break
            score = evaluate_candidate(policy_name, candidate, seeds, move_cap)
            games_played += len(seeds)
            scored.append((candidate, score))
            if best_score is None or score > best_score:
                best_score, best_weights = score, candidate
        if not scored:
            iteration -= 1
            break
        scored.sort(key=lambda t: -t[1])
        elite = scored[: max(1, min(elite_n, len(scored)))]
        elite_weights = [w for w, _ in elite]
        mean, std = update_distribution(elite_weights)
        entry = {
            "iteration": iteration,
            "evaluated": len(scored),
            "mean_score": round(statistics.mean(s for _, s in scored), 2),
            "elite_best_score": round(elite[0][1], 2),
            "mean_vector": [round(v, 4) for v in mean],
        }
        log.append(entry)
        if log_fn:
            log_fn(entry)
    return best_weights, best_score, log, iteration, games_played


def main(argv=None):
    parser = argparse.ArgumentParser(description="CEM: strojenie wag funkcji oceny (#59)")
    parser.add_argument("--policy", choices=["heuristic", "tray"], default="heuristic")
    parser.add_argument("--minutes", type=float, default=10.0)
    parser.add_argument("--games-per-candidate", type=int, default=20)
    parser.add_argument("--population", type=int, default=24)
    parser.add_argument("--elite", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0, help="seed RNG CEM i puli seedow treningowych")
    parser.add_argument("--config", default=BENCH_CONFIG)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        bench_seeds = json.load(fh)[: config["n_seeds"]]

    seeds = training_seeds(args.games_per_candidate, bench_seeds, salt=args.seed)

    init_mean = HeuristicPolicy.DEFAULT_WEIGHTS
    init_std = tuple(max(1.0, abs(w) * 0.5) for w in init_mean)
    rng = random.Random(args.seed)

    def log_fn(entry):
        print(
            "iter {iteration}: srednia={mean_score} elita_best={elite_best_score} "
            "(ocenione {evaluated})".format(**entry),
            file=sys.stderr,
        )

    started = time.time()
    best_weights, best_score, log, iterations, games_played = run_cem(
        args.policy, args.minutes, args.games_per_candidate, args.population,
        args.elite, seeds, config["move_cap"], init_mean, init_std, rng, log_fn,
    )
    duration_s = round(time.time() - started, 1)
    games_per_minute = round(games_played / (duration_s / 60.0), 2) if duration_s > 0 else None

    record = {
        "policy": args.policy,
        "feature_names": list(FEATURE_NAMES),
        "weights": list(best_weights),
        "best_score": round(best_score, 2) if best_score is not None else None,
        "iterations": iterations,
        "duration_s": duration_s,
        "games_played": games_played,
        "games_per_minute": games_per_minute,
        "training_seeds_n": len(seeds),
        "params": {
            "minutes": args.minutes,
            "games_per_candidate": args.games_per_candidate,
            "population": args.population,
            "elite": args.elite,
            "seed": args.seed,
        },
        "init_weights": list(init_mean),
        "log": log,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)

    print("Zapisano {0} ({1} iteracji, {2} gier, {3} gier/min, best={4})".format(
        args.out, iterations, games_played, games_per_minute, record["best_score"]
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
