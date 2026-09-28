"""
Testy `tools/z6_pary.py` (#182): wyłuskiwanie par "plansza -> tacka" z logów mostu
na małym, ręcznie skonstruowanym przykładzie (bez prawdziwych `bridge/runs/`).
"""
import json
import os
import sys
import tempfile
import unittest
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pieces import PIECE_POOL
from tools.z6_pary import (
    build_dataset,
    dedup_pairs,
    extract_from_jsonl_rows,
    extract_from_trusted_pomiar,
    shape_name_lookup,
)

EMPTY = [[0] * 8 for _ in range(8)]


def _shape(name):
    for p in PIECE_POOL:
        if p.name == name:
            return [row[:] for row in p.shape]
    raise KeyError(name)


def _board(fill_cell=None):
    board = [[0] * 8 for _ in range(8)]
    if fill_cell:
        y, x = fill_cell
        board[y][x] = 1
    return board


def _full_tray(names):
    return [_shape(n) for n in names]


def _row(board, tray_names, ok=None, observed=None, has_move=True):
    row = {"board": board, "tray": _full_tray(tray_names) if tray_names else [None, None, None]}
    if has_move:
        row["move"] = {"slot": 0, "x": 0, "y": 0}
        row["expected"] = board
        row["observed"] = observed if observed is not None else board
        row["ok"] = ok if ok is not None else True
    return row


class TestExtractFromRows(unittest.TestCase):
    def setUp(self):
        self.lookup = shape_name_lookup()

    def test_first_row_in_file_is_rejected_unverifiable(self):
        rows = [_row(EMPTY, ["1x1", "1x1", "1x1"])]
        rejected = Counter()
        pairs = extract_from_jsonl_rows(rows, "run/f.jsonl", self.lookup, rejected)
        self.assertEqual(pairs, [])
        self.assertEqual(rejected["brak_weryfikowalnego_poprzednika"], 1)

    def test_accepts_new_tray_after_verified_previous_move(self):
        board1 = _board()
        board2 = _board((0, 0))
        rows = [
            _row(board1, None, ok=True, observed=board2),
            _row(board2, ["1x1", "beam2-0", "square2"], ok=True),
        ]
        rejected = Counter()
        pairs = extract_from_jsonl_rows(rows, "run/f.jsonl", self.lookup, rejected)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["board"], board2)
        self.assertEqual(
            [t["name"] for t in pairs[0]["tray"]], ["1x1", "beam2-0", "square2"]
        )
        self.assertEqual(sum(rejected.values()), 0)

    def test_rejects_when_previous_move_had_discrepancy(self):
        board1 = _board()
        board2 = _board((0, 0))
        rows = [
            _row(board1, None, ok=False, observed=board2),
            _row(board2, ["1x1", "beam2-0", "square2"], ok=True),
        ]
        rejected = Counter()
        pairs = extract_from_jsonl_rows(rows, "run/f.jsonl", self.lookup, rejected)
        self.assertEqual(pairs, [])
        self.assertEqual(rejected["poprzedni_ruch_rozbiezny"], 1)

    def test_rejects_when_previous_row_has_no_move(self):
        board1 = _board()
        rows = [
            {"board": board1, "tray": [None, None, None], "okno": "ustawienia_wstecz"},
            _row(board1, ["1x1", "beam2-0", "square2"], ok=True),
        ]
        rejected = Counter()
        pairs = extract_from_jsonl_rows(rows, "run/f.jsonl", self.lookup, rejected)
        self.assertEqual(pairs, [])
        self.assertEqual(rejected["poprzedni_wiersz_bez_ruchu"], 1)

    def test_ignores_rows_with_partial_tray(self):
        board1 = _board()
        board2 = _board((0, 0))
        row2 = _row(board2, ["1x1", "beam2-0", "square2"], ok=True)
        row2["tray"][1] = None  # jeden slot juz uzyty w tej tacce -> nie "nowa tacka"
        rows = [_row(board1, None, ok=True, observed=board2), row2]
        rejected = Counter()
        pairs = extract_from_jsonl_rows(rows, "run/f.jsonl", self.lookup, rejected)
        self.assertEqual(pairs, [])
        self.assertEqual(sum(rejected.values()), 0)

    def test_rejects_unrecognized_shape(self):
        board1 = _board()
        board2 = _board((0, 0))
        row2 = _row(board2, ["1x1", "beam2-0", "square2"], ok=True)
        row2["tray"][2] = [[1, 1, 1, 1, 1, 1, 1, 1]]  # nie ma takiej pozy w pieces.py
        rows = [_row(board1, None, ok=True, observed=board2), row2]
        rejected = Counter()
        pairs = extract_from_jsonl_rows(rows, "run/f.jsonl", self.lookup, rejected)
        self.assertEqual(pairs, [])
        self.assertEqual(rejected["ksztalt_tacki_nierozpoznany"], 1)

    def test_rejects_board_size_mismatch(self):
        board1 = _board()
        bad_board = [[0] * 7 for _ in range(8)]
        rows = [
            _row(board1, None, ok=True, observed=bad_board),
            _row(bad_board, ["1x1", "beam2-0", "square2"], ok=True),
        ]
        rejected = Counter()
        pairs = extract_from_jsonl_rows(rows, "run/f.jsonl", self.lookup, rejected)
        self.assertEqual(pairs, [])
        self.assertEqual(rejected["zla_wielkosc_planszy"], 1)


