#!/usr/bin/env python3
"""
Z-6 pomiar 2 (#182): testy (a)-(d) na parach z `docs/data/z6-pary.json` wobec
H0 = `generator.py` (`Generator`: typ 1/15, potem orientacja 1/n w obrębie typu,
niezależnie od planszy, trzy klocki niezależnie). Bez scipy — jak
`tools/analiza_z6.py` (pomiar 1, #78), stąd import stamtąd zamiast duplikacji
(splot Poissona-dwumianowego, moc przybliżeniem normalnym).

Testy:
  (a) chi-kwadrat: częstości typów (15 kategorii) i orientacji (41 kategorii)
      wylosowanych klocków wobec jednostajnego H0.
  (b) test 1 z pomiaru 1 (#78): czy wylosowane typy mieszczą się na planszy
      częściej niż H0 (Poisson-dwumianowy) — ze stratyfikacją po zapełnieniu
      planszy (kwartyle tej próby), żeby ominąć efekt sufitowy z pomiaru 1.
  (c) grywalność całej tacki (można postawić wszystkie trzy w jakiejś
      kolejności, z czyszczeniem pełnych linii między postawieniami — stąd
      "w jakiejś kolejności" ma znaczenie) wobec oczekiwania H0 policzonego
      Monte Carlo (ziarno stałe) NA TYCH SAMYCH planszach, testem
      Poissona-dwumianowym (p_i różne per plansza, tak jak w (b)).
  (d) to samo co (c), tylko na planszach, gdzie MC-H0 daje grywalność < 0,9 —
      tam różnica byłaby najbardziej widoczna.

P-wartości korygowane Bonferronim za łączną liczbę testów wykonanych w tym
pomiarze (dynamicznie: 2 z (a) + liczba niepustych kwartyli z (b) + 1 z (c) +
1 z (d), patrz `n_tests_bonferroni` w wyniku).
"""
import json
import math
import os
import sys
from collections import Counter
from itertools import permutations

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from board import Board  # noqa: E402
from generator import PIECE_TYPE_WEIGHTS, Generator  # noqa: E402
from pieces import CANONICAL_TYPES, PIECE_POOL, PIECE_TYPES  # noqa: E402

from analiza_z6 import poisson_binomial_pmf, power_normal_approx  # noqa: E402

PAIRS_PATH = os.path.join(REPO_ROOT, "docs", "data", "z6-pary.json")
N_TYPES = len(CANONICAL_TYPES)
N_POSES = len(PIECE_POOL)
MC_SEED = 182
MC_REPS = 500
NODE_BUDGET = 20000
ALPHA = 0.05

# Przebiegi mostu, których pary weszły do kalibracji wag typów w `generator.py`
# (#186, patrz `docs/generator-wagi-typow.md` "Źródło i liczność próby": 326 par,
# `docs/data/z6-pary.json` w stanie sprzed dołożenia przebiegu tego cyklu). Test (a)
# na tych parach byłby kołowy -- wagi H0 pochodzą z tych samych obserwacji -- więc
# pomiar 3 (#191) liczy (a) tylko na parach spoza tego zbioru.
CALIBRATION_RUN_DIRS = frozenset(
    {"0d96333", "1402cff", "1bd38fa", "495cd91", "b4a7d26", "c1819ed", "d550db3", "d878d79"}
)

NAME_TO_TYPE = {p.name: p.type_index for p in PIECE_POOL}
NAME_TO_POSE = {p.name: p.index for p in PIECE_POOL}

# H0 = generator.py SKALIBROWANY (#186): typ losowany wg PIECE_TYPE_WEIGHTS, nie
# jednostajnie 1/15 jak w pomiarze 2 (#182) -- inaczej test (a) tego pomiaru
# odrzucałby H0 tylko dlatego, że testuje niewłaściwy (już nieaktualny) model.
_WEIGHT_SUM = sum(PIECE_TYPE_WEIGHTS)
TYPE_PROB_H0 = [w / _WEIGHT_SUM for w in PIECE_TYPE_WEIGHTS]


# ---------- chi-kwadrat: dystrybuanta bez scipy (Numerical Recipes gser/gcf) ----------


