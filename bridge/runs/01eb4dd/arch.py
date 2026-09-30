"""Pomocnik verifiera (#286): archiwizuje kawałek z bridge-out/ do katalogu przebiegu i podsumowuje tempo."""
import glob, json, os, shutil, statistics, sys

RUN = os.path.dirname(os.path.abspath(__file__))
OUT = "bridge-out"


def archive(k):
    shutil.copy(f"{OUT}/moves.jsonl", f"{RUN}/chunk{k}_moves.jsonl")
    for n in ("final.png", "chunk.log"):
        if os.path.exists(f"{OUT}/{n}"):
            shutil.copy(f"{OUT}/{n}", f"{RUN}/chunk{k}_{n}")
    for f in glob.glob(f"{OUT}/*_end.png") + glob.glob(f"{OUT}/*_unknown*.png"):
        shutil.copy(f, f"{RUN}/chunk{k}_{os.path.basename(f)}")
    for f in glob.glob(f"{OUT}/*_state.png") + glob.glob(f"{OUT}/*_aim.png") + glob.glob(f"{OUT}/*_read.png"):
        os.remove(f)
    os.remove(f"{OUT}/moves.jsonl")


def summary(ks):
    ts, tms, bad, n = [], [], 0, 0
    for k in ks:
        for line in open(f"{RUN}/chunk{k}_moves.jsonl"):
            r = json.loads(line)
            if "t_ms" in r or ("ok" in r and "t" in r and "slot" in r):
                ts.append(r["t"]); n += 1
                if r.get("ok") is False:
                    bad += 1
                if "t_ms" in r:
                    tms.append(sum(r["t_ms"].values()))
    mins = (max(ts) - min(ts)) / 60 if len(ts) > 1 else None
    return dict(postawienia=n, minuty=mins, na_minute=(n - 1) / mins if mins else None,
                mediana_t_ms=statistics.median(tms) if tms else None, ok_false=bad)


if __name__ == "__main__":
    if sys.argv[1] == "all":
        import subprocess
        k = int(sys.argv[2])
        archive(k)
        print("kawalek", summary([k]))
        out = subprocess.run(["python3", "tools/score_from_trajectory.py", RUN, "--first-chunk", "1", "--last-chunk", str(k)], capture_output=True, text=True).stdout
        d = json.loads(out)
        print("wzor", d["postawien"], d["wynik_main"])
        print(open(f"{RUN}/chunk{k}_chunk.log").read().strip().splitlines()[-1])
    elif sys.argv[1] == "arch":
        archive(int(sys.argv[2]))
    else:
        print(summary([int(x) for x in sys.argv[2:]]))
