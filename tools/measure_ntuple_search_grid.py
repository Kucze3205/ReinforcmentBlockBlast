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

`--compare-generators` (#221): zamiast siatki parametrów, gra `--spec` (domyślnie
ramię pomiaru #221) dwa razy na tych samych seedach — raz ze starym (ślepym na
planszę) generatorem, raz z nowym (`board.tray_playable`, "do skutku") — i
zwraca średnią, se, przeżycie, `capped_pct` oraz odsetek partii, które skończyły
się tacką nieukładalną **natychmiast po rzucie** (redraw, po którym żadne z 3
świeżych klocków nie da się postawić — patrz `play_game_with_generator`).
`benchmark.py` jest nietknięte przez #221, więc `benchmark.play_game`/`run_set`
zawsze konstruują `Game` domyślnie (nowy generator) i nie da się tam wybrać
starego bez naruszenia budżetu — stąd własna pętla partii niżej, nie `run_set`.

    python3 tools/measure_ntuple_search_grid.py --compare-generators --n-seeds 200 --jobs 4 --move-cap 4000 --out /tmp/gen_cmp.json
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
from game import Game

GENERATOR_COMPARE_SPEC = "lookahead-ntuple:ntuple/survival-adcga16-800k.json@beam=128,samples=0"

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


def grid_seeds(n, config):
    """`n` seedów deterministycznych, jawnie rozłącznych z `config['fixed_seed_file']`."""
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        fixed = set(json.load(fh))
    rng = random.Random(SEED_SALT)
    pool = rng.sample(range(1, 2**31 - 1), n + len(fixed))
    seeds = [s for s in pool if s not in fixed][:n]
    assert len(seeds) == n, "pula wylosowanych seedów za mała po odjęciu kolizji z fixed"
    return seeds


def spec_for(params):
    if not params:
        return "lookahead-ntuple:" + WEIGHTS
    return "lookahead-ntuple:" + WEIGHTS + "@" + ",".join(
        "{0}={1}".format(k, v) for k, v in params.items()
    )


def play_game_with_generator(policy, seed, move_cap, legacy_generator):
    """Jak `benchmark.play_game`, ale z jawnym wyborem generatora (#221) i
    dodatkowym sygnałem "tacka nieukładalna od razu po rzucie".

    `game.round_placement` wraca do 0 wyłącznie przy odświeżeniu tacki
    (`Game.apply_placement`) -- jeśli partia kończy się (`game.done`) zaraz PO
    takim odświeżeniu, bez żadnego postawienia z nowej tacki, to znaczy, że
    świeżo rozdane 3 klocki były niegrywalne natychmiast (dla starego
    generatora zwykłe zdarzenie; dla nowego -- tylko awaryjny limit
    `REJECT_MAX_ATTEMPTS` na planszy bez żadnej grywalnej tacki)."""
    game = Game(seed=seed, legacy_generator=legacy_generator)
    policy.reset(seed)
    if not game.available_actions():
        return game.score, game.placements, False, True
    while not game.done:
        if game.placements >= move_cap:
            return game.score, game.placements, True, False
        actions = game.available_actions()
        if not actions:
            break
        game.step(policy.act(game, actions))
    immediate_unplayable = game.done and game.round_placement == 0
    return game.score, game.placements, False, immediate_unplayable


_cmp_policy = None
_cmp_move_cap = None
_cmp_legacy = None


def _cmp_worker_init(spec, config, move_cap, legacy):
    global _cmp_policy, _cmp_move_cap, _cmp_legacy
    _cmp_policy = build_policy(spec, config)
    _cmp_move_cap = move_cap
    _cmp_legacy = legacy


def _cmp_worker_play(seed):
    return play_game_with_generator(_cmp_policy, seed, _cmp_move_cap, _cmp_legacy)


def compare_generators(spec, config, seeds, move_cap, jobs=1):
    results = {}
    for label, legacy in (("stary", True), ("nowy", False)):
        t0 = time.time()
        if jobs > 1:
            import multiprocessing

            with multiprocessing.Pool(
                jobs, initializer=_cmp_worker_init, initargs=(spec, config, move_cap, legacy)
            ) as pool:
                rows = pool.map(_cmp_worker_play, seeds)
        else:
            policy = build_policy(spec, config)
            rows = [play_game_with_generator(policy, s, move_cap, legacy) for s in seeds]
        dt = time.time() - t0

        scores = [r[0] for r in rows]
        survivals = [r[1] for r in rows]
        capped = [r[2] for r in rows]
        immediate_unplayable = [r[3] for r in rows]
        se = statistics.pstdev(scores) / (len(scores) ** 0.5) if len(scores) > 1 else 0.0
        results[label] = {
            "n_games": len(seeds),
            "mean": round(statistics.mean(scores), 2),
            "se": round(se, 2),
            "survival_mean": round(statistics.mean(survivals), 2),
            "capped_pct": round(100.0 * sum(capped) / len(capped), 2),
            "immediate_unplayable_pct": round(
                100.0 * sum(immediate_unplayable) / len(immediate_unplayable), 2
            ),
            "s_per_game": round(dt / len(seeds), 4),
            "duration_s": round(dt, 1),
        }
        print(label, results[label])
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-seeds", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--config", default="bench/config.json")
    parser.add_argument("--out", help="ścieżka JSON z wynikami (poza bench/*)")
    parser.add_argument("--labels", nargs="*", help="podzbiór etykiet z CONFIGS")
    parser.add_argument(
        "--compare-generators", action="store_true",
        help="#221: stary kontra nowy generator na --spec, zamiast siatki CONFIGS",
    )
    parser.add_argument("--spec", default=GENERATOR_COMPARE_SPEC, help="spec polityki dla --compare-generators")
    parser.add_argument("--move-cap", type=int, help="sufit postawień (domyślnie config['move_cap'])")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    seeds = grid_seeds(args.n_seeds, config)

    if args.compare_generators:
        move_cap = args.move_cap or config["move_cap"]
        results = compare_generators(args.spec, config, seeds, move_cap, jobs=args.jobs)
        out = {
            "n_seeds": args.n_seeds, "seed_salt": SEED_SALT, "jobs": args.jobs,
            "spec": args.spec, "move_cap": move_cap, "results": results,
        }
        if args.out:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(out, fh, indent=2, ensure_ascii=False)
        return 0

    configs = [c for c in CONFIGS if not args.labels or c[0] in args.labels]
    if args.labels and not configs:
        raise SystemExit("żadna etykieta nie pasuje; dostępne: " + ", ".join(c[0] for c in CONFIGS))

    baseline_scores = None
    results = []
    for label, params in configs:
        spec = spec_for(params)
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
        if not params:
            baseline_scores = scores
        elif baseline_scores is not None:
            # Sparowane na tych samych seedach (#102-styl) -- czulsze niz roznica
            # dwoch niezaleznych `se`, bo odejmuje wspolny szum seeda.
            result["vs_domyslna"] = paired_delta(scores, baseline_scores, config["threshold_pct"])
        print(result)
        results.append(result)

    out = {
        "n_seeds": args.n_seeds, "seed_salt": SEED_SALT, "jobs": args.jobs,
        "weights": WEIGHTS, "results": results,
    }
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
