"""Run the current projected SCUC candidate from a local supported instance."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import time


def main(argv=None):
    started = time.monotonic()
    from . import process_runner
    process_runner.apply_limits()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='Prepare and run one candidate; no data downloads')
    run.add_argument('--instance', required=True, type=Path, help='UC.jl 0.3 case1354pegase 36-hour JSON or JSON.gz')
    run.add_argument('--highs', required=True, type=Path, help='Official qualified HiGHS 1.15.1 CLI')
    run.add_argument('--workdir', required=True, type=Path, help='Fresh directory outside the installed source package')
    run.add_argument('--runtime-manifest', type=Path, help='Optional explicit native runtime manifest')
    args = parser.parse_args(argv)
    if not sys.dont_write_bytecode or not __debug__:
        parser.error('Run with Python -B and assertions enabled')
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        parser.error('This release supports Linux x86-64 only')
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE'):
        os.environ[key] = '1'
    from . import binding, case, case_binding, preparation, process_runner, receipts, runtime
    work = binding.fresh_directory(args.workdir)
    summary = dict(schema='current-scuc-cli-result/v1', passed=False, result_complete=False,
        work_directory=str(work), production_result=False, performance_comparison_claim=False,
        physical_dc_lower_bound_certified=False, native_executions_started=False)
    exit_code = 2
    try:
        binding.verify_package_source(binding.FREEZE, binding.sha(binding.FREEZE))
        summary['whole_cli_storage_admission'] = receipts.admit_cli(work)
        installed = runtime.discover_runtime(args.highs, args.runtime_manifest)
        manifest_path = installed.manifest_path
        preparation_started = time.monotonic()
        summary['native_executions_started'] = True
        descriptor = preparation.prepare(args.instance, manifest_path, work/'preparation')
        summary['preparation_elapsed_seconds'] = time.monotonic()-preparation_started
        summary['case'] = case_binding.record(descriptor)
        case.bind_case(descriptor)
        cfg = binding.config()
        arm = case.create_arm_manifest(descriptor, binding.FREEZE, work/'candidate-manifest.json')
        reference = case.create_source_reference(binding.FREEZE, work/'source-reference.json')
        command = [cfg['python'], '-B', '-s', '-m', 'current_scuc.phase',
            '--out', str(work/'candidate'), '--source-manifest', str(binding.FREEZE),
            '--source-manifest-sha256', binding.sha(binding.FREEZE),
            '--source-reference', str(reference), '--arm-manifest', str(arm),
            '--arm-manifest-sha256', binding.sha(arm)]
        process_runner.apply_limits()
        receipt = process_runner.run(command, work/'candidate.log', work, 1800.)
        binding.write(work/'candidate-process.json', receipt, fresh=True)
        summary['candidate_process'] = receipt
        process_runner.require_clean(receipt, allowed_returns=(0, 2))
        result_path = work/'candidate/result.json'
        completion_path = work/'candidate/completion.json'
        result = binding.read(result_path)
        completion = binding.read(completion_path)
        binding.require(completion.get('result_sha256') == binding.sha(result_path)
            and completion.get('passed') is result.get('passed') and result.get('result_complete') is True,
            'Candidate result/completion binding failed')
        summary.update(passed=result['passed'], production_result=True,
            candidate_result=case_binding.record(result_path), outcome=result['outcome'],
            candidate_whole_seconds=result['whole_phase_seconds'],
            candidate_process_wall_seconds=receipt['process_wall_seconds'],
            preparation_budget_seconds=600, candidate_budget_seconds=1800,
            full_cli_elapsed_is_authoritative=True, optional_archival_is_external=True)
        exit_code = 0 if result['passed'] else 2
    except (Exception, KeyboardInterrupt) as error:
        summary.update(passed=False, outcome='failed_or_incomplete', error_type=type(error).__name__, error=str(error))
    finally:
        summary.update(result_complete=True, full_cli_elapsed_seconds=time.monotonic()-started)
        binding.write(work/'RESULT.json', summary, fresh=True)
        print(json.dumps(dict(passed=summary['passed'], outcome=summary.get('outcome'),
            result=str(work/'RESULT.json'), full_cli_elapsed_seconds=summary['full_cli_elapsed_seconds']), sort_keys=True))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
