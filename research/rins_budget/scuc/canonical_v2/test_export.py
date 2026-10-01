#!/usr/bin/env python3
"""Actual-library input fidelity regressions, with no optimization calls."""
import argparse
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

import numpy as np

from export_v2 import ExportError, intended_model, load_generator, sha256, validate_bound_records, write_model
from readback import compare_loaded, load_model, verify_expected, verify_model

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / "generate.py"
EXTENDED = HERE.parent / "large_cases/generate_network_only.py"
LIBRARY = None
FIXTURES = HERE / "fixtures"
EXPECTED_V1_SMOKE_SHA256 = "3198718762c421b792622804f80c27bd5973b355e9404cd62b4986e801a1187c"
OUT = None
REPORTS = {}


def tree_hashes(path):
    return {str(p.relative_to(path)): sha256(p) for p in sorted(path.rglob("*")) if p.is_file()}


def source_fixture():
    generators = {}
    for name, status, uptime, downtime, must_run in (
            ("residual_on", 1, 3, 1, False), ("residual_off", -1, 1, 3, False),
            ("must", 8, 1, 1, [True, False, True, False]), ("ordinary", -8, 1, 1, False)):
        generators[name] = {"Bus": "b1", "Production cost curve (MW)": [0.0, 2.0, 5.0],
            "Production cost curve ($)": [10.0, 14.0, 23.0], "Startup costs ($)": [5.0],
            "Startup delays (h)": [downtime], "Minimum uptime (h)": uptime,
            "Minimum downtime (h)": downtime, "Initial status (h)": status,
            "Initial power (MW)": 0.0, "Must run?": must_run, "Reserve eligibility": ["r0"]}
    return {"Parameters": {"Version": "0.3", "Time horizon (h)": 4, "Time step (min)": 60},
        "Generators": generators, "Buses": {"b1": {"Load (MW)": [0, 1, 2, 3]}, "b2": {"Load (MW)": 1}},
        "Transmission lines": {"l1": {"Source bus": "b1", "Target bus": "b2", "Susceptance (S)": 1.0,
                                          "Normal flow limit (MW)": 20.0}},
        "Reserves": {"r0": {"Type": "spinning", "Amount (MW)": 1.0, "Shortfall penalty ($/MW)": -1.0}},
        "Contingencies": {}}


