"""
Siatka koszt/jakość parametrów przeszukania `lookahead-ntuple` (#195).

Mierzy kilka konfiguracji `NTupleLookaheadPolicy` na wagach rekordu
(`ntuple/survival-ad-70k.json`) przez ten sam harness co `benchmark.py`
(`build_policy`, `run_set`, `--jobs`), na seedach **spoza** `bench/seeds_fixed.json`
(sól `siatka-195`, rozłączność sprawdzona jawnie, nie przez brak kolizji na
próbie). Nic tu nie pisze do `bench/*` — oficjalny pomiar liczy osobne zadanie
`rola:bench` (#195: "zmierz i zapisz, nie oceniaj rekordu").

    python3 tools/measure_ntuple_search_grid.py --n-seeds 300 --jobs 4 --out /tmp/grid.json
    python3 tools/measure_ntuple_search_grid.py --n-seeds 50 --jobs 4 --labels "domyslna"

Tryb `--weights` (#216): zamiast siatki konfiguracji wiązki na jednym pliku wag,
mierzy **jeden** ustalony układ wiązki (`--search`, domyślnie `beam=128`) na
**kilku plikach wag** — do porównania przebiegów treningu przy tej samej
polityce testowej. Wiersz 0 jest bazą dla `paired_delta` niezależnie od trybu.
Własna sól (`--seed-salt`) odróżnia pulę seedów od domyślnej `siatka-195`, więc
dwa pomiary tego narzędzia (siatka configów i porównanie wag) nie dzielą puli:

    python3 tools/measure_ntuple_search_grid.py --n-seeds 200 --jobs 4 \\
        --seed-salt pilot-216 --search beam=128 \\
        --weights ntuple/survival-adcgx-8k.json ntuple/survival-adcgx-16k.json \\
                  ntuple/survival-adcgctrl-895k.json ntuple/survival-adcga16-800k.json
"""
import argparse
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import build_policy, load_config, paired_delta, run_set

WEIGHTS = "ntuple/survival-ad-70k.json"
SEED_SALT = "siatka-195"

# (etykieta, kwargs `NTupleLookaheadPolicy` poza domyślnymi; `{}` = spec bez `@...`).
CONFIGS = [
    ("domyslna", {}),
    ("s=4 b=3 in=2x2", dict(samples=4, branch=3, inner_beam=2, inner_depth=2)),
    ("s=8 b=4 in=4x3", dict(samples=8, branch=4, inner_beam=4, inner_depth=3)),
    ("beam=16 s=2 b=2 in=1x1", dict(beam=16, samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("beam=16 s=4 b=4 in=2x2", dict(beam=16, samples=4, branch=4, inner_beam=2, inner_depth=2)),
    ("beam=32 s=16 b=8 in=4x3", dict(beam=32, samples=16, branch=8, inner_beam=4, inner_depth=3)),
    ("beam=24 s=2 b=2 in=1x1", dict(beam=24, samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("beam=32 s=2 b=2 in=1x1", dict(beam=32, samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("beam=48 s=2 b=2 in=1x1", dict(beam=48, samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("beam=64 s=2 b=2 in=1x1", dict(beam=64, samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("beam=96 s=2 b=2 in=1x1", dict(beam=96, samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("beam=128 s=2 b=2 in=1x1", dict(beam=128, samples=2, branch=2, inner_beam=1, inner_depth=1)),
]


def grid_seeds(n, config, salt=SEED_SALT):
    """`n` seedów deterministycznych, jawnie rozłącznych z `config['fixed_seed_file']`."""
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        fixed = set(json.load(fh))
    rng = random.Random(salt)
    pool = rng.sample(range(1, 2**31 - 1), n + len(fixed))
    seeds = [s for s in pool if s not in fixed][:n]
    assert len(seeds) == n, "pula wylosowanych seedów za mała po odjęciu kolizji z fixed"
    return seeds


def spec_for(params, weights=WEIGHTS):
    if not params:
        return "lookahead-ntuple:" + weights
    return "lookahead-ntuple:" + weights + "@" + ",".join(
        "{0}={1}".format(k, v) for k, v in params.items()
    )


def parse_search_params(text):
    """`"beam=128,samples=4"` -> `{"beam": 128, "samples": 4}` (wzór `CONFIGS`)."""
    params = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        key, _, value = part.partition("=")
        params[key] = int(value)
    return params


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-seeds", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--config", default="bench/config.json")
    parser.add_argument("--out", help="ścieżka JSON z wynikami (poza bench/*)")
    parser.add_argument("--labels", nargs="*", help="podzbiór etykiet z CONFIGS")
    parser.add_argument(
        "--weights", nargs="*",
        help="#216: zamiast siatki CONFIGS na jednym pliku wag, mierz --search "
             "(domyślnie beam=128) na każdym z podanych plików wag; wiersz 0 jest bazą delty",
    )
    parser.add_argument("--search", default="beam=128", help="parametry wiązki w trybie --weights")
    parser.add_argument("--seed-salt", default=SEED_SALT, help="własna sól puli seedów")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    seeds = grid_seeds(args.n_seeds, config, salt=args.seed_salt)

    if args.weights:
        search_params = parse_search_params(args.search)
        rows = [(w, w, search_params) for w in args.weights]
    else:
        configs = [c for c in CONFIGS if not args.labels or c[0] in args.labels]
        if args.labels and not configs:
            raise SystemExit("żadna etykieta nie pasuje; dostępne: " + ", ".join(c[0] for c in CONFIGS))
        rows = [(label, WEIGHTS, params) for label, params in configs]

    baseline_scores = None
    results = []
    for label, weights, params in rows:
        spec = spec_for(params, weights)
        policy = build_policy(spec, config)
        t0 = time.time()
        summary = run_set(policy, seeds, config["move_cap"], jobs=args.jobs, spec=spec, config=config)
        dt = time.time() - t0
        scores = summary.pop("scores")
        summary.pop("survivals", None)
        summary.pop("capped_flags", None)
        se = statistics.pstdev(scores) / (len(scores) ** 0.5) if len(scores) > 1 else 0.0
        result = {
            "label": label,
            "spec": spec,
            "n_games": len(seeds),
            "mean": summary["mean"],
            "se": round(se, 2),
            "survival_mean": summary["survival_mean"],
            "s_per_game": round(dt / len(seeds), 4),
            "duration_s": round(dt, 1),
        }
        if baseline_scores is None:
            baseline_scores = scores
        else:
            # Sparowane na tych samych seedach (#102-styl) -- czulsze niz roznica
            # dwoch niezaleznych `se`, bo odejmuje wspolny szum seeda. Wiersz 0
            # (domyslna konfiguracja albo pierwszy plik wag w --weights) jest baza.
            result["vs_baza"] = paired_delta(scores, baseline_scores, config["threshold_pct"])
        print(result)
        results.append(result)

    out = {
        "n_seeds": args.n_seeds, "seed_salt": args.seed_salt, "jobs": args.jobs,
        "weights": args.weights or WEIGHTS, "search": args.search if args.weights else None,
        "results": results,
    }
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
