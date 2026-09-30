"""Kilka kawalkow po kolei na pierwszym planie: python3 seria.py OD DO. Zatrzymuje sie przy oknie/koncu partii."""
import json, subprocess, sys
D = "bridge/runs/558899e"
for k in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    subprocess.run(["python3", f"{D}/kawalek.py", str(k)], capture_output=True)
    sc = json.loads(subprocess.run(["python3", "tools/score_from_trajectory.py", D, "--first-chunk", "1", "--last-chunk", str(k)], capture_output=True, text=True).stdout)
    p = json.load(open(f"{D}/pomiar.json"))["partia_do_celu"]
    rows = [json.loads(l) for l in open(f"{D}/chunk{k}_moves.jsonl")]
    flag = [x for x in rows if x.get("okno") or x.get("koniec_partii")]
    print(k, "main", sc["wynik_main"], "post", p["postawienia"], "okna", p["okna"], "flagi", [{a: b for a, b in x.items() if a not in ("board", "expected", "observed", "tray")} for x in flag][:3], flush=True)
    if flag or sc["wynik_main"] >= 1000000:
        break
