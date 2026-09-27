"""
Test na `benchmark.py --jobs N` (#148): wynik bitowo ten sam jak przy `--jobs 1`.

Partie (seed x ramię) zależą tylko od swojego seeda i polityki, więc `--jobs 2`
musi dać ten sam plik wyjściowy co `--jobs 1`, poza `duration_s` (czas zegarowy)
i ewentualnie `sha`/`dirty` (stan repo mógł się zmienić między dwoma przebiegami).
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


class TestBenchmarkJobsBitwiseIdentical(unittest.TestCase):
    def run_benchmark(self, jobs, out_path):
        subprocess.check_call(
            [
                sys.executable, "benchmark.py",
                "--candidate", "greedy",
                "--previous", "random",
                "--issue", "148",
                "--n-seeds", "3",
                "--jobs", str(jobs),
                "--out", out_path,
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with open(out_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_jobs_1_and_jobs_2_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            out1 = os.path.join(tmp, "jobs1.json")
            out2 = os.path.join(tmp, "jobs2.json")
            record1 = self.run_benchmark(1, out1)
            record2 = self.run_benchmark(2, out2)
            self.assertEqual(strip_volatile(record1), strip_volatile(record2))


if __name__ == "__main__":
    unittest.main()
