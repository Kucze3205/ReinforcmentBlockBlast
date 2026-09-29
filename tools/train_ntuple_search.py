"""
Pilot #216: TD(0) po stanach następczych, gdzie polityką behawioralną (tą, która
wybiera ruchy podczas zbierania danych) jest tania wiązka `lookahead-ntuple`
(`policies.NTupleLookaheadPolicy`, `beam` 4-16, bez drugiego poziomu próbek),
zamiast zachłannej oceny jednego klocka jak w `tools/train_ntuple.py`. Wariant 2
z rankingu `docs/research/uczenie-z-przeszukania.md` sekcja (d): hipoteza #216 —
trening zachłanny rzadko widzi stany, do których dochodzi polityka grająca z
wiązką (dłuższe partie, pełniejsze plansze), więc ocena tam jest słaba.

Cel TD(0) jest identyczny jak w `train_ntuple.run_episode` — `r_t +
V(afterstate_t)`, `r` z `--reward` (`survival`: 1 za postawienie; `score`: `gain`)
— zmienia się wyłącznie **skąd biorą się odwiedzane afterstate'y**: nie z
`argmax` po jednym klocku, tylko z pierwszego ruchu sekwencji, którą wybrała
wiązka nad całą pozostałą tacką (ta sama funkcja co polityka grająca
`lookahead-ntuple`, patrz `policies.NTupleLookaheadPolicy`/`_tray_beam_search`).

## Równoległość: uśrednianie lokalnych kopii wag ("local SGD"), nie Hogwild

`nt_search`/rdzeń natywny trzyma wagi we własnym buforze C na proces — nie da
się go dzielić między procesami bez zmiany `ntuple_native.py` na pamięć
współdzieloną, co jest poza budżetem jednej sesji tego zadania. Zamiast tego:
odcinki dzielone są na `--jobs` procesów w **rundach** po `--round-episodes /
--jobs` odcinków na proces. Każdy proces dostaje kopię bieżących wag, gra swoją
porcję odcinków **sekwencyjnie, ucząc się w locie** (dokładnie jak
`train_ntuple.run_episode`, tyle że ruchy wybiera wiązka, nie `argmax`), i
oddaje swoje końcowe wagi. Po rundzie wagi mistrza to **średnia** wag
wszystkich procesów — standardowa technika równoległego SGD z okresowym
uśrednianiem (analogiczna do federated averaging), tańsza i prostsza niż
współdzielona pamięć z blokadami, kosztem drobnego rozjazdu wag w obrębie
rundy między procesami (znika przy uśrednieniu). `--round-episodes` musi
dzielić `--episodes`, `--episodes-per-run` i `--eval-every` (gdy podane) —
ewaluacja i zapis widzą tylko wagi **po** pełnej rundzie, nie w jej trakcie.

Stan (`--state`) jest **nowym formatem**, nie tym z `tools/train_ntuple.py` —
zaczyna liczenie odcinków od 0, nawet gdy wagi startowe pochodzą z innego
przebiegu (`--init-weights`, wczytywane przez `ntuple.NTupleValue.load` tylko
przy tworzeniu nowego stanu). To celowe uproszczenie względem wzoru kopiowania
stanu z `docs/ntuple-survival-adcga4.md` (ciągła numeracja od odcinka źródła):
ten trening ma **inny** schemat parametrów (`search_beam` i reszta), więc
`load_state` i tak nie przyjąłby cudzego pliku stanu — nowy początek numeracji
jest jaśniejszy niż udawanie ciągłości, której schemat i tak nie ma.

Wznawialne jak `tools/train_ntuple.py` — parametry (`seed`, `alpha`, `move_cap`,
`reward`, `layout`, `stages`, `thresholds`, `search_beam`, `search_samples`,
`search_branch`, `search_inner_beam`, `search_inner_depth`, `jobs`,
`round_episodes`) zapisane w stanie muszą zgadzać się z wywołaniem wznowienia.

    python3 tools/train_ntuple_search.py --state ntuple/survival-adcgx-state.json \\
        --out ntuple/survival-adcgx-weights.json --best-out ntuple/survival-adcgx-best.json \\
        --curve-out docs/data/ntuple-survival-adcgx-krzywa.json \\
        --init-weights ntuple/survival-adcga16-800k.json --reward survival --layout ADC \\
        --alpha 0.000007352941176470588 --seed 3 --move-cap 2000 --jobs 4 \\
        --round-episodes 40 --episodes 40000 --episodes-per-run <K> \\
        --eval-every 2000 --eval-episodes 200
"""
import argparse
import json
import multiprocessing
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import train_ntuple as tn
from game import Game
from ntuple import DEFAULT_LAYOUT, LAYOUTS, REWARD_SCORE, REWARD_SURVIVAL, REWARDS, NTupleValue
from policies import NTupleLookaheadPolicy

