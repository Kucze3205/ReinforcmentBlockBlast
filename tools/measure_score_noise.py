"""
Mierzy rozrzut (sigma) wyniku pojedynczej partii `TrayPolicy` na seedach
treningowych (#93).

Nie trenuje, nie zmienia wag — czyta `TrayPolicy.DEFAULT_WEIGHTS` i (opcjonalnie)
`weights.json`, rozgrywa po `--n-seeds` gier na zestaw wag i liczy statystyki
rozkładu wyniku pojedynczej gry: srednia, mediana, odchylenie standardowe (sigma),
wspolczynnik zmiennosci (sigma/srednia).

Seedy pochodza z `tools.tune_weights.training_seeds(n, bench_seeds, salt=81)` —
ten sam `salt=81`, ktorego uzyl przebieg CEM w #81, wiec pierwszych 6 seedow
zwroconych przy dowolnym `--n-seeds >= 6` to dokladnie te same 6 seedow, na
ktorych CEM ocenial kandydatow w #81 (sekwencja RNG zalezy tylko od salt, nie od
n). Rozlacznosc z `bench/seeds_fixed.json` jest wymuszona i sprawdzona wewnatrz
`training_seeds()` — tego zadanie nie dotyka.

    python3 tools/measure_score_noise.py --n-seeds 100
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import play_game
from policies import TrayPolicy
from tools.tune_weights import training_seeds

BENCH_CONFIG = "bench/config.json"
DEFAULT_N_SEEDS = 100
SALT = 81  # ten sam salt, co przebieg CEM #81 -> prefiks seedow jest identyczny


def load_bench_seeds(config_path):
    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        bench_seeds = json.load(fh)[: config["n_seeds"]]
    return bench_seeds, config["move_cap"]


def measure(weights, seeds, move_cap):
    """Zwraca liste wynikow pojedynczych gier, po jednej na seed."""
    scores = []
    for seed in seeds:
        policy = TrayPolicy(weights=weights)
        score, _placements, _capped = play_game(policy, seed, move_cap)
        scores.append(score)
    return scores


def summarize(scores):
    mean = statistics.mean(scores)
    median = statistics.median(scores)
    sigma = statistics.pstdev(scores)
    return {
        "n": len(scores),
        "mean": round(mean, 2),
        "median": round(median, 2),
        "sigma": round(sigma, 2),
        "cv": round(sigma / mean, 4) if mean else None,
        "sem_6": round(sigma / (6 ** 0.5), 2),
        "scores": [round(s, 2) for s in scores],
    }


def games_needed_for_delta(sigma, delta):
    """Najmniejsze k takie, ze sigma/sqrt(k) < delta (blad standardowy < roznica)."""
    if delta <= 0:
        return None
    k = 1
    while sigma / (k ** 0.5) >= delta:
        k += 1
        if k > 10 ** 7:
            return None
    return k


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Rozrzut wyniku pojedynczej partii TrayPolicy na seedach treningowych (#93)"
    )
    parser.add_argument("--n-seeds", type=int, default=DEFAULT_N_SEEDS)
    parser.add_argument("--salt", type=int, default=SALT)
    parser.add_argument("--config", default=BENCH_CONFIG)
    parser.add_argument("--weights-file", default="weights.json")
    parser.add_argument("--delta", type=float, default=None,
                         help="roznica srednich do rozdzielenia; jesli podana, liczy games_needed_for_delta")
    parser.add_argument("--out", default=None, help="opcjonalna sciezka do zapisu surowego JSON")
    args = parser.parse_args(argv)

    bench_seeds, move_cap = load_bench_seeds(args.config)
    seeds = training_seeds(args.n_seeds, bench_seeds, salt=args.salt)

    with open(args.weights_file, encoding="utf-8") as fh:
        tuned_weights = tuple(json.load(fh)["weights"])

    weight_sets = {
        "default": TrayPolicy.DEFAULT_WEIGHTS,
        args.weights_file: tuned_weights,
    }

    result = {"n_seeds": len(seeds), "salt": args.salt, "move_cap": move_cap, "sets": {}}
    started = time.time()
    for label, weights in weight_sets.items():
        scores = measure(weights, seeds, move_cap)
        stats = summarize(scores)
        if args.delta:
            stats["games_needed_for_delta"] = games_needed_for_delta(stats["sigma"], args.delta)
        result["sets"][label] = stats
        print(
            "{label}: n={n} srednia={mean} mediana={median} sigma={sigma} "
            "cv={cv} sem6={sem_6}".format(label=label, **stats),
            file=sys.stderr,
        )
    result["duration_s"] = round(time.time() - started, 1)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)

    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "scores"}
                       for k, v in result["sets"].items()}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
