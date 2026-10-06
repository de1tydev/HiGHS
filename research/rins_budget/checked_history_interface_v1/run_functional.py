"""Fixed six-arm generic qualification. Run only after source/build approval."""
from __future__ import annotations
import time
STARTED = time.monotonic()
import argparse
import json
import os
from pathlib import Path
import sys

from common import HERE, read_json, require, write_json
from driver import limits, run_case, run_process
from test_contracts import fixture


def worker(args):
    spec = read_json(args.out / 'cases.json')[args.worker_case]
    injection = None
    if spec['helper']:
        def injection(point, metadata, original):
            return [sys.executable, '-B', '-s', str(HERE / 'test_probe_helper.py'), spec['helper'],
                    str(point), str(metadata), str(args.library.resolve()), original[5]]
    result = run_case(spec['model'], spec['expected'], args.adapter, args.library, spec['query'],
                      spec['labels'], args.out / spec['name'], method=spec['method'], _test_probe_command=injection)
    require(result['passed'] and result['final_checked_objective'] == 13., 'Incorrect independently enumerated endpoint')
    if spec['name'] in ('cold', 'abstention', 'timeout', 'invalid_point'):
        require(result['final_start'] == 'cold', 'Expected clean cold fallback')
    if spec['name'] == 'partial':
        require(0 < len(result['prediction']['suggestions']) < 4, 'Partial consensus path absent')
        require(result['final_start'] == 'complete_original_matrix_checked', 'Checked complete handoff absent')
    if spec['name'] == 'timeout':
        require(result['probe_outcome'] == 'timeout' and result['calls'][0]['process']['hard_watchdog_killed'], 'Expected probe timeout absent')
    if spec['name'] == 'invalid_point':
        require(bool(result.get('point_rejections')), 'Malformed point was not rejected')
    write_json(args.out / (spec['name'] + '.functional.json'), dict(passed=True, actual_case_wall_seconds=time.monotonic() - STARTED,
                independent_enumerated_optimum=13., expected_probe_helper=spec['helper'], production_scuc=False))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter', type=Path, required=True)
    p.add_argument('--library', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--worker-case', type=int, choices=range(6))
    a = p.parse_args()
    limits()
    if a.worker_case is not None:
        worker(a)
        return
    require(a.out.parent.is_dir() and not a.out.exists(), 'Fresh campaign directory required')
    a.out.mkdir()
    records = []
    try:
        pure = run_process([sys.executable, '-B', '-s', str(HERE / 'test_contracts.py')], a.out, 'pure_tests', 60.)
        require(pure['runner_returncode'] == 0 and not pure['hard_watchdog_killed'], 'Pure test gate failed')
        tick = time.monotonic()
        (a.out / 'fixtures').mkdir()
        target = fixture(a.out / 'fixtures', 'target', (3, 4), day=8)
        historical = [fixture(a.out / 'fixtures', f'history{i}', demand, day=i)
                      for i, demand in enumerate(((3, 3), (3, 4), (4, 4)), 1)]
        labels = [str(x['label']) for x in historical]
        cases = []
        for name, selected, method, helper in (
                ('cold', [], 'consensus', None),
                ('partial', labels, 'consensus', None),
                ('infeasible_suggestion', labels[:1], 'nearest', None),
                ('abstention', labels[:2], 'consensus', None),
                ('timeout', labels, 'consensus', 'timeout'),
                ('invalid_point', labels, 'consensus', 'invalid')):
            cases.append(dict(name=name, model=str(target['model']), expected=str(target['expected']),
                              query=str(target['query_path']), labels=selected, method=method, helper=helper))
        write_json(a.out / 'cases.json', cases)
        require(time.monotonic() - tick <= 60., 'Fixture construction allowance exceeded')
        for index, spec in enumerate(cases):
            require(time.monotonic() - STARTED < 330., 'Campaign final reserve reached')
            command = [sys.executable, '-B', '-s', str(Path(__file__).resolve()), '--adapter', str(a.adapter.resolve()),
                       '--library', str(a.library.resolve()), '--out', str(a.out.resolve()), '--worker-case', str(index)]
            receipt = run_process(command, a.out, spec['name'] + '-whole', 30.)
            row = dict(name=spec['name'], process=receipt,
                       passed=receipt['runner_returncode'] == 0 and not receipt['hard_watchdog_killed'])
            records.append(row)
            write_json(a.out / (spec['name'] + '-gate.json'), row)
            require(row['passed'], 'Fixed arm failed; no retry or replacement')
        require(time.monotonic() - STARTED <= 360., 'Whole campaign ceiling')
        write_json(a.out / 'summary.json', dict(passed=True, attempted=records, pure_tests= pure,
                    complete_before_summary_seconds=time.monotonic() - STARTED, ceiling_seconds=360,
                    expected_native_optimizer_calls=8, test_helper_calls=2, production_scuc=False,
                    acceleration_claim=False, generalization_claim=False))
    except Exception as exc:
        write_json(a.out / 'failure.json', dict(passed=False, attempted=records, error=type(exc).__name__ + ': ' + str(exc),
                    elapsed_seconds=time.monotonic() - STARTED))
        raise


if __name__ == '__main__':
    main()
