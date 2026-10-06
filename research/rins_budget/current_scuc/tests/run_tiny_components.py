"""Explicit, bounded launcher for the existing test-only triangle components.

This is not a production entrypoint and does not relax its instance-family guard.
Executing this module performs the native tests; importing it performs none.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import time

from tests.fixed_triangle import write_source


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--highs', type=Path, required=True)
    parser.add_argument('--runtime-manifest', type=Path)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--suite', choices=('changed-master', 'transition'), default='changed-master')
    args = parser.parse_args(argv)
    started = time.monotonic()
    if not sys.dont_write_bytecode or not __debug__:
        parser.error('Run Python -B with assertions enabled')
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                 'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE'):
        os.environ[name] = '1'
    from current_scuc import binding, process_runner, receipts, runtime, storage_budget
    process_runner.apply_limits()
    args.workdir = args.workdir.absolute()
    admission = receipts.admit_whole(args.workdir.parent)
    work = binding.fresh_directory(args.workdir)
    outcome = dict(schema='current-scuc-tiny-component-test/v1', test_passed=False,
                   candidate_passed=False, production_result=False, work_directory=str(work),
                   suite=args.suite, whole_storage_admission=admission)
    code = 2
    try:
        installed = runtime.discover_runtime(args.highs, args.runtime_manifest)
        source = write_source(work/'fixed-source.json')
        config_path = work/'runtime.config.json'
        cfg = binding.configure(source, installed.manifest_path, config_path)
        os.environ.update(PRIMAL_CACHE_CONFIG=str(config_path),
                          PRIMAL_CACHE_CONFIG_SHA256=binding.sha(config_path),
                          CURRENT_SCUC_RUNTIME_MANIFEST=str(installed.manifest_path))
        tests = Path(__file__).resolve().parent
        worker_name = 'replay_tiny_transition' if args.suite == 'transition' else 'replay_tiny_components'
        worker = tests/(worker_name+'.py')
        source_files = {str(path): binding.sha(path) for path in
                        (Path(__file__).resolve(), tests/'fixed_triangle.py', worker)}
        storage_budget.atomic_json(work/'test-sources.json', source_files, fresh=True)
        command = [cfg['python'], '-B', '-s', '-m', 'tests.'+worker_name,
                   '--out', str(work/'run'), '--worker-source-sha256',
                   source_files[str(worker)], '--fixture-source-sha256',
                   source_files[str(tests/'fixed_triangle.py')]]
        log = work/'tiny-worker.log'
        storage_budget.admit_phase(work, phase='tiny component worker', writes=[
            storage_budget.WriteBound(log, storage_budget.PYTHON_FILE_LIMIT,
                                     'single contained Python worker stdout', '512 MiB inherited RLIMIT_FSIZE')],
            metadata_bytes=storage_budget.METADATA_LIMIT)
        with storage_budget.active_writer_reservations([
            storage_budget.WriteBound(log, storage_budget.PYTHON_FILE_LIMIT,
                                     'single contained Python worker stdout', '512 MiB inherited RLIMIT_FSIZE')]):
            measurement = process_runner.run(command, log, work, 180.)
        storage_budget.atomic_json(work/'tiny-worker-process.json', measurement, fresh=True)
        outcome['process'] = measurement
        process_runner.require_clean(measurement)
        binding.verify(source_files)
        result_path = work/'run/result.json'
        result = binding.read(result_path)
        binding.require(result.get('test_passed') is True
                        and result.get('candidate_passed') is False
                        and result.get('candidate_expected_nonpass_verified') is True
                        and result.get('production_advancement_qualified') is False
                        and result.get('test_outcome') == 'expected_candidate_nonpass_components_passed',
                        'Tiny candidate nonpass or component completion not verified')
        outcome.update(test_passed=True, candidate_passed=False,
                       result_path=str(result_path), result_sha256=binding.sha(result_path),
                       candidate_outcome=result['candidate_outcome'],
                       candidate_expected_nonpass_verified=True,
                       native_assessment_and_proof_admission_verified=True,
                       expected_shared_overflow_MWh=result['expected_shared_overflow_MWh'])
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        outcome.update(error_type=type(error).__name__, error=str(error), test_passed=False)
    finally:
        outcome['full_test_elapsed_seconds'] = time.monotonic()-started
        storage_budget.atomic_json(work/'TEST-RESULT.json', outcome, fresh=True)
        print(json.dumps({'test_passed': outcome['test_passed'], 'candidate_passed': False,
                          'result': str(work/'TEST-RESULT.json')}, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
