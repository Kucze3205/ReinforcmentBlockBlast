"""
Mierzy, ile sygnalu gubia obie kary -5 w game.step (issue #51).

Nie zmienia game.py. Powiela logike step() tutaj, zeby przechwycic
`gained`, ktore step wyrzuca w galezi game_over (linia 59) zamiast
zwrocic. Uruchamiane bez argumentow, bez sieci:

    python tools/measure_terminal_reward.py
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import fixed_seeds, load_config
from game import Game
from policies import GreedyPolicy

OUT_PATH = "docs/pomiar-kara-terminalna.md"


def measured_step(game, action):
    """Kopia game.step(), rozszerzona o prawdziwe `gained` przy game_over."""
    idx, x, y = action
    piece = game.pieces[idx] if 0 <= idx < len(game.pieces) else None
    if piece is None or not game.board.place_piece(piece, x, y):
        game.done = True
        return -5, "wrong_placement", None

    gained = game.apply_placement(idx)
    game.placements += 1

    if not game._can_place_any():
        game.done = True
        return -5, "game_over", gained

    return gained, "successful placement", gained


def play_episode(policy, seed, move_cap):
    game = Game(seed=seed)
    policy.reset(seed)

    episode_return = 0
    wrong_placement_count = 0
    game_over_discarded_gained = None
    capped = False

    while not game.done:
        if game.placements >= move_cap:
            capped = True
            break
        actions = game.available_actions()
        if not actions:
            break
        action = policy.act(game, actions)
        reward, event, true_gained = measured_step(game, action)
        episode_return += reward
        if event == "wrong_placement":
            wrong_placement_count += 1
        elif event == "game_over":
            game_over_discarded_gained = true_gained

    return {
        "episode_return": episode_return,
        "final_score": game.score,
        "wrong_placement_count": wrong_placement_count,
        "game_over_discarded_gained": game_over_discarded_gained,
        "capped": capped,
    }


def main():
    config = load_config()
    seeds = fixed_seeds(config)
    if len(seeds) < 300:
        print(
            "UWAGA: bench/seeds_fixed.json ma tylko {0} seedow (<300)".format(len(seeds)),
            file=sys.stderr,
        )
    move_cap = config["move_cap"]

    policy = GreedyPolicy()

    score_return_diffs = []
    score_return_pcts = []
    discarded_gains = []
    total_wrong_placement = 0
    n_capped = 0

    for seed in seeds:
        result = play_episode(policy, seed, move_cap)
        diff = result["final_score"] - result["episode_return"]
        score_return_diffs.append(diff)
        if result["final_score"]:
            score_return_pcts.append(100.0 * diff / result["final_score"])
        total_wrong_placement += result["wrong_placement_count"]
        if result["capped"]:
            n_capped += 1
        if result["game_over_discarded_gained"] is not None:
            discarded_gains.append(result["game_over_discarded_gained"])

    n = len(seeds)
    mean_diff = statistics.mean(score_return_diffs)
    mean_pct = statistics.mean(score_return_pcts) if score_return_pcts else 0.0

    mean_gain = statistics.mean(discarded_gains) if discarded_gains else 0.0
    median_gain = statistics.median(discarded_gains) if discarded_gains else 0.0
    max_gain = max(discarded_gains) if discarded_gains else 0.0

    report = []
    report.append("# Pomiar: ile sygnalu gubia obie kary -5 w game.step (#51)\n")
    report.append(
        "Polecenie odtwarzajace: `python tools/measure_terminal_reward.py`\n"
    )
    report.append(
        "Polityka: `GreedyPolicy` z policies.py. Seedy: pierwsze {0} z "
        "bench/seeds_fixed.json (stale, powtarzalne). move_cap = {1} "
        "(z bench/config.json).\n".format(n, move_cap)
    )

    report.append("## Suma nagrod z epizodu vs wynik partii\n")
    report.append(
        "Srednia roznica (wynik_partii - suma_nagrod) na partie: "
        "**{0:.2f}** punktu.\n".format(mean_diff)
    )
    report.append(
        "Srednia z (roznica / wynik_partii) na partie: **{0:.2f}%**.\n".format(mean_pct)
    )

    report.append("## `gained` wyrzucone w linii 59 (galaz game_over)\n")
    report.append(
        "Partii, ktore zakonczyly sie galezia game_over (nie ucietych sufitem ruchow): "
        "{0} z {1}.\n".format(len(discarded_gains), n)
    )
    report.append("- srednia: **{0:.2f}**".format(mean_gain))
    report.append("- mediana: **{0:.2f}**".format(median_gain))
    report.append("- maksimum: **{0:.2f}**\n".format(max_gain))

    report.append("## Galaz wrong_placement (linia 52)\n")
    report.append(
        "Liczba wystapien galezi wrong_placement na {0} partii polityki zachlannej "
        "(ktora wybiera wylacznie z listy legalnych akcji): **{1}**.\n".format(
            n, total_wrong_placement
        )
    )

    if n_capped:
        report.append(
            "Uwaga: {0} partii ucieto sufitem ruchow (move_cap={1}) i nie policzono ich "
            "do `gained` wyrzuconego w game_over (partia sie tam nie konczy przez ta galaz).\n".format(
                n_capped, move_cap
            )
        )

    text = "\n".join(report) + "\n"

    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(text)

    print(text)


if __name__ == "__main__":
    main()
