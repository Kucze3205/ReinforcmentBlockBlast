"""
TD(0) po stanach następczych do trenowania `ntuple.NTupleValue` (#123).

Wznawialny na wzór `tools/tune_weights.py --state` (#104): jedno wywołanie =
jeden odcinek treningu (jedna partia), pełny stan i wagi zapisywane po każdym.
RNG partii jest wyprowadzony z `(seed, numer odcinka)` — wznowienie po śmierci
sesji rozegra dokładnie te partie, co przebieg nieprzerwany.

    python tools/train_ntuple.py --state ntuple-state.json --out ntuple-weights.json \\
        --episodes 2 --seed 1

Polityka behawioralna (ta, którą trenujemy i którą zbieramy dane) jest zachłanna
o jeden pół-ruch w przód, tak jak `HeuristicPolicy`, tylko wartość liścia liczy
sieć N-tuple, nie `weights · features(board)`: dla każdej legalnej akcji z bieżącej
tacki liczy `gain + ntuple.value(afterstate)` i wybiera najlepszą. Afterstate =
plansza zaraz po postawieniu i ewentualnym czyszczeniu linii, przed dociągiem
kolejnej tacki — to jest ten sam punkt, w którym TD(0) n-tuple w 2048/SZ-Tetris
robi aktualizację (`docs/research/przeszukanie-z-wyuczona-ocena.md`, sekcja 1).

Aktualizacja TD(0) po każdym kroku (poza pierwszym):

    target = gain_t + V(afterstate_t)
    V(afterstate_{t-1}) += alpha * (target - V(afterstate_{t-1}))

i jedna dodatkowa po ostatnim kroku partii, z `target = 0` (stan terminalny —
gra się skończyła, żadnej przyszłej nagrody nie będzie). Kształtu nagrody nie
zmienia: `gain_t` to dokładnie to, co zwraca `policies._simulate_placement`
(ten sam wzór co `Game.apply_placement`), reużyty tu bez modyfikacji.

Seedy treningowe są rozłączne z `bench/seeds_fixed.json`, wymuszone asercją w
`episode_seed()` — tak jak `tools/tune_weights.training_seeds()` (#59, #123).
"""
import argparse
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from ntuple import NTupleValue
from policies import _simulate_placement

BENCH_CONFIG = "bench/config.json"
DEFAULT_OUT = "ntuple-weights.json"
DEFAULT_ALPHA = 0.001


def load_bench_seeds(config):
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        return set(json.load(fh)[: config["n_seeds"]])


def episode_seed(seed, episode_number, forbidden):
    """Seed partii danego odcinka: deterministyczny z `(seed, episode_number)`,
    rozłączny z `bench/seeds_fixed.json` (#123).

    Kolizja z zakazanym zbiorem jest rozstrzygana dodatkową solą, wyprowadzoną
    wciąż tylko z `(seed, episode_number)` — bez zależności od historii
    poprzednich odcinków, więc wynik jest identyczny w przebiegu ciągłym i
    wznowionym."""
    salt = 0
    while True:
        candidate = random.Random(
            "train_ntuple:{0}:{1}:{2}".format(seed, episode_number, salt)
        ).randrange(1, 2**31 - 1)
        if candidate not in forbidden:
            assert candidate not in forbidden, "seed treningowy pokrywa sie z bench/seeds_fixed.json"
            return candidate
        salt += 1


def _choose_action(ntuple, game, actions):
    """Zachłanna o jeden pół-ruch w przód wg `gain + ntuple.value(afterstate)`.

    Zwraca `(akcja, indeksy łat afterstate, gain)` — indeksy i gain są od razu
    potrzebne do aktualizacji TD, nie ma po co liczyć ich drugi raz."""
    best_action, best_idxs, best_gain, best_score = None, None, None, None
    for action in actions:
        gain, board_after = _simulate_placement(game, action)
        idxs = ntuple.indices(board_after)
        score = gain + ntuple.value_from_indices(idxs)
        if best_score is None or score > best_score:
            best_action, best_idxs, best_gain, best_score = action, idxs, gain, score
    return best_action, best_idxs, best_gain


def run_episode(ntuple, seed, move_cap, alpha):
    """Jedna partia z aktualizacją TD(0) po każdym postawieniu.

    Zwraca statystyki partii (do logu stanu) — same wagi `ntuple` są modyfikowane
    w miejscu."""
    game = Game(seed=seed)
    prev_idxs, prev_gain = None, None
    steps = 0
    td_errors = []
    while not game.done and steps < move_cap:
        actions = game.available_actions()
        if not actions:
            break
        action, idxs, gain = _choose_action(ntuple, game, actions)
        if prev_idxs is not None:
            target = prev_gain + ntuple.value_from_indices(idxs)
            error = target - ntuple.value_from_indices(prev_idxs)
            ntuple.update(prev_idxs, alpha * error)
            td_errors.append(error)
        game.step(action)
        prev_idxs, prev_gain = idxs, gain
        steps += 1

    if prev_idxs is not None:
        # Stan terminalny: żadnej przyszłej nagrody nie będzie, target = 0.
        error = 0.0 - ntuple.value_from_indices(prev_idxs)
        ntuple.update(prev_idxs, alpha * error)
        td_errors.append(error)

    return {
        "seed": seed,
        "score": game.score,
        "placements": game.placements,
        "steps": steps,
        "mean_abs_td_error": round(statistics.mean(abs(e) for e in td_errors), 4) if td_errors else 0.0,
    }