def mixed_model(generator):
    model = generator.Model()
    entries = [("fixed_zero", 0, 0, True), ("fixed_one", 1, 1, True), ("binary", 0, 1, True),
               ("fixed_cont_zero", 0, 0, False), ("fixed_cont_neg", -2.5, -2.5, False),
               ("free", -math.inf, math.inf, False), ("lower_only", -3, math.inf, False),
               ("upper_only", -math.inf, -2, False), ("two_sided", -7, 4, False),
               ("default_nonneg", 0, math.inf, False), ("positive_lower", 2, math.inf, False),
               ("upper_zero", -math.inf, 0, False), ("binary_after_cont", 0, 1, True)]
    for j, (name, lo, up, binary) in enumerate(entries):
        model.var(name, lo=lo, up=up, c=(-1)**j * (j + .25), binary=binary)
    model.row([(j, (-1)**j * (j + .125)) for j in range(len(entries))], "E", 3.5)
    model.row([(j, (j + 1) / 8) for j in range(len(entries))], "L", -2.25)
    model.row([(0, 1e-8), (2, -4.125), (12, 2.25)], "G", 1.25)
    return model


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, _ = load_generator(ORIGINAL)
        cls.extended, _ = load_generator(EXTENDED)

    def audit(self, model, label):
        old, new = OUT / (label + ".v1.mps"), OUT / (label + ".v2.mps")
        model.write(old, {})
        meta = write_model(model, new)
        a, b = old.read_bytes(), new.read_bytes()
        self.assertEqual(a.split(b"BOUNDS\n")[0], b.split(b"BOUNDS\n")[0])
        # Exact byte-edit proof: the only removed records are BV on fixed binaries.
        removed = {f" BV BND1  {name}\n".encode() for name, lo, up, binary in zip(model.names, model.lb, model.ub, model.binary) if binary and lo == up}
        self.assertEqual(b, b"".join(line for line in a.splitlines(keepends=True) if line not in removed))
        report = verify_model(model, new, LIBRARY, OUT / (label + ".v2.readback.log"))
        report.update(v1_sha256=sha256(old), v2_sha256=sha256(new), byte_edit_proof=True,
                      removed_redundant_bv_records=len(removed), metadata=meta)
        REPORTS[label] = report
        self.assertTrue(report["passed"], report["failures"])
        return new, report

    def test_01_mixed_bounds_both_frozen_model_classes(self):
        for label, generator in (("mixed_original", self.original), ("mixed_extended", self.extended)):
            with self.subTest(label=label):
                self.audit(mixed_model(generator), label)

    def test_02_source_residual_status_must_run_and_network(self):
        data = source_fixture()
        for label, generator, mode in (("source_uc", self.original, "uc"), ("source_network", self.original, "network"),
                                       ("source_n1", self.original, "n1"), ("source_extended_network", self.extended, "network")):
            with self.subTest(label=label):
                model, _ = generator.build(data, 4, mode)
                names = {name: i for i, name in enumerate(model.names)}
                for t in range(4):
                    for unit, value, fixed_hours in (("residual_on", 1, {0, 1}), ("residual_off", 0, {0, 1}), ("must", 1, {0, 2})):
                        j = names[f"u_{unit}_{t}"]
                        self.assertEqual((model.lb[j], model.ub[j]), (value, value) if t in fixed_hours else (0, 1))
                self.audit(model, label)

    def test_03_old_bug_reproduction_and_preserved_original_smoke(self):
        source = FIXTURES / "on_negative.json"
        model, _ = self.extended.build(json.loads(source.read_text()), 3, "network")
        new, _ = self.audit(model, "preserved_failed_smoke")
        old = OUT / "preserved_failed_smoke.v1.mps"
        self.assertEqual(sha256(old), EXPECTED_V1_SMOKE_SHA256)
        loaded = load_model(old, LIBRARY, OUT / "old_bug.raw.readback.log")
        report = compare_loaded(intended_model(model), loaded)
        REPORTS["old_bug_expected_failure"] = report
        self.assertFalse(report["passed"])
        self.assertTrue(loaded["diagnostics"])
        mismatches = report["fields"]["col_lower"]["first_mismatches"]
        self.assertEqual([x["column"] for x in mismatches], [f"u_offset_{t}" for t in range(3)])
        self.assertTrue(all(x["expected"] == 1 and x["loaded"] == 0 for x in mismatches))
        for field, check in report["fields"].items():
            if field != "col_lower":
                self.assertTrue(check["passed"], field)
        with self.assertRaisesRegex(ExportError, "Duplicate bound"):
            validate_bound_records(old)

    def test_04_fixed_zero_and_one_bug(self):
        model = mixed_model(self.original)
        old = OUT / "mixed_original.v1.mps"
        loaded = load_model(old, LIBRARY, OUT / "mixed_old_bug.raw.readback.log")
        report = compare_loaded(intended_model(model), loaded)
        REPORTS["fixed_zero_one_expected_failure"] = report
        self.assertFalse(report["passed"])
        self.assertEqual((loaded["col_lower"][0], loaded["col_upper"][0]), (0, 1))
        self.assertEqual((loaded["col_lower"][1], loaded["col_upper"][1]), (0, 1))
        self.assertEqual(list(loaded["integrality"][:3]), [1, 1, 1])

    def test_05_duplicate_and_unsupported_bounds_rejected(self):
        original = (OUT / "mixed_original.v2.mps").read_text()
        injected = [" FX BND1  fixed_zero  0", " BV BND1  fixed_zero", " LO BND1  lower_only  -3",
                    " UP BND1  two_sided  5", " FR BND1  free", " SC BND1  default_nonneg  1",
                    " UP OTHER  default_nonneg  1", " FX BND1  unknown  1", " FX BND1  free  nan",
                    " BV BND1  default_nonneg", " FX BND1  binary  0.5", " MI BND1  free  0"]
        for i, record in enumerate(injected):
            with self.subTest(record=record):
                path = OUT / f"malformed_bound_{i}.mps"
                path.write_text(original.replace("ENDATA\n", record + "\nENDATA\n"))
                with self.assertRaises(ExportError):
                    validate_bound_records(path)
        REPORTS["malformed_bound_rejections"] = {"passed": True, "rejected_count": len(injected), "records": injected}

    def test_06_unsupported_source_values_rejected(self):
        for label, mutate in (("binary_fractional", lambda m: m.lb.__setitem__(2, .5)),
                              ("invalid_bounds", lambda m: m.ub.__setitem__(8, -10)),
                              ("nan_cost", lambda m: m.obj.__setitem__(0, math.nan)),
                              ("duplicate_name", lambda m: m.names.__setitem__(1, m.names[0])),
                              ("unknown_integrality", lambda m: m.binary.__setitem__(0, 2))):
            with self.subTest(label=label):
                model = mixed_model(self.original)
                mutate(model)
                with self.assertRaises(ExportError):
                    write_model(model, OUT / (label + ".mps"))
                self.assertFalse((OUT / (label + ".mps")).exists())

    def test_07_every_comparison_field_is_enforced(self):
        model = mixed_model(self.original)
        expected = intended_model(model)
        loaded = load_model(OUT / "mixed_original.v2.mps", LIBRARY, OUT / "mutation_gate.readback.log")
        for field in expected:
            with self.subTest(field=field):
                altered = copy.deepcopy(loaded)
                if field in ("col_names", "row_names"):
                    altered[field][0] += "_wrong"
                elif isinstance(altered[field], np.ndarray):
                    altered[field][0] = altered[field][0] + 1 if math.isfinite(altered[field][0]) else 0
                else:
                    altered[field] += 1
                self.assertFalse(compare_loaded(expected, altered)["passed"], field)
        REPORTS["all_field_mutation_gate"] = {"passed": True, "fields": list(expected)}

    def test_08_dropped_matrix_warning_fails_closed(self):
        model = mixed_model(self.original)
        model.val[0] = 1e-12
        path = OUT / "dropped_coefficient.v2.mps"
        write_model(model, path)
        report = verify_model(model, path, LIBRARY, OUT / "dropped_coefficient.readback.log")
        REPORTS["dropped_coefficient_expected_failure"] = report
        self.assertFalse(report["passed"])
        self.assertTrue(report["diagnostics"])
        self.assertFalse(report["fields"]["a_value"]["passed"])

    def test_09_no_fixed_binary_is_byte_identical(self):
        model = mixed_model(self.original)
        model.ub[0], model.lb[1] = 1, 0
        _, report = self.audit(model, "no_fixed_binary")
        self.assertEqual(report["v1_sha256"], report["v2_sha256"])

    def test_10_cli_portable_export_and_no_overwrite(self):
        path = OUT / "cli_source.json"
        path.write_text(json.dumps(source_fixture(), indent=2) + "\n")
        output = OUT / "cli_output.mps"
        command = [sys.executable, str(HERE / "export_v2.py"), str(path), "--generator", str(ORIGINAL),
                   "--mode", "network", "--hours", "4", "--output", str(output), "--library", str(LIBRARY)]
        process = subprocess.run(command, text=True, capture_output=True)
        (OUT / "cli.stdout.log").write_text(process.stdout)
        (OUT / "cli.stderr.log").write_text(process.stderr)
        self.assertEqual(process.returncode, 0, process.stderr)
        meta = json.loads(Path(str(output) + ".meta.json").read_text())
        self.assertTrue(meta["api_fidelity_verified"])
        before = sha256(output)
        process = subprocess.run(command, text=True, capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("Refusing to overwrite", process.stderr)
        self.assertEqual(before, sha256(output))
        REPORTS["cli"] = {"passed": True, "mps_sha256": before, "mandatory_api_readback": True, "refused_overwrite": True}

    def test_11_fixed_continuous_lp_expected_dictionary(self):
        model = mixed_model(self.original)
        model.binary = [False] * len(model.binary)
        model.lb[2] = model.ub[2] = 1.0
        model.lb[-1] = model.ub[-1] = 0.0
        path = OUT / "fixed_continuous_lp.mps"
        write_model(model, path)
        report = verify_expected(intended_model(model), path, LIBRARY, OUT / "fixed_continuous_lp.readback.log")
        REPORTS["fixed_continuous_lp"] = report
        self.assertTrue(report["passed"], report["failures"])
        self.assertEqual(report["bound_record_audit"]["integer_columns"], 0)


def main():
    global OUT, LIBRARY
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--library", required=True, help="HiGHS shared library for actual readModel/getLp tests")
    args = parser.parse_args()
    LIBRARY = Path(args.library).resolve()
    OUT = Path(args.output_dir).resolve()
    OUT.mkdir(parents=True, exist_ok=False)
    before = {"original_generator": sha256(ORIGINAL), "extended_generator": sha256(EXTENDED),
              "fixture_tree": tree_hashes(FIXTURES)}
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExportTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after = {"original_generator": sha256(ORIGINAL), "extended_generator": sha256(EXTENDED),
             "fixture_tree": tree_hashes(FIXTURES)}
    report = {"passed": result.wasSuccessful() and before == after, "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "source_and_fixtures_unchanged": before == after,
              "preserved_files": before, "library_sha256": sha256(LIBRARY), "optimization_or_presolve_called": False,
              "reports": REPORTS}
    (OUT / "TEST_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
