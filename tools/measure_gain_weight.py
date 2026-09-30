"""
Pomiar `gain_weight` na dlugich partiach z gwarancja tacki (#248).

Wzor: #241 (`docs/dlugie-partie-gwarancja.md`) -- te same wagi, 16 pierwszych seedow
stalych, `complete=1`, `samples=0`, sufit 20000 postawien
(`docs/data/241-config-20k.json`). Kazda konfiguracja to jeden przebieg
`tools/measure_death_avoidability.py` zapisany do `docs/data/248-beam<B>-gw<W>.json`;
istniejacy plik jest pomijany, wiec przerwany przebieg wznawia sie od nastepnej
konfiguracji. Nic w tle.

    python3 tools/measure_gain_weight.py --beam 8 --gain-weights 0,5,20
    python3 tools/measure_gain_weight.py --summary
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import measure_death_avoidability as mda

WEIGHTS = "ntuple/survival-adce-400k.json"
CONFIG = "docs/data/241-config-20k.json"
OUT = "docs/data/248-beam%d-gw%d.json"


def spec(beam, gain_weight):
    return "lookahead-ntuple:%s@beam=%d,samples=0,complete=1,gain_weight=%d" % (
        WEIGHTS, beam, gain_weight)


def measure(beam, gain_weight, jobs, n_games):
    out = OUT % (beam, gain_weight)
    if os.path.exists(out):
        print("pomijam (jest):", out, flush=True)
        return
    mda.main([
        "--config", CONFIG, "--jobs", str(jobs), "--n-games", str(n_games),
        "--policy", spec(beam, gain_weight), "--out", out,
    ])


def summary_rows():
    rows = []
    for path in glob.glob("docs/data/248-beam*-gw*.json"):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        games = data["games"]
        scores = sorted(g["score"] for g in games)
        placements = sum(g["placements"] for g in games)
        params = dict(kv.split("=") for kv in data["policy"].split("@")[1].split(","))
        rows.append({
            "beam": int(params["beam"]),
            "gain_weight": int(params.get("gain_weight", 0)),
            "n_games": len(games),
            "deaths": sum(1 for g in games if not g.get("capped")),
            "mean": sum(scores) / len(scores),
            "median": (scores[len(scores) // 2 - 1] + scores[len(scores) // 2]) / 2,
            "min": scores[0],
            "max": scores[-1],
            "placements": placements / len(games),
            "pts_per_placement": sum(scores) / placements,
            "placements_per_s": placements / data["elapsed_s"],
            "elapsed_s": data["elapsed_s"],
        })
    return sorted(rows, key=lambda r: (r["beam"], r["gain_weight"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pomiar gain_weight na dlugich partiach (#248)")
    parser.add_argument("--beam", type=int, action="append", default=[])
    parser.add_argument("--gain-weights", default="0")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--n-games", type=int, default=16)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    if not args.summary:
        for beam in args.beam:
            for weight in (int(w) for w in args.gain_weights.split(",")):
                measure(beam, weight, args.jobs, args.n_games)
    print("| B | gain_weight | smierci | srednia | mediana | min-max | pkt/postawienie | postawien/s | elapsed_s |")
    for r in summary_rows():
        print("| %d | %d | %d/%d | %.0f | %.0f | %d-%d | %.1f | %.0f | %.1f |" % (
            r["beam"], r["gain_weight"], r["deaths"], r["n_games"], r["mean"], r["median"],
            r["min"], r["max"], r["pts_per_placement"], r["placements_per_s"], r["elapsed_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
