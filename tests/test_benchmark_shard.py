"""
Test na `benchmark.py --shard K/N` + `tools/merge_bench.py` (#167).

Odpowiednik `tests/test_benchmark_jobs.py` dla kawałkowania: złożenie N
kawałków musi dać `arms`/`deltas` identyczne z przebiegiem bez `--shard`
(agregaty są niezależne od kolejności seedów). Druga część testuje odmowę
`merge_bench.py` na niespójnych kawałkach.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import merge_bench  # noqa: E402

VOLATILE_KEYS = {"duration_s", "sha", "dirty"}

COMMON_ARGS = [
    "--candidate", "greedy",
    "--previous", "random",
    "--issue", "167",
    "--n-seeds", "6",
]


def strip_volatile(record):
    return {k: v for k, v in record.items() if k not in VOLATILE_KEYS}


def run_benchmark(extra_args, out_path):
    subprocess.check_call(
        [sys.executable, "benchmark.py"] + extra_args + ["--out", out_path],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with open(out_path, encoding="utf-8") as fh:
        return json.load(fh)


class TestShardMergeEqualsFullRun(unittest.TestCase):
    def test_three_shards_equal_full_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            shard_paths = []
            for k in (1, 2, 3):
                path = os.path.join(tmp, "shard{0}.json".format(k))
                data = run_benchmark(COMMON_ARGS + ["--shard", "{0}/3".format(k)], path)
                self.assertEqual(data["shard"], "{0}/3".format(k))
                shard_paths.append(path)

            merged_path = os.path.join(tmp, "merged.json")
            rc = merge_bench.main(["--out", merged_path] + shard_paths)
            self.assertEqual(rc, 0)
            with open(merged_path, encoding="utf-8") as fh:
                merged = json.load(fh)

            full = run_benchmark(COMMON_ARGS, os.path.join(tmp, "full.json"))

            self.assertEqual(merged["arms"], full["arms"])
            self.assertEqual(merged["deltas"], full["deltas"])
            self.assertNotIn("shard", merged)

    def test_shard_without_shard_flag_matches_normal_run(self):
        # Bez --shard benchmark działa dokładnie jak dziś (brak pola "shard").
        with tempfile.TemporaryDirectory() as tmp:
            data = run_benchmark(COMMON_ARGS, os.path.join(tmp, "full.json"))
            self.assertNotIn("shard", data)
            self.assertNotIn("scores", data["arms"]["candidate"]["fixed"])


class TestMergeBenchRefusal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.shard_paths = []
        for k in (1, 2):
            path = os.path.join(self.tmp.name, "shard{0}.json".format(k))
            run_benchmark(
                ["--candidate", "greedy", "--previous", "random", "--issue", "167",
                 "--n-seeds", "4", "--shard", "{0}/2".format(k)],
                path,
            )
            self.shard_paths.append(path)

    def test_refuses_different_sha(self):
        with open(self.shard_paths[1], encoding="utf-8") as fh:
            data = json.load(fh)
        data["sha"] = "deadbeefdeadbeef"
        mutated = os.path.join(self.tmp.name, "shard2-mutated.json")
        with open(mutated, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

        out = os.path.join(self.tmp.name, "out.json")
        rc = merge_bench.main(["--out", out, self.shard_paths[0], mutated])
        self.assertNotEqual(rc, 0)
        self.assertFalse(os.path.exists(out))

    def test_refuses_missing_shard(self):
        out = os.path.join(self.tmp.name, "out.json")
        rc = merge_bench.main(["--out", out, self.shard_paths[0]])
        self.assertNotEqual(rc, 0)
        self.assertFalse(os.path.exists(out))

    def test_refuses_duplicated_shard(self):
        out = os.path.join(self.tmp.name, "out.json")
        rc = merge_bench.main(["--out", out, self.shard_paths[0], self.shard_paths[0]])
        self.assertNotEqual(rc, 0)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