BENCH_CONFIG = "bench/config.json"
DEFAULT_OUT = "ntuple-search-weights.json"
DEFAULT_ALPHA = 0.001
DEFAULT_SAVE_EVERY_ROUNDS = 1
STATE_FORMAT = 1

PARAM_KEYS = (
    "seed", "alpha", "move_cap", "reward", "layout", "stages", "thresholds",
    "search_beam", "search_samples", "search_branch", "search_inner_beam",
    "search_inner_depth", "jobs", "round_episodes",
)


def run_episode_search(ntuple, search_policy, seed, move_cap, alpha, reward=REWARD_SCORE):
    """Jeden odcinek, jak `train_ntuple.run_episode`, tylko ruch wybiera
    `search_policy.act` (wiązka nad pozostałą tacką), nie `argmax` po jednym
    klocku. Cel i aktualizacja TD(0) są identyczne co do wzoru (#153: `r_t +
    V(afterstate_t)`)."""
    game = Game(seed=seed)
    search_policy.reset(seed)
    prev_idxs = None
    prev_stage = None
    steps = 0
    td_errors = []
    while not game.done and steps < move_cap:
        actions = game.available_actions()
        if not actions:
            break
        action = search_policy.act(game, actions)
        gain, board_after = tn._simulate_placement(game, action)
        r = tn.step_reward(reward, gain)
        idxs = ntuple.indices(board_after)
        stage = ntuple.stage(board_after)
        if prev_idxs is not None:
            target = r + ntuple.value_from_indices(idxs, stage)
            error = target - ntuple.value_from_indices(prev_idxs, prev_stage)
            ntuple.update(prev_idxs, alpha * error, prev_stage)
            td_errors.append(error)
        game.step(action)
        prev_idxs = idxs
        prev_stage = stage
        steps += 1

    if prev_idxs is not None:
        error = 0.0 - ntuple.value_from_indices(prev_idxs, prev_stage)
        ntuple.update(prev_idxs, alpha * error, prev_stage)
        td_errors.append(error)

    return {
        "seed": seed,
        "score": game.score,
        "placements": game.placements,
        "steps": steps,
        "mean_abs_td_error": round(statistics.mean(abs(e) for e in td_errors), 4) if td_errors else 0.0,
    }


def _worker_round(payload):
    (weights, reward, layout, stages, thresholds, train_seed, first_episode, n_episodes,
     move_cap, alpha, forbidden_seeds, search_beam, search_samples, search_branch,
     search_inner_beam, search_inner_depth, worker_index) = payload
    ntuple = NTupleValue(weights=weights, reward=reward, layout=layout,
                         stages=stages, thresholds=thresholds)
    policy = NTupleLookaheadPolicy(
        ntuple, beam=search_beam, samples=search_samples, branch=search_branch,
        inner_beam=search_inner_beam, inner_depth=search_inner_depth, seed=worker_index,
    )
    entries = []
    for i in range(n_episodes):
        episode = first_episode + i
        ep_seed = tn.episode_seed(train_seed, episode, forbidden_seeds)
        started = time.time()
        stats = run_episode_search(ntuple, policy, ep_seed, move_cap, alpha, reward)
        elapsed = time.time() - started
        entry = dict(stats)
        entry["episode"] = episode
        entry["duration_s"] = round(elapsed, 3)
        entries.append(entry)
    return ntuple.to_dict()["weights"], entries


