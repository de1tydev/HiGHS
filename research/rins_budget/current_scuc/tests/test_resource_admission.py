"""Fixed resource admission and early CLI boundaries; no numerical execution."""
import inspect
import io
import json
import os
from pathlib import Path
import resource
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from current_scuc import __main__ as cli
from current_scuc import binding, preparation, process_runner, receipts, runtime
from current_scuc import storage_budget as budget


class ResourceAdmissionTests(unittest.TestCase):
    def filesystem(self, available, block=4096):
        return dict(path='/reviewed', device=1, block_bytes=block, available_bytes=available)

    def test_fixed_thresholds_and_no_override_parameter(self):
        self.assertEqual(receipts.WHOLE_STORAGE_REQUIRED, 11*1024**3)
        self.assertEqual(receipts.CLI_STORAGE_REQUIRED, 16*1024**3)
        self.assertEqual(budget.FREE_FLOOR, 2*1024**3)
        for gate in (receipts.admit_whole, receipts.admit_cli):
            self.assertEqual(list(inspect.signature(gate).parameters), ['run_parent'])
        protocol=json.loads((Path(receipts.__file__).parent/'PROTOCOL.json').read_text())
        self.assertEqual(protocol['whole_storage_required_bytes'], receipts.WHOLE_STORAGE_REQUIRED)
        self.assertEqual(protocol['cli_storage_required_bytes'], receipts.CLI_STORAGE_REQUIRED)
        self.assertEqual({k:protocol[k] for k in ('preparation_seconds','preparation_worker_seconds',
            'candidate_seconds','solver_process_seconds')}, dict(preparation_seconds=600,
            preparation_worker_seconds=300,candidate_seconds=1800,solver_process_seconds=600))

    def test_candidate_boundary_preserves_active_stdout_reservation(self):
        threshold=receipts.WHOLE_STORAGE_REQUIRED
        writer=budget.WriteBound('/nonexistent-reviewed-stdout',budget.PYTHON_FILE_LIMIT,
            'phase stdout','existing process file limit')
        with budget.active_writer_reservations([writer]):
            with patch.object(budget,'filesystem',return_value=self.filesystem(threshold-1)):
                with self.assertRaises(budget.StorageAdmissionError):receipts.admit_whole('/reviewed')
            with patch.object(budget,'filesystem',return_value=self.filesystem(threshold)):
                result=receipts.admit_whole('/reviewed')
        self.assertTrue(result['admitted'])
        self.assertEqual(result['required_available_bytes'],threshold)
        self.assertEqual(result['absolute_launch_threshold_bytes'],threshold)
        self.assertEqual(result['active_writer_remaining_bytes'],budget.PYTHON_FILE_LIMIT)

    def test_cli_boundary_and_filesystem_are_checked_before_phase_reservation(self):
        threshold=receipts.CLI_STORAGE_REQUIRED
        for available,block in [(threshold-1,4096),(threshold,8192)]:
            with self.subTest(available=available,block=block), \
                    patch.object(budget,'filesystem',return_value=self.filesystem(available,block)), \
                    patch.object(budget,'require_free') as phase:
                with self.assertRaises((ValueError,budget.StorageAdmissionError)):receipts.admit_cli('/reviewed')
                phase.assert_not_called()
        with patch.object(budget,'filesystem',return_value=self.filesystem(threshold)):
            result=receipts.admit_cli('/reviewed')
        self.assertEqual(result['required_available_bytes'],threshold)
        self.assertEqual(result['absolute_launch_threshold_bytes'],threshold)

    def test_second_filesystem_observation_can_fail_closed(self):
        threshold=receipts.CLI_STORAGE_REQUIRED
        with patch.object(budget,'filesystem',side_effect=[self.filesystem(threshold),self.filesystem(threshold-1)]):
            with self.assertRaises(budget.StorageAdmissionError):receipts.admit_cli('/reviewed')

    def test_cli_retains_additional_active_writer_reservations(self):
        threshold=receipts.CLI_STORAGE_REQUIRED
        writer=budget.WriteBound('/nonexistent-reviewed-extra',4096,'extra bounded output','byte cap')
        with budget.active_writer_reservations([writer]), \
                patch.object(budget,'filesystem',return_value=self.filesystem(threshold)):
            with self.assertRaises(budget.StorageAdmissionError):receipts.admit_cli('/reviewed')

    def test_as_and_fsize_bad_readbacks_reject(self):
        expected={resource.RLIMIT_CORE:(0,0),resource.RLIMIT_AS:(7*1024**3,)*2,
            resource.RLIMIT_FSIZE:(512*1024**2,)*2}
        for limit in (resource.RLIMIT_AS,resource.RLIMIT_FSIZE):
            with self.subTest(limit=limit), patch.object(resource,'setrlimit'), \
                    patch.object(resource,'getrlimit',side_effect={**expected,limit:(1,1)}.__getitem__):
                with self.assertRaises(ValueError):process_runner.apply_limits()

    def test_cli_limit_failure_precedes_argument_parsing_and_output(self):
        with patch.object(process_runner,'apply_limits',side_effect=ValueError('guard failure')), \
                patch.object(cli.argparse,'ArgumentParser') as parser, \
                patch.object(binding,'fresh_directory') as fresh:
            with self.assertRaisesRegex(ValueError,'guard failure'):cli.main(['run'])
        parser.assert_not_called();fresh.assert_not_called()

    def exercise_cli(self, gate_error=None):
        events=[]; summaries=[]
        def event(name, value=None, error=None):
            def call(*args,**kwargs):
                events.append(name)
                if error:raise error
                return value
            return call
        def write(path,value,**kwargs):summaries.append(dict(value))
        with patch.dict(os.environ,{},clear=False), \
                patch.object(process_runner,'apply_limits',side_effect=event('limits')), \
                patch.object(binding,'fresh_directory',side_effect=event('fresh',Path('/reviewed'))), \
                patch.object(binding,'verify_package_source',side_effect=event('source')), \
                patch.object(receipts,'admit_cli',side_effect=event('storage',{'admitted':True},gate_error)), \
                patch.object(runtime,'discover_runtime',side_effect=event('runtime',SimpleNamespace(manifest_path=Path('/manifest')))), \
                patch.object(preparation,'prepare',side_effect=event('preparation',error=RuntimeError('stop at preparation boundary'))), \
                patch.object(binding,'write',side_effect=write), patch('sys.stdout',new=io.StringIO()):
            result=cli.main(['run','--instance','/input','--highs','/highs','--workdir','/reviewed'])
        self.assertEqual(result,2)
        self.assertEqual(len(summaries),1)
        return events,summaries[0]

    def test_cli_storage_failure_blocks_runtime_and_preparation(self):
        events,result=self.exercise_cli(budget.StorageAdmissionError('gate failure'))
        self.assertEqual(events,['limits','fresh','source','storage'])
        self.assertFalse(result['native_executions_started'])
        self.assertFalse(result['production_result'])
        self.assertFalse(result['passed'])
        self.assertTrue(result['result_complete'])

    def test_cli_gate_pass_precedes_runtime_and_preparation(self):
        events,result=self.exercise_cli()
        self.assertEqual(events,['limits','fresh','source','storage','runtime','preparation'])
        self.assertEqual(result['whole_cli_storage_admission'],{'admitted':True})
        self.assertFalse(result['production_result'])
        self.assertFalse(result['passed'])


if __name__=='__main__':unittest.main()
