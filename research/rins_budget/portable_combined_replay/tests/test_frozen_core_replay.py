"""Direct-core wiring/equality tests; every checker and process is mocked."""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

import cold_screen_pair as pair_driver
import contracts
import frozen_core_check as core_check
import frozen_core_replay as core_replay
import model_stage
from portable_runtime import sha
from test_portable_runtime import TemporaryTests


class DirectCoreCheckTests(TemporaryTests):
    def arguments(self, kind='mip'):
        return ['frozen_core_check.py', '--pairs', str(self.root / 'pairs.json'), '--kind', kind,
                '--model', str(self.root / 'master.mps'), '--solution', str(self.root / 'solution.sol'),
                '--result', str(self.root / 'result.json'), '--receipt', str(self.root / 'receipt.json')]

    def test_direct_dispatch_checks_pins_before_and_after_mock_checker(self):
        with patch.object(sys, 'argv', self.arguments()), patch.object(core_check, 'runtime_manifest') as runtime, \
             patch.object(core_check, 'verify') as verify, patch.object(core_check, 'sha', return_value='a' * 64), \
             patch.object(model_stage, 'check', return_value={'passed': True}) as check:
            core_check.main()
        self.assertEqual(runtime.call_count, 2)
        self.assertEqual(verify.call_count, 2)
        expected = {str((core_check.HERE / name).resolve()): digest for name, digest in core_check.FROZEN_CORE.items()}
        self.assertEqual(verify.call_args_list[0].args, (expected,))
        self.assertEqual(verify.call_args_list[1].args, (expected,))
        check.assert_called_once_with(core_check.HERE / 'tiny_triangle.json', 2, str(self.root / 'pairs.json'),
                                      'mip', str(self.root / 'master.mps'), str(self.root / 'solution.sol'))
        receipt = json.loads((self.root / 'receipt.json').read_text())
        self.assertTrue(receipt['passed'])
        self.assertEqual(receipt['excluded_result_fields'], [])

    def test_changed_historical_pin_prevents_checker_dispatch(self):
        with patch.object(sys, 'argv', self.arguments()), patch.object(core_check, 'runtime_manifest'), \
             patch.object(core_check, 'verify', side_effect=contracts.ContractError('changed historical source')), \
             patch.object(model_stage, 'check') as check:
            with self.assertRaises(contracts.ContractError): core_check.main()
        check.assert_not_called()
        self.assertFalse((self.root / 'result.json').exists())

    def test_invalid_kind_prevents_checker_dispatch(self):
        with patch.object(sys, 'argv', self.arguments('other')), patch.object(core_check, 'runtime_manifest') as runtime, \
             patch.object(model_stage, 'check') as check:
            with self.assertRaises(contracts.ContractError): core_check.main()
        runtime.assert_not_called(); check.assert_not_called()