def new_state(args, forbidden_seeds):
    return {
        "episode": 0,
        "episodes_target": args.episodes,
        "weights": None,  # wypelnione po pierwszym odcinku
        "games_played": 0,
        "duration_s": 0.0,
        "params": {
            "seed": args.seed,
            "alpha": args.alpha,
            "move_cap": args.move_cap,
        },
        "bench_seeds_n": len(forbidden_seeds),
        "log": [],
    }


def load_state(path, args, forbidden_seeds):
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    # Wznowienie z innymi parametrami dalo by przebieg, ktorego log klamie o tym,
    # co mierzyl (wzor z tools/tune_weights.load_state, #104).
    expected = {"seed": args.seed, "alpha": args.alpha, "move_cap": args.move_cap}
    for key, value in expected.items():
        if state["params"][key] != value:
            raise ValueError(
                "stan {0}: parametr {1} ({2}) nie zgadza sie z wywolaniem ({3})".format(
                    path, key, state["params"][key], value
                )
            )
    if state["bench_seeds_n"] != len(forbidden_seeds):
        raise ValueError(
            "stan {0} liczy inna liczbe zakazanych seedow bench — inna konfiguracja".format(path)
        )
    state["episodes_target"] = args.episodes
    return state


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def run_generational(args, config, forbidden_seeds):
    if os.path.exists(args.state):
        state = load_state(args.state, args, forbidden_seeds)
        ntuple = NTupleValue(weights=state["weights"]) if state["weights"] else NTupleValue()
        print(
            "Wznawiam {0}: odcinek {1}/{2}".format(args.state, state["episode"], args.episodes),
            file=sys.stderr,
        )
    else:
        state = new_state(args, forbidden_seeds)
        ntuple = NTupleValue()
        print("Nowy przebieg {0}: 0/{1} odcinkow".format(args.state, args.episodes), file=sys.stderr)

    ran = 0
    while state["episode"] < args.episodes and ran < args.episodes_per_run:
        episode = state["episode"] + 1
        seed = episode_seed(args.seed, episode, forbidden_seeds)
        started = time.time()
        stats = run_episode(ntuple, seed, args.move_cap, args.alpha)
        elapsed = time.time() - started

        state["episode"] = episode
        state["weights"] = ntuple.weights
        state["games_played"] += 1
        state["duration_s"] = round(state["duration_s"] + elapsed, 1)
        entry = dict(stats)
        entry["episode"] = episode
        entry["duration_s"] = round(elapsed, 3)
        state["log"].append(entry)

        write_json(args.state, state)
        ntuple.save(args.out)
        ran += 1
        print(
            "odcinek {0}/{1}: seed={2} wynik={3} postawienia={4} "
            "|blad_td|_sr={5} ({6} s)".format(
                episode, args.episodes, seed, stats["score"], stats["placements"],
                stats["mean_abs_td_error"], entry["duration_s"],
            ),
            file=sys.stderr,
        )

    done = state["episode"] >= args.episodes
    print(
        "Zapisano {0} i {1} ({2}/{3} odcinkow{4}, {5} partii)".format(
            args.out, args.state, state["episode"], args.episodes,
            ", KONIEC" if done else "", state["games_played"],
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="TD(0) po stanach następczych: trener sieci N-tuple (#123)"
    )
    parser.add_argument("--state", required=True, help="plik stanu treningu (wznawialny)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="plik wag ntuple.NTupleValue")
    parser.add_argument("--episodes", type=int, required=True, help="docelowa liczba odcinkow")
    parser.add_argument(
        "--episodes-per-run", type=int, default=1,
        help="ile odcinkow liczy jedno wywolanie (domyslnie 1: jedno wywolanie = jeden odcinek)",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed RNG odcinkow treningowych")
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA, help="krok TD(0)")
    parser.add_argument("--move-cap", type=int, default=None, help="sufit postawien na partie")
    parser.add_argument("--config", default=BENCH_CONFIG)
    args = parser.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)
    if args.move_cap is None:
        args.move_cap = config["move_cap"]

    forbidden_seeds = load_bench_seeds(config)
    return run_generational(args, config, forbidden_seeds)


if __name__ == "__main__":
    sys.exit(main())
