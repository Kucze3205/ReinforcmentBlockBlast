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

Ten sam wektor wag ocenia trzy polityki:

- `heuristic` — `policies.HeuristicPolicy`, jeden pół-ruch w przód.
- `tray` — `policies.TrayPolicy`, wyczerpujące przeszukanie z wiązką całej
  bieżącej tacki (#58). Strojenie musi oceniać kandydatów tą samą polityką,
  którą potem mierzy `benchmark.py` (`--candidate tray`) — inna implementacja
  tacki na czas strojenia dałaby fałszywy wynik (patrz `docs/odzyskanie-cyklu-3.md`).
- `lookahead` — `policies.LookaheadPolicy` z parametrami domyślnymi z #92
  (`beam=8, samples=2, branch=2, inner_beam=1, inner_depth=1`), czyli dokładnie
  ta polityka, którą mierzy `benchmark.py --candidate lookahead:<plik>` (#104).
  Ta sama zasada co wyżej: wagi strojone pod jedno przeszukanie nie są optymalne
  dla innego.

Job ma limit czasu: pętla CEM sprawdza deadline przed każdym kandydatem (nie
tylko między iteracjami), więc przerwanie w połowie iteracji nie gubi
najlepszego dotychczasowego wyniku — ten jest śledzony per-kandydat, nie
per-iteracja.

Tryb pokoleniowy (`--state`, #104): jedno wywołanie = jedno pokolenie, stan
(pokolenie, rozkład, elita, najlepszy dotąd, log) ląduje w pliku stanu, kolejne
wywołanie podejmuje z tego miejsca. Przebieg `lookahead` idzie w godzinach, a
runner ginie razem z tym, czego nie wypchnięto (#82) — bez tego jedna śmierć
sesji kasuje cały przebieg. Deadline'u tu nie ma: granicą jest pokolenie.

    python tools/tune_weights.py --policy lookahead --state cem-lookahead.json \\
        --generations 6 --games-per-candidate 32 --population 14 --elite 4 \\
        --seed 104 --init-weights-file weights.json --out weights-lookahead.json
"""
import argparse
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import play_game
from features import FEATURE_NAMES
from policies import HeuristicPolicy, LookaheadPolicy, TrayPolicy

BENCH_CONFIG = "bench/config.json"
DEFAULT_OUT = "weights.json"
MIN_STD = 0.05
POLICY_CHOICES = ("heuristic", "tray", "lookahead")


def build_policy(policy_name, weights):
    if policy_name == "heuristic":
        return HeuristicPolicy(weights=weights)
    if policy_name == "tray":
        return TrayPolicy(weights=weights)
    if policy_name == "lookahead":
        # Parametry domyślne klasy = parametry wybrane w #92 i mierzone przez
        # `benchmark.py`; strojenie ocenia dokładnie tę konfigurację (#104).
        return LookaheadPolicy(weights=weights)
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


def run_generation(policy_name, mean, std, population_size, elite_n, seeds, move_cap,
                   rng, iteration, deadline=None):
    """Jedno pokolenie CEM. Zwraca `None`, jeśli deadline uciął je przed pierwszym
    kandydatem; inaczej słownik z oceną populacji, elitą, nowym rozkładem i wpisem logu.

    `evaluated` jest w kolejności oceny (nie posortowanej) — wołający aktualizuje
    z niej najlepszego dotąd kandydat po kandydacie, jak wymaga #59."""
    population = sample_population(mean, std, population_size, rng)
    evaluated = []
    for candidate in population:
        if deadline is not None and time.monotonic() >= deadline:
            break
        score = evaluate_candidate(policy_name, candidate, seeds, move_cap)
        evaluated.append((candidate, score))
    if not evaluated:
        return None
    scored = sorted(evaluated, key=lambda t: -t[1])
    elite = scored[: max(1, min(elite_n, len(scored)))]
    new_mean, new_std = update_distribution([w for w, _ in elite])
    entry = {
        "iteration": iteration,
        "evaluated": len(scored),
        "mean_score": round(statistics.mean(s for _, s in scored), 2),
        "elite_best_score": round(elite[0][1], 2),
        "elite_mean_score": round(statistics.mean(s for _, s in elite), 2),
        "mean_vector": [round(v, 4) for v in new_mean],
    }
    return {
        "evaluated": evaluated,
        "elite": elite,
        "mean": new_mean,
        "std": new_std,
        "entry": entry,
    }


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
        result = run_generation(policy_name, mean, std, population_size, elite_n,
                                seeds, move_cap, rng, iteration, deadline)
        if result is None:
            iteration -= 1
            break
        for candidate, score in result["evaluated"]:
            games_played += len(seeds)
            if best_score is None or score > best_score:
                best_score, best_weights = score, candidate
        mean, std = result["mean"], result["std"]
        log.append(result["entry"])
        if log_fn:
            log_fn(result["entry"])
    return best_weights, best_score, log, iteration, games_played


def generation_rng(seed, generation):
    """RNG jednego pokolenia, wyprowadzony z seeda przebiegu i numeru pokolenia.

    Tryb pokoleniowy nie może przenieść stanu `random.Random` przez plik JSON w
    sposób, który nie zależy od wersji implementacji Mersenne Twistera; zamiast
    tego każde pokolenie dostaje własny, deterministycznie zasiany RNG. Skutek:
    wznowienie po śmierci sesji losuje dokładnie tę samą populację, co przebieg
    nieprzerwany (#104)."""
    return random.Random("tune_weights:cem:{0}:{1}".format(seed, generation))


def load_init_weights(path):
    """Wektor startowy `mean` z pliku w formacie `weights.json` (klucz `weights`)."""
    with open(path, encoding="utf-8") as fh:
        weights = tuple(json.load(fh)["weights"])
    if len(weights) != len(FEATURE_NAMES):
        raise ValueError(
            "wagi startowe {0}: oczekiwano {1} liczb (FEATURE_NAMES), otrzymano {2}".format(
                path, len(FEATURE_NAMES), len(weights)
            )
        )
    return weights


def build_record(state):
    """Rekord w formacie `weights.json` (czytelny dla `benchmark.load_tuned_weights`)."""
    duration_s = state["duration_s"]
    games_played = state["games_played"]
    return {
        "policy": state["policy"],
        "feature_names": list(FEATURE_NAMES),
        "weights": list(state["best_weights"]),
        "best_score": round(state["best_score"], 2) if state["best_score"] is not None else None,
        "iterations": state["generation"],
        "duration_s": round(duration_s, 1),
        "games_played": games_played,
        "games_per_minute": (
            round(games_played / (duration_s / 60.0), 2) if duration_s > 0 else None
        ),
        "training_seeds_n": len(state["seeds"]),
        "params": dict(state["params"]),
        "init_weights": list(state["init_weights"]),
        "log": state["log"],
    }


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def new_state(args, seeds, init_mean, init_std):
    return {
        "policy": args.policy,
        "feature_names": list(FEATURE_NAMES),
        "generation": 0,
        "generations_target": args.generations,
        "mean": list(init_mean),
        "std": list(init_std),
        "elite": [],
        "elite_scores": [],
        "best_weights": list(init_mean),
        "best_score": None,
        "games_played": 0,
        "duration_s": 0.0,
        "seeds": list(seeds),
        "init_weights": list(init_mean),
        "params": {
            "minutes": None,
            "games_per_candidate": args.games_per_candidate,
            "population": args.population,
            "elite": args.elite,
            "seed": args.seed,
            "generations": args.generations,
        },
        "log": [],
    }


def load_state(path, args, seeds):
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    # Wznowienie z niezgodnymi parametrami dałoby przebieg, którego log kłamie o
    # tym, co mierzył — lepiej stanąć niż skleić dwa różne przebiegi (#104).
    if state["policy"] != args.policy:
        raise ValueError("stan {0} jest dla polityki {1}, nie {2}".format(
            path, state["policy"], args.policy))
    if list(state["seeds"]) != list(seeds):
        raise ValueError("stan {0} ma inne seedy treningowe niz biezace parametry".format(path))
    expected = {
        "population": args.population,
        "elite": args.elite,
        "games_per_candidate": args.games_per_candidate,
        "seed": args.seed,
    }
    for key, value in expected.items():
        if state["params"][key] != value:
            raise ValueError("stan {0}: parametr {1} ({2}) nie zgadza sie z wywolaniem ({3})".format(
                path, key, state["params"][key], value))
    state["generations_target"] = args.generations
    state["params"]["generations"] = args.generations
    return state


def run_generational(args, seeds, move_cap, init_mean, init_std):
    """Tryb `--state`: pokolenie po pokoleniu, zapis stanu po każdym (#104)."""
    if os.path.exists(args.state):
        state = load_state(args.state, args, seeds)
        print("Wznawiam {0}: pokolenie {1}/{2}, best={3}".format(
            args.state, state["generation"], args.generations, state["best_score"]),
            file=sys.stderr)
    else:
        state = new_state(args, seeds, init_mean, init_std)
        print("Nowy przebieg {0}: 0/{1} pokolen".format(args.state, args.generations),
              file=sys.stderr)

    ran = 0
    while state["generation"] < args.generations and ran < args.generations_per_run:
        generation = state["generation"] + 1
        started = time.time()
        result = run_generation(
            args.policy, tuple(state["mean"]), tuple(state["std"]), args.population,
            args.elite, seeds, move_cap, generation_rng(args.seed, generation), generation,
        )
        elapsed = time.time() - started
        for candidate, score in result["evaluated"]:
            state["games_played"] += len(seeds)
            if state["best_score"] is None or score > state["best_score"]:
                state["best_score"], state["best_weights"] = score, list(candidate)
        state["mean"] = list(result["mean"])
        state["std"] = list(result["std"])
        state["elite"] = [list(w) for w, _ in result["elite"]]
        state["elite_scores"] = [round(s, 2) for _, s in result["elite"]]
        entry = dict(result["entry"])
        entry["duration_s"] = round(elapsed, 1)
        state["log"].append(entry)
        state["generation"] = generation
        state["duration_s"] = round(state["duration_s"] + elapsed, 1)

        write_json(args.state, state)
        write_json(args.out, build_record(state))
        ran += 1
        print(
            "pokolenie {0}/{1}: srednia={2} elita_srednia={3} elita_best={4} "
            "best_dotad={5} ({6} s)".format(
                generation, args.generations, entry["mean_score"], entry["elite_mean_score"],
                entry["elite_best_score"], round(state["best_score"], 2), entry["duration_s"]),
            file=sys.stderr,
        )

    done = state["generation"] >= args.generations
    print("Zapisano {0} i {1} ({2}/{3} pokolen{4}, {5} gier, best={6})".format(
        args.out, args.state, state["generation"], args.generations,
        ", KONIEC" if done else "", state["games_played"],
        round(state["best_score"], 2) if state["best_score"] is not None else None,
    ))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="CEM: strojenie wag funkcji oceny (#59)")
    parser.add_argument("--policy", choices=list(POLICY_CHOICES), default="heuristic")
    parser.add_argument("--minutes", type=float, default=10.0)
    parser.add_argument("--games-per-candidate", type=int, default=20)
    parser.add_argument("--population", type=int, default=24)
    parser.add_argument("--elite", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0, help="seed RNG CEM i puli seedow treningowych")
    parser.add_argument("--config", default=BENCH_CONFIG)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--init-weights-file", default=None,
                        help="plik w formacie weights.json: srodek rozkladu startowego "
                             "(domyslnie HeuristicPolicy.DEFAULT_WEIGHTS)")
    parser.add_argument("--state", default=None,
                        help="plik stanu CEM: wlacza tryb pokoleniowy (jedno wywolanie = "
                             "--generations-per-run pokolen, zapis stanu po kazdym)")
    parser.add_argument("--generations", type=int, default=6,
                        help="docelowa liczba pokolen w trybie --state")
    parser.add_argument("--generations-per-run", type=int, default=1,
                        help="ile pokolen liczy jedno wywolanie w trybie --state")
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        bench_seeds = json.load(fh)[: config["n_seeds"]]

    seeds = training_seeds(args.games_per_candidate, bench_seeds, salt=args.seed)

    if args.init_weights_file:
        init_mean = load_init_weights(args.init_weights_file)
    else:
        init_mean = HeuristicPolicy.DEFAULT_WEIGHTS
    init_std = tuple(max(1.0, abs(w) * 0.5) for w in init_mean)

    if args.state:
        return run_generational(args, seeds, config["move_cap"], init_mean, init_std)

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
