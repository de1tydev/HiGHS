"""Existing pure schedule/QA regressions, mechanically rebound to this package."""
import copy
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from current_scuc import adaptive, common, options, phase, seed

class PolicyTests(unittest.TestCase):
    def test_fixed_role_options_cold_first_and_later_unlimited(self):
        self.assertEqual([options.role_for_call(k) for k in (1,2,3)],['discovery','proof','proof'])
        self.assertEqual(options.option_text('proof'), options.PROOF)
        self.assertEqual(options.option_text('discovery'),options.PROOF+'mip_max_improving_sols = 1\n')
        for role,limit in [('discovery',1),('proof',2147483647)]:
            e=options.expected_options(role,120.,start=None)
            self.assertEqual(e['Int']['mip_max_improving_sols'],limit)
            self.assertEqual(e['String']['read_solution_file'],'')
            self.assertEqual(e['String']['log_file'],'')
        with self.assertRaises(ValueError):options.expected_options('discovery',120.,start='/old/point.sol')
        for call in (0,4,True):
            with self.assertRaises(ValueError):options.role_for_call(call)


    def test_actual_discovery_saving_only_reaches_final_allocation(self):
        l=phase.Ledger();l.debit('seed',180.,{'process_wall_seconds':60.})
        self.assertEqual(l.allocation('mip',1,1700.),180.)
        l.debit('mip',180.,{'process_wall_seconds':13.25})
        l.debit('carry',30.,{'process_wall_seconds':9.})
        self.assertEqual(l.allocation('mip',2,1500.),180.)
        l.debit('mip',180.,{'process_wall_seconds':121.})
        l.debit('carry',30.,{'process_wall_seconds':10.})
        self.assertEqual(l.allocation('mip',3,1300.),386.75)
        self.assertEqual(l.spent,213.25)
        self.assertFalse(l.debit('mip',386.75,{'process_wall_seconds':387.}))
        self.assertEqual(l.spent,600.25)
        self.assertEqual((phase.WHOLE_CAP,phase.SOLVER_CAP,phase.PROCESS_RESERVE),(1800.,600.,60.))


    def test_native_guard_evidence_survives_exception_without_real_limits(self):
        @contextmanager
        def fake_guard():
            record=dict(before=[512*1024**2]*2,effective=[64*1024**2,512*1024**2],restored=False)
            try:yield record
            finally:record.update(restored=True,after=[512*1024**2]*2)
        before=len(common.NATIVE_LIMIT_RECORDS)
        with patch.object(common,'native_limits',return_value=SimpleNamespace(native_output_guard=fake_guard)):
            with self.assertRaisesRegex(ValueError,'synthetic'):
                with common.native_call_guard('pure synthetic failure'):
                    raise ValueError('synthetic')
        record=common.NATIVE_LIMIT_RECORDS.pop()
        self.assertEqual(len(common.NATIVE_LIMIT_RECORDS),before)
        self.assertTrue(record['restored']);self.assertEqual(record['error_type'],'ValueError')
        self.assertEqual(record['action'],'pure synthetic failure')


    def test_pinned_lp_policy_and_exact_deadlines(self):
        policy=adaptive.lp_policy()
        self.assertEqual((policy.CERTIFICATE_CALL_CAP,policy.CERTIFICATE_TOTAL_CAP,policy.FINAL_RESERVE),(20.,120.,10.))
        self.assertIsNotNone(adaptive.native().PersistentLP)


    def test_only_stationarity_threshold_can_await_exact_seed_certificate(self):
        policy=adaptive.lp_policy()
        expected={'num_col':2,'num_row':1}
        solution=dict(version=3,run_status=0,model_status=7,col_value=np.zeros(2),col_dual=np.zeros(2),
            row_value=np.zeros(1),row_dual=np.zeros(1))
        quality=dict(passed=False,failures=[policy.STATIONARITY_FAILURE],stationarity={'max':3.519913479976822e-5})
        self.assertTrue(policy.projected_quality_gate(quality,expected,solution,3))
        for mutate in ('other_failure','nonfinite','native_status','stale_version','missing_dual','inconsistent_pass'):
            q=copy.deepcopy(quality);point=copy.deepcopy(solution)
            if mutate=='other_failure':q['failures'].append('primal row violation')
            elif mutate=='nonfinite':q['stationarity']['max']=float('nan')
            elif mutate=='native_status':point['model_status']=13
            elif mutate=='stale_version':point['version']=2
            elif mutate=='missing_dual':point['row_dual']=np.asarray([])
            else:q['passed']=True
            with self.subTest(mutate=mutate):self.assertFalse(policy.projected_quality_gate(q,expected,point,3))


    def test_policy_clock_and_terminal_contracts_preserved(self):
        self.assertEqual((seed.SEED_PROCESS_CAP,seed.NATIVE_TOTAL_CAP,seed.FINAL_RESERVE),(180.,60.,10.))
        ledger=phase.Ledger();self.assertEqual(ledger.allocation('seed',0,1800.),180.)
        ledger.debit('seed',180.,{'process_wall_seconds':60.})
        ledger.debit('mip',180.,{'process_wall_seconds':120.})
        self.assertEqual(ledger.allocation('carry',2,1200.),30.)
        ledger.debit('carry',30.,{'process_wall_seconds':30.})
        ledger.debit('mip',180.,{'process_wall_seconds':180.})
        self.assertEqual(ledger.allocation('carry',3,900.),30.)
        ledger.debit('carry',30.,{'process_wall_seconds':30.})
        self.assertEqual(ledger.allocation('mip',3,900.),180.)
        self.assertFalse(ledger.debit('mip',180.,{'process_wall_seconds':180.01}))