class FrozenReplayTests(TemporaryTests):
    def setUp(self):
        super().setUp()
        self.here = self.root / 'driver'; self.here.mkdir()
        for name in ('tiny_triangle.json', 'REVIEW_MANIFEST.json', 'CAMPAIGN_PLAN.json'):
            (self.here / name).write_text('{}')
        self.tiny = self.root / 'tiny'; self.tiny.mkdir()
        (self.tiny / 'replay').mkdir()
        self.witness = {'full_source_primal_pass': True, 'checked_upper': 660.0,
                        'new_pairs': [], 'matrix_check': {'passed': True, 'linear_objective': 660.0}}
        self.pair = {'tiny_pipeline_verified': True, 'results': {}}
        for arm, kinds in (('A', ('mip', 'mip')), ('B', ('lp', 'mip'))):
            trace = []
            for index, kind in enumerate(kinds, 1):
                stage = self.tiny / arm / ('stage_' + str(index)); stage.mkdir(parents=True)
                for name in ('pairs.json', 'master.mps', 'solution.sol'): (stage / name).write_text('fake witness')
                trace.append({'stage_directory': str(stage), 'kind': kind})
                for selector in ('A', 'B'):
                    (self.tiny / 'replay' / (f'{arm}_{index:02d}_{kind}_{selector}.json')).write_text(json.dumps(self.witness))
            self.pair['results'][arm] = {'state': {'trace': trace}}
        self.save_pair()
        (self.tiny / 'replay/RESULT.json').write_text('{"passed":true}')
        self.here_patch = patch.object(core_replay, 'HERE', self.here)
        self.here_patch.start(); self.addCleanup(self.here_patch.stop)

    def save_pair(self):
        (self.tiny / 'pair.json').write_text(json.dumps(self.pair))

    def execute(self, command, log, env, timeout, *, result=None, receipt_patch=None, process_patch=None):
        self.assertEqual(command[1:3], ['-B', '-s'])
        self.assertEqual(command[3], str(self.here / 'frozen_core_check.py'))
        self.assertEqual(timeout, 20.0)
        output = Path(command[command.index('--result') + 1])
        receipt = Path(command[command.index('--receipt') + 1])
        output.write_text(json.dumps(self.witness if result is None else result))
        receipt.write_text(json.dumps({'passed': True, 'result_sha256': sha(output), **(receipt_patch or {})}))
        return {'returncode': 0, 'hard_watchdog_killed': False, 'process_wall_seconds': 0.125, **(process_patch or {})}

    def run_mock(self, **options):
        with patch.object(pair_driver, 'execute', side_effect=lambda *args: self.execute(*args, **options)) as execute, \
             patch.object(pair_driver, 'environment', return_value={'PATH': '/mock'}):
            passed = core_replay.replay(self.tiny)
        return passed, execute

    def test_all_witnesses_compare_every_field_with_both_selectors(self):
        passed, execute = self.run_mock()
        self.assertTrue(passed); self.assertEqual(execute.call_count, 4)
        report = json.loads((self.tiny / 'frozen_core_replay/RESULT.json').read_text())
        self.assertEqual(report['witness_count'], 4)
        self.assertTrue(all(item['equal'] for item in report['checks']))
        self.assertTrue(all(item['excluded_fields'] == [] for item in report['checks']))

    def test_direct_core_field_difference_rejects_without_normalization(self):
        changed = copy.deepcopy(self.witness); changed['matrix_check']['linear_objective'] = 660.0000000001
        passed, execute = self.run_mock(result=changed)
        self.assertFalse(passed); self.assertEqual(execute.call_count, 1)

    def test_selector_field_difference_rejects(self):
        changed = copy.deepcopy(self.witness); changed['new_pairs'] = [[1, 2]]
        (self.tiny / 'replay/A_01_mip_B.json').write_text(json.dumps(changed))
        passed, execute = self.run_mock()
        self.assertFalse(passed); self.assertEqual(execute.call_count, 1)

    def test_numerically_equal_integer_float_substitution_rejected(self):
        changed = copy.deepcopy(self.witness); changed['checked_upper'] = 660
        self.assertEqual(changed, self.witness)
        passed, execute = self.run_mock(result=changed)
        self.assertFalse(passed); self.assertEqual(execute.call_count, 1)

    def test_numerically_equal_boolean_integer_substitution_rejected(self):
        changed = copy.deepcopy(self.witness); changed['full_source_primal_pass'] = 1
        self.assertEqual(changed, self.witness)
        passed, execute = self.run_mock(result=changed)
        self.assertFalse(passed); self.assertEqual(execute.call_count, 1)

    def test_receipt_digest_must_bind_direct_result(self):
        passed, execute = self.run_mock(receipt_patch={'result_sha256': '0' * 64})
        self.assertFalse(passed); self.assertEqual(execute.call_count, 1)

    def test_failed_receipt_rejects_equal_results(self):
        passed, execute = self.run_mock(receipt_patch={'passed': False})
        self.assertFalse(passed); self.assertEqual(execute.call_count, 1)

    def test_timeout_rejects_equal_results(self):
        passed, execute = self.run_mock(process_patch={'hard_watchdog_killed': True})
        self.assertFalse(passed); self.assertEqual(execute.call_count, 1)

    def test_failed_tiny_gate_refuses_any_process(self):
        self.pair['tiny_pipeline_verified'] = False; self.save_pair()
        with patch.object(pair_driver, 'execute') as execute:
            with self.assertRaises(ValueError): core_replay.replay(self.tiny)
        execute.assert_not_called()

    def test_failed_selector_equality_refuses_any_process(self):
        (self.tiny / 'replay/RESULT.json').write_text('{"passed":false}')
        with patch.object(pair_driver, 'execute') as execute:
            with self.assertRaises(ValueError): core_replay.replay(self.tiny)
        execute.assert_not_called()

    def test_empty_witnesses_fail_closed(self):
        for arm in ('A', 'B'): self.pair['results'][arm]['state']['trace'] = []
        self.save_pair()
        with patch.object(pair_driver, 'execute') as execute:
            try: passed = core_replay.replay(self.tiny)
            except ValueError: passed = False
        self.assertFalse(passed)
        execute.assert_not_called()
