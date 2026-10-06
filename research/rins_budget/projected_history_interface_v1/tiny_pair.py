#!/usr/bin/env python3
"""Explicit TEST ONLY cold/history pair on the published two-hour triangle.

Source adaptation of tests.run_tiny_components and tests.replay_tiny_transition.
Importing this file performs no native work. Running it explicitly launches cold
then history in separate fresh 150-second contained workers, with a 360-second
whole-pair cap and at most 60 seconds outside those workers. Both use seed 1,
the same sealed tiny_history runtime and the exact fixed_triangle source bytes.
There is no reference optimizer, extra LP, third integer attempt or production
advancement. A component PASS requires the known 2.25 MWh candidate NONPASS.
"""
from __future__ import annotations

import time
START = time.monotonic()
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import sys

HERE = Path(__file__).resolve().parent
TEST_PARENT = HERE.parent / 'current_scuc'
ARM_SECONDS = 150.
PAIR_SECONDS = 360.
OUTSIDE_SECONDS = 60.
FINAL_RESERVE = 20.
ORDINARY_SECONDS = 80.
NATIVE_SECONDS = 20.
INTEGER_LIMIT = 2
SEED = 1


def bind_paths(staged_parent):
    """Capture both import authorities before binding.configure's startup scan."""
    staged_parent = Path(staged_parent).resolve()
    if not (staged_parent / 'current_scuc/SOURCE_MANIFEST.json').is_file():
        raise ValueError('An already sealed staged parent is required')
    # process_runner supplies only the staged PYTHONPATH. Re-add the unchanged
    # published tests explicitly in every fresh worker before verify_freeze.
    for path in (str(TEST_PARENT.resolve()), str(staged_parent)):
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    from current_scuc import binding as b
    b.require(b.ROOT.resolve() == staged_parent / 'current_scuc', 'Wrong staged package imported')
    from tests import fixed_triangle
    b.require(Path(fixed_triangle.__file__).resolve() == TEST_PARENT / 'tests/fixed_triangle.py',
              'Wrong published triangle helper imported')
    return b, fixed_triangle


def source_files():
    return [Path(__file__).resolve(), HERE / 'PROTOCOL_AMENDMENT.md',
            *[TEST_PARENT / 'tests' / name for name in
              ('__init__.py', 'fixed_triangle.py', 'run_tiny_components.py', 'replay_tiny_transition.py')]]


