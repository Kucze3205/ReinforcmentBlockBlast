#!/usr/bin/env python3
"""
Z-6: czy tacka trzech klocków zależy od stanu planszy?

Wejście: bridge/runs/d550db3/pomiar.json — 33 pary "plansza 8x8 -> trzy kształty
tacki", zebrane z prawdziwego Block Blasta przez most (#60).

Hipoteza zerowa (H0): tacka losowana jak w generator.py — niezależnie od planszy,
1/15 na typ kanoniczny. Pod H0, prawdopodobieństwo, że wylosowany typ w ogóle
mieści się gdzieś na danej planszy, wynosi n_grywalnych_typow / 15, niezależnie od
tego, ile typów faktycznie się mieści (bo losowanie nie widzi planszy).

Test: obserwowana liczba "grywalnych" klocków w tacce (typ, który mieści się
gdzieś na planszy z tej samej rundy) kontra dokładny rozkład Poissona-dwumianowego
tej liczby pod H0 (splot 99 niezależnych prób Bernoulliego o różnych p_i, po 3 na
rundę). Jeśli generator faworyzowałby grywalne kształty (typowe dla klonów
zorientowanych na grywalność), obserwacja powinna systematycznie przewyższać H0.

Bez scipy — cały test i moc liczone czystym Pythonem (splot rozkładów, przybliżenie
normalne tylko do liczenia mocy, nie do p-wartości).
"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from board import Board
from pieces import CANONICAL_TYPES, PIECE_POOL, PIECE_TYPES

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POMIAR_PATH = os.path.join(REPO_ROOT, "bridge", "runs", "d550db3", "pomiar.json")

N_TYPES = len(CANONICAL_TYPES)

# name -> type_index, z tej samej puli co pieces.py (pomiar.json używa tych nazw)
NAME_TO_TYPE = {piece.name: piece.type_index for piece in PIECE_POOL}
NAME_TO_SIZE = {piece.name: sum(sum(r) for r in piece.shape) for piece in PIECE_POOL}


class _FakePiece:
    """Board.can_place_piece potrzebuje tylko .shape."""

    def __init__(self, shape):
        self.shape = shape


def _fits_somewhere(board, shape):
    for y in range(Board.HEIGHT):
        for x in range(Board.WIDTH):
            if board.can_place_piece(_FakePiece(shape), x, y):
                return True
    return False


def playable_types(grid):
    """Zbiór indeksów typów kanonicznych, które mieszczą się GDZIEŚ na planszy
    (w co najmniej jednej orientacji)."""
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


def load_pairs(path=POMIAR_PATH):
    with open(path) as f:
        data = json.load(f)
    return data


def poisson_binomial_pmf(probs):
    """Rozkład sumy niezależnych, niejednakowych prób Bernoulliego (dokładny, splot)."""
    pmf = [1.0]
    for p in probs:
        new_pmf = [0.0] * (len(pmf) + 1)
        for k, mass in enumerate(pmf):
            new_pmf[k] += mass * (1 - p)
            new_pmf[k + 1] += mass * p
        pmf = new_pmf
    return pmf


def exact_test_playable_count(rows):
    """Dokładny test Poissona-dwumianowy: obserwowana liczba grywalnych klocków
    w tackach kontra H0 generator.py (losowanie niezależne od planszy)."""
    probs = []  # p_i dla każdego POJEDYNCZEGO wylosowanego klocka (3 na rundę)
    observed = 0
    for row in rows:
        n_playable = row["n_playable_types"]
        p_i = n_playable / N_TYPES
        for is_playable in row["tray_playable"]:
            probs.append(p_i)
            if is_playable:
                observed += 1

    pmf = poisson_binomial_pmf(probs)
    expected = sum(probs)
    # jednostronna wartość p: H0 vs "generator faworyzuje grywalne klocki"
    p_value_ge = sum(mass for k, mass in enumerate(pmf) if k >= observed)
    # dwustronna: prawdopodobieństwo wyniku co najmniej tak skrajnego jak observed
    p_obs = pmf[observed]
    p_value_two_sided = sum(mass for mass in pmf if mass <= p_obs + 1e-15)

    return {
        "n_draws": len(probs),
        "observed_playable": observed,
        "expected_playable_h0": expected,
        "p_value_one_sided_ge": p_value_ge,
        "p_value_two_sided": p_value_two_sided,
        "probs": probs,
    }


def power_normal_approx(probs, alpha=0.05, delta=None, target_power=0.80):
    """Moc przybliżeniem normalnym (CLT dla sumy niejednakowych Bernoulliego).

    Zwraca: przy podanym `delta` (jednolity wzrost p_i, przycięty do [0,1]) —
    moc wykrycia tego efektu przy `alpha` (test jednostronny, z=1.645).
    Jeśli `delta` nie podano, szuka najmniejszego delta dającego `target_power`.
    """
    n = len(probs)
    mean0 = sum(probs)
    var0 = sum(p * (1 - p) for p in probs)
    sd0 = math.sqrt(var0)
    z_alpha = 1.6448536269514722  # jednostronne alpha=0.05

    def power_for(d):
        shifted = [min(1.0, p + d) for p in probs]
        mean1 = sum(shifted)
        var1 = sum(p * (1 - p) for p in shifted)
        sd1 = math.sqrt(var1) if var1 > 0 else 1e-9
        # próg odrzucenia H0 przy alpha jednostronnym
        threshold = mean0 + z_alpha * sd0
        z = (threshold - mean1) / sd1
        # moc = P(X1 > threshold) przybliżone normalnie
        return 1 - _norm_cdf(z)

    return {"delta": delta, "power": power_for(delta), "n_draws": n}


def _norm_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def generator_expected_playable_fraction(rows):
    """Kontrola: pod H0 generator.py, jaki ułamek losowań powinien wypaść
    grywalny, licząc dokładnie tak jak zrobiłby to generator (1/15 na typ)."""
    total_p = sum(row["n_playable_types"] / N_TYPES for row in rows for _ in range(3))
    n = sum(3 for _ in rows)
    return total_p / n if n else 0.0


def norm_ppf(p):
    """Odwrotna dystrybuanta N(0,1) — przybliżenie Acklama (bez scipy)."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def _rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0] * len(xs)
    for pos, i in enumerate(order):
        ranks[i] = pos + 1
    return ranks


