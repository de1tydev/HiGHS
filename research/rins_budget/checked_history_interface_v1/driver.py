"""Two fresh original-MILP processes. Generic functional scope, not SCUC."""
from __future__ import annotations
import argparse
import math
import os
from pathlib import Path
import resource
import shutil
import signal
import time

from common import check_point, expected_model, read_json, read_values, require, sha, write_json, write_values
from history import admit_synthetic, predict
from current_scuc import slot_envelope as envelope
from current_scuc.core.canonical_mps_export import readback


def health(out):
    available = int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))) * 1024
    require(available >= 2 * 1024**3 and shutil.disk_usage(out).free >= 2 * 1024**3, 'Resource headroom failed')
    todo, seen, rss = [os.getpid()], set(), 0
    while todo:
        pid = todo.pop()
        if pid in seen:
            continue
        seen.add(pid)
        todo.extend(envelope.children_of(pid))
        try:
            lines = Path(f'/proc/{pid}/status').read_text().splitlines()
        except FileNotFoundError:
            continue
        rss += sum(int(s.split()[1]) * 1024 for s in lines if s.startswith('VmRSS:'))
    require(rss <= 6 * 1024**3, 'Process-tree RSS cap')


def limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (7 * 1024**3,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2,) * 2)
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, envelope.request_stop)


def run_process(command, out, name, allocation):
    require(allocation > 1., 'No process cleanup reserve')
    health(out)
    receipt = envelope.supervise(command, dict(os.environ), out / (name + '.log'),
                                  timeout=allocation - 1., health_check=lambda: health(out))
    elapsed = receipt['total_slot_elapsed_seconds']
    receipt.update(allocation_seconds=allocation, process_wall_seconds=elapsed,
                   cleanup_verified=receipt['runner_launched'] and receipt['runner_returncode'] is not None
                   and not envelope.children_of(os.getpid()) and not receipt['adopted_checks_killed_and_reaped'])
    write_json(out / (name + '.process.json'), receipt)
    require(receipt['cleanup_verified'] and not receipt['error'] and not receipt['health_check_error']
            and not receipt['interruption'] and elapsed <= allocation, 'Unclean, interrupted or over-budget process')
    return receipt


