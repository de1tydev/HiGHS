"""Pure seam checks against the separately staged, sealed overlay package.

Stage first; then: PYTHONPATH=STAGED_PARENT python -B -s test_seams.py
No native solver is loaded or launched; these are synthetic protocol fixtures.
"""
import copy
import itertools
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from current_scuc import carry, common, history_scuc as history, phase, receipts


class ProjectedHistorySeams(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.run = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.rd = self.run / 'mip-01'
        self.rd.mkdir()
        self.identity = {}
        for key, name in [('model', 'master.mps'), ('expected', 'expected.json'),
                          ('api_report', 'matrix-api.json'), ('row_sidecar', 'rows.json')]:
            path = self.rd / name
            path.write_text(name)
            self.identity.update({key + '_path': str(path), key + '_sha256': history.b.sha(path)})
        for name in ('adapter', 'library'):
            (self.run / name).write_text('synthetic ' + name)
        self.plan = {'adapter': history.record(self.run / 'adapter'), 'profile': dict(history.PRODUCTION_PROFILE)}
        self.cfg = {'python': '/unused/python', 'library': str(self.run / 'library')}
        self.meta = dict(mode='probe', outcome='point', run_api_status=0, native_model_status=7,
            complete_primal_present=True, model_fields_verified=True, options_verified=True,
            options=history._options(), loaded_library_path=self.cfg['library'],
            point_objective=10., solver_reported_objective=10.)
        self.receipt = dict(returncode=0, resource_accounting_complete=True, cleanup_verified=True,
            wait4_echild=True, remaining_owned_pids=[], hard_watchdog_killed=False, interrupted=False,
            error=None, health_check_error=None, actual_within_allocation=True,
            runner_launched=True, process_wall_seconds=3.)
        self.state = dict(trace=[], carry_preparations=[], cut_batches=2)
        self.ledger = phase.Ledger()
        self.master = SimpleNamespace(check_integer_values=Mock(return_value=dict(
            passed=True, point_rounded=False, linear_objective=10., x=[1.])))
        self.proposal = {'mapped_current_commitments': [('u', 0, 0, 1)]}
        for owner, name, value in [(history, 'ADAPTER_SHA', self.plan['adapter']['sha256'])]:
            self.stack.enter_context(patch.object(owner, name, value))
        self.stack.enter_context(patch.object(history.b, 'config', return_value=self.cfg))
        self.stack.enter_context(patch.object(history, 'load_plan', return_value=(self.plan, 'a' * 64)))
        self.stack.enter_context(patch.object(history, 'propose', return_value=self.proposal))
        self.stack.enter_context(patch.object(history.time, 'monotonic', side_effect=itertools.count(100)))
        self.stack.enter_context(patch.object(common, 'storage', return_value=SimpleNamespace(WriteBound=Mock())))
        self.stack.enter_context(patch.object(common, 'start_output_phase'))
        self.launch = self.stack.enter_context(patch.object(history.process, 'run', side_effect=self.fake_run))
        phase.load_history_plan(self.state,self.ledger)
        self.assertEqual(self.ledger.calls,[])
        self.assertEqual(self.ledger.auxiliary[0]['stage'],'history_admission')
        self.ledger.debit('seed', 180., {'process_wall_seconds': 10.})

    def fake_run(self, command, log, out, allocation):
        log.write_text('synthetic API probe\n')
        (log.parent / 'api.json').write_text(json.dumps(self.meta))
        (log.parent / 'complete.point').write_text('u 1\n')
        return dict(self.receipt, command=command)

    def attempt(self):
        return phase.charged_history_attempt(self.state,self.ledger,lambda:
            history.attempt(self.plan, 'a' * 64, self.cfg, {}, {},
                {'identity': self.identity, 'expected': {}}, self.state, self.ledger,
                self.run, 1800., master=self.master))

    def schedule(self, role):
        self.state['ledger'] = self.ledger.record()
        evidence = dict(source_role=role, installed_cut_prefix=[{'source': 'seed'}])
        with patch.object(carry, 'transition_evidence', return_value=evidence):
            result = carry.schedule_transition(self.state, evidence['installed_cut_prefix'],
                carry_allocation=30., proof_allocation=180.)
            self.assertIs(carry.validate_transition(self.state, 2, stage='scheduled'), result)
        return result

    def accept(self):
        candidate = self.attempt()
        self.state['trace'].append(candidate['row'])
        with patch.object(phase.time, 'monotonic', return_value=candidate['check_started'] + 4.):
            self.assertEqual(phase.evaluate_history(candidate, lambda deadline: ('batch', deadline),
                self.ledger), ('batch', candidate['check_deadline']))
        return candidate['row']

    def test_accepted_history_is_charged_once_and_carries_to_proof_two(self):
        row = self.accept()
        logical = self.ledger.calls[1]
        probe = self.ledger.auxiliary[logical['charged_via_auxiliary']]
        self.assertEqual((logical['actual'], logical['optimizer_process_wall_seconds']), (0., 3.))
        self.assertEqual((probe['logical_call'], probe['actual']), (1, row['process']['process_wall_seconds']))
        self.assertEqual(self.ledger.spent, sum(r['actual'] for r in self.ledger.calls + self.ledger.auxiliary))
        self.assertEqual(self.ledger.actual_integer_process_count, 1)
        before=self.ledger.spent
        self.assertEqual(phase.charged_parent_history_check(self.state,self.ledger,lambda:'bound'),'bound')
        self.assertGreater(self.ledger.spent,before)
        self.assertTrue(self.schedule('history_probe')['consumed'])
        self.assertEqual(self.ledger.allocation('carry', 2, 1200.), 30.)
        self.ledger.debit('carry', 30., {'process_wall_seconds': 2.})
        self.assertEqual(self.ledger.allocation('mip', 2, 1200.), 180.)
        self.ledger.debit('mip', 180., {'process_wall_seconds': 5.})
        self.assertEqual(self.ledger.actual_integer_process_count, 2)

    def test_rejected_launched_probe_is_outside_trace_and_caps_cold_plus_proof(self):
        self.meta.update(outcome='no_point', complete_primal_present=False)
        self.assertIsNone(self.attempt())
        self.assertEqual(self.state['trace'], [])
        self.assertEqual([r['stage'] for r in self.ledger.calls], ['seed'])
        self.assertEqual(self.ledger.logical_call_limit, 2)
        probe = next(row for row in self.ledger.auxiliary if row['stage']=='history_probe')
        self.assertEqual(probe['classification'], 'rejected_auxiliary_attempt')
        self.assertNotIn('pending_check_started',self.state['history'])
        self.ledger.debit('mip', 180., {'process_wall_seconds': 5.})
        self.state['trace'].append(dict(call=1, role='discovery'))
        self.schedule('discovery')
        self.ledger.debit('carry', 30., {'process_wall_seconds': 2.})
        self.ledger.debit('mip', 180., {'process_wall_seconds': 5.})
        self.assertEqual(self.ledger.actual_integer_process_count, 3)
        self.assertEqual(self.ledger.allocation('mip', 3, 1200.), 0.)

    def test_abstention_preserves_three_logical_calls(self):
        self.proposal['mapped_current_commitments'] = []
        self.assertIsNone(self.attempt())
        self.launch.assert_not_called()
        self.assertEqual((self.ledger.logical_call_limit, self.ledger.actual_integer_process_count), (3, 0))
        self.assertEqual(self.state['trace'], [])

    def test_transition_requires_every_auxiliary_wall_in_sum(self):
        self.accept()
        baseline = self.ledger.record()
        evidence = dict(source_role='history_probe', installed_cut_prefix=[{'source': 'seed'}])
        for auxiliary in baseline['auxiliary']:
            with self.subTest(stage=auxiliary['stage']):
                ledger = copy.deepcopy(baseline)
                ledger['solver_process_wall_seconds'] -= auxiliary['actual']
                ledger['remaining'] += auxiliary['actual']
                self.state['ledger'] = ledger
                with patch.object(carry, 'transition_evidence', return_value=evidence):
                    with self.assertRaisesRegex(ValueError, 'auxiliary wall debit'):
                        carry.schedule_transition(self.state, evidence['installed_cut_prefix'],
                            carry_allocation=30., proof_allocation=180.)
                self.assertNotIn('discovery_proof_transition', self.state)

    def test_cancelled_probe_is_terminal(self):
        self.receipt['interrupted'] = True
        with self.assertRaisesRegex(ValueError, 'Abnormal or uncontained'):
            self.attempt()
        self.assertEqual(self.launch.call_count, 1)
        self.assertEqual(self.ledger.actual_integer_process_count, 1)
        self.assertEqual(self.state['trace'], [])

    def test_integrity_metadata_failure_is_terminal(self):
        self.meta['options_verified'] = False
        with self.assertRaisesRegex(ValueError, 'identity/options failed'):
            self.attempt()
        self.assertEqual(self.launch.call_count, 1)
        self.assertEqual(self.state['trace'], [])
        self.assertNotIn('classification', self.ledger.auxiliary[-1])

    def test_mutating_evaluation_exception_propagates_and_remains_charged(self):
        sentinel = []
        failure = RuntimeError('full oracle failed after mutation')
        candidate = dict(check_started=100., check_deadline=160.)
        def evaluator(deadline):
            sentinel.append(deadline)
            raise failure
        before=self.ledger.spent
        with patch.object(phase.time, 'monotonic', return_value=107.):
            with self.assertRaises(RuntimeError) as caught:
                phase.evaluate_history(candidate, evaluator, self.ledger)
        self.assertIs(caught.exception, failure)
        self.assertEqual(sentinel, [160.])
        self.assertEqual(self.ledger.spent, before+7.)
        self.assertEqual(self.ledger.auxiliary[-1]['stage'], 'history_check')
        self.launch.assert_not_called()

    def test_malformed_point_is_terminal(self):
        def malformed(*args):
            result=self.fake_run(*args)
            (args[1].parent/'complete.point').write_text('u 1\nu 0\n')
            return result
        self.launch.side_effect=malformed
        with self.assertRaisesRegex(ValueError,'Malformed historical complete point'):
            self.attempt()
        self.assertEqual(self.state['trace'],[])
        self.assertEqual(self.ledger.logical_call_limit,3)

    def test_missing_objective_metadata_is_terminal(self):
        self.meta.pop('point_objective')
        with self.assertRaises(KeyError):self.attempt()
        self.assertEqual(self.state['trace'],[])
        self.assertEqual(self.ledger.logical_call_limit,3)

    def test_objective_disagreement_is_terminal(self):
        self.meta['point_objective']=11.
        with self.assertRaisesRegex(ValueError,'Historical objective mismatch'):self.attempt()
        self.assertEqual(self.state['trace'],[])
        self.assertEqual(self.ledger.logical_call_limit,3)

    def test_checker_exception_is_terminal(self):
        self.master.check_integer_values.side_effect=ValueError('checker integrity fault')
        with self.assertRaisesRegex(ValueError,'checker integrity fault'):self.attempt()
        self.assertEqual(self.state['trace'],[])
        self.assertEqual(self.ledger.logical_call_limit,3)

    def test_explicit_numerical_infeasibility_can_fall_back(self):
        self.master.check_integer_values.return_value=dict(passed=False,linear_objective=10.,
            failures=['independent row infeasibility'],point_rounded=False,x=[1.])
        self.assertIsNone(self.attempt())
        self.assertEqual(self.state['trace'],[])
        self.assertEqual(self.ledger.logical_call_limit,2)
        self.assertEqual(self.state['history']['outcome'],'projected_point_rejected_cold_fallback')

    def test_canonical_checked_row_binds_api_artifacts_without_cli_report(self):
        row = self.accept()
        row.update(master_quality=dict(passed=True), evaluation={key: {} for key in (
            'adaptive_support_artifact', 'stored_lift_artifact', 'oracle_artifact',
            'full_source_quality_artifact', 'source_quality_artifact')})
        self.assertNotIn('report', row)
        self.state.update(run_directory=str(self.run), source_manifest_sha256='a' * 64, solver_random_seed=1)
        snapshot, receipt_path = self.run / 'snapshot.json', self.run / 'receipt.json'
        snapshot.write_text(json.dumps(self.state))
        records = [dict(path=str(p), role='state_snapshot' if p == snapshot else 'artifact',
            sha256=history.b.sha(p)) for p in [snapshot, *self.rd.rglob('*')] if p.is_file()]
        receipt = dict(point_id='mip-01', stage_kind='post_full_check', stage_state='validated',
            stage_id='stage', nonce='nonce', content_sha256='b' * 64)
        receipt_path.write_text(json.dumps(dict(whole_deadline_monotonic=1800.)))
        verified = dict(receipt=receipt, manifest={'artifacts': records},
            metadata_files_sha256={str(receipt_path): history.b.sha(receipt_path)})
        with patch.object(receipts, 'verify_receipt', return_value=verified):
            binding = receipts.bind_checked_stage(receipt_path, self.run, 1, 'a' * 64, row)
            for key in ('proposal', 'suggestions', 'request', 'metadata', 'point'):
                artifact = row['api_evidence'][key]
                self.assertEqual(binding['checked_point_files_sha256'][artifact['path']], artifact['sha256'])
            changed = copy.deepcopy(row)
            changed['api_evidence']['point']['sha256'] = 'f' * 64
            with self.assertRaisesRegex(ValueError, 'selected point differs'):
                receipts.bind_checked_stage(receipt_path, self.run, 1, 'a' * 64, changed)
            Path(row['api_evidence']['metadata']['path']).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                receipts.bind_checked_stage(receipt_path, self.run, 1, 'a' * 64, row)


if __name__ == '__main__':
    unittest.main()
