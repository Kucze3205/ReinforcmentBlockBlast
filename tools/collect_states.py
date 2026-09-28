"""
`tools/collect_states.py` — zbiera plansze napotkane w trakcie gry polityką
`lookahead-ntuple:<wagi>` na seedach treningowych, do `--start-states`
`tools/train_ntuple.py` (#168).

Motywacja: trening zawsze startuje z pustej planszy i uczy się na partiach
polityki zachłannej, która żyje ~90-95 postawień — przeszukiwanie
`lookahead-ntuple` z tą samą oceną żyje znacznie dłużej (rekord `bench/record.json`),
więc trening prawie nie widzi stanów późnej gry, w których przeszukiwanie
naprawdę gra i umiera. To narzędzie gra partie tą polityką i zapisuje napotkane
plansze, żeby trening mógł od czasu do czasu zacząć od jednej z nich.

    python tools/collect_states.py --weights ntuple/survival-ad-70k.json \\
        --episodes 200 --out ntuple/start-states-ad70k.json --jobs 4

Seedy partii zbierania są deterministyczne z `(--seed, numer_partii)` i
rozłączne z `bench/seeds_fixed.json` — ten sam wzór rozłączności co
`tools/train_ntuple.episode_seed`, ale własna przestrzeń nazw (kolekcja i
trening to osobne przebiegi, nie muszą być rozłączne między sobą).

`--sample-every N` zapisuje planszę co `N`-te postawienie (domyślnie każde);
`--jobs N` liczy partie w N procesach, jak `benchmark.py --jobs` — wynik
bitowo ten sam co `--jobs 1`, bo `Pool.map` zwraca wyniki w kolejności zadań.

Plik wyjściowy (JSON): `{"format": 1, "weights": <plik>, "n_games": <n>,
"seed": <seed>, "sample_every": <n>, "move_cap": <n>, "boards": [{"board":
<siatka 8x8>, "placement": <numer postawienia w partii>, "game_seed": <seed
partii>}, ...]}`. `tools/train_ntuple.load_start_states` czyta z niego same
siatki.
"""
import argparse
import json
import multiprocessing
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import build_policy, load_config
from game import Game

BENCH_CONFIG = "bench/config.json"
DEFAULT_OUT = "start-states.json"
DEFAULT_SAMPLE_EVERY = 1
NTUPLE_POLICY_PREFIX = "lookahead-ntuple"

# Ten sam zakres co seedy treningu/benchmarku (`tools/train_ntuple.py`).
SEED_HIGH = 2**31 - 1


def load_bench_seeds(config):
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        return set(json.load(fh)[: config["n_seeds"]])


def episode_seed(seed, episode_number, forbidden):
    """Seed partii zbierania: deterministyczny z `(seed, episode_number)`,
    rozłączny z `bench/seeds_fixed.json` — ta sama zasada co
    `tools.train_ntuple.episode_seed`, własna przestrzeń nazw (`collect_states:`),
    bo kolekcja jest osobnym przebiegiem od treningu."""
    salt = 0
    while True:
        candidate = random.Random(
            "collect_states:{0}:{1}:{2}".format(seed, episode_number, salt)
        ).randrange(1, SEED_HIGH)
        if candidate not in forbidden:
            return candidate
        salt += 1


def play_and_collect(policy, seed, move_cap, sample_every):
    """Jedna partia z gotową `policy` (`lookahead-ntuple:<plik>` z `build_policy`);
    zbiera plansze napotkane co `sample_every` postawień. Zwraca `(plansze, liczba
    postawień)`."""
    game = Game(seed=seed)
    policy.reset(seed)
    boards = []
    while not game.done:
        if game.placements >= move_cap:
            break
        actions = game.available_actions()
        if not actions:
            break
        if game.placements % sample_every == 0:
            boards.append({
                "board": [row[:] for row in game.board.grid],
                "placement": game.placements,
                "game_seed": seed,
            })
        game.step(policy.act(game, actions))
    return boards, game.placements


# Globalne, jak w benchmark.py: `Pool` buduje polityke raz na proces roboczy,
# nie raz na partię — `load_ntuple_weights` czytalby plik wag z dysku przy
# kazdej partii, gdyby polityke budowac w `_worker_play`.
_worker_policy = None
_worker_move_cap = None
_worker_sample_every = None


def _worker_init(spec, config, move_cap, sample_every):
    global _worker_policy, _worker_move_cap, _worker_sample_every
    _worker_policy = build_policy(spec, config)
    _worker_move_cap = move_cap
    _worker_sample_every = sample_every


def _worker_play(seed):
    return play_and_collect(_worker_policy, seed, _worker_move_cap, _worker_sample_every)


def collect(spec, config, seeds, move_cap, sample_every, jobs=1):
    if jobs > 1:
        with multiprocessing.Pool(
            jobs, initializer=_worker_init, initargs=(spec, config, move_cap, sample_every)
        ) as pool:
            results = pool.map(_worker_play, seeds)
    else:
        policy = build_policy(spec, config)
        results = [play_and_collect(policy, seed, move_cap, sample_every) for seed in seeds]

    boards = []
    lengths = []
    for game_boards, placements in results:
        boards.extend(game_boards)
        lengths.append(placements)
    return boards, lengths


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Zbiera plansze z partii lookahead-ntuple na seedach treningowych (#168)"
    )
    parser.add_argument("--weights", required=True, help="plik wag ntuple.NTupleValue")
    parser.add_argument("--episodes", type=int, required=True, help="liczba partii do rozegrania")
    parser.add_argument("--seed", type=int, default=0, help="seed bazowy seedow partii zbierania")
    parser.add_argument("--move-cap", type=int, default=None, help="sufit postawien na partie")
    parser.add_argument(
        "--sample-every", type=int, default=DEFAULT_SAMPLE_EVERY,
        help="co ile postawien zapisac plansze (domyslnie kazde postawienie)",
    )
    parser.add_argument("--out", default=DEFAULT_OUT, help="plik wyjsciowy JSON")
    parser.add_argument(
        "--jobs", type=int, default=1,
        help="partie liczone w N procesach; wynik bitowo ten sam co --jobs 1",
    )
    parser.add_argument("--config", default=BENCH_CONFIG)
    args = parser.parse_args(argv)

    if args.sample_every < 1:
        parser.error("--sample-every musi byc >= 1")

    config = load_config(args.config)
    if args.move_cap is None:
        args.move_cap = config["move_cap"]

    forbidden = load_bench_seeds(config)
    spec = NTUPLE_POLICY_PREFIX + ":" + args.weights
    seeds = [episode_seed(args.seed, ep, forbidden) for ep in range(1, args.episodes + 1)]

    boards, lengths = collect(spec, config, seeds, args.move_cap, args.sample_every, jobs=args.jobs)

    data = {
        "format": 1,
        "weights": args.weights,
        "n_games": args.episodes,
        "seed": args.seed,
        "sample_every": args.sample_every,
        "move_cap": args.move_cap,
        "boards": boards,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        # Bez wciecia: przy dziesiatkach tysiecy plansz `indent=2` pompuje plik
        # ~4x bez zysku dla czytelnosci (plik jest wejsciem dla load_start_states,
        # nie do recznej lektury).
        json.dump(data, fh)

    print(
        "Zebrano {0} plansz z {1} partii (dlugosc partii: srednia={2}, mediana={3}) -> {4}".format(
            len(boards), len(lengths),
            round(statistics.mean(lengths), 2) if lengths else 0.0,
            round(statistics.median(lengths), 2) if lengths else 0.0,
            args.out,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