def launch(args):
    b, fixture = bind_paths(args.staged_parent)
    from current_scuc import process_runner as process, receipts, runtime, storage_budget
    b.require(sys.dont_write_bytecode and __debug__, 'Run Python -B -s with assertions')
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'PYTHONDONTWRITEBYTECODE', 'PYTHONNOUSERSITE'):
        os.environ[key] = '1'
    process.apply_limits()
    admission = receipts.admit_whole(args.workdir.absolute().parent)
    work = b.fresh_directory(args.workdir)
    result = dict(schema='projected-history-triangle-pair/v1', test_passed=False,
                  component_passed=False, candidate_passed=False, production_result=False,
                  production_advancement_qualified=False, speed_claim=False,
                  arm_order=['cold', 'history'], arm_cap_seconds=ARM_SECONDS,
                  pair_cap_seconds=PAIR_SECONDS, outside_worker_cap_seconds=OUTSIDE_SECONDS,
                  max_integer_attempts_per_arm=INTEGER_LIMIT, whole_storage_admission=admission,
                  arms=[], solver_random_seed=SEED)
    worker_seconds = 0.
    code = 2
    try:
        installed = runtime.discover_runtime(args.highs, args.runtime_manifest)
        source = fixture.write_source(work / 'fixed-source.json')
        pins = {str(path): b.sha(path) for path in source_files()}
        pins_path = work / 'test-sources.json'
        storage_budget.atomic_json(pins_path, pins, fresh=True)
        config_path = work / 'runtime.config.json'
        cfg = b.configure(source, installed.manifest_path, config_path)
        os.environ.update(PRIMAL_CACHE_CONFIG=str(config_path), PRIMAL_CACHE_CONFIG_SHA256=b.sha(config_path),
                          CURRENT_SCUC_RUNTIME_MANIFEST=str(installed.manifest_path))
        plan = b.read(b.ROOT / 'history_plan.json')
        from current_scuc.history_scuc import TINY_PROFILE
        b.require(plan['mode'] == 'tiny_history' and plan['profile'] == TINY_PROFILE,
                  'Pair requires the separately sealed tiny_history profile')
        result.update(source_sha256=b.sha(source), source_manifest_sha256=cfg['source_manifest_sha256'],
                      test_sources_sha256=b.sha(pins_path), runtime_manifest_sha256=b.sha(installed.manifest_path))
        for index, arm in enumerate(('cold', 'history')):
            outside = time.monotonic() - START - worker_seconds
            b.require(outside < OUTSIDE_SECONDS and time.monotonic() - START + (2-index)*ARM_SECONDS <= PAIR_SECONDS,
                      'Whole pair cannot contain the remaining fixed worker slots')
            b.verify(pins)
            command = [cfg['python'], '-B', '-s', str(Path(__file__).resolve()),
                       '--staged-parent', str(Path(args.staged_parent).resolve()),
                       '--worker', arm, '--out', str(work / arm),
                       '--source-pins', str(pins_path), '--source-pins-sha256', b.sha(pins_path)]
            log = work / (arm + '-worker.log')
            writes = [storage_budget.WriteBound(log, storage_budget.PYTHON_FILE_LIMIT,
                      'one contained tiny worker stdout', '512 MiB inherited RLIMIT_FSIZE')]
            storage_budget.admit_phase(work, phase='fresh ' + arm + ' triangle worker', writes=writes,
                                       metadata_bytes=storage_budget.METADATA_LIMIT)
            with storage_budget.active_writer_reservations(writes):
                # The contained slot has its own 150-second watchdog. Outside
                # work consumes the separate 60-second allowance, rearmed below.
                signal.setitimer(signal.ITIMER_REAL, max(.001, START+PAIR_SECONDS-time.monotonic()))
                measurement = process.run(command, log, work, ARM_SECONDS)
            worker_seconds += measurement['process_wall_seconds']
            now = time.monotonic()
            signal.setitimer(signal.ITIMER_REAL, max(.001, min(START+PAIR_SECONDS-now,
                OUTSIDE_SECONDS-(now-START-worker_seconds))))
            storage_budget.atomic_json(work / (arm + '-worker-process.json'), measurement, fresh=True)
            arm_receipt = dict(arm=arm, process=measurement)
            result['arms'].append(arm_receipt)
            process.require_clean(measurement)
            b.verify(pins)
            report_path = work / arm / 'result.json'
            report = b.read(report_path)
            b.require(report['test_passed'] is True and report['candidate_passed'] is False and
                      report['candidate_expected_nonpass_verified'] is True and report['seed_lp_calls'] == 2 and
                      report['total_actual_integer_process_count'] <= INTEGER_LIMIT and
                      report['production_advancement_qualified'] is False, 'Tiny arm gates incomplete')
            b.require(report['fixture_source_sha256'] == result['source_sha256'] and
                      report['source_freeze']['source_manifest_sha256'] == result['source_manifest_sha256'],
                      'Pair fixture or runtime source identity changed between arms')
            arm_receipt.update(result_path=str(report_path), result_sha256=b.sha(report_path),
                               component_passed=report['component_passed'],
                               candidate_outcome=report['candidate_outcome'],
                               candidate_policy_continuation=report['candidate_policy_continuation'],
                               separate_component_proof=report['component_proof']['exercised'])
        result.update(test_passed=True, component_passed=True, candidate_expected_nonpass_verified=True,
                      expected_shared_overflow_MWh=2.25,
                      outcome='both_components_passed_both_candidates_expected_nonpass')
        code = 0
    except (Exception, KeyboardInterrupt) as exc:
        result.update(test_passed=False, component_passed=False, error_type=type(exc).__name__, error=str(exc))
    finally:
        elapsed = time.monotonic() - START
        result.update(whole_pair_seconds_before_serialization=elapsed,
                      supervised_worker_seconds=worker_seconds, outside_worker_seconds=elapsed-worker_seconds,
                      whole_time_passed=elapsed <= PAIR_SECONDS and elapsed-worker_seconds <= OUTSIDE_SECONDS)
        if not result['whole_time_passed']:
            result.update(test_passed=False, component_passed=False)
            code = 2
        storage_budget.atomic_json(work / 'PAIR-RESULT.json', result, fresh=True)
        # Include publication/accounting in the final bound rather than using
        # only the pre-serialization observation as successful completion.
        completed = time.monotonic()-START
        if completed > PAIR_SECONDS or completed-worker_seconds > OUTSIDE_SECONDS:
            result.update(test_passed=False, component_passed=False, whole_time_passed=False,
                          whole_pair_seconds_after_serialization=completed,
                          outside_worker_seconds_after_serialization=completed-worker_seconds)
            storage_budget.atomic_json(work / 'PAIR-RESULT.json', result)
            code = 2
        print(json.dumps(dict(test_passed=result['test_passed'], candidate_passed=False,
                              result=str(work / 'PAIR-RESULT.json')), sort_keys=True))
    return code


