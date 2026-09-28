#!/usr/bin/env python3
"""
Z-6 pomiar 2 (#182): ekstrakcja par "plansza w chwili nowej tacki -> trzy klocki"
ze wszystkich `bridge/runs/*/`.

Źródła:
- `bridge/runs/<run>/*.jsonl` (`moves.jsonl`, `moves_chunk*.jsonl`, `chunk*_moves.jsonl`,
  `moves_all.jsonl`) — surowe logi mostu, jeden wiersz = jeden ruch: `board` (plansza
  PRZED ruchem), `tray` (3 sloty, `null` = już użyty w tej tacce), `expected`/`observed`/`ok`
  po ruchu. Wiersz bez pola `ok` (okno ustawień/reklamy, restart apki) nie ma zweryfikowanego
  ruchu.
- `bridge/runs/d550db3/pomiar.json` — jedyny przebieg bez surowych `*.jsonl` (dane #78);
  już zawiera gotowe pary (`pairs`), traktowane jako zaufane (100% rozpoznane w pomiarze 1).
  Pozostałe `pomiar.json`/`analiza.json`/`podsumowanie.json` w innych katalogach to raporty
  z INNYCH pytań (reklamy, okna, restarty) — nie są parami i nie są tu czytane.

Wiersz liczy się jako "nowa tacka" tylko gdy wszystkie 3 sloty tacki są niepuste (pierwszy
ruch tacki - po nim sloty zaczynają zerować się do `null`). Plansza tego wiersza jest brana
pod uwagę tylko jeśli da się ją zweryfikować: wiersz i>0 w tym samym pliku, poprzedni wiersz
ma `ok == True`, i `observed` poprzedniego wiersza zgadza się z `board` tego wiersza. Wiersz
i==0 w pliku (początek pliku/chunka) jest ODRZUCANY — nie ma w tym samym pliku poprzedniego
ruchu do weryfikacji, a chunk mógł zacząć się po restarcie apki (nieciągłość planszy). To
świadomie konserwatywny wybór: część chunków w rzeczywistości kontynuuje poprzedni (patrz
`docs/z6-tacka-a-plansza.md`), ale odróżnienie kontynuacji od restartu na pewno wymagałoby
zgadywania, więc tracimy pojedynczy wiersz na plik zamiast ryzykować złą parę.

Deduplikacja jest globalna, po treści (plansza + nazwy trzech klocków w kolejności slotów),
niezależnie od pliku/przebiegu — chunk-loopy podczas zawieszek (most próbuje kilka razy tę
samą tackę) dają identyczne wiersze, które inaczej policzyłyby się wielokrotnie.
"""
import glob
import json
import os
import re
import sys
from collections import Counter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from pieces import PIECE_POOL  # noqa: E402

BRIDGE_RUNS_DIR = os.path.join(REPO_ROOT, "bridge", "runs")
OUTPUT_PATH = os.path.join(REPO_ROOT, "docs", "data", "z6-pary.json")
BOARD_SIZE = 8

# Katalogi przebiegów bez surowych *.jsonl, gdzie pomiar.json JEST już gotową listą par
# (a nie raportem z innego pytania) — patrz docstring modułu.
TRUSTED_PAIR_POMIAR = {"d550db3": "pomiar.json"}

_NUM_RE = re.compile(r"(\d+)")


def shape_name_lookup():
    """tuple(shape) -> nazwa pozy z pieces.py (dokładne dopasowanie kształtu tacki)."""
    lookup = {}
    for piece in PIECE_POOL:
        key = tuple(tuple(row) for row in piece.shape)
        lookup[key] = piece.name
    return lookup


def _natural_key(path):
    base = os.path.basename(path)
    nums = [int(n) for n in _NUM_RE.findall(base)]
    return (nums, base)


def list_run_dirs(bridge_runs_dir=BRIDGE_RUNS_DIR):
    if not os.path.isdir(bridge_runs_dir):
        return []
    return sorted(
        name
        for name in os.listdir(bridge_runs_dir)
        if os.path.isdir(os.path.join(bridge_runs_dir, name))
    )


def list_moves_files(run_dir, bridge_runs_dir=BRIDGE_RUNS_DIR):
    pattern = os.path.join(bridge_runs_dir, run_dir, "*.jsonl")
    return sorted(glob.glob(pattern), key=_natural_key)


def _is_full_tray(tray):
    return isinstance(tray, list) and len(tray) == 3 and all(t is not None for t in tray)


def _is_valid_board(board):
    return (
        isinstance(board, list)
        and len(board) == BOARD_SIZE
        and all(isinstance(r, list) and len(r) == BOARD_SIZE for r in board)
    )


