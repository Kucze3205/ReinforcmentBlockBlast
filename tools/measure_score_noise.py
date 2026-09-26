"""
Mierzy rozrzut (sigma) wyniku i przezycia pojedynczej partii dla podanej
polityki i podanych wag, na seedach treningowych (#101).

Nie trenuje, nie zmienia wag, nie dotyka CEM — czyta wektor wag z pliku (albo
uzywa domyslnych wag polityki) i rozgrywa `--n-games` partii, kazda na osobnym
seedzie z `tools.tune_weights.training_seeds()` (rozlacznym z
`bench/seeds_fixed.json`, ten sam podzial, ktorego uzywa CEM). Wypisuje dla
wyniku i dla przezycia: srednia, odchylenie standardowe, wspolczynnik
zmiennosci (sigma/srednia) i blad standardowy sredniej (sigma/sqrt(n)); oraz
korelacje Pearsona i Spearmana miedzy wynikiem a przezyciem, partia po partii.

    python3 tools/measure_score_noise.py --policy lookahead --weights-file weights.json --n-games 150
    python3 tools/measure_score_noise.py --policy tray --weights-file weights.json --n-games 150 --out /tmp/tray.json

`lookahead` kosztuje ok. 2,0 s/partia na `weights.json` (docs/lookahead.md) —
150 partii to okolo 5 minut.

`--seed-file` (#112) podmienia zrodlo seedow: zamiast `training_seeds()`
(seedy treningowe, rozlaczne z benchmarkiem) bierze pierwsze `--n-games`
seedow wprost z podanego pliku-listy, np. `bench/seeds_fixed.json` — te same
300 seedow, na ktorych liczy `benchmark.py`. `--series-out` zrzuca serie
partia-po-partii `(seed, score, survival, capped)` do JSON-a, obok podsumowania
z `--out`:

    python3 tools/measure_score_noise.py --policy lookahead --weights-file weights.json \\
        --n-games 300 --seed-file bench/seeds_fixed.json --series-out docs/data/serie-300-lookahead.json

`--detailed` (#119) uzywa `play_series_detailed` zamiast `play_series`: rozgrywa
partie wlasna petla (nie `benchmark.play_game`) i rozbija kazde postawienie na
`placement_points`/`clear_points` (roznica `gained - placement_points(piece)`,
scoring.py sie nie zmienia — to tylko odczyt publicznego stanu `Game` z
zewnatrz, ten sam trik co `policies._simulate_placement`), oraz liczy combo:
maksimum, srednia combo w chwili czyszczenia, dlugosci nieprzerwanych
lancuchow (wartosc `combo` tuz przed zerwaniem) i przyczyne kazdego zerwania
(`brak_legalnego_czyszczenia` — zadna dostepna akcja nie czyscilaby linii —
albo `wybor_polityki` — jakas czyscilaby, polityka wybrala inna). Zerwanie to
wylacznie przejscie `combo>0 -> combo==0` bez czyszczenia w tym postawieniu
(`game.py:85-89`); lancuch wciaz zywy w momencie konca partii/sufitu ruchow
jest liczony do rozkladu dlugosci osobno, jako ucieciowy (nie jako zerwanie).
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import percentile, play_game
from game import Game
from policies import HeuristicPolicy, LookaheadPolicy, TrayPolicy
from scoring import placement_points as scoring_placement_points
from tools.tune_weights import training_seeds

BENCH_CONFIG = "bench/config.json"
DEFAULT_SALT = 101

POLICY_CLASSES = {
    "heuristic": HeuristicPolicy,
    "tray": TrayPolicy,
    "lookahead": LookaheadPolicy,
}


def load_bench_seeds(config_path):
    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        bench_seeds = json.load(fh)[: config["n_seeds"]]
    return bench_seeds, config["move_cap"]


def load_weights(path):
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        return tuple(json.load(fh)["weights"])


def play_series(policy_name, weights, seeds, move_cap):
    """Zwraca `(scores, survivals, capped)`, po jednej trojce na seed.

    `capped` mowi, czy partia zostala ucieta sufitem ruchow (#112: taka partia
    nie jest zakonczona i kubelki dlugosci partii musza to odroznic).
    """
    policy_cls = POLICY_CLASSES[policy_name]
    policy = policy_cls(weights=weights) if weights is not None else policy_cls()
    scores, survivals, capped = [], [], []
    for seed in seeds:
        policy.reset(seed)
        score, placements, was_capped = play_game(policy, seed, move_cap)
        scores.append(score)
        survivals.append(placements)
        capped.append(was_capped)
    return scores, survivals, capped


def _any_action_would_clear(board, pieces, actions):
    """Czy ktorakolwiek z `actions` (idx, x, y) na `pieces`/`board` wyczyscilaby linie.

    Symulacja na kopii planszy (`Board.copy`), bez zadnej mutacji stanu gry —
    ten sam wzorzec co `policies._simulate_placement`, tylko interesuje nas
    wylacznie fakt czyszczenia, nie punkty.
    """
    for idx, x, y in actions:
        sim_board = board.copy()
        sim_board.place_piece(pieces[idx], x, y)
        rows, cols = sim_board.check_full_lines()
        if rows or cols:
            return True
    return False


def play_game_detailed(policy, seed, move_cap):
    """Jedna partia z rozbiciem punktow i statystyka combo (#119).

    Zwraca slownik: `score`, `survival`, `capped`, `placement_points`,
    `clear_points` (roznica `gained - placement_points(piece)`, wiec suma obu
    pol jest dokladnie rowna `score`), `clears`, `max_combo`,
    `mean_combo_at_clear` (None gdy `clears == 0`), `breaks`,
    `breaks_no_legal_clear`, `breaks_policy_choice`, `chain_lengths` (dlugosci
    lancuchow zerwanych licznikiem) i `unresolved_chain_at_end` (0 albo combo
    wciaz zywe, gdy partia sie skonczyla/zostala ucieta zanim lancuch pekl).
    """
    policy.reset(seed)
    game = Game(seed=seed)

    placement_points_total = 0
    clear_points_total = 0
    clears = 0
    max_combo = 0
    combo_at_clears = []
    chain_lengths = []
    breaks_no_legal_clear = 0
    breaks_policy_choice = 0
    capped = False

    while not game.done:
        if game.placements >= move_cap:
            capped = True
            break
        actions = game.available_actions()
        if not actions:
            break

        action = policy.act(game, actions)
        idx, _x, _y = action
        pieces_before = list(game.pieces)
        board_before = game.board.copy()
        placement_pts = scoring_placement_points(pieces_before[idx])
        combo_before = game.combo

        gained, _score, _done, _info = game.step(action)
        lines = game.last_lines_cleared
        combo_after = game.combo

        placement_points_total += placement_pts
        clear_points_total += gained - placement_pts

        if lines > 0:
            clears += 1
            max_combo = max(max_combo, combo_after)
            combo_at_clears.append(combo_after)
        elif combo_before > 0 and combo_after == 0:
            chain_lengths.append(combo_before)
            if _any_action_would_clear(board_before, pieces_before, actions):
                breaks_policy_choice += 1
            else:
                breaks_no_legal_clear += 1

    return {
        "seed": seed,
        "score": game.score,
        "survival": game.placements,
        "capped": capped,
        "placement_points": placement_points_total,
        "clear_points": clear_points_total,
        "clears": clears,
        "max_combo": max_combo,
        "mean_combo_at_clear": (
            round(statistics.mean(combo_at_clears), 4) if combo_at_clears else None
        ),
        "breaks": len(chain_lengths),
        "breaks_no_legal_clear": breaks_no_legal_clear,
        "breaks_policy_choice": breaks_policy_choice,
        "chain_lengths": chain_lengths,
        "unresolved_chain_at_end": game.combo,
    }


def play_series_detailed(policy_name, weights, seeds, move_cap):
    """`play_game_detailed` na kazdym seedzie z `seeds`, ta sama polityka/wagi."""
    policy_cls = POLICY_CLASSES[policy_name]
    policy = policy_cls(weights=weights) if weights is not None else policy_cls()
    return [play_game_detailed(policy, seed, move_cap) for seed in seeds]


def combo_summary(records):
    """Agreguje rekordy `play_game_detailed` z calej serii (#119, kryteria akceptacji)."""
    total_score = sum(r["score"] for r in records)
    total_placement = sum(r["placement_points"] for r in records)
    total_clear = sum(r["clear_points"] for r in records)

    all_chain_lengths = [length for r in records for length in r["chain_lengths"]]
    censored_chain_lengths = [r["unresolved_chain_at_end"] for r in records if r["unresolved_chain_at_end"] > 0]
    pooled_chain_lengths = all_chain_lengths + censored_chain_lengths

    total_breaks = sum(r["breaks"] for r in records)
    total_no_legal = sum(r["breaks_no_legal_clear"] for r in records)
    total_policy_choice = sum(r["breaks_policy_choice"] for r in records)

    total_clears = sum(r["clears"] for r in records)
    combo_weighted_sum = sum(
        (r["mean_combo_at_clear"] or 0) * r["clears"] for r in records
    )

    return {
        "n_games": len(records),
        "total_score": total_score,
        "placement_points_pct": round(100.0 * total_placement / total_score, 2) if total_score else None,
        "clear_points_pct": round(100.0 * total_clear / total_score, 2) if total_score else None,
        "clears_per_game": summarize([r["clears"] for r in records]),
        "max_combo_per_game": summarize([r["max_combo"] for r in records]),
        "mean_combo_at_clear_pooled": (
            round(combo_weighted_sum / total_clears, 4) if total_clears else None
        ),
        "breaks_per_game": summarize([r["breaks"] for r in records]),
        "break_causes": {
            "total_breaks": total_breaks,
            "no_legal_clear": total_no_legal,
            "policy_choice": total_policy_choice,
            "no_legal_clear_pct": round(100.0 * total_no_legal / total_breaks, 2) if total_breaks else None,
            "policy_choice_pct": round(100.0 * total_policy_choice / total_breaks, 2) if total_breaks else None,
        },
        "chain_length": {
            "n_broken": len(all_chain_lengths),
            "n_censored_at_game_end": len(censored_chain_lengths),
            "median": round(statistics.median(pooled_chain_lengths), 2) if pooled_chain_lengths else None,
            "p90": round(percentile(pooled_chain_lengths, 90), 2) if pooled_chain_lengths else None,
            "max": max(pooled_chain_lengths) if pooled_chain_lengths else None,
        },
    }


def dump_series_detailed(path, records):
    """Zrzut partia-po-partii z pelnym rozbiciem punktow/combo (#119)."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)


def load_seeds_from_file(path, n_games):
    """Seedy wprost z pliku (np. `bench/seeds_fixed.json`), nie z `training_seeds()`.

    Plik jest lista (#112, jak `bench/seeds_fixed.json`), nie slownikiem.
    `n_games` obcina liste tak, jak `benchmark.py` obcina `n_seeds` — zeby
    wywolanie z domyslnym `--n-games` nie zaladowalo cichutko calego pliku.
    """
    with open(path, encoding="utf-8") as fh:
        seeds = json.load(fh)
    if not isinstance(seeds, list):
        raise ValueError(path + ": oczekiwano listy seedow, nie slownika")
    return seeds[:n_games] if n_games else seeds


def dump_series(path, seeds, scores, survivals, capped):
    """Zrzut partia-po-partii do JSON-a: `(seed, wynik, postawienia, ucieta)` (#112)."""
    rows = [
        {"seed": seed, "score": score, "survival": survival, "capped": bool(was_capped)}
        for seed, score, survival, was_capped in zip(seeds, scores, survivals, capped)
    ]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)


def summarize(values):
    mean = statistics.mean(values)
    sigma = statistics.pstdev(values)
    sem = sigma / (len(values) ** 0.5)
    return {
        "n": len(values),
        "mean": round(mean, 2),
        "sigma": round(sigma, 2),
        "cv": round(sigma / mean, 4) if mean else None,
        "sem": round(sem, 2),
        "sem_pct_of_mean": round(100.0 * sem / mean, 2) if mean else None,
    }


def _ranks(values):
    """Rangi srednie (remisy dostaja srednia rang) — do korelacji Spearmana."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs, ys):
    return statistics.correlation(_ranks(xs), _ranks(ys))


def games_per_candidate_table(sigma, mean, counts=(6, 16, 32, 64)):
    """SEM wyrazony w % sredniej i najmniejsza roznica miedzy dwoma niezaleznie
    ocenianymi kandydatami rozroznialna na poziomie 2 bledow standardowych.

    Zakladane: dwaj kandydaci o tej samej sigma, ocenieni na NIEZALEZNYCH
    proba ch (nie CRN/parowanie) — SE roznicy srednich to sqrt(2)*SEM, wiec
    prog wykrywalnosci to 2*sqrt(2)*SEM. Parowanie (te same seedy obu
    kandydatom, jak dzis w tune_weights.py) dalaby mniejszy prog przy
    dodatniej korelacji miedzy kandydatami — tego tutaj nie mierzymy.
    """
    rows = []
    for n in counts:
        sem = sigma / (n ** 0.5)
        sem_pct = 100.0 * sem / mean if mean else None
        min_diff = 2.0 * (2.0 ** 0.5) * sem
        min_diff_pct = 100.0 * min_diff / mean if mean else None
        rows.append({
            "n_games": n,
            "sem": round(sem, 2),
            "sem_pct_of_mean": round(sem_pct, 2) if sem_pct is not None else None,
            "min_detectable_diff": round(min_diff, 2),
            "min_detectable_diff_pct": round(min_diff_pct, 2) if min_diff_pct is not None else None,
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Sigma wyniku i przezycia partii, na seedach treningowych (#101)"
    )
    parser.add_argument("--policy", choices=sorted(POLICY_CLASSES), required=True)
    parser.add_argument("--weights-file", default=None,
                         help="plik z kluczem 'weights' (np. weights.json); brak = wagi domyslne polityki")
    parser.add_argument("--n-games", type=int, default=150)
    parser.add_argument("--salt", type=int, default=DEFAULT_SALT,
                         help="sol training_seeds(); ta sama sol na obu politykach daje te same seedy")
    parser.add_argument("--seed-file", default=None,
                         help="plik z lista seedow (np. bench/seeds_fixed.json); pomija training_seeds() "
                              "i --salt, bierze pierwsze --n-games seedow wprost z pliku")
    parser.add_argument("--config", default=BENCH_CONFIG)
    parser.add_argument("--out", default=None, help="opcjonalna sciezka do zapisu surowego JSON")
    parser.add_argument("--series-out", default=None,
                         help="opcjonalna sciezka do zrzutu serii partia-po-partii (seed, score, survival, capped)")
    parser.add_argument("--detailed", action="store_true",
                         help="#119: rozbicie punktow (placement/clear) i statystyki combo na partie; "
                              "--series-out zrzuca pelne rekordy zamiast (seed, score, survival, capped)")
    args = parser.parse_args(argv)

    bench_seeds, move_cap = load_bench_seeds(args.config)
    if args.seed_file:
        seeds = load_seeds_from_file(args.seed_file, args.n_games)
    else:
        seeds = training_seeds(args.n_games, bench_seeds, salt=args.salt)
    weights = load_weights(args.weights_file)

    if args.detailed:
        records = play_series_detailed(args.policy, weights, seeds, move_cap)
        scores = [r["score"] for r in records]
        survivals = [r["survival"] for r in records]
    else:
        scores, survivals, capped = play_series(args.policy, weights, seeds, move_cap)

    result = {
        "policy": args.policy,
        "weights_file": args.weights_file,
        "n_games": len(seeds),
        "salt": args.salt if not args.seed_file else None,
        "seed_file": args.seed_file,
        "score": summarize(scores),
        "survival": summarize(survivals),
        "pearson_score_survival": round(statistics.correlation(scores, survivals), 4),
        "spearman_score_survival": round(spearman(scores, survivals), 4),
        "games_per_candidate": {
            "score": games_per_candidate_table(summarize(scores)["sigma"], summarize(scores)["mean"]),
            "survival": games_per_candidate_table(summarize(survivals)["sigma"], summarize(survivals)["mean"]),
        },
    }
    if args.detailed:
        result["combo"] = combo_summary(records)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
    if args.series_out:
        if args.detailed:
            dump_series_detailed(args.series_out, records)
        else:
            dump_series(args.series_out, seeds, scores, survivals, capped)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