class TestDedup(unittest.TestCase):
    def test_deduplicates_identical_board_and_tray(self):
        pair = {
            "id": "a#0",
            "board": EMPTY,
            "tray": [{"recognized": True, "name": "1x1"}] * 3,
        }
        pair_dup = dict(pair, id="b#0")
        rejected = Counter()
        unique = dedup_pairs([pair, pair_dup], rejected)
        self.assertEqual(len(unique), 1)
        self.assertEqual(rejected["duplikat"], 1)

    def test_keeps_pairs_with_different_tray_order(self):
        base_tray_names = ["1x1", "beam2-0", "square2"]
        pair_a = {
            "id": "a#0",
            "board": EMPTY,
            "tray": [{"recognized": True, "name": n} for n in base_tray_names],
        }
        pair_b = {
            "id": "b#0",
            "board": EMPTY,
            "tray": [{"recognized": True, "name": n} for n in reversed(base_tray_names)],
        }
        rejected = Counter()
        unique = dedup_pairs([pair_a, pair_b], rejected)
        self.assertEqual(len(unique), 2)
        self.assertEqual(rejected["duplikat"], 0)


class TestTrustedPomiar(unittest.TestCase):
    def test_reads_d550db3_style_pomiar_json(self):
        data = {
            "source": "test",
            "pairs": [
                {
                    "round": 1,
                    "board": EMPTY,
                    "tray": [
                        {"recognized": True, "name": "1x1", "raw": [[1]]},
                        {"recognized": True, "name": "beam2", "raw": [[1, 1]]},
                        {"recognized": True, "name": "square2", "raw": [[1, 1], [1, 1]]},
                    ],
                },
                {
                    "round": 2,
                    "board": EMPTY,
                    "tray": [
                        {"recognized": False, "name": None, "raw": [[1]]},
                        {"recognized": True, "name": "beam2", "raw": [[1, 1]]},
                        {"recognized": True, "name": "square2", "raw": [[1, 1], [1, 1]]},
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = os.path.join(tmp, "d550db3")
            os.makedirs(run_dir)
            with open(os.path.join(run_dir, "pomiar.json"), "w") as f:
                json.dump(data, f)
            rejected = Counter()
            # extract_from_trusted_pomiar reads from BRIDGE_RUNS_DIR/<run_dir>/<filename>
            import tools.z6_pary as z6_pary

            old = z6_pary.BRIDGE_RUNS_DIR
            z6_pary.BRIDGE_RUNS_DIR = tmp
            try:
                pairs = extract_from_trusted_pomiar("d550db3", "pomiar.json", rejected)
            finally:
                z6_pary.BRIDGE_RUNS_DIR = old
        self.assertEqual(len(pairs), 1)
        self.assertEqual(rejected["ksztalt_tacki_nierozpoznany"], 1)


class TestBuildDataset(unittest.TestCase):
    def test_build_dataset_on_small_fixture_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = os.path.join(tmp, "run1")
            os.makedirs(run_dir)
            board1 = _board()
            board2 = _board((0, 0))
            rows = [
                _row(board1, None, ok=True, observed=board2),
                _row(board2, ["1x1", "beam2-0", "square2"], ok=True),
            ]
            with open(os.path.join(run_dir, "moves.jsonl"), "w") as f:
                for row in rows:
                    f.write(json.dumps(row) + "\n")

            dataset = build_dataset(bridge_runs_dir=tmp)
        self.assertEqual(dataset["n_accepted"], 1)
        self.assertEqual(dataset["pairs"][0]["id"], "run1/moves.jsonl#1")


if __name__ == "__main__":
    unittest.main()