def extract_from_jsonl_rows(rows, source_id, lookup, rejected):
    """rows: lista już sparsowanych wierszy (dict) z jednego pliku *_moves.jsonl."""
    pairs = []
    for i, row in enumerate(rows):
        tray = row.get("tray")
        if not _is_full_tray(tray):
            continue  # nie moment nowej tacki - nie liczy się jako kandydat

        board = row.get("board")
        if not _is_valid_board(board):
            rejected["zla_wielkosc_planszy"] += 1
            continue

        if i == 0:
            rejected["brak_weryfikowalnego_poprzednika"] += 1
            continue

        prev = rows[i - 1]
        if "ok" not in prev or "observed" not in prev:
            rejected["poprzedni_wiersz_bez_ruchu"] += 1
            continue
        if not prev["ok"]:
            rejected["poprzedni_ruch_rozbiezny"] += 1
            continue
        if prev["observed"] != board:
            rejected["board_niezgodny_z_poprzednim_observed"] += 1
            continue

        names = []
        for shape in tray:
            key = tuple(tuple(r) for r in shape)
            name = lookup.get(key)
            if name is None:
                names = None
                break
            names.append(name)
        if names is None:
            rejected["ksztalt_tacki_nierozpoznany"] += 1
            continue

        pairs.append(
            {
                "id": f"{source_id}#{i}",
                "board": board,
                "tray": [{"recognized": True, "name": n} for n in names],
            }
        )
    return pairs


def extract_from_moves_file(file_path, run_dir, lookup, rejected):
    with open(file_path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    source_id = f"{run_dir}/{os.path.basename(file_path)}"
    return extract_from_jsonl_rows(rows, source_id, lookup, rejected)


def extract_from_trusted_pomiar(run_dir, filename, rejected):
    path = os.path.join(BRIDGE_RUNS_DIR, run_dir, filename)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    pairs = []
    for pair in data["pairs"]:
        board = pair["board"]
        if not _is_valid_board(board):
            rejected["zla_wielkosc_planszy"] += 1
            continue
        names = []
        for piece in pair["tray"]:
            if not piece.get("recognized", True):
                names = None
                break
            names.append(piece["name"])
        if names is None or len(names) != 3:
            rejected["ksztalt_tacki_nierozpoznany"] += 1
            continue
        pairs.append(
            {
                "id": f"{run_dir}/{filename}#{pair['round']}",
                "board": board,
                "tray": [{"recognized": True, "name": n} for n in names],
            }
        )
    return pairs


def dedup_pairs(pairs, rejected):
    seen = {}
    unique = []
    for pair in pairs:
        signature = (
            tuple(tuple(r) for r in pair["board"]),
            tuple(t["name"] for t in pair["tray"]),
        )
        if signature in seen:
            rejected["duplikat"] += 1
            continue
        seen[signature] = pair["id"]
        unique.append(pair)
    return unique


def build_dataset(bridge_runs_dir=BRIDGE_RUNS_DIR):
    lookup = shape_name_lookup()
    rejected = Counter()
    raw_pairs = []
    sources = []

    for run_dir in list_run_dirs(bridge_runs_dir):
        if run_dir in TRUSTED_PAIR_POMIAR:
            filename = TRUSTED_PAIR_POMIAR[run_dir]
            path = os.path.join(bridge_runs_dir, run_dir, filename)
            if not os.path.exists(path):
                continue
            pairs = extract_from_trusted_pomiar(run_dir, filename, rejected)
            raw_pairs.extend(pairs)
            sources.append(f"{run_dir}/{filename}")
            continue

        for file_path in list_moves_files(run_dir, bridge_runs_dir):
            pairs = extract_from_moves_file(file_path, run_dir, lookup, rejected)
            raw_pairs.extend(pairs)
            sources.append(os.path.relpath(file_path, REPO_ROOT))

    deduped = dedup_pairs(raw_pairs, rejected)

    return {
        "pairs": deduped,
        "sources": sources,
        "n_accepted": len(deduped),
        "n_rejected_total": sum(rejected.values()),
        "rejected_by_reason": dict(sorted(rejected.items())),
    }


def main():
    dataset = build_dataset()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"zapisano: {os.path.relpath(OUTPUT_PATH, REPO_ROOT)}")
    print(f"pary zaakceptowane: {dataset['n_accepted']}")
    print(f"pary odrzucone: {dataset['n_rejected_total']}")
    for reason, count in dataset["rejected_by_reason"].items():
        print(f"  {reason}: {count}")
    return dataset


if __name__ == "__main__":
    main()