def worker(args):
    b, fixture = bind_paths(args.staged_parent)
    from current_scuc import process_runner as process, runtime as local_runtime
    from current_scuc import common, adaptive, admission, carry, diagnostics, history_scuc, no_shedding, options, phase
    from current_scuc.common import (ROOT, GuardedLP, bounded_write, evaluate_point, helpers, module,
        native_call_guard, native_command, native_receipt, native_shape_guard, read_bundle,
        require, start_output_phase, storage)
    from current_scuc.seed import run_seed
    require(sys.dont_write_bytecode and __debug__, 'Run tiny Python -B -s with assertions')
    require(b.sha(args.source_pins) == args.source_pins_sha256, 'Tiny source pin document changed')
    pins = b.read(args.source_pins)
    require(set(pins) == {str(path) for path in source_files()}, 'Incomplete external test source pins')
    b.verify(pins)
    frozen = b.verify_freeze()
    cfg = b.config()
    b.write = bounded_write
    process.apply_limits()
    f = helpers()
    deadline = START + ARM_SECONDS
    out = b.fresh_directory(args.out)
    ledger = phase.Ledger()
    component = dict(exercised=False, passed=False, actual_integer_process_count=0,
                     charged_wall_seconds=0., production_continuation=False)
    state = dict(run_directory=str(out), source_manifest_sha256=b.sha(__file__), solver_random_seed=SEED,
                 trace=[], quality_failed=False, mechanism_failed=False, carry_preparations=[], cut_batches=2)
    if args.worker == 'history':
        plan, plan_sha = phase.load_history_plan(state, ledger)
    else:
        plan_path = ROOT / 'history_plan.json'
        plan, plan_sha = b.read(plan_path), b.sha(plan_path)
    require(plan['mode'] == 'tiny_history' and plan['profile'] == history_scuc.TINY_PROFILE,
            'Production history profile cannot run in tiny harness')
    status = dict(schema='projected-history-triangle-arm/v1', arm=args.worker,
                  passed=False, test_passed=False, component_passed=False, candidate_passed=False,
                  production_result=False, production_advancement_qualified=False, speed_claim=False,
                  fixture_fixed_before_outcomes=True, source_freeze=frozen, solver_random_seed=SEED,
                  trace=state['trace'], component_proof=component, candidate_policy_continuation=False,
                  reference_mip_calls=0, seed_lp_calls=0, full_physical_passes=0)

    def total_actual():
        return ledger.actual_integer_process_count + component['actual_integer_process_count']

    def launch_integer_allowed():
        require(total_actual() < INTEGER_LIMIT, 'Tiny two-actual-integer allowance exhausted')
        require(deadline - time.monotonic() > ORDINARY_SECONDS + FINAL_RESERVE,
                'No fixed ordinary slot plus final reserve remains')

    def verify_sources():
        b.verify(pins)
        b.verify_freeze()

    def parent_history_check(operation):
        return phase.charged_parent_history_check(state, ledger, operation)

    try:
        installed = local_runtime.discover_runtime(cfg['binary'], cfg['runtime_manifest'])
        with native_call_guard('tiny runtime ABI qualification'):
            status['runtime_qualification'] = local_runtime.qualify_capi(installed)
        with Path(cfg['numerical_lock']).open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            model, _, _, qa, oracle_module = f.load_modules()
            projection, capi = adaptive.adapter(), adaptive.native()
            generator = module('_integer_tiny_generator', ROOT / 'core/scuc/generate.py')
            exporter = module('_integer_tiny_exporter', ROOT / 'core/canonical_mps_export/export_v2.py')
            master = module('_integer_master', ROOT / 'master.py')
            data, pairs = fixture.family_fixture()
            source = fixture.write_source(out / 'source.json')
            require(b.sha(source) == cfg['inputs']['current']['sha256'], 'Published triangle fixture bytes changed')
            status['fixture_source_sha256'] = b.sha(source)
            built, _ = generator.build(data, 2, 'n1', security_pairs=pairs)
            original = model.validate_model(exporter.intended_model(built))
            mps = out / 'original-subset.mps'
            exporter.write_model(built, mps)
            expected_path = out / 'original.expected.json'
            expected_path.write_text(json.dumps(master.json_value(original), allow_nan=False) + '\n')
            oracle = oracle_module.PreparedOracle(data, original, pairs, generator,
                dict(fixture='fixed-existing-triangle', source_sha256=f.sha256(source),
                     expected_sha256=f.sha256(expected_path), mps_sha256=f.sha256(mps),
                     generator_sha256=f.sha256(generator.__file__)), production_scope=False,
                deadline=deadline-FINAL_RESERVE)
            oracle.source_data = data
            projected, metadata, _ = adaptive.make_base(original, data, 2, pairs, oracle.lodf,
                oracle.pins['source_sha256'], oracle.full_scope)
            require(len(metadata['retained_original_columns']) == 30 and sum(original['integrality']) == 12,
                    'Published tiny original column/binary inventory changed')
            require((metadata['first_start_family']['row_count'], metadata['fixed_family_nnz']) == (4, 10),
                    'Tiny complete first-start family changed')
            require(metadata['hard_zero_subset']['changed_shed_upper_bounds'] == 6 and
                    metadata['hard_zero_subset']['reserve_shortfall_columns'] == 0, 'Tiny hard-zero inventory changed')
            status.update(first_start_family=metadata['first_start_family'], hard_zero_subset=metadata['hard_zero_subset'])
            metadata['source_binary_authority'] = master.source_binary_authority(data, 2)
            seedout = out / 'seed'
            seedout.mkdir()
            seed_tick = time.monotonic()
            seed_allocation = min(60., deadline-seed_tick-ORDINARY_SECONDS-FINAL_RESERVE)
            require(seed_allocation > 1., 'No tiny seed window')
            try:
                with GuardedLP(capi.PersistentLP, cfg['library'], seedout / 'native.log', SEED) as lp:
                    lp.pass_model(projected)
                    seeded = run_seed(lp, oracle, original, metadata, seedout, seed_tick+seed_allocation,
                                      model=model, projection=projection, qa=qa)
                    require(seeded['calls'] == 2 and seeded['retained_batches'] == 2 and seeded['oracle_evaluations'] == 2,
                            'Exactly two fresh seed LP calls/evaluations required')
                    require(type(lp.options.get('random_seed')) is int and lp.options['random_seed'] == SEED,
                            'Tiny seed solver seed changed')
                    seeded.update(solver_random_seed=SEED, native_options=dict(lp.options))
            finally:
                seed_wall = time.monotonic()-seed_tick
                require(ledger.debit('seed', seed_allocation, dict(process_wall_seconds=seed_wall,
                            runner_launched=False)), 'Tiny inline seed debit exceeded allocation')
                status['seed_debit_scope'] = 'Inline LP seed, checks and destruction inside this supervised arm; not an extra worker'
            status.update(seed=seeded, seed_lp_calls=seeded['calls'])
            seeded.update(projection_artifact=f.bundle(seedout, 'projection', metadata, {}),
                          original_model_hashes=model.model_hashes(original))
            f.write_json(seedout, 'result.json', seeded, {})
            tiny_arm = dict(solver_random_seed=SEED, inputs={role: dict(path=str(path), sha256=f.sha256(path))
                for role, path in [('source', source), ('expected', expected_path), ('library', Path(cfg['library']))]})
            tiny_arm_path = out / 'tiny-arm.json'
            f.write_json(out, 'tiny-arm.json', tiny_arm, {})
            state.update(arm_manifest_sha256=f.sha256(tiny_arm_path), seed=seeded)
            cut_prefix = [dict(source='seed', artifact=seeded['batches_artifact'])]
            batches = read_bundle(seedout, seeded['batches_artifact'])
            # Same fresh process-local seed cache and explicit prefix promotion as
            # the published tiny transition. No state is reused across arms.
            runtime = common.ADAPTIVE_RUNTIME
            runtime.bank = []
            for batch in batches:
                projected, metadata, _ = adaptive.install(projected, metadata, batch)
                runtime.adopt(batch)
            runtime.expected = projected
            require(adaptive.activation(metadata).admitted == 2 and adaptive.activation(metadata).evaluations == 2,
                    'Tiny installed seed prefix changed')
            io = module('_integer_frozen_io', b.CORE / 'canonical_mps_export/io_announcements.py')
            from current_scuc.core.driver.primal_and_bound import solver_report
            from current_scuc.contracts import LIBRARY

            def solve(exported, *, role, prepared=None, request_path=None, transition=False, separate=False):
                """The ordinary published CLI parser, readback and containment path."""
                launch_integer_allowed()
                path = Path(exported['identity']['model_path'])
                rd = path.parent
                solution, opt = rd / 'solution.sol', rd / 'solver.options'
                start = Path(prepared['start']['path']) if prepared else None
                opt.write_text(options.option_text(role))
                probe = options.probe(cfg, opt, NATIVE_SECONDS, start=start, role=role, solver_random_seed=SEED)
                require(type(probe['options'].get('random_seed')) is int and probe['options']['random_seed'] == SEED and
                        type(probe.get('solver_random_seed')) is int and probe['solver_random_seed'] == SEED,
                        'Tiny ordinary solver seed changed')
                b.write(rd / 'options-readback.json', probe, fresh=True)
                if transition:
                    parent_history_check(lambda: carry.verify_transition_proof(
                        state, exported['identity'], probe, start, production=False))
                command = options.command(cfg, path, opt, solution, NATIVE_SECONDS,
                                          start=start, role=role, solver_random_seed=SEED)
                verify_sources()
                phase.verify_export(exported['identity'])
                if request_path is not None:
                    parent_history_check(lambda: carry.verify_prepared(
                        prepared, request_path, f.sha256(request_path), exported['identity']))
                elif prepared is not None:
                    def check_separate():
                        require(separate and f.sha256(start) == prepared['start']['sha256'], 'Separate carry point changed')
                        b.verify({**prepared['consumed_files_sha256'], **prepared['evidence_files_sha256']})
                    parent_history_check(check_separate)
                shape = native_shape_guard(exported['expected'])
                wrapped, limit = native_command(command, rd, cfg, solver=True)
                budget = storage()
                start_output_phase(rd, 'tiny native CLI', [budget.WriteBound(rd/name, budget.NATIVE_FILE_LIMIT,
                    'three fixed native CLI outputs', 'native exec64MiB file limit')
                    for name in ('solver.log', 'Highs.log', 'solution.sol')])
                launch_integer_allowed()
                receipt = process.run(wrapped, rd / 'solver.log', out, ORDINARY_SECONDS, solver=False)
                if separate:
                    if receipt.get('runner_launched', True):
                        component['actual_integer_process_count'] += 1
                    component['ordinary_process'] = receipt
                else:
                    debit_ok = ledger.debit('mip', ORDINARY_SECONDS, receipt)
                    require(debit_ok, 'Tiny ordinary ledger debit failed')
                require(total_actual() <= INTEGER_LIMIT, 'Tiny actual integer process limit exceeded')
                receipt.update(native_limit_request=limit, native_output_shape=shape)
                b.write(rd / 'solver.process.json', receipt, fresh=True)
                process.require_clean(receipt)
                receipt['native_limit_receipt'] = native_receipt(rd, limit, receipt)
                verify_sources()
                if request_path is not None:
                    parent_history_check(lambda: carry.verify_prepared(
                        prepared, request_path, f.sha256(request_path), exported['identity']))
                elif prepared is not None:
                    parent_history_check(check_separate)
                start_admission = (admission.check_admission((rd / 'solver.log').read_text(),
                    carry.g.unrat(prepared['exact_check']['projected_objective_exact'])) if start else None)
                clean, io_receipt = io.filter_known_io((rd / 'solver.log').read_text(), path, solution, solver=True)
                preliminary = solver_report(clean, receipt, 'mip', path, LIBRARY, identities_valid=True)
                clean, advisory = diagnostics.filter_scaling_advisories(clean, mip_report=preliminary,
                    measurement=receipt, model_path=path, role=role)
                require(len(re.findall(r'^Solving report[ \t]*$', clean, re.M)) == 1, 'Tiny ambiguous top-level CLI report')
                report = diagnostics.admit_report(solver_report(clean, receipt, 'mip', path, LIBRARY,
                                                               identities_valid=True), role=role)
                if role == options.DISCOVERY:
                    require(report['global_lower'] is None and not report['bound_status_valid'] and
                            not report['certificate_bound_eligible'] and not report['upper_bound_eligible'],
                            'Tiny discovery leaked bounds')
                else:
                    require(report['bound_status_valid'] and report['status'] == 'Optimal', 'Tiny proof finite bound absent')
                parsed = master.parse_solution(solution, exported['expected'], role=role)
                require(parsed is not None and parsed['status'] == report['status'], 'Tiny point/report mismatch')
                checked = master.check_integer_point(exported['expected'], parsed, role=role)
                require(checked['passed'], 'Tiny current-master integer point failed')
                x = checked.pop('x')
                return x, dict(role=role, solver_random_seed=SEED, report=report, point_check=checked,
                    master_quality=checked, process=receipt, options_readback=probe, io_filter=io_receipt,
                    advisory_filter=advisory, start_admission=start_admission,
                    incumbent_input=str(start) if start else None, no_basis_or_search_state_input=True,
                    native_limit_seconds=NATIVE_SECONDS, allocation_seconds=ORDINARY_SECONDS, command=command,
                    native_limit_request=limit, native_limit_receipt=receipt['native_limit_receipt'],
                    master_identity=exported['identity'], options_artifacts=dict(options_path=str(opt),
                        options_sha256=f.sha256(opt), readback_path=str(rd / 'options-readback.json'),
                        readback_sha256=f.sha256(rd / 'options-readback.json')))

            best = None
            lower = seeded['lower_exact_lp']

            def finish_point(x, row, exported, rd, call, *, history_candidate=None, separate=False):
                nonlocal metadata, best, lower
                if history_candidate is not None:
                    try:
                        batch, ev = phase.evaluate_history(history_candidate, lambda check_deadline:
                            evaluate_point(x, original, metadata, oracle, rd, call+1, check_deadline,
                                projection=projection, qa=qa, integer=True, master=master, persist_batch=False), ledger)
                    finally:
                        state['history'].pop('pending_check_started', None)
                    state['history']['outcome'] = 'accepted_full_original_checked_endpoint'
                else:
                    batch, ev = evaluate_point(x, original, metadata, oracle, rd, call+1, deadline-FINAL_RESERVE,
                        projection=projection, qa=qa, integer=True, master=master, persist_batch=False)
                point_lower = lower
                if row.get('report', {}).get('bound_status_valid'):
                    point_lower = max(point_lower, row['report']['global_lower'])
                span = diagnostics.interval(point_lower, ev['provisional_upper'])
                require(span['passed'], 'Tiny endpoint ordering failed')
                point = dict(evaluation=ev, call=call, directory=str(rd), master_identity=exported['identity'])
                if not separate:
                    lower = point_lower
                    if best is None or no_shedding.selection_key(point) < no_shedding.selection_key(best):
                        best = point
                    selected_span = diagnostics.interval(lower, best['evaluation']['provisional_upper'])
                    selected_call = best['call']
                else:
                    selected_span, selected_call = span, call
                require(selected_span['passed'], 'Tiny selected endpoint ordering failed')
                row.update(call=call, evaluation=ev, interval=span, provisional_interval=span,
                    selected_endpoint_interval=selected_span, selected_endpoint_call=selected_call,
                    master_identity=exported['identity'], model_hashes=model.model_hashes(projected), cut_batches=2,
                    production_stop_eligible=no_shedding.stop_eligible(ev, selected_span))
                if not separate:
                    state['trace'].append(row)
                check_path = rd / 'tiny-point-check.json'
                def save_checked_point():
                    b.write(check_path, ev, fresh=True)
                    row.update(checked_archive=str(check_path),
                               checked_stage_binding=dict(path=str(check_path), sha256=f.sha256(check_path)))
                parent_history_check(save_checked_point)
                row['continuation_support'] = no_shedding.excluding_support(batch, metadata, x, runtime.bank)
                require(not row['production_stop_eligible'], 'Known overflow fixture became production eligible')
                require(row['continuation_support']['passed'] is False and
                        row['continuation_support']['materially_violated_rows'] == 0,
                        'Published tiny needs new support; no tuning or third integer call is permitted')
                return batch, point

            rd = out / 'mip-01'
            rd.mkdir()
            restored = master.restore_integrality(projected, metadata, original)
            exported = master.export_master(restored, rd / 'master.mps', cfg['library'])
            state['integer_target_identity_sha256'] = restored['identity']['integer_target_identity_sha256']
            candidate = None
            if args.worker == 'history':
                require(total_actual() == 0, 'History probe must be first integer attempt')
                candidate = phase.charged_history_attempt(state, ledger, lambda:
                    history_scuc.attempt(plan, plan_sha, cfg, data, restored, exported,
                                         state, ledger, out, deadline, master=master))
                require(total_actual() <= INTEGER_LIMIT, 'Tiny API actual integer process limit exceeded')
            if candidate is None:
                x, row = solve(exported, role=options.DISCOVERY)
            else:
                row = candidate['row']
                check = candidate['check']
                x = check.pop('x')
                row['master_quality'] = check
                row['point_check'] = check
                status['history_api_bounds_discarded'] = True
            batch, first_point = finish_point(x, row, exported, rd, 1, history_candidate=candidate)
            first_span = row['selected_endpoint_interval']
            open_interval = first_span['gap'] > .01 and not first_span['qualified']
            available = total_actual() < INTEGER_LIMIT
            do_transition = open_interval and available and (row['role'] == history_scuc.ROLE or
                row.get('report', {}).get('discovery_stop_activated') is True)
            separate = (args.worker == 'history' and candidate is not None and
                        first_span['qualified'] and available)
            if do_transition:
                remaining = deadline-time.monotonic()-FINAL_RESERVE
                carry_allocation = min(30., remaining-ORDINARY_SECONDS)
                require(carry_allocation > 1., 'No natural carry/proof window')
                state['ledger'] = ledger.record()
                status['discovery_proof_transition'] = parent_history_check(lambda:
                    carry.schedule_transition(state, cut_prefix, carry_allocation=carry_allocation,
                                              proof_allocation=ORDINARY_SECONDS, production=False))
                status['candidate_policy_continuation'] = True
            before = copy.deepcopy(metadata)
            metadata = adaptive.terminal(projected, metadata, batch)
            require(before['projected_hashes'] == metadata['projected_hashes'] and
                    before['map_hash'] == metadata['map_hash'] and before['line_caps'] == metadata['line_caps'],
                    'Non-installed checked point changed current master')
            if do_transition:
                rd2 = out / 'mip-02'
                rd2.mkdir()
                next_restored = master.restore_integrality(projected, metadata, original)
                next_exported = master.export_master(next_restored, rd2 / 'master.mps', cfg['library'])
                state['pending_master'] = dict(call=2, identity=next_exported['identity'], cut_batches=2,
                                               cut_prefix=list(cut_prefix))
                prep_alloc = min(30., deadline-time.monotonic()-ORDINARY_SECONDS-FINAL_RESERVE)
                require(prep_alloc > 1., 'Tiny carry window exhausted; consumed transition remains consumed')
                prep_record = dict(target_call=2, allocation_seconds=prep_alloc)
                state['carry_preparations'].append(prep_record)
                snapshot = rd2 / 'carry-state.json'
                b.write(snapshot, state, fresh=True)
                request = dict(schema=carry.SCHEMA, run_directory=str(out), state_path=str(snapshot),
                    state_sha256=f.sha256(snapshot), source_manifest_path=str(Path(__file__).resolve()),
                    source_manifest_sha256=b.sha(__file__), arm_manifest_path=str(tiny_arm_path),
                    arm_manifest_sha256=f.sha256(tiny_arm_path), target_call=2, pending_master=state['pending_master'],
                    seed_result_path=str(seedout / 'result.json'), seed_result_sha256=f.sha256(seedout / 'result.json'))
                request_path = rd2 / 'carry-request.json'
                b.write(request_path, request, fresh=True)
                prepout = rd2 / 'carry'
                prepout.mkdir()
                tick = time.monotonic()
                try:
                    prepared = carry.prepare(request, prepout, tick+prep_alloc, production=False)
                finally:
                    prep_record['process_wall_seconds'] = time.monotonic()-tick
                    require(ledger.debit('carry', prep_alloc, prep_record), 'Tiny carry debit exceeded allocation')
                prepared['request_sha256'] = f.sha256(request_path)
                b.write(prepout / 'result.json', prepared, fresh=True)
                parent_history_check(lambda: carry.verify_prepared(
                    prepared, request_path, f.sha256(request_path), next_exported['identity']))
                prep_record['preparation'] = prepared
                require(prepared['mapping']['binary_values_rounded'] is False, 'Tiny carry repaired binaries')
                x2, row2 = solve(next_exported, role=options.PROOF_ROLE, prepared=prepared,
                                 request_path=request_path, transition=True)
                batch2, _ = finish_point(x2, row2, next_exported, rd2, 2)
                require(row2['start_admission']['passed'], 'Natural ordinary proof did not admit complete start')
                metadata = adaptive.terminal(projected, metadata, batch2)
                state['discovery_proof_transition']['outcome'] = 'proof_checked_no_new_support'
                status['natural_carry_proof_passed'] = True
            elif separate:
                # The candidate policy already stopped. Exercise its unused
                # allowance as a separately named component, never a trace row.
                component.update(exercised=True, reason='Natural API checked interval already closed',
                                 saved_source_call=1, candidate_interval=copy.deepcopy(first_span))
                component_tick = time.monotonic()
                component_history_debit_before = ledger.spent
                try:
                    crd = out / 'component-proof'
                    crd.mkdir()
                    current_restored = master.restore_integrality(projected, metadata, original)
                    current_exported = master.export_master(current_restored, crd / 'master.mps', cfg['library'])
                    carry.same_transition_master(exported['identity'], current_exported['identity'])
                    prepout = crd / 'carry'
                    prepout.mkdir()
                    ev = first_point['evaluation']
                    api_binding = parent_history_check(lambda: history_scuc.verify_api_evidence(row, expected_seed=SEED))
                    phase.verify_export(exported['identity'])
                    consumed = dict(api_binding['files_sha256'])
                    for prefix in ('model', 'expected', 'api_report', 'row_sidecar'):
                        consumed[exported['identity'][prefix+'_path']] = exported['identity'][prefix+'_sha256']
                    for name in ('stored_lift_artifact', 'oracle_artifact', 'full_source_quality_artifact',
                                 'source_quality_artifact', 'adaptive_support_artifact'):
                        for kind in ('document', 'arrays'):
                            if kind in ev[name]:
                                consumed[str(rd / ev[name][kind]['path'])] = ev[name][kind]['sha256']
                    check_binding = row['checked_stage_binding']
                    consumed[check_binding['path']] = check_binding['sha256']
                    def read_saved_point():
                        b.verify(consumed)
                        lift = read_bundle(rd, ev['stored_lift_artifact'])['values']
                        saved_oracle = read_bundle(rd, ev['oracle_artifact'])
                        require(read_bundle(rd, ev['full_source_quality_artifact']) == ev['full_source_quality'],
                                'Saved API full source check changed')
                        saved_quality = read_bundle(rd, ev['source_quality_artifact'])
                        saved_quality.pop('activities', None)
                        require(saved_quality == ev['source_quality'], 'Saved API original check changed')
                        return lift, saved_oracle
                    lift, saved_oracle = parent_history_check(read_saved_point)
                    prep_alloc = min(30., deadline-time.monotonic()-ORDINARY_SECONDS-FINAL_RESERVE)
                    require(prep_alloc > 1., 'No separate saved-point carry/proof window')
                    prep_deadline = time.monotonic()+prep_alloc
                    px, activities, mapping, exact, start_record = carry.prepare_point(original,
                        current_exported['expected'], metadata, saved_oracle, lift, ev, master, prepout, production=False)
                    native = carry.assess(current_exported['expected'], px, activities,
                        current_exported['identity']['model_path'], Path(start_record['path']), prepout,
                        cfg['library'], f.sha256(cfg['library']), prep_deadline, model)
                    require(time.monotonic() < prep_deadline, 'Separate carry/native assessment exceeded allocation')
                    require(mapping['binary_values_rounded'] is False, 'Separate carry rounded binaries')
                    prepared = dict(passed=True, start=start_record, mapping=mapping, exact_check=exact,
                        optimizer_calls=0, target_master_identity=current_exported['identity'],
                        consumed_files_sha256=consumed,
                        evidence_files_sha256={str(p): f.sha256(p) for p in prepout.iterdir() if p.is_file()}, **native)
                    b.write(prepout / 'result.json', prepared, fresh=True)
                    component['preparation'] = prepared
                    cx, crow = solve(current_exported, role=options.PROOF_ROLE, prepared=prepared, separate=True)
                    cbatch, cpoint = finish_point(cx, crow, current_exported, crd, 2, separate=True)
                    require(crow['start_admission']['passed'], 'Separate ordinary proof did not admit complete start')
                    metadata = adaptive.terminal(projected, metadata, cbatch)
                    component.update(proof=crow, point=cpoint, passed=True,
                                     candidate_endpoint_promoted=False, logical_trace_row_added=False)
                finally:
                    component['whole_component_seconds'] = time.monotonic()-component_tick
                    component['history_checks_already_charged_in_candidate_ledger_seconds'] = ledger.spent-component_history_debit_before
                    component['charged_wall_seconds'] = max(0., component['whole_component_seconds']-
                        component['history_checks_already_charged_in_candidate_ledger_seconds'])
            else:
                status['unexercised_reason'] = ('Two actual integer attempts exhausted after clean history fallback'
                    if not available else 'Existing fixture did not satisfy an authorized natural or separate continuation branch')

            require(best is not None, 'No complete candidate point for final physical checks')
            require(time.monotonic() < deadline, 'No final physical window')
            physical = module('_integer_physical', ROOT / 'physical.py')

            def physical_check(point, directory):
                ev = point['evaluation']
                request = dict(source_path=str(source), source_sha256=f.sha256(source),
                    expected_path=str(expected_path), expected_sha256=f.sha256(expected_path),
                    mps_path=str(mps), mps_sha256=f.sha256(mps), mapping_pairs=[list(p) for p in pairs],
                    stored_lift_directory=point['directory'], stored_lift_artifact=ev['stored_lift_artifact'],
                    full_scope=metadata['full_scope'], full_literal_check=ev['full_source_quality'],
                    integer_target_identity=point['master_identity']['integer_target'],
                    integer_target_identity_sha256=state['integer_target_identity_sha256'],
                    source_binary_authority=metadata['source_binary_authority'], oracle_objective=ev['oracle_objective'],
                    provisional_upper=ev['provisional_upper'], hours=2, retained_values_sha256=ev['retained_values_sha256'])
                directory.mkdir()
                f.write_json(directory.parent, directory.name+'-request.json', request, {})
                checked = physical.run(request, directory, production=False)
                require(checked['passed'] and checked['optimization_called'] is False, 'Full original/source/direct DC checks failed')
                require(abs(checked['checked_upper']-ev['provisional_upper']) <= max(1e-5, abs(ev['provisional_upper'])*1e-9),
                        'Final physical/original upper mismatch')
                quality = no_shedding.slack_quality(original, read_bundle(point['directory'], ev['stored_lift_artifact'])['values'])
                fixture.require_expected_quality(quality)
                require(time.monotonic() < deadline, 'Final physical whole deadline exceeded')
                status['full_physical_passes'] += 1
                f.write_json(directory, 'result.json', checked, {})
                return checked, quality

            checked, quality = physical_check(best, out / 'physical')
            status.update(physical=checked, quality=quality, candidate_interval=diagnostics.interval(lower, checked['checked_upper']))
            if component['exercised']:
                component['physical'], component['quality'] = physical_check(component['point'], out / 'component-physical')
                component['full_original_source_listed_outage_direct_dc_verified'] = True
            require(not no_shedding.stop_eligible(best['evaluation'], status['candidate_interval']),
                    'Known material-overflow candidate falsely passed')
            verify_sources()
            status['loaded_python_runtime'] = local_runtime.verify_loaded_runtime(cfg['python_distribution_files'])
            status['loaded_native_runtime'] = local_runtime.verify_native_mappings(installed)
            coverage = status.get('natural_carry_proof_passed', False) or component['passed']
            if args.worker == 'history':
                coverage = coverage and candidate is not None
            require(total_actual() <= INTEGER_LIMIT and adaptive.activation(metadata).admitted == 2,
                    'Tiny attempt or installed-prefix inventory changed')
            status.update(passed=coverage, test_passed=coverage, component_passed=coverage,
                candidate_expected_nonpass_verified=True, candidate_outcome='material_shared_overflow',
                expected_shared_overflow_MWh=2.25, installed_batches=2,
                point_evaluations=adaptive.activation(metadata).evaluations,
                candidate_mip_calls=len(state['trace']), candidate_stopped_naturally=bool(coverage),
                full_integer_reference_called=False, history=state.get('history'),
                carry_preparations=state['carry_preparations'],
                outcome='components_passed_candidate_expected_nonpass' if coverage else 'authorized_branch_unexercised')
    except BaseException as exc:
        status.update(passed=False, test_passed=False, component_passed=False,
                      error_type=type(exc).__name__, error=str(exc), outcome='terminal_failure')
        if 'discovery_proof_transition' in state:
            state['discovery_proof_transition']['outcome'] = 'failed_or_incomplete'
    finally:
        status.update(ledger=ledger.record(), history=state.get('history'),
            total_actual_integer_process_count=total_actual(), candidate_actual_integer_process_count=ledger.actual_integer_process_count,
            component_actual_integer_process_count=component['actual_integer_process_count'],
            combined_charged_wall_seconds=ledger.spent+component['charged_wall_seconds'],
            component_wall_includes_native_assessment_and_proof_once=True,
            native_output_limits=list(common.NATIVE_LIMIT_RECORDS), whole_seconds_before_serialization=time.monotonic()-START,
            max_integer_attempts=INTEGER_LIMIT, whole_cap_seconds=ARM_SECONDS, final_reserve_seconds=FINAL_RESERVE)
        if status['whole_seconds_before_serialization'] >= ARM_SECONDS or total_actual() > INTEGER_LIMIT:
            status.update(passed=False, test_passed=False, component_passed=False)
        f.write_json(out, 'result.json', status, {})
    print(json.dumps(dict(arm=args.worker, test_passed=status['test_passed'], candidate_passed=False,
                         result=str(out / 'result.json')), sort_keys=True))
    return 0 if status['test_passed'] else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged-parent', type=Path, required=True)
    parser.add_argument('--highs', type=Path)
    parser.add_argument('--runtime-manifest', type=Path)
    parser.add_argument('--workdir', type=Path)
    parser.add_argument('--worker', choices=('cold', 'history'), help=argparse.SUPPRESS)
    parser.add_argument('--out', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--source-pins', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--source-pins-sha256', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        if not all((args.out, args.source_pins, args.source_pins_sha256)):
            parser.error('Internal worker requires output and pinned test sources')
        return worker(args)
    if not all((args.highs, args.runtime_manifest, args.workdir)):
        parser.error('--highs, --runtime-manifest and --workdir are required for the pair')
    # The existing envelope owns all child cleanup. This alarm enforces the
    # outside-worker allowance as well as the complete pair wall; an alarm
    # inside supervise is caught by its existing reap/cleanup path.
    def expired(signum, frame):
        raise TimeoutError('Triangle pair whole/outside-worker deadline reached')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(.001, START+OUTSIDE_SECONDS-time.monotonic()))
    try:
        return launch(args)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.)
        signal.signal(signal.SIGALRM, previous)


if __name__ == '__main__':
    raise SystemExit(main())