def run_case(model_path, expected_path, adapter, library, query_path, label_paths, out,
             *, method='consensus', seconds=30., _test_probe_command=None):
    """The private injected command exists solely for deterministic test helpers.

    No CLI flag, input JSON key, environment variable or production path exposes it.
    Every process uses an unchanged MPS; every deadline is this invocation's clock.
    """
    started = time.monotonic()
    require(type(seconds) in (float, int) and math.isfinite(seconds) and 15 <= seconds <= 30, 'First gate permits 15..30 seconds per arm')
    out = Path(out).absolute()
    require(out.parent.is_dir() and not out.exists() and not out.is_symlink(), 'Fresh output directory required')
    out.mkdir()
    paths = [Path(p).resolve() for p in (model_path, expected_path, adapter, library, query_path)]
    model_path, expected_path, adapter, library, query_path = paths
    frozen = {str(p): sha(p) for p in paths}
    result = dict(schema='checked-history-generic-two-process/v1', passed=False, scope='generic_original_milp_only',
                  production_scuc_integrated=False, probe_lower_bound=None, probe_upper_bound=None,
                  final_lower_bound=None, optimality_certified=False, stages=[], calls=[], seconds_ceiling=float(seconds))
    last = started

    def remaining():
        return seconds - (time.monotonic() - started)

    def unchanged():
        require(all(sha(p) == h for p, h in frozen.items()), 'Changed model/query/adapter/runtime')
        require(not envelope.STOP_REASON, 'Cancellation is terminal')

    def mark(name, cap):
        nonlocal last
        now = time.monotonic()
        result['stages'].append(dict(stage=name, actual_seconds=now - last, cap_seconds=cap))
        require(now - last <= cap and remaining() >= 0, 'Stage or whole budget exceeded: ' + name)
        last = now

    def native(stage, point_input, allocation):
        unchanged()
        output, metadata = out / (stage + '.point'), out / (stage + '.native.json')
        native_seconds = min(2., allocation - 2.) if stage == 'probe' else allocation - 3.
        require(native_seconds > 0, 'Insufficient native allocation')
        command = [str(adapter), str(model_path), str(point_input) if point_input else '-', str(output),
                   str(metadata), format(native_seconds, '.17g'), stage]
        if stage == 'probe' and _test_probe_command is not None:
            command = _test_probe_command(output, metadata, command)
        receipt = run_process(command, out, stage, allocation)
        result['calls'].append(dict(stage=stage, process=receipt, model_sha256=frozen[str(model_path)]))
        unchanged()
        if receipt['hard_watchdog_killed']:
            return None, 'timeout'
        meta = read_json(metadata)
        require(meta['mode'] == stage and meta['model_fields_verified'] is True, 'Native model fidelity failed')
        loaded = Path(meta['loaded_library_path']).resolve()
        require(loaded == library and sha(loaded) == frozen[str(library)], 'Native loaded a different library')
        require(meta['options_verified'] is True and meta['options'] == dict(threads=2, parallel='off', random_seed=1, time_limit=native_seconds,
                                      mip_rel_gap=0, mip_abs_gap=0), 'Native options changed')
        result['calls'][-1]['process_id'] = meta['process_id']
        if receipt['runner_returncode'] not in (0, 2):
            return None, 'native_error'
        if meta['outcome'] != 'point' or meta['complete_primal_present'] is not True:
            return None, 'no_point'
        return (output, meta), 'candidate_pending_check'

    def validate(candidate):
        if candidate is None:
            return None
        path, meta = candidate
        try:
            values = read_values(path, expected['col_names'])
            checked = check_point(expected, values)
            require(checked['passed'], 'Complete original matrix check failed')
            for key in ('point_objective', 'solver_reported_objective'):
                number = meta[key]
                require(type(number) in (int, float) and math.isfinite(number), 'Missing native objective diagnostic')
                require(abs(checked['objective_recomputed'] - number) <= max(1e-5, abs(number) * 1e-10), 'Objective readback mismatch')
            return values, checked
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            result.setdefault('point_rejections', []).append(type(exc).__name__ + ': ' + str(exc))
            return None

    try:
        limits()
        expected = expected_model(expected_path)
        require(expected['sense'] == 1 and expected['offset'] == 0, 'First gate is zero-offset minimization')
        require(expected['num_col'] <= 1024 and expected['num_row'] <= 4096, 'First functional gate excludes large models')
        query = read_json(query_path)
        require(query['scope'] == 'synthetic_test' and query['columns'] == expected['col_names'], 'First solve gate uses synthetic checked history only')
        require(query['feature_spec'] == 'two-period-demand-identity/v1' and expected['num_row'] == 3
                and query['feature'] == [float(v) for v in expected['row_lower'][:2]], 'Query features must come from target input, not a solution')
        labels = [admit_synthetic(p) for p in label_paths]
        prediction = predict(query, labels, method=method, k=3)
        result['prediction'] = prediction
        fidelity = readback.verify_expected(expected, model_path, library, out / 'original.readback.log')
        require(fidelity['passed'], 'Original MPS differs from independent expected model')
        write_json(out / 'original.readback.json', fidelity)
        unchanged()
        mark('admission_prediction_readback', 2.)
        start = None
        if prediction['suggestions']:
            suggestion_path = out / 'suggestions.txt'
            with suggestion_path.open('x') as stream:
                for name, value in prediction['suggestions'].items():
                    require(type(value) is int and value in (0, 1), 'Nonliteral proposal')
                    stream.write(f'{name} {value}\n')
            candidate, result['probe_outcome'] = native('probe', suggestion_path, min(5., remaining() - 18.))
            mark('probe_process_and_io', 5.)
            checked = validate(candidate)
            if checked:
                values, _ = checked
                start = out / 'checked-complete.start'
                write_values(start, expected['col_names'], values)
                require(read_values(start, expected['col_names']) == values, 'Start serialization changed values')
                result['transferred_point_sha256'] = sha(start)
            mark('probe_original_matrix_check', 5.)
        else:
            result['probe_outcome'] = 'abstained'
        result['final_start'] = 'complete_original_matrix_checked' if start else 'cold'
        allocation = remaining() - 5.
        require(allocation >= 3., 'Final process reserve exhausted')
        candidate, result['final_outcome'] = native('final', start, allocation)
        mark('ordinary_final_process', allocation)
        checked = validate(candidate)
        require(checked is not None, 'No checked final original-model point')
        _, result['final_original_matrix_check'] = checked
        result['final_checked_objective'] = checked[1]['objective_recomputed']
        unchanged()
        pids = [c['process_id'] for c in result['calls'] if 'process_id' in c]
        require(len(pids) == len(set(pids)), 'Processes were not fresh')
        mark('final_matrix_check', 5.)
        result['passed'] = True
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        result['wall_seconds_before_result_write'] = time.monotonic() - started
        result['ledger_within_ceiling'] = result['wall_seconds_before_result_write'] <= seconds
        result['passed'] = result['passed'] and result['ledger_within_ceiling']
        write_json(out / 'result.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'expected', 'adapter', 'library', 'query', 'out'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--label', action='append', default=[], type=Path)
    p.add_argument('--method', choices=('previous', 'nearest', 'consensus'), default='consensus')
    a = p.parse_args()
    result = run_case(a.model, a.expected, a.adapter, a.library, a.query, a.label, a.out, method=a.method)
    raise SystemExit(0 if result['passed'] else 2)


if __name__ == '__main__':
    main()
