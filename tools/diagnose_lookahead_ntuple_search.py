"""
Diagnoza #202: dlaczego glebsze/szersze `samples`/`branch`/`inner_*` w
`lookahead-ntuple` pogarsza wynik, mimo ze `#195` (docs/przeszukanie-siatka.md)
pokazalo, ze samo poszerzenie `beam` (pierwszy poziom) pomaga.

Test klucza: **przeklecie optymalizatora** (optimizer's curse, Smith & Winkler
2006) -- gdy wybiera sie argmax po `branch` kandydatach, kazdy oceniony srednia
z `samples` prob Monte Carlo (plus `max` po `inner_beam` w kazdej probce),
wybrany kandydat jest ukarany podwojnie: to zarowno prawdziwie dobry stan, jak
i ten, ktoremu los/szum estymatora najbardziej sprzyjal. Im wiecej alternatyw
(`branch`) i im wiecej operacji `max` w estymacji kazdej z nich (`inner_beam`,
`inner_depth`), tym wiekszy oczekiwany rozmiar tego zawyzenia.

Metoda: gra sie N partii dwiema konfiguracjami `NTupleLookaheadPolicy` (te same
kwargs co #195: `beam` stale, `samples`/`branch`/`inner_beam`/`inner_depth`
rozne). W kazdej decyzji, w ktorej polityka faktycznie uzywa drugiego poziomu
(`samples > 0` i >= 2 odrebne pierwsze akcje), powtarza sie DOKLADNIE te sama
selekcje co `LookaheadPolicy.act` (te same wywolania `_search`/
`_distinct_first_actions`, na tym samym `self._sampler` -- gra idzie dalej
identycznie jak przy zwyklym `policy.act`), a dla wybranego kandydata dokleja
sie NIEZALEZNA, duza probke ("holdout", osobny `Generator`, nie rusza
`policy._sampler`) tej samej estymacji. Roznica

    obciazenie = wartosc_decyzyjna - wartosc_holdout

mierzy, o ile decyzyjny estymator (maly `samples`) jest optymistyczny wzgledem
nisko-wariancyjnego oszacowania tej samej wielkosci. Osobno liczy sie, jak
czesto akcja wybrana na podstawie proby decyzyjnej roznisie sie od akcji, ktora
wygralaby przy ocenie WSZYSTKICH kandydatow `branch` holdoutem (uczciwe,
maloszumne porownanie) -- to przeklada obciazenie na realna zmiane decyzji.

Nic tu nie pisze do `bench/*`; osobne od `tools/measure_ntuple_search_grid.py`
(ktory mierzy sam wynik koncowy partii, nie mechanizm).

    python3 tools/diagnose_lookahead_ntuple_search.py --n-games 12 --out /tmp/diag202.json
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import build_policy, load_config
from game import Game
from generator import Generator

WEIGHTS = "ntuple/survival-ad-70k.json"
SEED_SALT = "diag-202"

CONFIGS = [
    ("domyslna beam=8 s=2 b=2 in=1x1", {}),
    ("beam=8 s=4 b=3 in=2x2 (anomalia #195)",
     dict(samples=4, branch=3, inner_beam=2, inner_depth=2)),
]


def diag_seeds(n, config):
    """`n` seedow rozlacznych z `bench/seeds_fixed.json`, sol wlasna (rozna od
    `tools/measure_ntuple_search_grid.py`, zeby nie dzielic puli z #195)."""
    import random
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        fixed = set(json.load(fh))
    rng = random.Random(SEED_SALT)
    pool = rng.sample(range(1, 2**31 - 1), n + len(fixed))
    seeds = [s for s in pool if s not in fixed][:n]
    assert len(seeds) == n
    return seeds


def spec_for(params):
    if not params:
        return "lookahead-ntuple:" + WEIGHTS
    return "lookahead-ntuple:" + WEIGHTS + "@" + ",".join(
        "%s=%s" % kv for kv in params.items()
    )


def _mean_best_score(inner_states):
    return max(inner_states, key=lambda c: c["score"])["score"]


def _decision_with_diag(policy, game, actions, holdout_n, holdout_sampler):
    """Odtwarza `LookaheadPolicy.act` krok po kroku, dokladajac holdout dla
    kazdego kandydata `branch`. Zwraca `None`, gdy decyzja nie uzywa drugiego
    poziomu (tak samo jak `act`), albo diagnostyke."""
    pieces0 = tuple(game.pieces)
    depth = sum(1 for p in pieces0 if p is not None)
    if depth == 0 or not actions:
        return None, actions[0] if actions else None

    frontier, _ = policy._search(
        game.board, pieces0, game.combo, game.combo_counter, policy.beam,
        root_actions=actions,
    )
    candidates = policy._distinct_first_actions(frontier)
    if policy.samples <= 0 or len(candidates) < 2:
        best = max(frontier, key=lambda c: c["score"])
        return None, best["first_action"]

    trays = [tuple(policy._sampler.next_pieces()) for _ in range(policy.samples)]
    decision_value, holdout_value = {}, {}
    for state in candidates:
        action = state["first_action"]
        total = 0.0
        for tray in trays:
            inner, _ = policy._search(
                state["board"], tray, state["combo"], state["combo_counter"],
                policy.inner_beam, depth=policy.inner_depth,
            )
            total += _mean_best_score(inner)
        decision_value[action] = state[policy._path_key] + total / len(trays)

        htotal = 0.0
        for _ in range(holdout_n):
            htray = tuple(holdout_sampler.next_pieces())
            inner, _ = policy._search(
                state["board"], htray, state["combo"], state["combo_counter"],
                policy.inner_beam, depth=policy.inner_depth,
            )
            htotal += _mean_best_score(inner)
        holdout_value[action] = state[policy._path_key] + htotal / holdout_n

    decision_best = max(decision_value, key=decision_value.get)
    holdout_best = max(holdout_value, key=holdout_value.get)
    diag = {
        "n_candidates": len(candidates),
        "decision_best_bias": decision_value[decision_best] - holdout_value[decision_best],
        "agree": decision_best == holdout_best,
    }
    return diag, decision_best


def run_config(label, params, seeds, holdout_n, move_cap):
    config = load_config()
    spec = spec_for(params)
    policy = build_policy(spec, config)
    decisions = []
    scores, survivals = [], []
    t0 = time.time()
    for seed in seeds:
        game = Game(seed=seed)
        policy.reset(seed)
        holdout_sampler = Generator(seed="diag-202-holdout:%r" % (seed,))
        placements = 0
        while not game.done:
            if game.placements >= move_cap:
                break
            actions = game.available_actions()
            if not actions:
                break
            diag, action = _decision_with_diag(policy, game, actions, holdout_n, holdout_sampler)
            if diag is not None:
                decisions.append(diag)
            game.step(action)
            placements += 1
        scores.append(game.score)
        survivals.append(game.placements)
    dt = time.time() - t0
    biases = [d["decision_best_bias"] for d in decisions]
    agrees = [d["agree"] for d in decisions]
    return {
        "label": label,
        "spec": spec,
        "n_games": len(seeds),
        "n_decisions_with_search": len(decisions),
        "mean_score": round(statistics.mean(scores), 2),
        "mean_survival": round(statistics.mean(survivals), 2),
        "mean_decision_best_bias": round(statistics.mean(biases), 4) if biases else None,
        "se_decision_best_bias": (
            round(statistics.pstdev(biases) / (len(biases) ** 0.5), 4) if len(biases) > 1 else None
        ),
        "agree_rate_decision_vs_holdout": round(100.0 * sum(agrees) / len(agrees), 2) if agrees else None,
        "duration_s": round(dt, 1),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-games", type=int, default=12)
    parser.add_argument("--holdout-n", type=int, default=24)
    parser.add_argument("--config", default="bench/config.json")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    seeds = diag_seeds(args.n_games, config)
    results = []
    for label, params in CONFIGS:
        result = run_config(label, params, seeds, args.holdout_n, config["move_cap"])
        print(result)
        results.append(result)

    out = {"n_games": args.n_games, "holdout_n": args.holdout_n, "seed_salt": SEED_SALT,
           "weights": WEIGHTS, "results": results}
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
