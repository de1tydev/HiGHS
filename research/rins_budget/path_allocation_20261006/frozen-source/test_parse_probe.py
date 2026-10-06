"""Synthetic fixtures only: no native library imports, builds, or solves."""

import copy
import json
import unittest

from parse_probe import UINT64_MAX, VECTOR_NAMES, combine_models, parse_log


def fixture(eligible=32, submip=0, depth=0, highsint_bytes=4):
    cost = dict(submip=submip, depth=depth, num_col=10, num_row=6,
                eligible=eligible, transform_calls=2 * eligible,
                transform_failed=0, first_transform_failed=0,
                rhs_first_rejected=0, rhs_order_rejected=0, truncated=0,
                mixing_ready=eligible, requested_rows=2 * eligible,
                usable_rows=2 * eligible, capacity_anomalies=0,
                scratch_init_seconds=0.004 if eligible else 0,
                scratch_destroy_seconds=0.002 if eligible else 0,
                path_body_seconds=0.05, clock_pair_samples=32,
                clock_pair_seconds=0.00000032)
    records = [("PATH_MIX_COST", cost)]
    widths = (highsint_bytes, 8, 8, 1, 8, 8, 8)
    for name, width in zip(VECTOR_NAMES, widths):
        size = 16 if name in VECTOR_NAMES[:4] else 2
        payload = eligible * size * width
        records.append(("PATH_MIX_VECTOR", dict(
            submip=submip, depth=depth, name=name,
            inferred_growth_requests=eligible,
            requested_payload_bytes=payload,
            new_capacity_payload_bytes=payload,
            final_capacity_payload_bytes=payload,
            max_capacity_payload_bytes=size * width if eligible else 0)))
    records.append(("SEP_COST", dict(name="path", submip=submip, depth=depth,
                                     seconds=0.06, pool_delta=0, lp_iterations=0)))
    return records


def encode(records):
    return "\n".join(tag + " " + " ".join(f"{k}={v}" for k, v in fields.items())
                     for tag, fields in records) + "\n"