def _average_weights(weight_sets, stages):
    """Średnia arytmetyczna kilku kompletów wag tego samego kształtu (#216:
    scalanie procesów równoległych po rundzie, patrz moduł docstring)."""
    n = len(weight_sets)
    if stages == 1:
        return [[sum(vals) / n for vals in zip(*cols)] for cols in zip(*weight_sets)]
    merged = []
    for stage in range(stages):
        stage_sets = [ws[stage] for ws in weight_sets]
        merged.append([[sum(vals) / n for vals in zip(*cols)] for cols in zip(*stage_sets)])
    return merged


def new_state(args, forbidden_seeds):
    return {
        "format": STATE_FORMAT,
        "episode": 0,
        "episodes_target": args.episodes,
        "weights": None,
        "games_played": 0,
        "duration_s": 0.0,
        "params": {key: getattr(args, key) for key in PARAM_KEYS},
        "bench_seeds_n": len(forbidden_seeds),
        "log_bytes": 0,
        "windows": [],
        "eval": {"every": None, "episodes": None, "points": [], "best": None},
    }


def load_state(path, args, forbidden_seeds):
    with open(path, encoding="utf-8") as fh:
        state = json.load(fh)
    expected = {key: getattr(args, key) for key in PARAM_KEYS}
    expected["thresholds"] = list(expected["thresholds"])
    for key, value in expected.items():
        stored = state["params"][key]
        if key == "thresholds":
            stored = list(stored)
        if stored != value:
            raise ValueError(
                "stan {0}: parametr {1} ({2}) nie zgadza sie z wywolaniem ({3})".format(
                    path, key, stored, value
                )
            )
    if state["bench_seeds_n"] != len(forbidden_seeds):
        raise ValueError(
            "stan {0} liczy inna liczbe zakazanych seedow bench — inna konfiguracja".format(path)
        )
    ev = state["eval"]
    if ev["points"] and (ev["every"], ev["episodes"]) != (args.eval_every, args.eval_episodes):
        raise ValueError(
            "stan {0}: ewaluacja co {1} na {2} partiach nie zgadza sie z wywolaniem "
            "(co {3} na {4})".format(path, ev["every"], ev["episodes"], args.eval_every, args.eval_episodes)
        )
    lp = tn.log_path(path, state["episode"]) if state["episode"] else tn.log_path(path)
    if os.path.exists(lp) and os.path.getsize(lp) > state["log_bytes"]:
        os.truncate(lp, state["log_bytes"])
    state["episodes_target"] = args.episodes
    return state


def save(args, state, ntuple, pending_log):
    if pending_log:
        tn._append_log_entries(args.state, pending_log)
        pending_log.clear()
    lp = tn.log_path(args.state, state["episode"]) if state["episode"] else tn.log_path(args.state)
    state["log_bytes"] = os.path.getsize(lp) if os.path.exists(lp) else 0
    state["weights"] = ntuple.to_dict()["weights"]
    tn.write_json(args.out, tn.weights_payload(ntuple))
    tn.write_json(args.state, state)
    if args.curve_out:
        tn.write_json(args.curve_out, tn.curve(state))


def run_eval(args, state, ntuple, seeds):
    point = dict(odcinki=state["episode"], **tn.evaluate(ntuple, seeds, args.move_cap, args.reward))
    ev = state["eval"]
    ev["points"].append(point)
    improved = ev["best"] is None or point["sredni_wynik"] > ev["best"]["sredni_wynik"]
    if improved:
        ev["best"] = point
        tn.write_json(args.best_out, tn.weights_payload(ntuple, ewaluacja=point))
    print(
        "ewaluacja po {0} odcinkach: wynik_sr={1} przezycie_sr={2} ({3} partii){4}".format(
            point["odcinki"], point["sredni_wynik"], point["srednie_przezycie"],
            point["n_partii"], " — NAJLEPSZA, zapisano " + args.best_out if improved else "",
        ),
        file=sys.stderr,
    )


