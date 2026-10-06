"""Pure text/status fixtures. No runner main, exporter, or native calls."""
import unittest
from run_probe import parity, read_status

VALID = """  Status Optimal
  Primal bound 188182
  Dual bound 188165.733226
  Gap 0.00864% (tolerance: 0.01%)
  Nodes 3
  LP iterations 11461
"""


class RunnerTextTests(unittest.TestCase):
    def test_valid_status(self):
        result = read_status(VALID)
        self.assertEqual(result["status"], "Optimal")
        self.assertEqual(result["iterations"], "11461")

    def test_invalid_status_and_fields(self):
        for original, replacement in (
            ("Optimal", "Time limit reached"),
            ("188182", "nan"),
            ("188165.733226", "inf"),
            ("0.00864%", "-1%"),
            ("0.00864%", "0.02%"),
            ("Nodes 3", "Nodes -1"),
            ("LP iterations 11461", "LP iterations absent"),
        ):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                read_status(VALID.replace(original, replacement))
        with self.assertRaises(ValueError):
            read_status(VALID.replace("  Status Optimal\n", ""))

    def test_exact_parity_includes_point_and_trajectory(self):
        original = dict(read_status(VALID), solution_sha256="same")
        self.assertTrue(parity(original, dict(original))["passed"])
        for field in ("status", "primal", "dual", "gap", "nodes", "iterations",
                      "solution_sha256"):
            changed = dict(original)
            changed[field] = "different"
            result = parity(original, changed)
            self.assertFalse(result["passed"])
            self.assertEqual(set(result["differences"]), {field})


if __name__ == "__main__":
    unittest.main()
