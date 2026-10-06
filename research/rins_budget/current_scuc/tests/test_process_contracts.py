"""Pure containment contract tests; never launch a process or apply a limit."""
import os
import resource
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from current_scuc import process_runner


class ProcessContractsTest(unittest.TestCase):
    def test_fixed_address_space_is_independent_of_rss(self):
        with patch.object(process_runner.resource, 'setrlimit') as applied:
            process_runner.apply_limits()
        self.assertEqual(applied.call_args_list[0].args, (resource.RLIMIT_AS, (7*1024**3,)*2))
        self.assertEqual(applied.call_args_list[1].args, (resource.RLIMIT_FSIZE, (512*1024**2,)*2))
        self.assertEqual(process_runner.MEMORY_BYTES, 6*1024**3)
        self.assertEqual(process_runner.HEADROOM_BYTES, 2*1024**3)

    def test_wait_observer_records_only_exact_reaps(self):
        usage = SimpleNamespace(ru_utime=1.25, ru_stime=.5, ru_maxrss=42)
        observer = process_runner.WaitObserver()
        with patch.object(os, 'wait4', side_effect=[(12, 0, usage), ChildProcessError()]):
            result = observer.wait4(12, 0)
            with self.assertRaises(ChildProcessError):
                observer.wait4(-1, 0)
        self.assertEqual(result[0], 12)
        self.assertTrue(observer.echild)
        self.assertEqual(observer.records, [{'pid': 12, 'returncode': 0, 'user_cpu_seconds': 1.25,
                                            'system_cpu_seconds': .5, 'peak_rss_KiB': 42}])

    def test_admission_rejects_each_cleanup_failure(self):
        valid = dict(returncode=0, resource_accounting_complete=True, cleanup_verified=True,
                     wait4_echild=True, remaining_owned_pids=[], hard_watchdog_killed=False,
                     interrupted=False, error=None, health_check_error=None, actual_within_allocation=True)
        process_runner.require_clean(valid)
        faults = {'returncode': 1, 'resource_accounting_complete': False, 'cleanup_verified': False,
                  'wait4_echild': False, 'remaining_owned_pids': [12], 'hard_watchdog_killed': True,
                  'interrupted': True, 'error': 'launch failed', 'health_check_error': 'RSS gate',
                  'actual_within_allocation': False}
        for key, value in faults.items():
            with self.subTest(field=key), self.assertRaises(ValueError):
                process_runner.require_clean({**valid, key: value})


if __name__ == '__main__':
    unittest.main()