def run_generational(args, config, forbidden_seeds, pool):
    layout = LAYOUTS[args.layout]
    if os.path.exists(args.state):
        state = load_state(args.state, args, forbidden_seeds)
        ntuple = NTupleValue(
            weights=state["weights"], reward=args.reward, layout=layout,
            stages=args.stages, thresholds=args.thresholds,
        ) if state["weights"] else NTupleValue(
            reward=args.reward, layout=layout, stages=args.stages, thresholds=args.thresholds,
        )
        print("Wznawiam {0}: odcinek {1}/{2}".format(args.state, state["episode"], args.episodes),
              file=sys.stderr)
    else:
        state = new_state(args, forbidden_seeds)
        if args.init_weights:
            ntuple = NTupleValue.load(args.init_weights)
            if ntuple.reward != args.reward or ntuple.layout != layout or \
                    ntuple.stages != args.stages or tuple(ntuple.thresholds) != args.thresholds:
                raise ValueError(
                    "--init-weights {0}: reward/layout/stages/thresholds nie zgadzaja sie "
                    "z wywolaniem".format(args.init_weights)
                )
        else:
            ntuple = NTupleValue(reward=args.reward, layout=layout, stages=args.stages,
                                 thresholds=args.thresholds)
        for lp in tn._log_block_paths(args.state):
            os.remove(lp)
        print("Nowy przebieg {0}: 0/{1} odcinkow".format(args.state, args.episodes), file=sys.stderr)

    seeds_eval = None
    if args.eval_every:
        state["eval"]["every"] = args.eval_every
        state["eval"]["episodes"] = args.eval_episodes
        seeds_eval = tn.eval_seeds(args.eval_episodes, forbidden_seeds)

    per_worker = args.round_episodes // args.jobs
    pending_log = []
    ran = 0
    while state["episode"] < args.episodes and ran < args.episodes_per_run:
        weights = ntuple.to_dict()["weights"]
        first_episode = state["episode"] + 1
        payloads = [
            (weights, args.reward, layout, args.stages, args.thresholds, args.seed,
             first_episode + w * per_worker, per_worker, args.move_cap, args.alpha,
             forbidden_seeds, args.search_beam, args.search_samples, args.search_branch,
             args.search_inner_beam, args.search_inner_depth, w)
            for w in range(args.jobs)
        ]
        started = time.time()
        if args.jobs == 1:
            results = [_worker_round(payloads[0])]
        else:
            results = pool.map(_worker_round, payloads)
        elapsed = time.time() - started

        weight_sets = [w for w, _ in results]
        ntuple = NTupleValue(
            weights=_average_weights(weight_sets, args.stages), reward=args.reward,
            layout=layout, stages=args.stages, thresholds=args.thresholds,
        )

        round_episodes = args.round_episodes
        state["episode"] = first_episode + round_episodes - 1
        state["games_played"] += round_episodes
        state["duration_s"] += elapsed
        for _, entries in results:
            for entry in entries:
                pending_log.append(entry)
                tn._add_to_windows(state["windows"], entry)
        ran += round_episodes
        print(
            "runda do odcinka {0}/{1}: {2} odcinkow w {3} procesach, {4:.3f} s "
            "({5:.5f} s/odcinek)".format(
                state["episode"], args.episodes, round_episodes, args.jobs, elapsed,
                elapsed / round_episodes,
            ),
            file=sys.stderr,
        )

        evaluated = bool(args.eval_every) and state["episode"] % args.eval_every == 0
        if evaluated:
            run_eval(args, state, ntuple, seeds_eval)
        last = state["episode"] >= args.episodes or ran >= args.episodes_per_run
        if evaluated or last:
            save(args, state, ntuple, pending_log)

    if ran == 0:
        save(args, state, ntuple, pending_log)

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
        description="TD(0) po stanach nastepczych z trajektorii wiazki (#216, wariant 2)"
    )
    parser.add_argument("--state", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--episodes", type=int, required=True)
    parser.add_argument("--episodes-per-run", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    parser.add_argument("--move-cap", type=int, default=None)
    parser.add_argument("--reward", choices=REWARDS, default=REWARD_SCORE)
    parser.add_argument("--layout", choices=sorted(LAYOUTS), default=DEFAULT_LAYOUT)
    parser.add_argument("--stages", type=int, default=1)
    parser.add_argument("--thresholds", default="")
    parser.add_argument("--eval-every", type=int, default=None)
    parser.add_argument("--eval-episodes", type=int, default=20)
    parser.add_argument("--best-out", default=None)
    parser.add_argument("--curve-out", default=None)
    parser.add_argument(
        "--init-weights", default=None,
        help="plik wag ntuple.NTupleValue (np. przebiegu train_ntuple.py) do zaladowania "
             "jako start NOWEGO stanu (#216) — tylko przy tworzeniu stanu, ktorego jeszcze "
             "nie ma; odcinki tego narzedzia licza sie od 0 niezaleznie od odcinka zrodla",
    )
    parser.add_argument("--jobs", type=int, default=4, help="liczba procesow rownoleglych na runde")
    parser.add_argument(
        "--round-episodes", type=int, default=40,
        help="odcinkow na runde (dzielone rowno na --jobs procesow); wagi sa usredniane "
             "miedzy procesami po kazdej rundzie (patrz docstring modulu)",
    )
    parser.add_argument("--search-beam", type=int, default=8, help="beam polityki behawioralnej")
    parser.add_argument(
        "--search-samples", type=int, default=0,
        help="probki drugiego poziomu polityki behawioralnej (0 = tylko biezaca tacka, tanio)",
    )
    parser.add_argument("--search-branch", type=int, default=2)
    parser.add_argument("--search-inner-beam", type=int, default=1)
    parser.add_argument("--search-inner-depth", type=int, default=1)
    parser.add_argument("--config", default=BENCH_CONFIG)
    args = parser.parse_args(argv)

    if args.stages < 1:
        parser.error("--stages musi byc >= 1")
    raw_thresholds = args.thresholds.strip()
    try:
        thresholds = tuple(int(t) for t in raw_thresholds.split(",")) if raw_thresholds else ()
    except ValueError:
        parser.error("--thresholds musi byc lista liczb calkowitych oddzielonych przecinkami")
    if len(thresholds) != args.stages - 1:
        parser.error("--thresholds musi miec dokladnie --stages - 1 progow (ma %d, trzeba %d)"
                     % (len(thresholds), args.stages - 1))
    args.thresholds = thresholds
    if args.jobs < 1:
        parser.error("--jobs musi byc >= 1")
    if args.round_episodes < 1 or args.round_episodes % args.jobs != 0:
        parser.error("--round-episodes musi byc >= 1 i podzielne przez --jobs")
    if args.episodes % args.round_episodes != 0:
        parser.error("--episodes musi byc wielokrotnoscia --round-episodes")
    if args.episodes_per_run % args.round_episodes != 0:
        parser.error("--episodes-per-run musi byc wielokrotnoscia --round-episodes")
    if args.eval_every is not None:
        if args.eval_every < 1 or args.eval_episodes < 1:
            parser.error("--eval-every i --eval-episodes musza byc >= 1")
        if args.eval_every % args.round_episodes != 0:
            parser.error("--eval-every musi byc wielokrotnoscia --round-episodes")
        if not args.best_out:
            parser.error("--eval-every wymaga --best-out")
    else:
        args.eval_episodes = None

    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)
    if args.move_cap is None:
        args.move_cap = config["move_cap"]

    forbidden_seeds = tn.load_bench_seeds(config)
    pool = multiprocessing.Pool(processes=args.jobs) if args.jobs > 1 else None
    try:
        return run_generational(args, config, forbidden_seeds, pool)
    finally:
        if pool is not None:
            pool.close()
            pool.join()


if __name__ == "__main__":
    sys.exit(main())
