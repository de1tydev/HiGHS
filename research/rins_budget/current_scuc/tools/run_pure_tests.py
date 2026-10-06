#!/usr/bin/env python3
"""Run pure regressions while preventing subprocess, factor, and solver entry."""
import ctypes
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import numpy as np
import scipy.sparse.linalg as sparse_linalg


def forbidden(*args, **kwargs):
    raise AssertionError('Pure tests forbid native entry, processes, factorization and solves')


if __name__ == '__main__':
    if not sys.dont_write_bytecode:
        raise RuntimeError('Run with Python -B')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    discovered = unittest.defaultTestLoader.discover(str(root/'tests'), pattern='test_*.py')
    def flatten(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite): yield from flatten(item)
            else: yield item
    tests = list(flatten(discovered))
    import_checks = [t for t in tests if t.id().endswith('.test_no_native_or_scientific_imports')]
    import_result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(import_checks))
    pure_suite = unittest.TestSuite(t for t in tests if t not in import_checks)
    with patch.object(ctypes, 'CDLL', forbidden), patch.object(subprocess, 'Popen', forbidden), \
         patch.object(sparse_linalg, 'splu', forbidden), patch.object(sparse_linalg, 'spsolve', forbidden), \
         patch.object(np.linalg, 'solve', forbidden):
        result = unittest.TextTestRunner(verbosity=2).run(pure_suite)
    raise SystemExit(not (result.wasSuccessful() and import_result.wasSuccessful()))
