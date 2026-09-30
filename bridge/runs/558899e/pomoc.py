"""Pomoc verifiera #262: po kawalku przenosi pliki, liczy wynik i stan partii_do_celu.
Uzycie: python3 pomoc.py K T0 T1   (K numer kawalka, T0/T1 czas przed/po z time.time())"""
import glob, json, os, shutil, subprocess, sys, statistics
D = os.path.dirname(os.path.abspath(__file__))
K, T0, T1 = int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
POL = "lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000"
src = sorted(glob.glob("bridge-out/moves*.jsonl"))
assert len(src) == 1, src
shutil.move(src[0], f"{D}/chunk{K}_moves.jsonl")
states = sorted(glob.glob("bridge-out/*_state.png"))
last = states[-1] if states else None
for p in sorted(glob.glob("bridge-out/*.png")):
    b = os.path.basename(p)
    if b in ("000_state.png", "final.png", "_score.png") or b.endswith("_end.png") or p == last or "okno" in b:
        shutil.move(p, f"{D}/chunk{K}_{b}")
    else:
        os.remove(p)
pj = f"{D}/pomiar.json"
if os.path.exists(pj):
    d = json.load(open(pj))
else:
    d = {"run": "558899e", "partia_do_celu": {"polityka": POL, "kawalki": [], "czasy": []}}
p = d["partia_do_celu"]
p["kawalki"].append(f"chunk{K}_moves.jsonl")
p["czasy"].append([T0, T1])
rows = []
for f in p["kawalki"]:
    for l in open(f"{D}/{f}"):
        r = json.loads(l)
        r["_f"] = f
        rows.append(r)
ok = [r for r in rows if r.get("ok")]
ms = sorted(r["decision_ms"] for r in rows if "decision_ms" in r)
if ms:
    p["decision_ms"] = {"mediana": statistics.median(ms), "p95": ms[int(0.95 * (len(ms) - 1))], "max": ms[-1], "n": len(ms)}
p["postawienia"] = len(ok)
p["ruchy_zapisane"] = len(rows)
p["dziury"] = [f"{r['_f']}: ruch {r['n']} ok=false" for r in rows if not r.get("ok")]
p["okna"] = [dict(kawalek=r["_f"], ruch=r["n"], okno=r["okno"]) for r in rows if r.get("okno")]
sc = subprocess.run(["python3", "tools/score_from_trajectory.py", D, "--first-chunk", "1", "--last-chunk", str(K)], capture_output=True, text=True).stdout
print(sc[-1500:])
p["min_gry_kawalkow"] = round(sum(b - a for a, b in p["czasy"]) / 60, 1)
p["minuty"] = round((T1 - p["czasy"][0][0]) / 60, 1)
p["postawien_na_minute"] = round(len(ok) / p["min_gry_kawalkow"], 2)
p["ostatni_wynik_apka_pole_score"] = next((r["score"] for r in reversed(rows) if r.get("score") is not None), None)
json.dump(d, open(pj, "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: p[k] for k in ("postawienia", "ruchy_zapisane", "minuty", "postawien_na_minute", "decision_ms", "okna", "dziury", "ostatni_wynik_apka_pole_score")}, ensure_ascii=False))
