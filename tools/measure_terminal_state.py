"""
Mierzy jak umiera partia (#128): stan planszy w chwili konca, ktory typ klocka
zabija, czy szesc recznych cech (`features.FEATURE_NAMES`) widzi nadchodzaca
smierc wczesniej, i czy smierc byla wymuszona geometria czy wyborem polityki.

Nie zmienia `features.py`, `policies.py`, `game.py` ani zadnego pliku wag —
wlasna petla rozgrywki (wzor: `tools/measure_score_noise.py --detailed`),
czyta publiczny stan `Game`/`Board` z zewnatrz, niczego w nim nie zmienia.
Bez sieci, bez emulatora, nic w tle.

    python3 tools/measure_terminal_state.py --n-games 100 \\
        --out docs/data/terminal-state-100-summary.json \\
        --series-out docs/data/terminal-state-100.json

Metoda (d), "czy polityka mogla uciec": dla kazdej z ostatnich (do) 10 tur
kazdej partii sprawdzamy jeden pol-ruch w przod (symulacja na kopii planszy,
`Board.copy()`, ten sam trik co `policies._simulate_placement` i
`measure_score_noise._any_action_would_clear`) -- czy ktorykolwiek NIEWYBRANY
legalny ruch tamtej tury zostawia przynajmniej jedno legalne postawienie dla
pozostalych klockow z tacki. Dla ostatniej tury partii (`pos_from_end=0`) to
pytanie jest doslowne: "czy smierc dalo sie ominac". Dla wczesniejszych tur
(`pos_from_end=1..9`) rzeczywisty ruch z definicji przezyl (gra trwala dalej),
wiec sprawdzenie mowi cos innego: czy wybrany ruch byl JEDYNYM przezywajacym
(pulapka juz zamknieta N tur przed faktycznym koncem), czy byl jednym z wielu.
Nie jest to pelna symulacja calej reszty partii (tego "jeden pol-ruch"
celowo unika) -- tylko najblizszy horyzont.
"""
import argparse
import collections
import json
import os
import random
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import percentile
from board import Board
from features import FEATURE_NAMES, features
from game import Game
from pieces import CANONICAL_TYPES
from policies import LookaheadPolicy

K_VALUES = (1, 5, 10, 20)
DEATH_WINDOW = 10

BENCH_CONFIG = "bench/config.json"
BENCH_SEEDS = "bench/seeds_fixed.json"


def load_bench_seeds(n_games, config_path=BENCH_CONFIG):
    with open(config_path, encoding="utf-8") as fh:
        config = json.load(fh)
    with open(config["fixed_seed_file"], encoding="utf-8") as fh:
        seeds = json.load(fh)[:n_games]
    return seeds, config["move_cap"]


def load_weights(path):
    if path is None:
        return None
    with open(path, encoding="utf-8") as fh:
        return tuple(json.load(fh)["weights"])


def can_place_any_on(board, pieces):
    """Czy ktorykolwiek z `pieces` (moga byc `None`) da sie gdziekolwiek postawic na `board`."""
    for piece in pieces:
        if piece is None:
            continue
        for y in range(Board.HEIGHT - len(piece.shape) + 1):
            for x in range(Board.WIDTH - len(piece.shape[0]) + 1):
                if board.can_place_piece(piece, x, y):
                    return True
    return False