class ProbeParserTests(unittest.TestCase):
    def test_valid_scopes_zero_attempts_and_raw_records(self):
        raw = encode(fixture()) + encode(fixture(0, 1, 2)) + encode(fixture(2, 1, 1))
        parsed = parse_log("ordinary solver output\n" + raw)
        self.assertEqual(len(parsed["invocations"]), 3)
        self.assertEqual(parsed["summary"]["A"], 34)
        self.assertAlmostEqual(parsed["summary"]["S"], 0.012)
        self.assertAlmostEqual(parsed["summary"]["P"], 0.15)
        self.assertAlmostEqual(parsed["summary"]["O"], 2 * 34 * 1e-8)
        self.assertEqual(parsed["scopes"]["main"]["A"], 32)
        self.assertEqual(parsed["scopes"]["submip"]["A"], 2)
        self.assertEqual(parsed["scopes"]["by_depth"]["2"]["A"], 0)
        self.assertEqual(parsed["invocations"][0]["raw_lines"], encode(fixture()).splitlines())
        self.assertTrue(parsed["materiality_pass"])
        json.dumps(parsed, allow_nan=False)

    def test_highsint_widths(self):
        self.assertTrue(parse_log(encode(fixture(highsint_bytes=8)), 8)["accounting_valid"])
        with self.assertRaises(ValueError):
            parse_log(encode(fixture(highsint_bytes=8)), 4)
        for width in (1, 2, True, 4.0):
            with self.subTest(width=width), self.assertRaises(ValueError):
                parse_log(encode(fixture()), width)

    def test_missing_duplicate_reordered_and_interrupted_records(self):
        records = fixture()
        candidates = [[], records[1:], records[:-1], records[:-2] + records[-1:],
                      records[:2] + [records[1]] + records[2:],
                      [records[0], records[2], records[1]] + records[3:],
                      records + [records[-1]], records[:1] + records]
        for index, candidate in enumerate(candidates):
            with self.subTest(index=index), self.assertRaises(ValueError):
                parse_log(encode(candidate))
        with self.assertRaises(ValueError):
            parse_log(encode(records).replace("PATH_MIX_VECTOR", "noise\nPATH_MIX_VECTOR", 1))

    def test_malformed_and_duplicate_fields(self):
        raw = encode(fixture())
        for changed in (raw.replace("eligible=32", "eligible=32 eligible=32"),
                        raw.replace("eligible=32", "eligible"),
                        raw.replace("eligible=32", "unexpected=32"),
                        raw.replace("PATH_MIX_COST", "PATH_MIX_COST_BROKEN"),
                        raw.replace("SEP_COST", "prefix SEP_COST")):
            with self.subTest(changed=changed[:90]), self.assertRaises(ValueError):
                parse_log(changed)

    def test_numeric_and_scope_domains(self):
        mutations = [(0, "eligible", -1), (0, "eligible", UINT64_MAX + 1),
                     (0, "eligible", "1.0"), (0, "submip", 2),
                     (0, "depth", -1), (0, "depth", 1 << 31),
                     (0, "num_col", 1 << 31), (0, "num_col", (1 << 31) - 1),
                     (0, "scratch_init_seconds", "NaN"),
                     (0, "scratch_destroy_seconds", "inf"),
                     (0, "path_body_seconds", "1e999"),
                     (0, "clock_pair_seconds", "-0.01"),
                     (1, "requested_payload_bytes", -1),
                     (1, "new_capacity_payload_bytes", UINT64_MAX + 1),
                     (1, "depth", 9), (8, "submip", 1),
                     (8, "seconds", "nan"), (8, "seconds", 0.001),
                     (8, "pool_delta", -(1 << 31) - 1),
                     (8, "pool_delta", 1 << 31),
                     (8, "lp_iterations", -(1 << 63) - 1),
                     (8, "lp_iterations", 1 << 63)]
        for index, key, value in mutations:
            with self.subTest(index=index, key=key, value=value), self.assertRaises(ValueError):
                changed = copy.deepcopy(fixture())
                changed[index][1][key] = value
                parse_log(encode(changed))

    def test_every_predeclared_accounting_identity(self):
        mutations = [(0, "capacity_anomalies", 1), (0, "clock_pair_samples", 31),
                     (0, "first_transform_failed", 1), (0, "mixing_ready", 33),
                     (0, "usable_rows", 65), (0, "truncated", 1),
                     (0, "transform_calls", 31), (0, "transform_calls", 65),
                     (0, "scratch_init_seconds", 0.049),
                     (1, "inferred_growth_requests", 31),
                     (1, "requested_payload_bytes", 2044),
                     (5, "requested_payload_bytes", 504),
                     (1, "new_capacity_payload_bytes", 2044),
                     (1, "final_capacity_payload_bytes", 2052),
                     (6, "inferred_growth_requests", 65),
                     (7, "inferred_growth_requests", 31)]
        for index, key, value in mutations:
            with self.subTest(index=index, key=key), self.assertRaises(ValueError):
                changed = copy.deepcopy(fixture())
                changed[index][1][key] = value
                parse_log(encode(changed))

    def test_sum_tolerance_and_nonfinite_aggregate(self):
        records = fixture()
        records[0][1]["path_body_seconds"] = 0.006 - 0.5e-9
        self.assertTrue(parse_log(encode(records))["accounting_valid"])
        records[0][1]["path_body_seconds"] = 0.006 - 2e-9
        with self.assertRaises(ValueError):
            parse_log(encode(records))
        records = fixture(0)
        records[0][1]["path_body_seconds"] = 1e308
        records[8][1]["seconds"] = 1e308
        with self.assertRaises(ValueError):
            parse_log(encode(records) * 2)

    def test_companion_fields_and_placement(self):
        records = fixture()
        records[8][1]["name"] = "tableau"
        with self.assertRaises(ValueError):
            parse_log(encode(records))

    def test_signed_companion_and_unrelated_separator_deltas(self):
        records = fixture()
        records[8][1]["pool_delta"] = -(1 << 31)
        records[8][1]["lp_iterations"] = -(1 << 63)
        other = ("SEP_COST", dict(name="lp_resolve", submip=0, depth=0,
                                  seconds=0.01, pool_delta=-3, lp_iterations=-4))
        parsed = parse_log(encode([other] + records))
        companion = parsed["invocations"][0]["separator_cost"]
        self.assertEqual(companion["pool_delta"], -(1 << 31))
        self.assertEqual(companion["lp_iterations"], -(1 << 63))
        unrelated = parsed["other_separator_records"][0]["record"]
        self.assertEqual(unrelated["pool_delta"], -3)
        self.assertEqual(unrelated["lp_iterations"], -4)
        records[8][1]["name"] = "unknown"
        with self.assertRaises(ValueError):
            parse_log(encode(records))
        records = fixture()
        records[8][1].pop("seconds")
        with self.assertRaises(ValueError):
            parse_log(encode(records))

    def test_signal_screens_and_exact_model_pair(self):
        passing = parse_log(encode(fixture()))
        failing = parse_log(encode(fixture(0)))
        combined = combine_models({"dcmulti": passing, "gesa2": passing})
        self.assertTrue(combined["both_models_materiality_pass"])
        self.assertIsNone(combined["gate_pass"])
        self.assertTrue(combined["external_checks_required"])
        failed = combine_models({"dcmulti": passing, "gesa2": failing})
        self.assertFalse(failed["both_models_materiality_pass"])
        self.assertFalse(failed["gate_pass"])
        for models in ({}, {"dcmulti": passing},
                       {"dcmulti": passing, "gesa2": passing, "other": passing}):
            with self.assertRaises(ValueError):
                combine_models(models)
        for key, value in (("scratch_init_seconds", 0.001),
                           ("clock_pair_seconds", 1), ("path_body_seconds", 1)):
            records = fixture()
            records[0][1][key] = value
            records[8][1]["seconds"] = 2
            self.assertFalse(parse_log(encode(records))["materiality_pass"])


if __name__ == "__main__":
    unittest.main()
