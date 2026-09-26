"""
Koszt i jakość `LookaheadPolicy` w funkcji parametrów przeszukania (#92).

Ten sam harness i **te same seedy** co `tools/measure_tray_cost.py` (funkcja
`measurement_seeds`, sól `"tray-cost:79"`, rozłączne z `bench/seeds_fixed.json`),
żeby tabela z `docs/lookahead.md` dała się położyć obok tabel z #79 i #88.

Mierzy per decyzję czas (`time.perf_counter`) i rozgałęzienie (`last_expanded`,
suma kandydatów rozwiniętych na obu poziomach), per partia wynik i przeżycie.
Z tego wylicza **szacowany czas jednego ramienia benchmarku** (600 partii =
300 stałych + 300 rotowanych seedów) — liczba, która decyduje, czy polityka w
ogóle zmieści się w limicie 3600 s na polecenie (`.github/loop/loop.py:408`).

    python3 tools/measure_lookahead_cost.py            # pełna tabela, 40 partii na wiersz
    python3 tools/measure_lookahead_cost.py 8          # szybki przebieg, 8 partii na wiersz
    python3 tools/measure_lookahead_cost.py 100 "s=2 b=2 in=1x1"   # wybrane wiersze, po etykiecie

Pierwszy argument to liczba partii na wiersz; kolejne to **dokładne** etykiety z
`CONFIGS` (bez nich mierzone są wszystkie wiersze). Seedy powyżej 40 są dalszym
ciągiem tej samej deterministycznej sekwencji, więc 40-seedowa tabela jest
prefiksem 100-seedowej.
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from policies import LookaheadPolicy, TrayPolicy
from tools.measure_tray_cost import MOVE_CAP, N_GAMES, measurement_seeds, percentile

ARM_GAMES = 600  # 300 seedów stałych + 300 rotowanych, patrz bench/config.json

# (etykieta, fabryka polityki). Wiersz odniesienia to czysta TrayPolicy.
CONFIGS = (
    ("tray beam=8 (odniesienie)", lambda: TrayPolicy(beam=8)),
    ("s=2 b=2 in=1x1", lambda: LookaheadPolicy(samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("s=3 b=3 in=1x1", lambda: LookaheadPolicy(samples=3, branch=3, inner_beam=1, inner_depth=1)),
    ("s=3 b=3 in=1x1 kara=0", lambda: LookaheadPolicy(
        samples=3, branch=3, inner_beam=1, inner_depth=1, death_penalty=0.0)),
    ("s=4 b=4 in=1x1", lambda: LookaheadPolicy(samples=4, branch=4, inner_beam=1, inner_depth=1)),
    ("s=3 b=3 in=2x2", lambda: LookaheadPolicy(samples=3, branch=3, inner_beam=2, inner_depth=2)),
    ("s=3 b=3 in=1x3", lambda: LookaheadPolicy(samples=3, branch=3, inner_beam=1, inner_depth=3)),
    ("beam=4 s=3 b=3 in=1x1", lambda: LookaheadPolicy(
        beam=4, samples=3, branch=3, inner_beam=1, inner_depth=1)),
    # Drugi przebieg: dostrojenie wokół zwycięzcy pierwszego (s=2 b=2 in=1x1).
    ("s=1 b=2 in=1x1", lambda: LookaheadPolicy(samples=1, branch=2, inner_beam=1, inner_depth=1)),
    ("s=3 b=2 in=1x1", lambda: LookaheadPolicy(samples=3, branch=2, inner_beam=1, inner_depth=1)),
    ("s=2 b=3 in=1x1", lambda: LookaheadPolicy(samples=2, branch=3, inner_beam=1, inner_depth=1)),
    ("s=2 b=2 in=1x1 kara=0", lambda: LookaheadPolicy(
        samples=2, branch=2, inner_beam=1, inner_depth=1, death_penalty=0.0)),
    ("s=2 b=2 in=1x1 kara=-50", lambda: LookaheadPolicy(
        samples=2, branch=2, inner_beam=1, inner_depth=1, death_penalty=-50.0)),
    ("s=2 b=2 in=1x1 kara=-500", lambda: LookaheadPolicy(
        samples=2, branch=2, inner_beam=1, inner_depth=1, death_penalty=-500.0)),
    ("beam=6 s=2 b=2 in=1x1", lambda: LookaheadPolicy(
        beam=6, samples=2, branch=2, inner_beam=1, inner_depth=1)),
    ("beam=12 s=2 b=2 in=1x1", lambda: LookaheadPolicy(
        beam=12, samples=2, branch=2, inner_beam=1, inner_depth=1)),
)


def measure(label, make_policy, seeds):
    policy = make_policy()
    decision_times, expanded, scores, survivals = [], [], [], []
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
    mean_ms = 1000 * statistics.mean(decision_times)
    mean_survival = statistics.mean(survivals)
    return {
        "label": label,
        "n_games": len(seeds),
        "n_decisions": len(decision_times),
        "mean_decision_ms": round(mean_ms, 3),
        "p95_decision_ms": round(1000 * percentile(decision_times, 95), 3),
        "mean_expanded": round(statistics.mean(expanded), 2),
        "mean_score": round(statistics.mean(scores), 2),
        "mean_survival": round(mean_survival, 2),
        # Ekstrapolacja jak w docs/przeszukanie-tacki.md: czas decyzji × decyzji
        # na partię × 600 partii. To jest liczba porównywana z limitem 1800 s.
        "arm_600_s": round(mean_ms / 1000.0 * mean_survival * ARM_GAMES, 1),
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    n_games = int(argv[0]) if argv else N_GAMES
    wanted = argv[1:]
    configs = [c for c in CONFIGS if not wanted or c[0] in wanted]
    if wanted and not configs:
        raise SystemExit("żadna etykieta nie pasuje; dostępne:\n  "
                         + "\n  ".join(c[0] for c in CONFIGS))
    # `measurement_seeds` dokłada seedy w ustalonej kolejności, więc prefiks 40
    # sztuk jest ten sam co w #79/#88 niezależnie od tego, ile ich zamówimy.
    seeds = measurement_seeds(n_games)
    print("Seedy pomiaru (%d, prefiks %d wspólny z tools/measure_tray_cost.py):"
          % (len(seeds), min(n_games, N_GAMES)))
    print(seeds)
    print()
    header = "{0:<26} {1:>9} {2:>9} {3:>9} {4:>9} {5:>10} {6:>12}".format(
        "konfiguracja", "śr.ms", "p95 ms", "rozgał.", "wynik", "przeżycie", "ramię 600 s"
    )
    print(header)
    print("-" * len(header))
    started = time.time()
    results = []
    for label, make_policy in configs:
        r = measure(label, make_policy, seeds)
        results.append(r)
        print("{0:<26} {1:>9} {2:>9} {3:>9} {4:>9} {5:>10} {6:>12}".format(
            r["label"], r["mean_decision_ms"], r["p95_decision_ms"], r["mean_expanded"],
            r["mean_score"], r["mean_survival"], r["arm_600_s"],
        ))
    print()
    print("%d partii na wiersz, %d wierszy. Całkowity czas pomiaru: %.1f s"
          % (len(seeds), len(configs), time.time() - started))
    return results


if __name__ == "__main__":
    main()
