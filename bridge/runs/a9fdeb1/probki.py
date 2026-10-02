"""Kopiuje do repo próbki: seria z najdłuższym napisem każdego rodzaju (co druga klatka do 16. i ostatnia)."""
import json
import os
import shutil

R = "bridge/runs/a9fdeb1/"
r = [x for x in json.load(open(R + "napis-czas.json")) if "seria" in x]
for k in sorted({x["rodzaj"] for x in r}):
    x = max((y for y in r if y["rodzaj"] == k), key=lambda y: y["t_zniknie_trwale_s"])
    d = R + "serie/s%03d_%s/" % (x["seria"], k)
    os.makedirs(d, exist_ok=True)
    n = x["klatek"]
    for f in sorted(set(list(range(0, min(n, 16), 2)) + [n - 1])):
        shutil.copy("/tmp/napis/s%03d/%02d.png" % (x["seria"], f), d + "%02d.png" % f)
    print(k, x["seria"])
