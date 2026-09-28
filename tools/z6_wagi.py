#!/usr/bin/env python3
"""
#186: estymacja wag typów klocków w `generator.py` z `docs/data/z6-pary.json`
(ekstrakcja `tools/z6_pary.py`, testy brzegowe `tools/z6_testy.py`, pomiar
#182 w `docs/z6-tacka-a-plansza.md`).

Jednostka próby: TACKA (para "plansza -> trzy klocki"), licząc każdą raz - nie
pojedynczy klocek - żeby nie liczyć trzykrotnie planszy, na której akurat
wylosowano trzy razy ten sam typ. Waga typu = częstość tego typu wśród
3 * n_tacek wylosowanych klocków (MLE multinomialu), z przedziałem ufności
Wilsona 95% (dwumianowy per-typ, standardowe przybliżenie dla marginesu
multinomialu, bez korekty na liczbę typów - to jest opis rozkładu, nie test
istotności).

Orientacja w obrębie typu: dla każdego typu z >1 pozą, chi-kwadrat częstości
póz wobec jednostajnego 1/n_poz, na WYLOSOWANYCH klockach tego typu (nie na
tackach - orientacja jest własnością pojedynczego klocka). Korekta
Bonferroniego za liczbę testowalnych typów (te z >1 pozą; 1x1/square2/square3
mają dokładnie jedną pozę i nie da się ich testować).
"""
import json
import math
import os
import sys
from collections import Counter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from pieces import CANONICAL_TYPES, PIECE_POOL, PIECE_TYPES  # noqa: E402
from z6_testy import chi2_sf  # noqa: E402

PAIRS_PATH = os.path.join(REPO_ROOT, "docs", "data", "z6-pary.json")
N_TYPES = len(CANONICAL_TYPES)
ALPHA = 0.05

NAME_TO_TYPE = {p.name: p.type_index for p in PIECE_POOL}


def load_pairs(path=PAIRS_PATH):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["pairs"]


def wilson_ci(count, n, z=1.959963984540054):
    """Przedział ufności Wilsona (95% domyślnie) dla proporcji count/n."""
    if n == 0:
        return (0.0, 0.0)
    p = count / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def type_weights(pairs):
    names = [t["name"] for pair in pairs for t in pair["tray"]]
    n = len(names)
    type_counts = Counter(NAME_TO_TYPE[name] for name in names)
    rows = []
    for t in range(N_TYPES):
        count = type_counts.get(t, 0)
        lo, hi = wilson_ci(count, n)
        rows.append(
            {
                "type": CANONICAL_TYPES[t][0],
                "type_index": t,
                "n_obs": count,
                "weight": count / n,
                "ci95": (lo, hi),
            }
        )
    return {"n_draws": n, "n_trays": len(pairs), "rows": rows}


def orientation_tests(pairs):
    pose_counts = Counter(t["name"] for pair in pairs for t in pair["tray"])
    results = []
    for t, (type_name, _) in enumerate(CANONICAL_TYPES):
        pose_indices = PIECE_TYPES[t]
        n_poses = len(pose_indices)
        if n_poses <= 1:
            continue
        counts = [pose_counts.get(PIECE_POOL[i].name, 0) for i in pose_indices]
        n = sum(counts)
        if n == 0:
            results.append({"type": type_name, "n_poses": n_poses, "n_draws": 0,
                             "chi2": None, "p_value": None})
            continue
        expected = n / n_poses
        stat = sum((c - expected) ** 2 / expected for c in counts)
        df = n_poses - 1
        results.append(
            {
                "type": type_name,
                "n_poses": n_poses,
                "n_draws": n,
                "counts": counts,
                "chi2": stat,
                "df": df,
                "p_value": chi2_sf(stat, df),
            }
        )
    n_tested = sum(1 for r in results if r["p_value"] is not None)
    alpha_bonf = ALPHA / n_tested if n_tested else ALPHA
    for r in results:
        r["alpha_bonferroni"] = alpha_bonf
        r["reject_uniform"] = (r["p_value"] is not None and r["p_value"] < alpha_bonf)
    return {"n_tested": n_tested, "alpha_bonferroni": alpha_bonf, "results": results}


def main():
    pairs = load_pairs()
    w = type_weights(pairs)
    print(f"tacek: {w['n_trays']}  klockow: {w['n_draws']}")
    print(f"{'typ':10s} {'obs':>5s} {'waga':>8s} {'CI95 lo':>9s} {'CI95 hi':>9s}")
    for r in w["rows"]:
        lo, hi = r["ci95"]
        print(f"{r['type']:10s} {r['n_obs']:5d} {r['weight']:8.4f} {lo:9.4f} {hi:9.4f}")

    print()
    o = orientation_tests(pairs)
    print(f"testy orientacji: {o['n_tested']} typów, alpha Bonferroniego = {o['alpha_bonferroni']:.5f}")
    for r in o["results"]:
        if r["p_value"] is None:
            print(f"  {r['type']:10s} n_poz={r['n_poses']} brak obserwacji")
            continue
        flag = "ODRZUCA 1/n" if r["reject_uniform"] else "1/n OK"
        print(f"  {r['type']:10s} n_poz={r['n_poses']} n={r['n_draws']:4d} "
              f"chi2={r['chi2']:7.3f} df={r['df']} p={r['p_value']:.4g}  {flag}")
    return {"weights": w, "orientation": o}


if __name__ == "__main__":
    main()
