#!/usr/bin/env python3
"""Run inherited contracts with explicit mocks; never import numerical packages.

Invoke with python3 -B -S tests/run_pure_tests.py. Exactly three inherited tests
requiring actual NumPy scalars are outside this suite and explicitly skipped. The
separator stub prevents patch resolution from importing topology code.
"""
import argparse
import importlib.abc
import ctypes
import io
import json
from pathlib import Path
import sys
import subprocess
import time
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / 'tests'
DRIVER = ROOT / 'payload/combined_screening_driver'
sys.path[:0] = [str(DRIVER), str(TESTS), str(ROOT)]


class NoNumericalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'numpy', 'scipy', 'highspy'}:
            raise AssertionError('Real numerical import prohibited: ' + fullname)
        return None


def install_mocks():
    if any(name.split('.')[0] in {'numpy', 'scipy', 'highspy'} for name in sys.modules):
        raise AssertionError('Numerical module loaded before pure-test harness')
    separator = types.ModuleType('fractional_separator')
    separator.__pure_test_mock__ = True
    def prohibited(*args, **kwargs):
        raise AssertionError('Unmocked separator work prohibited')
    for name in ('source_scope', 'source_data_sha256', 'separate', 'separate_integer_network'):
        setattr(separator, name, prohibited)
    # These inherited tests assert matrix/control behavior, not point hashing.
    # Keep that external witness dependency visibly mocked as well.
    separator.point_sha256 = Mock(name='mock_point_sha256', return_value='a' * 64)
    sys.modules['fractional_separator'] = separator
    sys.meta_path.insert(0, NoNumericalImports())


PENDING_SCIENTIFIC_TESTS = {
    'test_contract.SourceWrapperTests.test_trusted_numpy_base_and_residual_cross_boundary',
    'test_contract.TrustedScalarTests.test_finite_numpy_real_only_and_no_input_mutation',
    'test_contract.TrustedScalarTests.test_reject_nonfinite_bool_complex_arrays_and_coercibles',
}


def mark_pending_scientific_tests(suite):
    found = set()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            found.update(mark_pending_scientific_tests(item))
        elif item.id() in PENDING_SCIENTIFIC_TESTS:
            test = getattr(type(item), item._testMethodName)
            test.__unittest_skip__ = True
            test.__unittest_skip_why__ = 'Excluded from this standard-library-only suite; real NumPy scalar tests run separately'
            found.add(item.id())
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', type=Path,
                        help='Optional existing output directory for JSON/log evidence; default only prints results')
    args = parser.parse_args()
    if not sys.flags.no_site or not sys.dont_write_bytecode or not __debug__:
        raise SystemExit('Use an assertion-enabled interpreter with -B -S')
    install_mocks()
    start = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern='test_*.py')
    found = mark_pending_scientific_tests(suite)
    if found != PENDING_SCIENTIFIC_TESTS:
        raise AssertionError('Inherited scientific test inventory changed: ' + repr(found))
    stream = io.StringIO()
    with patch.object(subprocess, 'Popen', side_effect=AssertionError('Unmocked external process prohibited')), \
         patch.object(ctypes, 'CDLL', side_effect=AssertionError('Unmocked DSO loading prohibited')):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = stream.getvalue()
    sys.stdout.write(log)
    real_numerical = sorted(name for name, module in sys.modules.items()
                            if name.split('.')[0] in {'numpy', 'scipy', 'highspy'}
                            and not getattr(module, '__pure_test_mock__', False))
    record = {
        'schema': 1,
        'scope': 'standard-library-only inherited contract and portable binding tests',
        'command': 'python3 -B -S tests/run_pure_tests.py',
        'tests_run': result.testsRun,
        'tests_passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'passed': result.wasSuccessful() and not real_numerical,
        'status': 'pure_subset_passed_scientific_tests_separate' if result.wasSuccessful() and not real_numerical else 'failed',
        'duration_seconds': round(time.monotonic() - start, 6),
        'real_numerical_modules_loaded': real_numerical,
        'explicit_test_doubles': ['fractional_separator entry points for inherited model_stage mocks',
                                 'fractional_separator.point_sha256 returns a fixed mock witness'],
        'limitations': ['No actual NumPy or SciPy behavior, solver execution, C API, model generation, or topology is tested'],
        'failed_tests': [test.id() for test, _ in result.failures + result.errors],
        'skipped_tests': [{'test': test.id(), 'reason': reason} for test, reason in result.skipped],
    }
    if args.results_dir is not None:
        safe_log = log.replace(str(ROOT), '<portable-package>').replace(sys.base_prefix, '<python-prefix>')
        (args.results_dir / 'TEST_RESULTS.json').write_text(json.dumps(record, indent=2, allow_nan=False) + '\n')
        (args.results_dir / 'TEST_RESULTS.log').write_text(safe_log)
    return 0 if record['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