def _gser(a, x, itmax=500, eps=1e-14):
    if x <= 0:
        return 0.0
    gln = math.lgamma(a)
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(itmax):
        ap += 1
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * eps:
            break
    return total * math.exp(-x + a * math.log(x) - gln)


def _gcf(a, x, itmax=500, eps=1e-14, fpmin=1e-300):
    gln = math.lgamma(a)
    b = x + 1 - a
    c = 1 / fpmin
    d = 1 / b
    h = d
    for i in range(1, itmax + 1):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < eps:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def chi2_sf(x, df):
    """P-wartość (ogon górny) rozkładu chi-kwadrat: P(X >= x), df stopni swobody."""
    if x <= 0:
        return 1.0
    a = df / 2.0
    xx = x / 2.0
    if xx < a + 1:
        return 1.0 - _gser(a, xx)
    return _gcf(a, xx)


# ---------- statyczna grywalność typu (test b, metoda #78) ----------


class _FakePiece:
    def __init__(self, shape):
        self.shape = shape


def _fits_somewhere(board, shape):
    for y in range(Board.HEIGHT):
        for x in range(Board.WIDTH):
            if board.can_place_piece(_FakePiece(shape), x, y):
                return True
    return False


def playable_types(grid):
    board = Board()
    board.grid = grid
    playable = set()
    for type_index, pose_indices in enumerate(PIECE_TYPES):
        for pose_index in pose_indices:
            shape = PIECE_POOL[pose_index].shape
            if _fits_somewhere(board, shape):
                playable.add(type_index)
                break
    return playable


# ---------- grywalność całej tacki, z czyszczeniem linii (testy c, d) ----------


def _can_place(grid, shape, x, y):
    for dy, row in enumerate(shape):
        for dx, cell in enumerate(row):
            if cell:
                bx, by = x + dx, y + dy
                if not (0 <= bx < Board.WIDTH and 0 <= by < Board.HEIGHT):
                    return False
                if grid[by][bx]:
                    return False
    return True


def _place_and_clear(grid, shape, x, y):
    new_grid = [row[:] for row in grid]
    for dy, row in enumerate(shape):
        for dx, cell in enumerate(row):
            if cell:
                new_grid[y + dy][x + dx] = 1
    full_rows = [i for i, row in enumerate(new_grid) if all(row)]
    full_cols = [c for c in range(Board.WIDTH) if all(new_grid[r][c] for r in range(Board.HEIGHT))]
    for r in full_rows:
        new_grid[r] = [0] * Board.WIDTH
    for c in full_cols:
        for r in range(Board.HEIGHT):
            new_grid[r][c] = 0
    return new_grid


def _dfs_playable(grid, shapes, idx, budget):
    if idx == len(shapes):
        return True, budget
    shape = shapes[idx]
    for y in range(Board.HEIGHT):
        for x in range(Board.WIDTH):
            if budget <= 0:
                return None, budget
            budget -= 1
            if _can_place(grid, shape, x, y):
                new_grid = _place_and_clear(grid, shape, x, y)
                result, budget = _dfs_playable(new_grid, shapes, idx + 1, budget)
                if result:
                    return True, budget
                if result is None:
                    return None, budget
    return False, budget


def tray_playable(grid, shapes, node_budget=NODE_BUDGET):
    """Czy da się postawić wszystkie 3 kształty w JAKIEJŚ kolejności, z
    czyszczeniem pełnych linii między postawieniami (stąd kolejność ma
    znaczenie — inaczej niż statyczne `playable_types`). Zwraca True/False,
    albo None gdy `node_budget` (łączny, przez wszystkie 6 permutacji) się
    wyczerpał zanim padło rozstrzygnięcie."""
    budget = node_budget
    for perm in permutations(range(3)):
        ordered = [shapes[i] for i in perm]
        result, budget = _dfs_playable(grid, ordered, 0, budget)
        if result:
            return True
        if result is None:
            return None
    return False


# ---------- wczytanie par i cechy ----------


def load_pairs(path=PAIRS_PATH):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["pairs"]


def pair_run_dir(pair_id):
    return pair_id.split("/")[0]


