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

- `heuristic` — `policies.HeuristicPolicy`, jeden pół-ruch w przód (import,
  bez zmian w `policies.py`).
- `tray` — `TraySearchPolicy` niżej: próbuje wszystkie **6 kolejności**
  ułożenia bieżącej tacki (wzór z `JacksonW98/block-blast-bot` cytowany w
  `docs/research/kierunek-algorytmiczny.md`), a w obrębie każdej kolejności
  wybiera zachłannie (1-ply, `w · features(...)` po każdym postawieniu) gdzie
  postawić kolejny klocek. To NIE jest przeszukanie wyczerpujące po pozycjach
  (kolejność × pozycja1 × pozycja2 × pozycja3) — zmierzone w tym zadaniu: przy
  pustej planszy i małych klockach to iloczyn rzędu 10^5-10^6 liści na jedną
  decyzję, za drogie w Pythonie na tym symulatorze w limicie czasu joba.
  Kompromis: pełne rozgałęzienie po kolejności (to jest ta część, którą
  literatura wiąże z wygraną), zachłanne po pozycji (tania). Nie wchodzi w
  `policies.py`, bo #59 dopuszcza do zapisu tylko ten plik, `weights.json`
  i `docs/strojenie-wag.md`.

Job ma limit czasu: pętla CEM sprawdza deadline przed każdym kandydatem (nie
tylko między iteracjami), więc przerwanie w połowie iteracji nie gubi
najlepszego dotychczasowego wyniku — ten jest śledzony per-kandydat, nie
per-iteracja.
"""
import argparse
import itertools
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import play_game
from board import Board
from features import FEATURE_NAMES, features
from policies import HeuristicPolicy
from scoring import COMBO_COUNTER_BASE, FULL_CLEAR_BONUS, clear_points, placement_points

BENCH_CONFIG = "bench/config.json"
DEFAULT_OUT = "weights.json"
MIN_STD = 0.05


class TraySearchPolicy:
    """6 kolejności ułożenia bieżącej tacki, zachłanne (1-ply) dobieranie
    pozycji w obrębie każdej kolejności, `w · features(...)` na planszy po
    całej rundzie decyduje, która kolejność wygrywa (patrz moduł wyżej).

    Plan liczony raz na rundę (gdy `self._plan` jest pusty) i konsumowany
    postawienie po postawieniu — bez tego przeszukanie powtarzałoby się 3x.
    Jeżeli żadna kolejność nie ułoży się w całości (rzadkie, planszą prawie
    pełna), plan jest odpowiednio krótszy — kolejne wywołanie `act` przeliczy
    resztę od aktualnego stanu `game.pieces`."""

    def __init__(self, weights):
        self.weights = tuple(weights)
        self.name = "tray"
        self._plan = []

    def reset(self, game_seed):
        self._plan = []

    def act(self, game, actions):
        if not self._plan:
            self._plan = self._plan_round(game, actions)
        return self._plan.pop(0)

    def _plan_round(self, game, actions):
        tray = [(idx, p) for idx, p in enumerate(game.pieces) if p is not None]
        best_seq, best_score = None, None
        for order in itertools.permutations(tray):
            seq, score = _greedy_plan(game.board, game.combo, game.combo_counter, order, self.weights)
            if not seq:
                continue
            if best_score is None or score > best_score:
                best_score, best_seq = score, seq
        if best_seq is None:
            # Zadna kolejnosc nie ulozyla ani jednego klocka -- niemozliwe przy
            # niepustym `actions` (gwarancja wywolujacego), zapora defensywna.
            return [actions[0]]
        return best_seq


def _greedy_plan(board, combo, combo_counter, order, weights):
    """Dla jednej kolejności `order` (lista `(idx, piece)`) dobiera zachłannie
    (1-ply, `w · features(...)`) pozycję każdego kolejnego klocka na kopii
    `board`, powtarzając logikę combo z `game.py:apply_placement`. Zwraca
    `(sekwencja_akcji, wynik_koncowy)`; sekwencja jest krótsza od `order`,
    jeśli w pewnym momencie żaden z pozostałych klocków się nie mieści."""
    seq = []
    total_gain = 0
    cur_board = board
    cur_combo, cur_combo_counter = combo, combo_counter
    for i, (idx, piece) in enumerate(order):
        remaining_after = len(order) - i - 1
        h, w = len(piece.shape), len(piece.shape[0])
        best = None
        for y in range(Board.HEIGHT - h + 1):
            for x in range(Board.WIDTH - w + 1):
                if not cur_board.can_place_piece(piece, x, y):
                    continue
                nboard = cur_board.copy()
                nboard.place_piece(piece, x, y)
                step_gain = placement_points(piece)
                rows, cols = nboard.check_full_lines()
                lines = len(rows) + len(cols)
                if lines > 0:
                    ncombo = cur_combo + 1
                    ncombo_counter = COMBO_COUNTER_BASE + remaining_after
                    step_gain += clear_points(ncombo, lines)
                elif cur_combo_counter <= 1:
                    ncombo, ncombo_counter = 0, COMBO_COUNTER_BASE
                else:
                    ncombo, ncombo_counter = cur_combo, cur_combo_counter - 1
                nboard.clear_lines(rows, cols)
                if not any(any(row) for row in nboard.grid):
                    step_gain += FULL_CLEAR_BONUS
                step_score = step_gain + sum(wt * f for wt, f in zip(weights, features(nboard)))
                if best is None or step_score > best[0]:
                    best = (step_score, (idx, x, y), step_gain, nboard, ncombo, ncombo_counter)
        if best is None:
            break
        _score, action, step_gain, cur_board, cur_combo, cur_combo_counter = best
        seq.append(action)
        total_gain += step_gain
    final_score = total_gain + sum(wt * f for wt, f in zip(weights, features(cur_board)))
    return seq, final_score


def build_policy(policy_name, weights):
    if policy_name == "heuristic":
        return HeuristicPolicy(weights=weights)
    if policy_name == "tray":
        return TraySearchPolicy(weights)
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
