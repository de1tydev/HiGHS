"""Solver-free checks of the portable fixture runner's output parsing."""

import unittest

from run_paired_probe import final_json


class ProbeOutputTests(unittest.TestCase):
    def test_plain_output(self):
        self.assertEqual(final_json('{"status":"Optimal"}\n'), {"status": "Optimal"})

    def test_native_profile_prefix(self):
        self.assertEqual(final_json('Native profile text\n{"nodes":3}\n'), {"nodes": 3})

    def test_last_json_record(self):
        self.assertEqual(final_json('{"old":true}\n{"new":true}\n'), {"new": True})

    def test_missing_record(self):
        with self.assertRaises(ValueError):
            final_json("Profile only\n")

    def test_malformed_record(self):
        with self.assertRaises(ValueError):
            final_json("{truncated\n")


if __name__ == "__main__":
    unittest.main()
