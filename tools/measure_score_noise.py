"""
Mierzy rozrzut (sigma) wyniku i przezycia pojedynczej partii dla podanej
polityki i podanych wag, na seedach treningowych (#101).

Nie trenuje, nie zmienia wag, nie dotyka CEM — czyta wektor wag z pliku (albo
uzywa domyslnych wag polityki) i rozgrywa `--n-games` partii, kazda na osobnym
seedzie z `tools.tune_weights.training_seeds()` (rozlacznym z
`bench/seeds_fixed.json`, ten sam podzial, ktorego uzywa CEM). Wypisuje dla
wyniku i dla przezycia: srednia, odchylenie standardowe, wspolczynnik
zmiennosci (sigma/srednia) i blad standardowy sredniej (sigma/sqrt(n)); oraz
korelacje Pearsona i Spearmana miedzy wynikiem a przezyciem, partia po partii.

    python3 tools/measure_score_noise.py --policy lookahead --weights-file weights.json --n-games 150
    python3 tools/measure_score_noise.py --policy tray --weights-file weights.json --n-games 150 --out /tmp/tray.json

`lookahead` kosztuje ok. 2,0 s/partia na `weights.json` (docs/lookahead.md) —
150 partii to okolo 5 minut.

`--seed-file` (#112) podmienia zrodlo seedow: zamiast `training_seeds()`
(seedy treningowe, rozlaczne z benchmarkiem) bierze pierwsze `--n-games`
seedow wprost z podanego pliku-listy, np. `bench/seeds_fixed.json` — te same
300 seedow, na ktorych liczy `benchmark.py`. `--series-out` zrzuca serie
partia-po-partii `(seed, score, survival, capped)` do JSON-a, obok podsumowania
z `--out`:

    python3 tools/measure_score_noise.py --policy lookahead --weights-file weights.json \\
        --n-games 300 --seed-file bench/seeds_fixed.json --series-out docs/data/serie-300-lookahead.json
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import play_game
from policies import HeuristicPolicy, LookaheadPolicy, TrayPolicy
from tools.tune_weights import training_seeds

BENCH_CONFIG = "bench/config.json"
DEFAULT_SALT = 101

POLICY_CLASSES = {
    "heuristic": HeuristicPolicy,
    "tray": TrayPolicy,
    "lookahead": LookaheadPolicy,
}


def load_bench_seeds(config_path):
    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        bench_seeds = json.load(fh)[: config["n_seeds"]]
    return bench_seeds, config["move_cap"]


def load_weights(path):
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        return tuple(json.load(fh)["weights"])


def play_series(policy_name, weights, seeds, move_cap):
    """Zwraca `(scores, survivals, capped)`, po jednej trojce na seed.

    `capped` mowi, czy partia zostala ucieta sufitem ruchow (#112: taka partia
    nie jest zakonczona i kubelki dlugosci partii musza to odroznic).
    """
    policy_cls = POLICY_CLASSES[policy_name]
    policy = policy_cls(weights=weights) if weights is not None else policy_cls()
    scores, survivals, capped = [], [], []
    for seed in seeds:
        policy.reset(seed)
        score, placements, was_capped = play_game(policy, seed, move_cap)
        scores.append(score)
        survivals.append(placements)
        capped.append(was_capped)
    return scores, survivals, capped


def load_seeds_from_file(path, n_games):
    """Seedy wprost z pliku (np. `bench/seeds_fixed.json`), nie z `training_seeds()`.

    Plik jest lista (#112, jak `bench/seeds_fixed.json`), nie slownikiem.
    `n_games` obcina liste tak, jak `benchmark.py` obcina `n_seeds` — zeby
    wywolanie z domyslnym `--n-games` nie zaladowalo cichutko calego pliku.
    """
    with open(path, encoding="utf-8") as fh:
        seeds = json.load(fh)
    if not isinstance(seeds, list):
        raise ValueError(path + ": oczekiwano listy seedow, nie slownika")
    return seeds[:n_games] if n_games else seeds


def dump_series(path, seeds, scores, survivals, capped):
    """Zrzut partia-po-partii do JSON-a: `(seed, wynik, postawienia, ucieta)` (#112)."""
    rows = [
        {"seed": seed, "score": score, "survival": survival, "capped": bool(was_capped)}
        for seed, score, survival, was_capped in zip(seeds, scores, survivals, capped)
    ]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)


def summarize(values):
    mean = statistics.mean(values)
    sigma = statistics.pstdev(values)
    sem = sigma / (len(values) ** 0.5)
    return {
        "n": len(values),
        "mean": round(mean, 2),
        "sigma": round(sigma, 2),
        "cv": round(sigma / mean, 4) if mean else None,
        "sem": round(sem, 2),
        "sem_pct_of_mean": round(100.0 * sem / mean, 2) if mean else None,
    }


def _ranks(values):
    """Rangi srednie (remisy dostaja srednia rang) — do korelacji Spearmana."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs, ys):
    return statistics.correlation(_ranks(xs), _ranks(ys))


def games_per_candidate_table(sigma, mean, counts=(6, 16, 32, 64)):
    """SEM wyrazony w % sredniej i najmniejsza roznica miedzy dwoma niezaleznie
    ocenianymi kandydatami rozroznialna na poziomie 2 bledow standardowych.

    Zakladane: dwaj kandydaci o tej samej sigma, ocenieni na NIEZALEZNYCH
    proba ch (nie CRN/parowanie) — SE roznicy srednich to sqrt(2)*SEM, wiec
    prog wykrywalnosci to 2*sqrt(2)*SEM. Parowanie (te same seedy obu
    kandydatom, jak dzis w tune_weights.py) dalaby mniejszy prog przy
    dodatniej korelacji miedzy kandydatami — tego tutaj nie mierzymy.
    """
    rows = []
    for n in counts:
        sem = sigma / (n ** 0.5)
        sem_pct = 100.0 * sem / mean if mean else None
        min_diff = 2.0 * (2.0 ** 0.5) * sem
        min_diff_pct = 100.0 * min_diff / mean if mean else None
        rows.append({
            "n_games": n,
            "sem": round(sem, 2),
            "sem_pct_of_mean": round(sem_pct, 2) if sem_pct is not None else None,
            "min_detectable_diff": round(min_diff, 2),
            "min_detectable_diff_pct": round(min_diff_pct, 2) if min_diff_pct is not None else None,
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sigma wyniku i przezycia partii, na seedach treningowych (#101)"
    )
    parser.add_argument("--policy", choices=sorted(POLICY_CLASSES), required=True)
    parser.add_argument("--weights-file", default=None,
                         help="plik z kluczem 'weights' (np. weights.json); brak = wagi domyslne polityki")
    parser.add_argument("--n-games", type=int, default=150)
    parser.add_argument("--salt", type=int, default=DEFAULT_SALT,
                         help="sol training_seeds(); ta sama sol na obu politykach daje te same seedy")
    parser.add_argument("--seed-file", default=None,
                         help="plik z lista seedow (np. bench/seeds_fixed.json); pomija training_seeds() "
                              "i --salt, bierze pierwsze --n-games seedow wprost z pliku")
    parser.add_argument("--config", default=BENCH_CONFIG)
    parser.add_argument("--out", default=None, help="opcjonalna sciezka do zapisu surowego JSON")
    parser.add_argument("--series-out", default=None,
                         help="opcjonalna sciezka do zrzutu serii partia-po-partii (seed, score, survival, capped)")
    args = parser.parse_args(argv)

    bench_seeds, move_cap = load_bench_seeds(args.config)
    if args.seed_file:
        seeds = load_seeds_from_file(args.seed_file, args.n_games)
    else:
        seeds = training_seeds(args.n_games, bench_seeds, salt=args.salt)
    weights = load_weights(args.weights_file)

    scores, survivals, capped = play_series(args.policy, weights, seeds, move_cap)

    result = {
        "policy": args.policy,
        "weights_file": args.weights_file,
        "n_games": len(seeds),
        "salt": args.salt if not args.seed_file else None,
        "seed_file": args.seed_file,
        "score": summarize(scores),
        "survival": summarize(survivals),
        "pearson_score_survival": round(statistics.correlation(scores, survivals), 4),
        "spearman_score_survival": round(spearman(scores, survivals), 4),
        "games_per_candidate": {
            "score": games_per_candidate_table(summarize(scores)["sigma"], summarize(scores)["mean"]),
            "survival": games_per_candidate_table(summarize(survivals)["sigma"], summarize(survivals)["mean"]),
        },
    }
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
    if args.series_out:
        dump_series(args.series_out, seeds, scores, survivals, capped)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