def is_out_of_calibration(pair_id):
    return pair_run_dir(pair_id) not in CALIBRATION_RUN_DIRS


def build_rows(pairs):
    rows = []
    for pair in pairs:
        grid = pair["board"]
        playable = playable_types(grid)
        n_filled = sum(sum(r) for r in grid)
        fill = n_filled / (Board.WIDTH * Board.HEIGHT)
        names = [t["name"] for t in pair["tray"]]
        type_indices = [NAME_TO_TYPE[n] for n in names]
        shapes = [PIECE_POOL[NAME_TO_POSE[n]].shape for n in names]
        rows.append(
            {
                "id": pair["id"],
                "board": grid,
                "fill": fill,
                "n_playable_types": len(playable),
                "type_indices": type_indices,
                "pose_names": names,
                "tray_playable_type": [t in playable for t in type_indices],
                "shapes": shapes,
            }
        )
    return rows


# ---------- test (a): chi-kwadrat typów i orientacji ----------


def chi_square_types(rows):
    """H0 = generator.py skalibrowany (#186): typ losowany wg TYPE_PROB_H0, nie
    jednostajnie 1/15 (to była H0 pomiaru 2, #182 - już nieaktualna)."""
    counts = Counter()
    for r in rows:
        for t in r["type_indices"]:
            counts[t] += 1
    n = sum(counts.values())
    stat = 0.0
    expected_by_type = {}
    for t in range(N_TYPES):
        expected = n * TYPE_PROB_H0[t]
        expected_by_type[t] = expected
        stat += (counts.get(t, 0) - expected) ** 2 / expected
    df = N_TYPES - 1
    return {
        "n_draws": n,
        "chi2": stat,
        "df": df,
        "p_value": chi2_sf(stat, df),
        "expected_by_type": {CANONICAL_TYPES[t][0]: expected_by_type[t] for t in range(N_TYPES)},
        "observed_by_type": {CANONICAL_TYPES[t][0]: counts.get(t, 0) for t in range(N_TYPES)},
    }


def chi_square_orientations(rows):
    """H0 = generator.py skalibrowany: typ wg TYPE_PROB_H0, orientacja w obrębie
    typu wciąż 1/n (niezmieniona przez #186)."""
    counts = Counter()
    for r in rows:
        for name in r["pose_names"]:
            counts[name] += 1
    n = sum(counts.values())
    stat = 0.0
    for piece in PIECE_POOL:
        n_poses_in_type = len(PIECE_TYPES[piece.type_index])
        expected = n * TYPE_PROB_H0[piece.type_index] * (1.0 / n_poses_in_type)
        observed = counts.get(piece.name, 0)
        stat += (observed - expected) ** 2 / expected
    df = N_POSES - 1
    return {
        "n_draws": n,
        "chi2": stat,
        "df": df,
        "p_value": chi2_sf(stat, df),
    }


# ---------- test (b): test 1 z #78, stratyfikowany po zapełnieniu ----------


