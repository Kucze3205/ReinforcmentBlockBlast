"""Jeden kawalek na pierwszym planie: python3 kawalek.py K  (czas przed/po, most, pomoc.py, commit)."""
import subprocess, sys, time
D = "bridge/runs/558899e"
K = sys.argv[1]
POL = "lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000"
t0 = time.time()
r = subprocess.run(["python3", "bridge.py", "150", POL], capture_output=True, text=True)
t1 = time.time()
print("\n".join(r.stdout.splitlines()[-4:]))
print(r.stderr[-500:])
out = subprocess.run(["python3", f"{D}/pomoc.py", K, str(t0), str(t1)], capture_output=True, text=True)
lines = out.stdout.splitlines()
print("\n".join(l for l in lines if l.lstrip().startswith(('"wynik_main', '"pkt_na_postawienie_main', '{'))))
print(out.stderr[-800:])
subprocess.run(["git", "add", D])
subprocess.run(["git", "commit", "-qm", f"verifier #262: kawalek {K}"])
