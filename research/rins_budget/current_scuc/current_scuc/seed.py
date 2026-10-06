#!/usr/bin/env python3
"""Exactly two fresh LP solves; the second full cut batch is retained for MIP."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import time
START = time.monotonic()
import argparse
from pathlib import Path
import sys
from current_scuc.common import helpers, require, finite, verify_manifest, prepare, evaluate_point, module, GuardedLP, storage, start_output_phase, bounded_write

SEED_PROCESS_CAP = 180.
NATIVE_TOTAL_CAP = 60.
FINAL_RESERVE = 10.


def run_seed(lp, oracle, original, metadata, out, deadline, *, model, projection, qa, certified_lower=None, record=None):
    f = helpers()
    import current_scuc.adaptive as adaptive; import current_scuc.common as common
    policy=adaptive.lp_policy()
    state=adaptive.activation(metadata)
    require(state.active==() and state.evaluations==state.admitted==0,'Fresh empty adaptive seed required')
    runtime=common.ADAPTIVE_RUNTIME=adaptive.Runtime(oracle,metadata,out)
    runtime.expected=lp.expected
    if certified_lower is None:
        certified_lower = module('_integer_exact_lower', f.ROOT/'science/certified_lower.py')
    require(lp.expected['sense'] == 1 and lp.expected['offset'] == 0, 'Wrong seed objective')
    require(not any(lp.expected['integrality']), 'Seed must be continuous')
    initial = dict(schema='adaptive-line-integer-seed/v1', passed=False, result_complete=False,
        calls=0, cut_batches=0, retained_batches=0, oracle_evaluations=0, full_scope_scans=0,
        cut_nnz=0, balance_nnz=int(metadata['balance_nonzeros']), rounds=[], exact_lp_lowers=[],
        actual_stage_costs={}, certificate_attempts=0, full_scope=metadata['full_scope'],
        physical_dc_lower_bound_certified=False, historical_inputs_used=False,
        hard_zero_subset=metadata['hard_zero_subset'], lower_domain=metadata['hard_zero_subset']['lower_domain'],
        projected_quality_policy='pinned adaptive LP stationarity-only substitution by mandatory exact current-matrix certificate',
        exact_lower_attempts_max=2)
    if record is None:
        record = {}
    record.update(initial)
    batches = []
    require(f.valid_full_scope(metadata['full_scope']), 'Missing full seed scope')
    require(record['balance_nnz'] <= f.MAX_NEW_NNZ, 'Initial balance growth ceiling')
    for index in range(2):
        require(time.monotonic()+FINAL_RESERVE < deadline and lp.get_runtime() < NATIVE_TOTAL_CAP,
            'Insufficient seed native window')
        current = {'round': index, 'model_version': lp.version, 'cut_batches': index,
            'map_hash':metadata['map_hash'],'matrix_identity':metadata['matrix_identity'],
            'activation_before_solve':metadata['activation']}
        require(adaptive.activation(metadata).evaluations==index and adaptive.activation(metadata).admitted==index,'Seed ledger chronology')
        record['rounds'].append(current)
        current['matrix_snapshot'] = f.bundle(out, f'round-{index:02d}-matrix', lp.expected, record['actual_stage_costs'])
        if index==0:record['base_matrix_artifact']=current['matrix_snapshot']
        current['native'] = lp.run_with_cumulative_limit(deadline, native_total_cap=NATIVE_TOTAL_CAP,
            reserve_seconds=FINAL_RESERVE)
        record['calls'] += 1
        solution = lp.get_solution()
        current['solution_artifact'] = f.bundle(out, f'round-{index:02d}-solution', solution, record['actual_stage_costs'])
        quality = qa.check_solution(lp.expected, solution)
        require(policy.projected_quality_gate(quality, lp.expected, solution, lp.version), 'Seed LP QA failed')
        current['projected_quality'] = quality
        require(record['certificate_attempts']<2,'Only two fresh seed certificate attempts')
        binding=dict(map_hash=metadata['map_hash'],matrix_identity=metadata['matrix_identity'],
            source_identity=metadata['source_identity'],scope_identity=metadata['scope_identity'],
            model_version=lp.version,solution_version=solution['version'],
            snapshot_document_sha256=current['solution_artifact']['document']['sha256'],
            snapshot_arrays_sha256=current['solution_artifact'].get('arrays',{}).get('sha256'))
        certificate = policy.measured_lower_certificate(lp.expected, solution, deadline, certified_lower=certified_lower,
            model=model, record=record, current=current, out=out,binding=binding)
        require(certificate is not None, 'Exact seed LP lower certificate failed')
        current['stationarity_threshold_replaced_by_exact_certificate']="independent stationarity residual" in quality.get('failures',[])
        current['exact_current_matrix_certificate_required']=True
        current.pop('lower_certificate', None)
        record['exact_lp_lowers'].append(dict(kind='exactLP', lower=certificate['original_bound_down'],
            matrix_hashes=model.model_hashes(lp.expected), cut_batches=index,adaptive_binding=binding,
            activation_snapshot=dict(metadata['activation']),certificate_relabels_promoted_matrix=False,
            full_scope_identity_sha256=metadata['full_scope_identity_sha256'], sense=1, offset=0,
            hard_zero_subset_identity_sha256=metadata['hard_zero_subset']['identity_sha256'],
            lower_domain=metadata['hard_zero_subset']['lower_domain'],
            certificate_artifact=current['lower_certificate_artifact'], matrix_snapshot=current['matrix_snapshot']))
        batch, evaluated = evaluate_point(solution['col_value'], original, metadata, oracle, out, index,
            deadline, projection=projection, qa=qa)
        current.update(evaluated)
        require(record['retained_batches']<2 and record['balance_nnz']+record['cut_nnz']+batch['nnz']<=1048576,'Seed batch growth ceiling')
        batches.append(batch)
        record['retained_batches'] += 1
        record['cut_nnz'] += batch['nnz']
        record['oracle_evaluations'] += 1
        record['full_scope_scans'] += 2
        # Deliberately do not test continuous interval closure here. Both batches
        # are required, and the second is persisted without a third LP solve.
        if index == 0:
            require(time.monotonic()+FINAL_RESERVE < deadline, 'No seed second-solve window')
            runtime.expected,metadata,current['composite_addition']=adaptive.install(lp.expected,metadata,batch,lp=lp)
            runtime.adopt(batch)
            record['cut_batches'] += 1
        else:
            metadata=adaptive.terminal(lp.expected,metadata,batch)
            current['terminal_support_uninstalled']=True
            current['support_promotable_from_preinstall_snapshot']=True
        f.write_json(out, f'round-{index:02d}-receipt.json', current, record['actual_stage_costs'])
    record['batches_artifact'] = f.bundle(out, 'fresh-seed-batches', batches, record['actual_stage_costs'])
    record.update(passed=True, outcome='two_seed_solves_complete', native_cumulative_seconds=lp.get_runtime(),
        lower_exact_lp=max(v['lower'] for v in record['exact_lp_lowers']),
        activation_final=metadata['activation'],adaptive_cache=adaptive.support().cache_receipt(runtime.cache),
        combined_elementary_requests=runtime.check_requests())
    require(record['calls'] == 2 and record['retained_batches'] == 2 and record['cut_batches'] == 1 and record['certificate_attempts']==2,
        'Seed fixed schedule changed')
    require(finite(record['native_cumulative_seconds']) and record['native_cumulative_seconds'] <= NATIVE_TOTAL_CAP,
        'Seed native cumulative limit exceeded')
    return record


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ('out', 'manifest', 'manifest-sha256'):
        ap.add_argument('--'+key, required=True)
    ap.add_argument('--deadline', type=float, required=True)
    args = ap.parse_args(argv)
    require(sys.dont_write_bytecode and __debug__, 'Run Python -B with assertions')
    require(finite(args.deadline), 'Nonfinite seed deadline')
    deadline = min(START+SEED_PROCESS_CAP, args.deadline)
    f = helpers()
    out = f.output_directory(args.out)
    result = dict(schema='adaptive-line-integer-seed/v1', passed=False, result_complete=False,
        physical_dc_lower_bound_certified=False)
    budget=storage()
    start_output_phase(out,'seed initialization',[budget.WriteBound(out/'native.log',budget.NATIVE_FILE_LIMIT,
        'native-only LP log','64-MiB soft limit around each synchronous native call')])
    lp = None
    try:
        manifest, paths, identities = verify_manifest(args.manifest, args.manifest_sha256, deadline)
        model, projection, capi, qa, oracle, original, intended, metadata, data = prepare(paths, manifest, deadline)
        result['runtime'] = f.verify_loaded_runtime(identities)
        lp = GuardedLP(capi.PersistentLP,paths['library'], out/'native.log')
        result['projection_artifact']=f.bundle(out,'projection',metadata,{})
        readback = lp.pass_model(intended)
        run_seed(lp, oracle, original, metadata, out, deadline, model=model, projection=projection, qa=qa, record=result)
        result.update(projected_input_readback=readback, verified_manifest_sha256=args.manifest_sha256,
            original_model_hashes=model.model_hashes(original),
            native_identity=lp.identity, native_options=lp.options, native_default_tolerances=lp.defaults)
    except BaseException as exc:
        result.update(passed=False, outcome='seed_failed', error=type(exc).__name__+': '+str(exc))
    finally:
        if lp is not None:
            try:
                result['native_calls'] = lp.run_records
                result['native_cumulative_seconds'] = lp.get_runtime()
                result['native_diagnostics'] = lp.diagnostics()
                require(not result['native_diagnostics']['fatal'], 'Fatal terminal seed diagnostics')
                result['terminal_runtime'] = f.verify_loaded_runtime(identities)
            except BaseException as exc:
                result.update(passed=False, outcome='seed_terminal_failed', error=type(exc).__name__+': '+str(exc))
            finally:
                try:
                    lp.destroy()
                    result['native_object_destroyed'] = True
                    result['native_output_limits'] = lp.limit_records
                except BaseException as exc:
                    result.update(passed=False, outcome='seed_destroy_failed', native_object_destroyed=False,
                        destroy_error=type(exc).__name__+': '+str(exc))
        if time.monotonic() >= deadline:
            result.update(passed=False, outcome='seed_deadline_exceeded')
        from current_scuc.common import NATIVE_LIMIT_RECORDS
        result['native_output_limits']=list(NATIVE_LIMIT_RECORDS)
        result.update(result_complete=True, actual_worker_seconds=time.monotonic()-START,
            parent_process_start_through_reap_is_authoritative=True)
        f.write_json(out, 'result.json', result, {})
        f.write_json(out, 'completion.json', dict(result_sha256=f.sha256(out/'result.json'), passed=result['passed'],
            parent_process_start_through_reap_is_authoritative=True), {})
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    from current_scuc.common import storage
    budget=storage()
    stdout_path=Path('/proc/self/fd/1').resolve()
    with budget.active_writer_reservations([budget.WriteBound(stdout_path,512*1024**2,
            'Python worker prospective stdout file policy','inherited 512-MiB RLIMIT_FSIZE')]):
        raise SystemExit(main())
