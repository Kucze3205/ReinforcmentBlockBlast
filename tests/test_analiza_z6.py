"""
Test dla #198: `power_normal_approx` ignorował parametr `alpha` — `z_alpha` był zakodowany
na sztywno dla 0,05 (zgłoszone w #191).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from analiza_z6 import power_normal_approx

PROBS = [0.2, 0.3, 0.25, 0.4, 0.15, 0.35, 0.28, 0.22, 0.31, 0.19]


class TestPowerNormalApproxAlpha(unittest.TestCase):
    def test_default_alpha_matches_old_hardcoded_result(self):
        """0,11202221679163038 to wynik ze starego, na sztywno zakodowanego z_alpha=1.6448536269514722
        (jednostronne alpha=0,05); `norm_ppf(0.95)` różni się od tej stałej tylko przybliżeniem
        Acklama (błąd < 1e-9), więc tolerancja `places=7` odróżnia poprawkę od regresji."""
        result = power_normal_approx(PROBS, alpha=0.05, delta=0.05)
        self.assertAlmostEqual(result["power"], 0.11202221679163038, places=7)

    def test_smaller_alpha_gives_smaller_power(self):
        power_05 = power_normal_approx(PROBS, alpha=0.05, delta=0.05)["power"]
        power_01 = power_normal_approx(PROBS, alpha=0.01, delta=0.05)["power"]
        self.assertLess(power_01, power_05)

    def test_larger_alpha_gives_larger_power(self):
        power_05 = power_normal_approx(PROBS, alpha=0.05, delta=0.05)["power"]
        power_10 = power_normal_approx(PROBS, alpha=0.10, delta=0.05)["power"]
        self.assertGreater(power_10, power_05)


if __name__ == "__main__":
    unittest.main()
