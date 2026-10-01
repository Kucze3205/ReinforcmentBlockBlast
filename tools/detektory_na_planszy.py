"""Regresja detektorow okien mostu (#311): przechodzi po klatkach `NNN_state.png` z `docs/seria/s*`,
po ktorych most wykonal ruch (wpis `move` w `chunkK_moves.jsonl` dla tego `n` i kawalka `kawalek_K`),
czyli po zywej planszy (bez ruchow, po ktorych plansza sie nie zmienila), i liczy trafienia kazdego detektora `is_*_screen` z `bridge.py`.
Kazde trafienie to falszywe okno. Uzycie: python3 tools/detektory_na_planszy.py [--lista]"""
import collections
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bridge  # noqa: E402

SERIE = ("s1", "s2", "s3", "s4")


def detektory():
    return {n: f for n, f in sorted(vars(bridge).items())
            if re.fullmatch(r"is_\w+_screen", n) and callable(f)}


def klatki_z_ruchem(seria_dir):
    """Generuje sciezki `NNN_state.png`, po ktorych jest wpis z `move`."""
    for moves in sorted(glob.glob(os.path.join(seria_dir, "partia-*", "chunk*_moves.jsonl"))):
        partia = os.path.dirname(moves)
        k = re.search(r"chunk(\d+)_moves", moves).group(1)
        with open(moves) as f:
            wpisy = [json.loads(line) for line in f]
        for i, e in enumerate(wpisy):
            if e.get("move") is None or "n" not in e:
                continue
            # po ruchu mogla wejsc prawdziwa reklama (nastepny wpis `reklama_*`): ta klatka nie jest plansza
            if i + 1 < len(wpisy) and str(wpisy[i + 1].get("okno", "")).startswith("reklama"):
                continue
            # ruch, po ktorym plansza stoi w miejscu (zawieszenie, #323), to nie zywa plansza: pod spodem reklama
            if e.get("observed") is not None and e.get("observed") == e.get("board"):
                continue
            p = os.path.join(partia, "kawalek_" + k, "%03d_state.png" % e["n"])
            if os.path.exists(p):
                yield p


def main(argv):
    dets = detektory()
    licznik = {s: collections.Counter() for s in SERIE}
    klatek = collections.Counter()
    trafienia = []
    for s in SERIE:
        for p in klatki_z_ruchem(os.path.join(ROOT, "docs", "seria", s)):
            img = np.asarray(Image.open(p).convert("RGB")).astype(int)
            klatek[s] += 1
            for name, f in dets.items():
                if f(img):
                    licznik[s][name] += 1
                    trafienia.append((name, os.path.relpath(p, ROOT)))
    print("detektor".ljust(30) + "".join(s.rjust(8) for s in SERIE))
    print("klatek".ljust(30) + "".join(str(klatek[s]).rjust(8) for s in SERIE))
    for name in dets:
        print(name.ljust(30) + "".join(str(licznik[s][name]).rjust(8) for s in SERIE))
    if "--lista" in argv:
        for name, p in trafienia:
            print(name, p)
    return 1 if trafienia else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