def connected_empty_regions(grid):
    """Wielkosci (w komorkach) spojnych (4-sasiedztwo) obszarow pustych pol.

    Niezalezne od `features._empty_regions` (ktora liczy tylko ILE obszarow,
    nie ich rozmiary) -- osobna implementacja na `board.grid`, nie na maskach
    bitowych; test krzyzuje liczbe obszarow miedzy obiema.
    """
    height = len(grid)
    width = len(grid[0])
    seen = [[False] * width for _ in range(height)]
    sizes = []
    for y0 in range(height):
        for x0 in range(width):
            if grid[y0][x0] or seen[y0][x0]:
                continue
            size = 0
            stack = [(y0, x0)]
            seen[y0][x0] = True
            while stack:
                y, x = stack.pop()
                size += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width and not grid[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            sizes.append(size)
    return sizes


def _simulate_alt_leaves_move(board_before, pieces_before, alt_action):
    """Jeden pol-ruch w przod: `alt_action` zamiast tego, co naprawde wybrano.

    Kopia planszy (`Board.copy()`), postawienie, czyszczenie linii -- ten sam
    wzor co `policies._simulate_placement` -- i sprawdzenie, czy cokolwiek z
    pozostalej tacki (bez klocka uzytego w `alt_action`) da sie jeszcze
    postawic. Nie idzie dalej niz jeden ply -- pelna re-symulacja reszty
    partii jest tu celowo pominieta.
    """
    idx, x, y = alt_action
    sim_board = board_before.copy()
    sim_board.place_piece(pieces_before[idx], x, y)
    rows, cols = sim_board.check_full_lines()
    sim_board.clear_lines(rows, cols)
    remaining = list(pieces_before)
    remaining[idx] = None
    return can_place_any_on(sim_board, remaining)


def play_game_trace(policy, seed, move_cap):
    """Rozgrywa jedna partie, zwraca `(per_turn_metrics, window, terminal_pieces, placements)`.

    `per_turn_metrics`: lista slownikow (jeden na udane postawienie) z cechami
    i metrykami planszy PO tym postawieniu (`board_after`).
    `window`: do ostatnich `DEATH_WINDOW` tur, kazda ze stanem PRZED
    postawieniem (`board_before`/`pieces_before`/`actions`/`chosen`), w
    kolejnosci chronologicznej -- potrzebne do (d).
    """
    policy.reset(seed)
    game = Game(seed=seed)
    per_turn_metrics = []
    window = collections.deque(maxlen=DEATH_WINDOW)

    while not game.done:
        if game.placements >= move_cap:
            break
        actions = game.available_actions()
        if not actions:
            break

        board_before = game.board.copy()
        pieces_before = list(game.pieces)
        action = policy.act(game, actions)
        game.step(action)

        board_after = game.board
        empty_sizes = connected_empty_regions(board_after.grid)
        per_turn_metrics.append({
            "features": features(board_after),
            "occupied_cells": sum(sum(row) for row in board_after.grid),
            "empty_regions": len(empty_sizes),
            "largest_empty_region": max(empty_sizes) if empty_sizes else 0,
        })
        window.append({
            "board_before": board_before,
            "pieces_before": pieces_before,
            "actions": actions,
            "chosen": action,
        })

    terminal_pieces = [p for p in game.pieces if p is not None]
    return per_turn_metrics, list(window), terminal_pieces, game.placements


def analyze_game(policy, seed, move_cap):
    """Jedna partia -> rekord JSON-friendly do agregacji (patrz funkcje `summarize_*`)."""
    per_turn, window, terminal_pieces, placements = play_game_trace(policy, seed, move_cap)
    capped = placements >= move_cap
    result = {"seed": seed, "survival": placements, "capped": capped}
    if capped or not per_turn:
        return result

    terminal = per_turn[-1]
    result["terminal_occupied_cells"] = terminal["occupied_cells"]
    result["terminal_empty_regions"] = terminal["empty_regions"]
    result["terminal_largest_empty_region"] = terminal["largest_empty_region"]
    result["terminal_piece_types"] = [CANONICAL_TYPES[p.type_index][0] for p in terminal_pieces]

    rng = random.Random(seed)
    random_idx = rng.randrange(len(per_turn))
    result["random_turn_index"] = random_idx
    result["feature_random"] = per_turn[random_idx]["features"]

    end_idx = len(per_turn) - 1
    feature_at_k = {}
    for k in K_VALUES:
        idx = end_idx - k
        feature_at_k[str(k)] = per_turn[idx]["features"] if idx >= 0 else None
    result["feature_at_k"] = feature_at_k

    escape_window = []
    n_window = len(window)
    for pos in range(n_window):
        turn = window[n_window - 1 - pos]
        escapable = any(
            _simulate_alt_leaves_move(turn["board_before"], turn["pieces_before"], alt)
            for alt in turn["actions"] if alt != turn["chosen"]
        )
        escape_window.append({"pos_from_end": pos, "escapable": escapable})
    result["escape_window"] = escape_window
    return result


def distribution_summary(values):
    if not values:
        return None
    return {
        "n": len(values),
        "median": round(statistics.median(values), 2),
        "p10": round(percentile(values, 10), 2),
        "p90": round(percentile(values, 90), 2),
    }


def summarize_terminal_board(records):
    """(a): rozklad stanu planszy w chwili konca, na rekordach z `analyze_game`."""
    valid = [r for r in records if not r.get("capped") and "terminal_occupied_cells" in r]
    return {
        "n": len(valid),
        "n_excluded_capped_or_empty": len(records) - len(valid),
        "occupied_cells": distribution_summary([r["terminal_occupied_cells"] for r in valid]),
        "empty_regions": distribution_summary([r["terminal_empty_regions"] for r in valid]),
        "largest_empty_region": distribution_summary([r["terminal_largest_empty_region"] for r in valid]),
    }


def piece_type_distribution(records):
    """(b): rozklad typow klockow z tacki w chwili konca (kazdy taki klocek nie mial
    zadnego legalnego postawienia, bo `_can_place_any` sprawdza kazdy z osobna)."""
    counter = Counter()
    for r in records:
        for name in r.get("terminal_piece_types", []):
            counter[name] += 1
    total = sum(counter.values())
    by_type = {
        name: {"count": count, "pct": round(100.0 * count / total, 2)}
        for name, count in counter.items()
    } if total else {}
    dominant = max(counter, key=counter.get) if counter else None
    return {
        "total": total,
        "by_type": by_type,
        "dominant": dominant,
        "dominant_pct": round(100.0 * counter[dominant] / total, 2) if dominant else None,
    }


def cliffs_delta(a, b):
    """Cliff's delta w [-1, 1]: 0 = brak separacji, +-1 = separacja pelna.
    `> 0` znaczy: wartosci z `a` typowo wieksze niz z `b`."""
    if not a or not b:
        return None
    gt = lt = 0
    for x in a:
        for y in b:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1
    return (gt - lt) / (len(a) * len(b))


def feature_k_vs_random(records, feature_index, k):
    """(c) dla jednej cechy/jednego K: rozklad `K postawien przed koncem` kontra
    rozklad `losowa tura tej samej partii`, i separacja (Cliff's delta)."""
    k_values = [
        r["feature_at_k"][str(k)][feature_index]
        for r in records
        if r.get("feature_at_k", {}).get(str(k)) is not None
    ]
    random_values = [r["feature_random"][feature_index] for r in records if "feature_random" in r]
    delta = cliffs_delta(k_values, random_values)
    return {
        "k": k,
        "n_k": len(k_values),
        "n_random": len(random_values),
        "k_summary": distribution_summary(k_values),
        "random_summary": distribution_summary(random_values),
        "cliffs_delta": round(delta, 4) if delta is not None else None,
    }


def escape_stats(records):
    """(d): dla kazdej pozycji `pos_from_end` (0 = ostatnia tura partii) w oknie
    ostatnich `DEATH_WINDOW` tur, odsetek tur wymuszonych (`forced_pct`, zaden
    inny legalny ruch nie przezylby jednego pol-ruchu dluzej) kontra tur, w
    ktorych alternatywa istniala (`policy_choice_pct`)."""
    by_pos = {}
    for r in records:
        for w in r.get("escape_window", []):
            by_pos.setdefault(w["pos_from_end"], []).append(w["escapable"])
    out = {}
    for pos, vals in sorted(by_pos.items()):
        n = len(vals)
        n_escapable = sum(1 for v in vals if v)
        out[pos] = {
            "n": n,
            "forced_pct": round(100.0 * (n - n_escapable) / n, 2),
            "policy_choice_pct": round(100.0 * n_escapable / n, 2),
        }
    return out


def build_report(records):
    report = {
        "n_games": len(records),
        "n_capped": sum(1 for r in records if r.get("capped")),
        "terminal_board": summarize_terminal_board(records),
        "killer_piece_types": piece_type_distribution(records),
        "feature_predictiveness": {
            name: [feature_k_vs_random(records, i, k) for k in K_VALUES]
            for i, name in enumerate(FEATURE_NAMES)
        },
        "escape_by_turns_before_end": escape_stats(records),
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Jak umiera partia lookahead:weights.json (#128)")
    parser.add_argument("--weights-file", default="weights.json")
    parser.add_argument("--n-games", type=int, default=100)
    parser.add_argument("--config", default=BENCH_CONFIG)
    parser.add_argument("--out", default=None, help="sciezka do zapisu zagregowanego raportu JSON")
    parser.add_argument("--series-out", default=None, help="sciezka do zapisu surowych rekordow partia-po-partii")
    args = parser.parse_args(argv)

    seeds, move_cap = load_bench_seeds(args.n_games, args.config)
    weights = load_weights(args.weights_file)
    policy = LookaheadPolicy(weights=weights) if weights is not None else LookaheadPolicy()

    records = [analyze_game(policy, seed, move_cap) for seed in seeds]
    report = build_report(records)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
    if args.series_out:
        with open(args.series_out, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
