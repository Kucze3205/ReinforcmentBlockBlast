#!/usr/bin/env python3
"""
Z-6 pomiar 2 (#182), jedną komendą: pkt 1 (ekstrakcja par z `bridge/runs/*/`,
`tools/z6_pary.py`) + pkt 2 (testy (a)-(d) wobec H0=`generator.py`,
`tools/z6_testy.py`). Deterministyczne — ziarno Monte Carlo stałe
(`tools.z6_testy.MC_SEED`).

    python3 tools/z6_pomiar2.py

Zapisuje `docs/data/z6-pary.json` (pkt 1) i drukuje wynik testów (pkt 2) —
wklejany ręcznie do sekcji "Pomiar 2" w `docs/z6-tacka-a-plansza.md`
(werdykt wymaga prozy, nie tylko liczb, patrz `## Cel` w issue #182).
"""
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import z6_pary  # noqa: E402
import z6_testy  # noqa: E402


def main():
    print("=== pkt 1: ekstrakcja par (tools/z6_pary.py) ===")
    dataset = z6_pary.main()
    print()
    print("=== pkt 2: testy (a)-(d) wobec H0 = generator.py (tools/z6_testy.py) ===")
    result = z6_testy.main()
    return {"dataset": dataset, "tests": result}


if __name__ == "__main__":
    main()