def quartile_edges(values, n_bins=4):
    xs = sorted(values)
    n = len(xs)
    edges = []
    for i in range(1, n_bins):
        idx = min(n - 1, (i * n) // n_bins)
        edges.append(xs[idx])
    # unikalne, rosnące progi (przy powtórzeniach wartości kwartyle mogą się zlepić)
    unique_edges = sorted(set(edges))
    return unique_edges


def assign_bin(fill, edges):
    for i, edge in enumerate(edges):
        if fill <= edge:
            return i
    return len(edges)


def test1_stratified(rows, n_bins=4):
    edges = quartile_edges([r["fill"] for r in rows], n_bins)
    n_actual_bins = len(edges) + 1
    bins = [[] for _ in range(n_actual_bins)]
    for r in rows:
        bins[assign_bin(r["fill"], edges)].append(r)

    results = []
    for i, bin_rows in enumerate(bins):
        probs = []
        observed = 0
        for r in bin_rows:
            p_i = r["n_playable_types"] / N_TYPES
            for is_playable in r["tray_playable_type"]:
                probs.append(p_i)
                if is_playable:
                    observed += 1
        entry = {
            "bin": i,
            "n_pairs": len(bin_rows),
            "fill_range": [min((r["fill"] for r in bin_rows), default=None),
                           max((r["fill"] for r in bin_rows), default=None)],
            "n_draws": len(probs),
        }
        if probs:
            pmf = poisson_binomial_pmf(probs)
            expected = sum(probs)
            entry.update(
                {
                    "observed_playable": observed,
                    "expected_playable_h0": expected,
                    "p_value_one_sided_ge": sum(m for k, m in enumerate(pmf) if k >= observed),
                    "power_grid": [power_normal_approx(probs, delta=d) for d in (0.01, 0.05, 0.10)],
                }
            )
        results.append(entry)
    return {"edges": edges, "bins": results}


# ---------- testy (c), (d): grywalność całej tacki, MC vs obserwacja ----------


def mc_expected_playability(rows, mc_reps=MC_REPS, seed=MC_SEED):
    gen = Generator(seed=seed)
    results = {}
    for r in rows:
        playable = 0
        unknown = 0
        for _ in range(mc_reps):
            pieces = gen.next_pieces()
            shapes = [p.shape for p in pieces]
            outcome = tray_playable(r["board"], shapes)
            if outcome is None:
                unknown += 1
            elif outcome:
                playable += 1
        denom = mc_reps - unknown
        results[r["id"]] = {
            "p_h0": (playable / denom) if denom else None,
            "unknown": unknown,
            "reps": mc_reps,
        }
    return results


def observed_playability(rows):
    results = {}
    for r in rows:
        results[r["id"]] = tray_playable(r["board"], r["shapes"])
    return results


def poisson_binomial_test(probs, observed):
    pmf = poisson_binomial_pmf(probs)
    expected = sum(probs)
    p_ge = sum(m for k, m in enumerate(pmf) if k >= observed)
    p_obs = pmf[observed]
    p_two_sided = sum(m for m in pmf if m <= p_obs + 1e-15)
    return {
        "n": len(probs),
        "observed_playable": observed,
        "expected_playable_h0": expected,
        "p_value_one_sided_ge": p_ge,
        "p_value_two_sided": p_two_sided,
    }


def tray_playability_test(rows, mc_results, obs_results, subset_ids=None):
    probs = []
    observed = 0
    n_unknown_mc = 0
    n_unknown_obs = 0
    n_subset_total = 0
    for r in rows:
        if subset_ids is not None and r["id"] not in subset_ids:
            continue
        n_subset_total += 1
        mc = mc_results[r["id"]]
        obs = obs_results[r["id"]]
        if mc["p_h0"] is None:
            n_unknown_mc += 1
            continue
        if obs is None:
            n_unknown_obs += 1
            continue
        probs.append(mc["p_h0"])
        if obs:
            observed += 1

    if not probs:
        return {"n": 0, "n_unknown_mc": n_unknown_mc, "n_unknown_obs": n_unknown_obs,
                "n_subset_total": n_subset_total}

    result = poisson_binomial_test(probs, observed)
    result["n_unknown_mc"] = n_unknown_mc
    result["n_unknown_obs"] = n_unknown_obs
    result["n_subset_total"] = n_subset_total
    result["power_grid"] = [power_normal_approx(probs, delta=d) for d in (0.01, 0.05, 0.10)]
    return result


# ---------- werdykt ----------


def run_all(pairs=None):
    if pairs is None:
        pairs = load_pairs()
    rows = build_rows(pairs)
    new_rows = [r for r in rows if is_out_of_calibration(r["id"])]

    if new_rows:
        test_a_types = chi_square_types(new_rows)
        test_a_orient = chi_square_orientations(new_rows)
        n_a_tests = 2
    else:
        test_a_types = None
        test_a_orient = None
        n_a_tests = 0
    test_b = test1_stratified(rows)

    mc_results = mc_expected_playability(rows)
    obs_results = observed_playability(rows)
    test_c = tray_playability_test(rows, mc_results, obs_results)

    low_ids = {
        rid for rid, mc in mc_results.items() if mc["p_h0"] is not None and mc["p_h0"] < 0.9
    }
    test_d = tray_playability_test(rows, mc_results, obs_results, subset_ids=low_ids)

    n_bins_used = sum(1 for b in test_b["bins"] if b["n_draws"] > 0)
    n_tests = n_a_tests + n_bins_used + 1 + 1
    alpha_bonf = ALPHA / n_tests

    return {
        "n_pairs": len(rows),
        "n_pairs_out_of_calibration": len(new_rows),
        "fill_min": min((r["fill"] for r in rows), default=None),
        "fill_median": sorted(r["fill"] for r in rows)[len(rows) // 2] if rows else None,
        "fill_max": max((r["fill"] for r in rows), default=None),
        "fill_min_out_of_calibration": min((r["fill"] for r in new_rows), default=None),
        "fill_median_out_of_calibration": (
            sorted(r["fill"] for r in new_rows)[len(new_rows) // 2] if new_rows else None
        ),
        "fill_max_out_of_calibration": max((r["fill"] for r in new_rows), default=None),
        "test_a_types": test_a_types,
        "test_a_orientations": test_a_orient,
        "test_b_stratified": test_b,
        "test_c_tray_playability": test_c,
        "test_d_tray_playability_low_h0": test_d,
        "n_low_h0_boards": len(low_ids),
        "mc_seed": MC_SEED,
        "mc_reps": MC_REPS,
        "alpha": ALPHA,
        "n_tests_bonferroni": n_tests,
        "alpha_bonferroni": alpha_bonf,
    }


def _fmt_p(p):
    return f"{p:.4g}"


def main():
    result = run_all()
    print(f"pary: {result['n_pairs']} (spoza próby kalibracyjnej: {result['n_pairs_out_of_calibration']}), "
          f"zapełnienie: min={result['fill_min']:.3f} "
          f"mediana={result['fill_median']:.3f} max={result['fill_max']:.3f}")
    print(f"korekta Bonferroniego: {result['n_tests_bonferroni']} testów, "
          f"alpha={result['alpha_bonferroni']:.5f} (z {result['alpha']})")
    print()
    a_t = result["test_a_types"]
    a_o = result["test_a_orientations"]
    if a_t is None:
        print("(a) pominięty: brak par spoza próby kalibracyjnej wag (byłby kołowy)")
    else:
        print(f"(a) chi-kwadrat typów [tylko pary spoza kalibracji]: n={a_t['n_draws']} "
              f"chi2={a_t['chi2']:.3f} df={a_t['df']} p={_fmt_p(a_t['p_value'])}")
        print(f"(a) chi-kwadrat orientacji [tylko pary spoza kalibracji]: n={a_o['n_draws']} "
              f"chi2={a_o['chi2']:.3f} df={a_o['df']} p={_fmt_p(a_o['p_value'])}")
    print()
    print(f"(b) test 1 (#78) stratyfikowany, progi kwartyli: {result['test_b_stratified']['edges']}")
    for b in result["test_b_stratified"]["bins"]:
        if b["n_draws"] == 0:
            print(f"  bin {b['bin']}: brak par")
            continue
        print(f"  bin {b['bin']} (n_par={b['n_pairs']}, fill={b['fill_range']}): "
              f"obs={b['observed_playable']} exp={b['expected_playable_h0']:.2f} "
              f"p={_fmt_p(b['p_value_one_sided_ge'])}")
    print()
    c = result["test_c_tray_playability"]
    print(f"(c) grywalność całej tacki: n={c['n']} obs={c.get('observed_playable')} "
          f"exp={c.get('expected_playable_h0', 0):.2f} "
          f"p_ge={_fmt_p(c.get('p_value_one_sided_ge', 1))} "
          f"p_2s={_fmt_p(c.get('p_value_two_sided', 1))}")
    d = result["test_d_tray_playability_low_h0"]
    print(f"(d) to samo, tylko plansze z H0 grywalnością < 0.9 "
          f"(n_takich_plansz={result['n_low_h0_boards']}): n={d['n']} "
          f"obs={d.get('observed_playable')} exp={d.get('expected_playable_h0', 0):.2f} "
          f"p_ge={_fmt_p(d.get('p_value_one_sided_ge', 1))} "
          f"p_2s={_fmt_p(d.get('p_value_two_sided', 1))}")
    return result


if __name__ == "__main__":
    main()
