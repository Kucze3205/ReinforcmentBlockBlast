"""
Czy smierc rekordu dalo sie ominac jedna tacke wczesniej (#236).

Pomiar diagnostyczny, nic nie zmienia w grze ani w polityce. Wlasna petla
rozgrywki (szkielet: `tools/measure_terminal_state.py`), bez sieci i bez
emulatora, nic w tle.

    python3 tools/measure_death_avoidability.py --jobs 4 --n-games 100 \\
        --policy lookahead-ntuple:ntuple/survival-adcga16-800k.json@beam=128,samples=0 \\
        --out docs/data/death-avoidability-100.json

Dla kazdej smierci (partia, ktora nie dobila do sufitu ruchow):
  (a) chybienie wyszukiwania: czy tacka smierci (stan planszy na jej poczatku)
      dawala sie ulozyc w calosci -- przeglad wyczerpujacy, kolejnosci x pozycje;
  (b) unikalna o tacke: z planszy na poczatku POPRZEDNIEJ tacki wszystkie pelne
      ulozenia tamtej tacki (plansze koncowe bez duplikatow); dla kazdej
      losujemy nastepna tacke tak jak gra (kopia stanu `Game`/generatora, RNG w
      tym samym stanie, generator widzi plansze) i sprawdzamy, czy da sie ja
      ulozyc w calosci. Rangi wg oceny N-tuple polityki (1 = najlepsza).
"""
import argparse
import collections
import copy
import json
import multiprocessing
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import benchmark
from board import Board
from game import Game
from generator import Generator

BENCH_CONFIG = "bench/config.json"
SAMPLE_LIMIT = 5000
SAMPLE_SEED = 236

W = Board.WIDTH
H = Board.HEIGHT
ROW_MASKS = [((1 << W) - 1) << (y * W) for y in range(H)]
COL_MASKS = [sum(1 << (y * W + x) for y in range(H)) for x in range(W)]

_placements_cache = {}


def grid_to_bits(grid):
    bits = 0
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell:
                bits |= 1 << (y * W + x)
    return bits


def bits_to_grid(bits):
    return [[(bits >> (y * W + x)) & 1 for x in range(W)] for y in range(H)]


def shape_masks(shape):
    """Maski bitowe wszystkich pozycji ksztaltu na planszy."""
    key = tuple(tuple(row) for row in shape)
    cached = _placements_cache.get(key)
    if cached is None:
        cached = []
        for y in range(H - len(shape) + 1):
            for x in range(W - len(shape[0]) + 1):
                mask = 0
                for dy, row in enumerate(shape):
                    for dx, cell in enumerate(row):
                        if cell:
                            mask |= 1 << ((y + dy) * W + x + dx)
                cached.append(mask)
        _placements_cache[key] = cached
    return cached


def place_and_clear(bits, mask):
    bits |= mask
    clear = 0
    for rm in ROW_MASKS:
        if bits & rm == rm:
            clear |= rm
    for cm in COL_MASKS:
        if bits & cm == cm:
            clear |= cm
    return bits & ~clear


def tray_solvable(bits, shapes):
    """Czy wszystkie `shapes` da sie ulozyc w jakiejs kolejnosci (przeglad wyczerpujacy)."""
    masks = [shape_masks(s) for s in shapes]
    seen = set()

    def dfs(b, remaining):
        if not remaining:
            return True
        if (b, remaining) in seen:
            return False
        seen.add((b, remaining))
        for i in range(len(masks)):
            if not remaining & (1 << i):
                continue
            for m in masks[i]:
                if not b & m and dfs(place_and_clear(b, m), remaining & ~(1 << i)):
                    return True
        return False

    return dfs(bits, (1 << len(shapes)) - 1)


def tray_final_boards(bits, shapes):
    """Zbior plansz koncowych (jako bity) po ulozeniu wszystkich `shapes` w calosci."""
    masks = [shape_masks(s) for s in shapes]
    finals = set()
    seen = set()

    def dfs(b, remaining):
        if not remaining:
            finals.add(b)
            return
        if (b, remaining) in seen:
            return
        seen.add((b, remaining))
        for i in range(len(masks)):
            if not remaining & (1 << i):
                continue
            for m in masks[i]:
                if not b & m:
                    dfs(place_and_clear(b, m), remaining & ~(1 << i))

    dfs(bits, (1 << len(shapes)) - 1)
    return finals


def next_tray_like_game(game, grid):
    """Nastepna tacka, jaka wylosowalaby gra `game` na planszy `grid`.

    Nie dotyka `game`: generator to swiezy obiekt z kopia stanu RNG, plansza
    to osobna kopia siatki. Wolane na migawce `Game` z poczatku tacki (RNG
    nietkniety miedzy losowaniem tacki a nastepnym losowaniem).
    """
    board = Board()
    board.grid = [row[:] for row in grid]
    gen = Generator(seed=None, board=board, legacy=game.generator.legacy)
    gen.rng.setstate(game.generator.rng.getstate())
    return gen.next_pieces()


