"""
Prog etapu N-tuple (#203/#209) z kwantyla zapelnienia afterstate'ow.

Rozgrywa partie zachlanna polityka treningu (`tools.train_ntuple._choose_action`,
bez uczenia) na wagach z podanego pliku i zbiera liczbe zajetych komorek
(`ntuple.occupied_count`) kazdego wybranego afterstate'u z kazdej partii, potem
wypisuje kwantyl (domyslnie mediana) tego rozkladu jako sugerowany prog etapu 2.

    python3 tools/measure_ntuple_stage_threshold.py --weights ntuple/survival-adg-200k.json
"""
import argparse
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from ntuple import NTupleValue, REWARD_SURVIVAL, board_bits, occupied_count
from tools.train_ntuple import _choose_action, eval_seeds, load_bench_seeds


def collect_occupied(ntuple, seeds, move_cap, reward):
    occupied = []
    for seed in seeds:
        game = Game(seed=seed)
        steps = 0
        while not game.done and steps < move_cap:
            actions = game.available_actions()
            if not actions:
                break
            action, _idxs, _r, _stage = _choose_action(ntuple, game, actions, reward)
            game.step(action)
            occupied.append(occupied_count(board_bits(game.board)))
            steps += 1
    return occupied


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", required=True, help="plik wag ntuple.NTupleValue (jeden etap)")
    parser.add_argument("--n-games", type=int, default=200)
    parser.add_argument("--move-cap", type=int, default=2000)
    parser.add_argument("--quantile", type=float, default=0.5, help="kwantyl w (0, 1), domyslnie mediana")
    parser.add_argument("--config", default="bench/config.json")
    args = parser.parse_args(argv)

    import json
    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)
    forbidden = load_bench_seeds(config)
    seeds = eval_seeds(args.n_games, forbidden)

    ntuple = NTupleValue.load(args.weights)
    occupied = collect_occupied(ntuple, seeds, args.move_cap, REWARD_SURVIVAL)

    occupied.sort()
    threshold = statistics.quantiles(occupied, n=100, method="inclusive")[
        min(98, max(0, round(args.quantile * 100) - 1))
    ]
    result = {
        "weights": args.weights,
        "n_games": args.n_games,
        "n_afterstates": len(occupied),
        "quantile": args.quantile,
        "min": occupied[0],
        "p25": statistics.quantiles(occupied, n=4, method="inclusive")[0],
        "median": statistics.median(occupied),
        "p75": statistics.quantiles(occupied, n=4, method="inclusive")[2],
        "max": occupied[-1],
        "threshold": int(round(threshold)),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