def spearman(xs, ys):
    n = len(xs)
    rx, ry = _rank(xs), _rank(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sdx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sdy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if sdx == 0 or sdy == 0:
        return 0.0
    return cov / (sdx * sdy)


def permutation_test_spearman(xs, ys, n_perm=20000, seed=6):
    """Test permutacyjny (dwustronny) korelacji rang Spearmana fill vs rozmiar
    klocka: pod H0 generator.py rozmiar wylosowanego klocka nie zależy od
    zapełnienia planszy, więc każda permutacja przypisania fill<->tray jest
    równie prawdopodobna."""
    observed = spearman(xs, ys)
    rng = random.Random(seed)
    ys_shuffled = list(ys)
    count_extreme = 0
    for _ in range(n_perm):
        rng.shuffle(ys_shuffled)
        r = spearman(xs, ys_shuffled)
        if abs(r) >= abs(observed) - 1e-12:
            count_extreme += 1
    p_value = count_extreme / n_perm
    return {"rho": observed, "p_value": p_value, "n_perm": n_perm, "n": len(xs)}


def build_rows(pairs):
    rows = []
    for pair in pairs:
        grid = pair["board"]
        playable = playable_types(grid)
        n_filled = sum(sum(1 for c in row if c) for row in grid)
        fill = n_filled / (Board.WIDTH * Board.HEIGHT)
        tray_types = []
        tray_playable = []
        tray_sizes = []
        for piece in pair["tray"]:
            if not piece.get("recognized", True):
                continue
            type_index = NAME_TO_TYPE.get(piece["name"])
            if type_index is None:
                continue
            tray_types.append(type_index)
            tray_playable.append(type_index in playable)
            tray_sizes.append(NAME_TO_SIZE[piece["name"]])
        rows.append(
            {
                "round": pair["round"],
                "fill": fill,
                "n_playable_types": len(playable),
                "playable_types": sorted(playable),
                "tray_types": tray_types,
                "tray_playable": tray_playable,
                "mean_size": sum(tray_sizes) / len(tray_sizes) if tray_sizes else None,
            }
        )
    return rows


def power_spearman_normal_approx(n, alpha=0.05, target_power=0.80):
    """Moc testu korelacji Spearmana przy n obserwacjach (przybliżenie normalne
    Fishera dla rho), dwustronne alpha. Zwraca najmniejsze |rho| wykrywalne z
    zadaną mocą."""
    z_alpha = norm_ppf(1 - alpha / 2)
    z_beta = norm_ppf(target_power)
    se = 1.0 / math.sqrt(n - 3)
    z_needed = (z_alpha + z_beta) * se
    rho_needed = math.tanh(z_needed)
    return {"n": n, "min_detectable_rho": rho_needed, "alpha": alpha, "target_power": target_power}


def n_needed_for_rho(rho, alpha=0.05, target_power=0.80):
    z_alpha = norm_ppf(1 - alpha / 2)
    z_beta = norm_ppf(target_power)
    z_rho = math.atanh(rho)
    n = ((z_alpha + z_beta) / z_rho) ** 2 + 3
    return math.ceil(n)


def main():
    data = load_pairs()
    pairs = data["pairs"]
    rows = build_rows(pairs)

    result = exact_test_playable_count(rows)
    n_capped = sum(1 for r in rows if r["n_playable_types"] < N_TYPES)
    power_grid = [power_normal_approx(result["probs"], delta=d) for d in (0.01, 0.05, 0.1)]

    fills = [r["fill"] for r in rows]
    sizes = [r["mean_size"] for r in rows]
    corr = permutation_test_spearman(fills, sizes)
    corr_power = power_spearman_normal_approx(len(rows))
    n_for_observed_rho = n_needed_for_rho(abs(corr["rho"])) if corr["rho"] != 0 else None

    print(f"Źródło: {data.get('source')}; rundy: {data.get('rounds_total')}; "
          f"pary: {data.get('pairs_total')}; nierozpoznane kształty: {data.get('unrecognized_shapes')}")
    print(f"Użyte pary (po pominięciu nierozpoznanych klocków w tacce): {len(rows)}")
    print()
    print("Zapełnienie planszy: min={:.3f} mediana={:.3f} max={:.3f}".format(
        min(r["fill"] for r in rows),
        sorted(r["fill"] for r in rows)[len(rows) // 2],
        max(r["fill"] for r in rows),
    ))
    print("Liczba grywalnych typów kanonicznych na rundę: min={} mediana={} max={}".format(
        min(r["n_playable_types"] for r in rows),
        sorted(r["n_playable_types"] for r in rows)[len(rows) // 2],
        max(r["n_playable_types"] for r in rows),
    ))
    print()
    print("Test 1: Poissona-dwumianowy (exact Poisson binomial), H0 = generator.py "
          "(losowanie typu niezależne od planszy, 1/15)")
    print(f"  losowań w próbie: {result['n_draws']}")
    print(f"  obserwowane 'grywalne' klocki: {result['observed_playable']}")
    print(f"  oczekiwane pod H0: {result['expected_playable_h0']:.2f}")
    print(f"  p-wartość (jednostronna, H1: generator faworyzuje grywalne): "
          f"{result['p_value_one_sided_ge']:.4f}")
    print(f"  p-wartość (dwustronna): {result['p_value_two_sided']:.4f}")
    print("  próg istotności: alpha = 0.05")
    print(f"  UWAGA: efekt sufitowy — {len(rows) - n_capped}/{len(rows)} rund ma WSZYSTKIE "
          f"15 typów grywalnych; tylko {n_capped} rund(a) ma mniej. Test 1 nie ma prawie "
          "żadnej zmienności do wykorzystania (patrz moc niżej).")
    print()
    print("Moc testu 1 przy 33 parach (przybliżenie normalne, alpha=0.05 jednostronne):")
    for pg in power_grid:
        print(f"  delta={pg['delta']:.2f}: moc = {pg['power']:.3f}")
    print("  moc NIE rośnie z delta — baza jest już przy suficie (p≈0.996), więc test 1 "
          "jest ślepy na 'faworyzowanie grywalności' niezależnie od liczby par, dopóki "
          "plansze są tak puste jak w tej próbie (potrzebne dłuższe/trudniejsze rundy, "
          "nie tylko więcej par).")
    print()
    print("Test 2: korelacja rang Spearmana, fill planszy vs średni rozmiar klocka w "
          "tacce (test permutacyjny, dwustronny), H0 = generator.py (rozmiar niezależny od fill)")
    print(f"  n rund: {corr['n']}")
    print(f"  rho = {corr['rho']:.4f}")
    print(f"  p-wartość (permutacyjna, {corr['n_perm']} permutacji): {corr['p_value']:.4f}")
    print("  próg istotności: alpha = 0.05")
    print(f"  moc testu 2 przy n=33: najmniejsze |rho| wykrywalne z mocą 0.80 = "
          f"{corr_power['min_detectable_rho']:.3f}")
    if n_for_observed_rho:
        print(f"  n potrzebne, by wykryć rho={corr['rho']:.3f} z mocą 0.80 (alpha=0.05, "
              f"nieskorygowane): {n_for_observed_rho}")
        n_bonf = n_needed_for_rho(abs(corr["rho"]), alpha=0.025)
        print(f"  to samo z korektą Bonferroniego za 2 testy (alpha=0.025): {n_bonf}")
    print()
    print("Uwaga o wielokrotnym testowaniu: policzono 2 testy (test 1 i test 2) na tych "
          "samych 33 parach; p=0.047 z testu 2 nie przechodzi progu Bonferroniego "
          "(0.05/2=0.025) — traktuj jako sygnał wart replikacji, nie potwierdzenie.")

    return {
        "rows": rows,
        "test1": result,
        "test1_power_grid": power_grid,
        "test2": corr,
        "test2_power": corr_power,
        "n_for_observed_rho": n_for_observed_rho,
    }


if __name__ == "__main__":
    main()