def analyze_death(start_prev, start_death, value_fn, rng_seed=SAMPLE_SEED, sample_limit=SAMPLE_LIMIT):
    """(a) i (b) dla jednej smierci.

    `start_prev`: migawka `Game` na poczatku poprzedniej tacki (albo `None`),
    `start_death`: migawka `Game` na poczatku tacki smierci. `value_fn(grid)` to
    ocena planszy; wieksza = lepsza.
    """
    death_bits = grid_to_bits(start_death.board.grid)
    death_shapes = [p.shape for p in start_death.pieces if p is not None]
    result = {"a_solvable": tray_solvable(death_bits, death_shapes)}
    if start_prev is None:
        result["b"] = None
        return result

    prev_shapes = [p.shape for p in start_prev.pieces if p is not None]
    finals = tray_final_boards(grid_to_bits(start_prev.board.grid), prev_shapes)
    chosen_bits = death_bits
    n_total = len(finals)
    sampled = n_total > sample_limit
    if sampled:
        chosen_in = chosen_bits in finals
        pool = sorted(finals - {chosen_bits})
        keep = random.Random(rng_seed).sample(pool, sample_limit - (1 if chosen_in else 0))
        finals = set(keep) | ({chosen_bits} if chosen_in else set())
    finals = sorted(finals)

    values = {b: value_fn(bits_to_grid(b)) for b in finals}
    survivors = []
    for b in finals:
        tray = next_tray_like_game(start_prev, bits_to_grid(b))
        if tray_solvable(b, [p.shape for p in tray]):
            survivors.append(b)

    def rank(v):
        return 1 + sum(1 for b in finals if values[b] > v)

    result["b"] = {
        "n_final_boards": n_total,
        "sampled": sampled,
        "n_evaluated": len(finals),
        "n_survive": len(survivors),
        "survive_frac": len(survivors) / len(finals) if finals else 0.0,
        "any_survive": bool(survivors),
        "chosen_in_set": chosen_bits in values,
        "chosen_rank": rank(values[chosen_bits]) if chosen_bits in values else None,
        "best_survivor_rank": rank(max(values[b] for b in survivors)) if survivors else None,
    }
    return result


def play_and_analyze(policy, seed, move_cap):
    """Jedna partia -> rekord. Migawki `Game` z poczatku dwoch ostatnich tacek."""
    policy.reset(seed)
    game = Game(seed=seed)
    starts = collections.deque(maxlen=2)
    while not game.done:
        if game.placements >= move_cap:
            break
        actions = game.available_actions()
        if not actions:
            break
        if game.round_placement == 0:
            starts.append(copy.deepcopy(game))
        game.step(policy.act(game, actions))

    record = {"seed": seed, "placements": game.placements, "score": game.score,
              "capped": game.placements >= move_cap and not game.done}
    if record["capped"]:
        return record
    if game.round_placement == 0:
        starts.append(copy.deepcopy(game))  # smierc zaraz po wylosowaniu tacki
    if not starts:
        return record
    start_death = starts[-1]
    start_prev = starts[-2] if len(starts) == 2 else None
    ntuple = policy.ntuple

    def value_fn(grid):
        b = Board()
        b.grid = grid
        return ntuple.value(b)

    record.update(analyze_death(start_prev, start_death, value_fn))
    return record


def summarize(records):
    deaths = [r for r in records if not r.get("capped") and "a_solvable" in r]
    with_b = [r for r in deaths if r["b"] is not None]
    survivable = [r for r in with_b if r["b"]["any_survive"]]
    a_miss = sum(1 for r in deaths if r["a_solvable"])

    def med(xs):
        return round(statistics.median(xs), 4) if xs else None

    return {
        "n_games": len(records),
        "n_capped": sum(1 for r in records if r.get("capped")),
        "n_deaths": len(deaths),
        "a_search_miss": a_miss,
        "a_search_miss_pct": round(100.0 * a_miss / len(deaths), 2) if deaths else None,
        "n_deaths_with_previous_tray": len(with_b),
        "b_any_survive": len(survivable),
        "b_any_survive_pct": round(100.0 * len(survivable) / len(with_b), 2) if with_b else None,
        "b_median_survive_frac": med([r["b"]["survive_frac"] for r in with_b]),
        "b_median_survive_frac_among_avoidable": med([r["b"]["survive_frac"] for r in survivable]),
        "b_median_chosen_rank": med([r["b"]["chosen_rank"] for r in with_b if r["b"]["chosen_rank"] is not None]),
        "b_median_best_survivor_rank": med([r["b"]["best_survivor_rank"] for r in survivable]),
        "b_median_n_final_boards": med([r["b"]["n_final_boards"] for r in with_b]),
        "b_times_sampled": sum(1 for r in with_b if r["b"]["sampled"]),
    }


_worker_policy = None
_worker_move_cap = None


def _worker_init(spec, config, move_cap):
    global _worker_policy, _worker_move_cap
    _worker_policy = benchmark.build_policy(spec, config)
    _worker_move_cap = move_cap


def _worker_run(seed):
    return play_and_analyze(_worker_policy, seed, _worker_move_cap)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Czy smierc dalo sie ominac jedna tacke wczesniej (#236)")
    parser.add_argument("--policy", required=True, help="specyfikacja jak w benchmark.py --candidate")
    parser.add_argument("--n-games", type=int, default=100)
    parser.add_argument("--config", default=BENCH_CONFIG)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    config = benchmark.load_config(args.config)
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        seeds = json.load(fh)[:args.n_games]
    move_cap = config["move_cap"]

    t0 = time.time()
    if args.jobs > 1:
        with multiprocessing.Pool(args.jobs, initializer=_worker_init,
                                  initargs=(args.policy, config, move_cap)) as pool:
            records = pool.map(_worker_run, seeds, chunksize=1)
    else:
        policy = benchmark.build_policy(args.policy, config)
        records = [play_and_analyze(policy, s, move_cap) for s in seeds]
    elapsed = round(time.time() - t0, 1)

    out = {"policy": args.policy, "n_games": args.n_games, "elapsed_s": elapsed,
           "summary": summarize(records), "games": records}
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)
    print(json.dumps(out["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
