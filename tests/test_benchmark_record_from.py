"""
Test na `benchmark.py --record-from` / `--keep-record-scores` (#219).

Cel: ramię `record` nie liczy się od nowa, gdy identyczny pomiar (ten sam
`source_hashes`, `config`, `spec` i `weights_hash`) już istnieje w pliku
`bench/*.json` z wcześniej wyprodukowanego przebiegu (`--keep-record-scores`).
Zestaw rotowany zawsze liczy się na nowo (zależy od soli `issue`).

Bez żadnej z dwóch nowych flag wynik ma być bitowo taki sam jak przed #219.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VOLATILE_KEYS = {"duration_s", "sha", "dirty"}


def strip_volatile(record):
    return {k: v for k, v in record.items() if k not in VOLATILE_KEYS}


def run_benchmark(extra_args, out_path, check=True):
    proc = subprocess.run(
        [sys.executable, "benchmark.py"] + extra_args + ["--out", out_path],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and proc.returncode != 0:
        raise AssertionError("benchmark.py zakończył się kodem " + str(proc.returncode) + ": " + proc.stderr)
    with open(out_path, encoding="utf-8") as fh:
        return json.load(fh), proc


COMMON = ["--candidate", "greedy", "--record", "heuristic", "--previous", "random",
          "--issue", "219", "--n-seeds", "4"]


class TestRecordFromMatchesFullRun(unittest.TestCase):
    def test_record_from_matches_direct_recomputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            anchor_path = os.path.join(tmp, "anchor.json")
            anchor, _ = run_benchmark(COMMON + ["--keep-record-scores"], anchor_path)
            self.assertIn("scores", anchor["arms"]["record"]["fixed"])

            cached_path = os.path.join(tmp, "cached.json")
            cached, _ = run_benchmark(
                ["--candidate", "tray", "--record", "heuristic", "--issue", "219", "--n-seeds", "4",
                 "--record-from", anchor_path],
                cached_path,
            )
            self.assertEqual(cached["status"], "ok")

            direct_path = os.path.join(tmp, "direct.json")
            direct, _ = run_benchmark(
                ["--candidate", "tray", "--record", "heuristic", "--issue", "219", "--n-seeds", "4"],
                direct_path,
            )

            self.assertEqual(
                cached["arms"]["record"]["fixed"], direct["arms"]["record"]["fixed"]
            )
            self.assertEqual(
                cached["arms"]["record"]["rotated"], direct["arms"]["record"]["rotated"]
            )
            self.assertEqual(cached["deltas"], direct["deltas"])

    def test_without_new_flags_output_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = run_benchmark(COMMON, os.path.join(tmp, "plain.json"))
            self.assertNotIn("scores", data["arms"]["record"]["fixed"])
            self.assertNotIn("scores", data["arms"]["candidate"]["fixed"])


class TestRecordFromRefusal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.anchor_path = os.path.join(self.tmp.name, "anchor.json")
        self.anchor, _ = run_benchmark(COMMON + ["--keep-record-scores"], self.anchor_path)

    def _tampered(self, mutate):
        data = json.loads(json.dumps(self.anchor))
        mutate(data)
        path = os.path.join(self.tmp.name, "tampered.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        return path

    def test_refuses_mismatched_source_hashes(self):
        path = self._tampered(
            lambda d: d["source_hashes"].update({"game.py": "0000000000000000"})
        )
        out = os.path.join(self.tmp.name, "out.json")
        data, _ = run_benchmark(
            ["--candidate", "greedy", "--record", "heuristic", "--issue", "219", "--n-seeds", "4",
             "--record-from", path],
            out,
        )
        self.assertEqual(data["status"], "blocked")
        self.assertIn("source_hashes", data["blocked_reason"])

    def test_refuses_mismatched_move_cap(self):
        path = self._tampered(lambda d: d["config"].update({"move_cap": 123}))
        out = os.path.join(self.tmp.name, "out.json")
        data, _ = run_benchmark(
            ["--candidate", "greedy", "--record", "heuristic", "--issue", "219", "--n-seeds", "4",
             "--record-from", path],
            out,
        )
        self.assertEqual(data["status"], "blocked")
        self.assertIn("config", data["blocked_reason"])

    def test_refuses_mismatched_spec(self):
        out = os.path.join(self.tmp.name, "out.json")
        data, _ = run_benchmark(
            ["--candidate", "greedy", "--record", "lookahead", "--issue", "219", "--n-seeds", "4",
             "--record-from", self.anchor_path],
            out,
        )
        self.assertEqual(data["status"], "blocked")
        self.assertIn("spec", data["blocked_reason"])

    def test_refuses_file_without_kept_scores(self):
        plain_path = os.path.join(self.tmp.name, "plain.json")
        run_benchmark(COMMON, plain_path)
        out = os.path.join(self.tmp.name, "out.json")
        data, _ = run_benchmark(
            ["--candidate", "greedy", "--record", "heuristic", "--issue", "219", "--n-seeds", "4",
             "--record-from", plain_path],
            out,
        )
        self.assertEqual(data["status"], "blocked")
        self.assertIn("wyników per seed", data["blocked_reason"])

    def test_refuses_shard_combined_with_record_from(self):
        out = os.path.join(self.tmp.name, "out.json")
        proc = subprocess.run(
            [sys.executable, "benchmark.py", "--candidate", "greedy", "--record", "heuristic",
             "--issue", "219", "--n-seeds", "4", "--shard", "1/2",
             "--record-from", self.anchor_path, "--out", out],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
