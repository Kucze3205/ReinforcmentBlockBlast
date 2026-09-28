#!/usr/bin/env python3
"""
Z-6 / #186: czy niedobór `diag2`/`diag3`/`1x1` w `docs/data/z6-pary.json` jest
artefaktem rozpoznawania mostu, a nie realną wagą generatora.

`tools/z6_pary.py` liczy tackę tylko gdy most rozpoznał WSZYSTKIE trzy sloty
(patrz `_is_full_tray` — wymaga trzech elementów niepustych). Jeśli most
częściej gubi (czyta jako pusty slot, `bridge.read_tray` zwraca `None` przy
< 20 pikselach dopasowanych) akurat `diag2`/`diag3`/`1x1` — bo to najmniejsze
lub najbardziej "dziurawe" kształty, najtrudniejsze do złapania progiem
`is_block` — to te tacki wypadają z próby całe, a nie tylko brakujący slot.
Wtedy niedobór w `z6-pary.json` byłby artefaktem odczytu, nie wagą gry.

Metoda: "świeża tacka" to strukturalnie pierwszy wiersz PO ruchu, który
postawił trzeci (ostatni) klocek poprzedniej tacki — czyli wiersz `i` taki, że
poprzedni wiersz `i-1` (w tym samym pliku) miał dokładnie 1 niepusty slot
(ostatni klocek tacki, o krok od postawienia). To jest zdarzenie strukturalne
(licznik niepustych slotów), niezależne od tego, czy most poprawnie rozpoznał
KSZTAŁT nowej tacki w wierszu `i` — inaczej niż `_is_full_tray`, które samo
wymaga pełnego rozpoznania i dlatego nie nadaje się do zmierzenia stopy utraty.

Dla każdego takiego wiersza `i` liczymy 3 sloty:
  - `pusty`: `tray[slot] is None` (most nie znalazł tam żadnych pikseli bloku),
  - `nierozpoznany`: slot niepusty, ale kształt nie pasuje do żadnej z 41 poz
    z `pieces.py` (odczyt częściowy/zaszumiony),
  - `rozpoznany`: kształt pasuje.

`bridge/runs/d550db3/pomiar.json` nie ma surowych `*.jsonl` (patrz
`tools/z6_pary.py`), więc nie wnosi wierszy do tego liczenia — już jest
przefiltrowany do 100% rozpoznanych, stąd nie mówi nic o stopie utraty.
"""
import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from z6_pary import (  # noqa: E402
    BRIDGE_RUNS_DIR,
    TRUSTED_PAIR_POMIAR,
    _natural_key,
    list_run_dirs,
    shape_name_lookup,
)


def _tray_non_null_count(tray):
    if not isinstance(tray, list) or len(tray) != 3:
        return None
    return sum(1 for slot in tray if slot is not None)


def _slot_status(slot, lookup):
    if slot is None:
        return "pusty"
    key = tuple(tuple(row) for row in slot)
    return "rozpoznany" if key in lookup else "nierozpoznany"


def scan_file(file_path, lookup):
    with open(file_path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    fresh_trays = []
    for i in range(1, len(rows)):
        prev_count = _tray_non_null_count(rows[i - 1].get("tray"))
        if prev_count != 1:
            continue  # poprzedni wiersz nie jest "ostatni klocek tacki"
        tray = rows[i].get("tray")
        if not isinstance(tray, list) or len(tray) != 3:
            continue  # most nie zwrócił nawet trzech slotów - poza zakresem tej miary
        statuses = [_slot_status(slot, lookup) for slot in tray]
        fresh_trays.append({"id": f"{os.path.basename(file_path)}#{i}", "statuses": statuses})
    return fresh_trays


def run(bridge_runs_dir=BRIDGE_RUNS_DIR):
    lookup = shape_name_lookup()
    fresh_trays = []
    n_files = 0
    for run_dir in list_run_dirs(bridge_runs_dir):
        if run_dir in TRUSTED_PAIR_POMIAR:
            continue  # brak surowych *.jsonl, patrz docstring modułu
        pattern = os.path.join(bridge_runs_dir, run_dir, "*.jsonl")
        for file_path in sorted(glob.glob(pattern), key=_natural_key):
            n_files += 1
            fresh_trays.extend(
                {**ft, "id": f"{run_dir}/{ft['id']}"} for ft in scan_file(file_path, lookup)
            )

    n_trays = len(fresh_trays)
    n_slots = n_trays * 3
    n_empty = sum(s.count("pusty") for ft in fresh_trays for s in [ft["statuses"]])
    n_unrecognized = sum(s.count("nierozpoznany") for ft in fresh_trays for s in [ft["statuses"]])
    n_recognized = n_slots - n_empty - n_unrecognized
    n_trays_all_recognized = sum(1 for ft in fresh_trays if ft["statuses"].count("rozpoznany") == 3)
    n_trays_with_loss = n_trays - n_trays_all_recognized

    return {
        "n_files": n_files,
        "n_fresh_trays": n_trays,
        "n_slots": n_slots,
        "n_slots_pusty": n_empty,
        "n_slots_nierozpoznany": n_unrecognized,
        "n_slots_rozpoznany": n_recognized,
        "n_trays_z_utrata": n_trays_with_loss,
        "n_trays_w_pelni_rozpoznane": n_trays_all_recognized,
        "fresh_trays": fresh_trays,
    }


def main():
    result = run()
    print(f"plików przeskanowanych: {result['n_files']}")
    print(f"świeżych tacek (strukturalnie): {result['n_fresh_trays']}")
    print(f"sloty łącznie: {result['n_slots']}")
    print(f"  pusty (None):        {result['n_slots_pusty']}")
    print(f"  nierozpoznany kształt: {result['n_slots_nierozpoznany']}")
    print(f"  rozpoznany:          {result['n_slots_rozpoznany']}")
    loss_rate = (result["n_slots_pusty"] + result["n_slots_nierozpoznany"]) / result["n_slots"]
    print(f"stopa utraty slotu: {loss_rate:.4f}")
    print(f"tacek z co najmniej jedną utratą: {result['n_trays_z_utrata']} / {result['n_fresh_trays']}")
    return result


if __name__ == "__main__":
    main()
