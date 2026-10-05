#!/usr/bin/env python3
"""Fixed continuous and integer network projection demonstration; no case input."""
import time
START = time.monotonic()
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parent
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[key] = '1'
sys.dont_write_bytecode = True


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, default=PACKAGE.parent)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--mode', choices=('continuous', 'integer', 'both'), default='both')
    args = parser.parse_args()
    if not __debug__ or not sys.dont_write_bytecode:
        raise ValueError('Run Python -B without -O')
    if sys.platform != 'linux':
        raise ValueError('This tiny adapter supports Linux/glibc only')
    verify = load('_network_projection_verify', PACKAGE/'verify_files.py')
    verify.verify()
    research, source, build, out = (getattr(args, k).resolve() for k in ('research', 'source', 'build', 'out'))
    if any(out.is_relative_to(p) or p.is_relative_to(out) for p in (PACKAGE, source, build)):
        raise ValueError('Use a distinct external output directory')
    out.mkdir(parents=False, exist_ok=False)
    result = dict(schema='network-projection-portable-tiny-v1', passed=False, mode=args.mode,
                  fixed_fixture=True, real_case_constructed=False, performance_sample=False,
                  portable_full_case_replay_claimed=False, physical_dc_lower_bound_certified=False)
    def save(name, value):
        text = json.dumps(clean(value), sort_keys=True, indent=2, allow_nan=False)+'\n'
        path = out/name
        with path.open('x') as stream:
            stream.write(text)
        if path.read_text() != text:
            raise ValueError('Artifact readback mismatch')
    def clean(value):
        if hasattr(value, 'tolist'):return clean(value.tolist())
        if isinstance(value, dict):return {str(k):clean(v) for k,v in value.items()}
        if isinstance(value, (list,tuple)):return [clean(v) for v in value]
        if isinstance(value, Path):return str(value)
        return value
    try:
        kit = research/'portable_pristine_reference_replay_v3/replay'
        adapter = load('_public_pristine_adapter', kit/'prepare_replay.py')
        adapter.release(research)
        source_identity = adapter.source_inventory(source)
        runtime = adapter.build_identity(source, build)
        inspection = load('_public_python_inspection', kit/'payload/combined_screening_driver/runtime_inspect.py')
        python_identity = inspection.startup()
        for p in python_identity['sites']:
            if p not in sys.path:sys.path.append(p)
        import numpy as np
        import scipy
        from threadpoolctl import threadpool_limits
        sys.path.insert(0, str(PACKAGE/'src/network-projection-lp-core-v1'))
        sys.path.insert(0, str(PACKAGE/'src'))
        import model, capi, qa, fixture, gates, integer_bridge, tiny_mip
        from tiny_schedule import TinySchedule
        certificate = load('_projection_exact_certificate', PACKAGE/'src/network-projection-certified-lower-v2/certified_lower.py')
        projection = load('_projection_full_transform', PACKAGE/'src/network-projection-full-oracle-v1/full_projection.py')
        oracle_module = load('_projection_full_oracle', PACKAGE/'src/network-projection-full-oracle-v1/oracle.py')
        generator = load('_public_scuc_generator', kit/'payload/scuc/generate.py')
        exporter = load('_public_canonical_exporter', kit/'payload/canonical_mps_export/export_v2.py')
        checker = load('_public_source_checker', kit/'payload/scuc/check_solution.py')
        capi.configure_runtime(source, adapter.sha(runtime['library']), kit/'payload/canonical_mps_export')
        result['runtime'] = dict(source=source_identity, build=runtime, python=python_identity,
                                 numpy=np.__version__, scipy=scipy.__version__)
        # Native calls have individual limits; external timeout remains authoritative.
        deadline = START+150.
        with threadpool_limits(limits=1):
            data, pairs = fixture.fixture()
            save('source.json', data)
            built, _ = generator.build(data, 2, 'n1', security_pairs=pairs)
            original = model.validate_model(exporter.intended_model(built))
            oracle = oracle_module.PreparedOracle(data, original, pairs, generator,
                {'fixture':'fixed-three-bus-two-hour'}, production_scope=False, deadline=deadline)
            projected, metadata = projection.transform_expected(original, data, 2, pairs, oracle.lodf,
                full_scope=oracle.full_scope, deadline=deadline)
            metadata['source_binary_authority'] = integer_bridge.source_binary_authority(data, 2)
            model.require(oracle.full_scope['unsigned_security_pair_hours'] == 8 and oracle.full_scope['counts']['signed_soft_rows'] == 24, 'Tiny full scope changed')
            save('projection.json', metadata)
            result['full_scope'] = oracle.full_scope
            seeds = []
            schedule = TinySchedule(args.mode)
            def evaluate(x, tag, cut_index, integer=False):
                retained = projection.restore_retained(x, metadata)
                retained.setflags(write=False)
                before = retained.tobytes()
                evaluated = oracle.evaluate(retained, deadline=deadline)
                model.require(retained.tobytes() == before and not retained.flags.writeable, 'Retained point changed')
                model.require(gates.certificate_gate(evaluated['certificate'], oracle.full_scope), 'Oracle cut certificate failed')
                model.require(evaluated['original_network_lift']['network_residual_le_1e_5'], 'Network recovery failed')
                lift = np.asarray(evaluated['original_network_lift']['values'])
                gates.verify_retained(retained, lift, metadata)
                # Independent readback from the actual emitted artifact precedes QA.
                path = out/(tag+'-lift.npy')
                with path.open('xb') as stream:np.save(stream, lift, allow_pickle=False)
                with path.open('rb') as stream:stored = np.load(stream, allow_pickle=False)
                gates.verify_retained(retained, stored, metadata)
                full_check = oracle.check_lift(stored, deadline=deadline)
                digest = hashlib.sha256(stored.tobytes()).hexdigest()
                model.require(gates.full_lift_gate(full_check, oracle.full_scope, digest), 'Stored full-scope lift check failed')
                primal = qa.check_primal(original, stored)
                primal.pop('activities', None)
                model.require(primal['passed'], 'Original-matrix lift check failed')
                row = dict(oracle_certificate=evaluated['certificate'], full_scope_check=full_check,
                           original_primal=primal, upper=primal['objective_recomputed'], lift_sha256=digest)
                if integer:
                    iq = integer_bridge.check_integer_values(original, dict(zip(original['col_names'],stored)))
                    iq.pop('x', None)
                    model.require(iq['passed'] and iq['binary_count'] == 12, 'Original integer lift failed')
                    row['original_integer'] = iq
                save(tag+'-evaluation.json', row)
                batch = gates.mapped_cuts(evaluated['cut_rows'], metadata, cut_index)
                return batch, row, stored
            with capi.PersistentLP(runtime['library'], out/'seed-native.log') as lp:
                result['projected_input_readback'] = lp.pass_model(projected)
                for i in range(2):
                    native = lp.run_with_cumulative_limit(deadline, native_total_cap=30., reserve_seconds=5.)
                    solution = lp.get_solution()
                    quality = qa.check_solution(lp.expected, solution)
                    model.require(gates.projected_quality_gate(quality, lp.expected, solution, lp.version), 'Seed quality failed')
                    proof = certificate.certify(lp.expected, solution['row_dual'], deadline_monotonic=min(time.monotonic()+20.,deadline))
                    gates.lower_certificate_gate(proof, lp.expected, solution['row_dual'], model=model)
                    batch, evaluated, _ = evaluate(solution['col_value'], 'seed-'+str(i), i)
                    schedule.record_seed(batch, proof['original_bound_down'], evaluated['upper'])
                    seeds.append(dict(native=native, quality=quality, lower_certificate=proof, evaluation=evaluated))
                    save('seed-'+str(i)+'-certificate.json', proof)
                    if i == 0:
                        seeds[-1]['row_addition'] = lp.add_rows(batch['lower'],batch['upper'],batch['starts'],batch['index'],batch['value'],batch['names'])
                result['seed_native_identity'] = lp.identity
                seed_batches, seed_lower = schedule.integer_seed()
                seed_state_hash = integer_bridge.object_hash({'batches':seed_batches,'lower':seed_lower})
                continuous_rounds = []
                # Continuous validation may need more cuts than fixed integer seeding.
                # These additions stay on this LP object and never enter integer_seed().
                while schedule.continuous_action() == 'continue':
                    pending, index = schedule.continuation_input()
                    addition = lp.add_rows(pending['lower'],pending['upper'],pending['starts'],pending['index'],pending['value'],pending['names'])
                    native = lp.run_with_cumulative_limit(deadline, native_total_cap=30., reserve_seconds=5.)
                    solution = lp.get_solution()
                    quality = qa.check_solution(lp.expected, solution)
                    model.require(gates.projected_quality_gate(quality, lp.expected, solution, lp.version), 'Continuous quality failed')
                    proof = certificate.certify(lp.expected, solution['row_dual'], deadline_monotonic=min(time.monotonic()+20.,deadline))
                    gates.lower_certificate_gate(proof, lp.expected, solution['row_dual'], model=model)
                    batch, evaluated, _ = evaluate(solution['col_value'], 'continuous-'+str(index), index)
                    schedule.record_continuation(batch, proof['original_bound_down'], evaluated['upper'])
                    save('continuous-'+str(index)+'-certificate.json', proof)
                    continuous_rounds.append(dict(row_addition=addition,native=native,quality=quality,
                                                  lower_certificate=proof,evaluation=evaluated))
                model.require(schedule.continuous_action() in ('closed','skip'), 'Tiny continuous call/addition cap reached without closure')
                isolated_batches, isolated_lower = schedule.integer_seed()
                model.require(integer_bridge.object_hash({'batches':isolated_batches,'lower':isolated_lower}) == seed_state_hash,
                              'Continuous work changed the fixed integer seed')
            result['seed'] = seeds
            result['integer_seed_state_sha256'] = seed_state_hash
            full_built, _ = generator.build(data, 2, 'n1', security_pairs=fixture.FULL_TINY_PAIRS)
            full_expected = model.validate_model(exporter.intended_model(full_built))
            if args.mode in ('continuous', 'both'):
                with capi.PersistentLP(runtime['library'], out/'full-continuous-native.log') as lp:
                    lp.pass_model(full_expected)
                    lp.run_with_cumulative_limit(deadline, native_total_cap=20., reserve_seconds=5.)
                    solution = lp.get_solution()
                    check = qa.check_solution(lp.expected, solution)
                    model.require(check['passed'], 'Tiny explicit full continuous QA failed')
                    objective = check['primal']['objective_recomputed']
                    lower, upper = schedule.continuous_lower, schedule.continuous_upper
                    model.require(abs(objective-upper) <= 1e-5 and lower <= objective+1e-7, 'Tiny continuous parity failed')
                    result['continuous'] = dict(passed=True, lower=lower, upper=upper,
                        total_lp_calls=schedule.continuous_calls,row_additions=schedule.continuous_additions,
                        continuation_rounds=continuous_rounds,integer_seed_unchanged=True,
                        explicit_full_reference_objective=objective, explicit_full_reference_quality=check)
            if args.mode in ('integer','both'):
                for batch in seed_batches:
                    projected = model.append_rows(projected,batch['lower'],batch['upper'],batch['starts'],batch['index'],batch['value'],batch['names'])
                trace = []
                for index in range(3):
                    restored = integer_bridge.restore_integrality(projected, metadata, original)
                    x, native = tiny_mip.solve(restored['expected'], runtime['library'], out/('integer-'+str(index)+'-native.log'), deadline)
                    batch, evaluated, stored = evaluate(x, 'integer-'+str(index), schedule.integer_cut_index(index), integer=True)
                    mip_lower = max(seed_lower, native['numerical_lower'])
                    gap = (evaluated['upper']-mip_lower)/max(abs(evaluated['upper']),1e-10)
                    model.require(gap >= -1e-9, 'Negative integer interval')
                    trace.append(dict(native=native, evaluation=evaluated, lower=mip_lower,
                                      upper=evaluated['upper'], gap=gap, model_hashes=model.model_hashes(projected)))
                    if gap <= .01:break
                    projected = model.append_rows(projected,batch['lower'],batch['upper'],batch['starts'],batch['index'],batch['value'],batch['names'])
                model.require(len(trace) >= 2 and trace[0]['gap'] > .01 and trace[-1]['gap'] <= .01, 'Tiny did not exercise a closing second integer master')
                model.require(trace[0]['model_hashes'] != trace[1]['model_hashes'], 'Integer master unchanged after cut')
                reference_x, reference = tiny_mip.solve(full_expected, runtime['library'], out/'full-integer-native.log', deadline)
                reference_objective = reference['point_check']['linear_objective']
                model.require(abs(reference_objective-1540.5) <= 1e-5 and abs(reference_objective-trace[-1]['upper']) <= 1e-5, 'Tiny full integer parity failed')
                save('integer-original-values.json', dict(zip(original['col_names'], map(float,stored))))
                physical = checker.check(out/'source.json', out/'integer-original-values.json', 'n1', 2, 1e-5)
                model.require(physical['pass_primal'] and physical['security']['outages_checked'] == 3, 'Tiny direct physical outage check failed')
                model.require(abs(physical['linear_model_cost']-trace[-1]['upper']) <= 1e-5, 'Tiny physical objective mismatch')
                result['integer'] = dict(passed=True, trace=trace, full_reference=reference,
                    full_reference_objective=reference_objective, physical_check=physical,
                    adapter='fresh public C API; distinct from recorded production CLI parser')
            mapped = set()
            for line in Path('/proc/self/maps').read_text().splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) == 6 and fields[5].startswith('/') and 'libhighs' in fields[5]:
                    mapped.add(str(Path(fields[5]).resolve()))
            expected_libraries = {runtime['library'], runtime['extras']}
            model.require(mapped == expected_libraries, 'Unexpected or missing loaded HiGHS native provider')
            adapter.verify(runtime['build_pins'])
            result['verified_loaded_libraries'] = {p:adapter.sha(p) for p in sorted(mapped)}
            model.require(time.monotonic() < deadline, 'Tiny whole deadline exceeded')
            result['passed'] = True
    except BaseException as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
        raise
    finally:
        result['whole_seconds_before_serialization'] = time.monotonic()-START
        save('result.json', result)
    print(json.dumps({'passed':True,'mode':args.mode,'result':str(out/'result.json')}))

if __name__ == '__main__':
    main()
