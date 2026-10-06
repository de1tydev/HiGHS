#!/usr/bin/env python3
"""One fresh integer candidate with checked incumbent carry; fixed two-LP/three-MIP schedule, frozen watchdog."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import time
START = time.monotonic()
import argparse
import fcntl
import os
from pathlib import Path
import re
import sys
BASE = PACKAGE_ROOT
from current_scuc.common import ROOT, require, finite, module, helpers, verify_manifest, prepare, read_bundle, append_batch, evaluate_point, storage, native_command, native_receipt, native_shape_guard, bounded_write, start_output_phase, IO_ADMISSIONS, NATIVE_LIMIT_RECORDS
from current_scuc.diagnostics import interval, lower_record, best_lower, filter_scaling_advisories, admit_report
import current_scuc.options as options
import current_scuc.carry as carry
import current_scuc.admission as admission
import current_scuc.adaptive as adaptive
import current_scuc.common as common
import current_scuc.no_shedding as no_shedding

WHOLE_CAP = 1800.
SOLVER_CAP = 600.
FINAL_RESERVE = 360.
PROCESS_RESERVE = 60.
MAX_CALLS = 3
WHOLE_STORAGE_REQUIRED = 26974885888


class Ledger:
    """Contained seed/MIP/carry process walls debit this one candidate ledger."""
    def __init__(self):
        self.spent = 0.
        self.calls = []

    def allocation(self, stage, index, whole_remaining):
        require(finite(whole_remaining), 'Nonfinite whole window')
        require(stage in ('seed','mip','carry'), 'Unknown charged stage')
        if stage == 'seed':
            require(index == 0 and not self.calls, 'Seed can run only once first')
            return max(0., min(180., SOLVER_CAP-self.spent, whole_remaining-FINAL_RESERVE))
        if stage == 'carry':
            require(index in (2,3) and sum(c['stage']=='mip' for c in self.calls)==index-1 and
                sum(c['stage']=='carry' for c in self.calls)==index-2,'fixed carry preparation schedule changed')
            return max(0.,min(30.,SOLVER_CAP-self.spent,whole_remaining-FINAL_RESERVE))
        require(any(c['stage'] == 'seed' for c in self.calls), 'MIP cannot precede seed')
        require(index == 1+sum(c['stage'] == 'mip' for c in self.calls) and 1 <= index <= MAX_CALLS,
            'Fixed MIP call schedule changed')
        cap = 180. if index < 3 else SOLVER_CAP
        return max(0., min(cap, SOLVER_CAP-self.spent, whole_remaining-FINAL_RESERVE))

    def debit(self, stage, allocation, receipt):
        actual = receipt.get('process_wall_seconds')
        require(finite(actual) and actual >= 0 and finite(allocation) and allocation > 0, 'Invalid process wall debit')
        self.spent += actual  # Including overruns, before clean-process admission.
        self.calls.append(dict(stage=stage, allocation=allocation, actual=actual,
            overrun=max(0., actual-allocation), within_allocation=actual <= allocation))
        return self.spent <= SOLVER_CAP and actual <= allocation

    def record(self):
        return dict(solver_process_wall_seconds=self.spent, remaining=max(0., SOLVER_CAP-self.spent),
            ceiling_seconds=SOLVER_CAP, in_budget=self.spent <= SOLVER_CAP, calls=list(self.calls))


def seed_eligible(result):
    require(result.get('schema') == 'adaptive-line-integer-seed/v1' and result.get('passed') is True,
        'Seed failed or incomplete')
    require(result.get('calls') == 2 and result.get('cut_batches') == 1 and result.get('retained_batches') == 2
        and result.get('oracle_evaluations') == 2 and result.get('full_scope_scans') == 4, 'Seed schedule/coverage changed')
    require(result.get('native_object_destroyed') is True and finite(result.get('native_cumulative_seconds'))
        and 0 <= result['native_cumulative_seconds'] <= 60., 'Seed native limit/cleanup failed')
    require(len(result.get('exact_lp_lowers', [])) == 2 and all(finite(r['lower']) for r in result['exact_lp_lowers']),
        'Fresh exact seed lower absent')
    require(result.get('physical_dc_lower_bound_certified') is False, 'Unsupported seed claim')
    activation=result.get('activation_final',{})
    require(activation.get('evaluations')==2 and activation.get('admitted')==1,'Seed terminal support was installed or evaluation count changed')
    require(result.get('base_matrix_artifact')==result['rounds'][0]['matrix_snapshot'],'Seed base snapshot alias drift')
    for index,lower in enumerate(result['exact_lp_lowers']):
        require(lower['cut_batches']==index and lower['activation_snapshot']['admitted']==index
            and lower['activation_snapshot']['evaluations']==index
            and lower['certificate_relabels_promoted_matrix'] is False,'Seed certificate snapshot scope')
    return True


def read_complete(directory):
    f = helpers()
    result = f.strict_json(Path(directory)/'result.json')
    completion = f.strict_json(Path(directory)/'completion.json')
    require(completion.get('result_sha256') == f.sha256(Path(directory)/'result.json') and
        completion.get('passed') is result.get('passed') and result.get('result_complete') is True,
        'Incomplete/mismatched worker result')
    return result


def physical_worker_allowed(state, best, whole_remaining):
    return best is not None and whole_remaining > 61. and not state.get('mechanism_failed', False)


def terminal_gate(state, *, whole_seconds):
    return (state.get('advancement_qualified') is True and state.get('quality_failed') is False and state.get('final_upper_admitted') is True
        and state.get('interval', {}).get('qualified') is True and state.get('terminal_local_checkpoint_verified') is True
        and state.get('ledger', {}).get('in_budget') is True and finite(whole_seconds) and whole_seconds <= WHOLE_CAP
        and state.get('physical_dc_lower_bound_certified') is False)


def verify_export(identity):
    """The actually solved files must still be the exact read-back master."""
    f = helpers()
    require(identity.get('api_fidelity_verified') is True,'Missing native matrix fidelity gate')
    for prefix in ('model','expected','api_report','row_sidecar'):
        require(f.sha256(identity[prefix+'_path']) == identity[prefix+'_sha256'],
            'Changed exported master artifact: '+prefix)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ('out','source-manifest','source-manifest-sha256','source-reference','arm-manifest','arm-manifest-sha256'):
        ap.add_argument('--'+key, required=True)
    a = ap.parse_args(argv)
    require(sys.dont_write_bytecode and __debug__, 'Require Python -B and assertions')
    deadline = START+WHOLE_CAP
    f = helpers()
    import current_scuc.binding as b
    from current_scuc import receipts as local
    from current_scuc import process_runner as process
    freeze = Path(a.source_manifest).resolve()
    common.verify_source_freeze(freeze, a.source_manifest_sha256)
    require(b.sha(a.arm_manifest) == a.arm_manifest_sha256, 'Candidate manifest changed')
    reference = local.validate_source_reference(b.read(a.source_reference))
    require(reference['source_manifest_sha256'] == a.source_manifest_sha256, 'Wrong local source binding')
    import current_scuc.heldout as heldout
    cfgpath = heldout.config_path()
    os.environ['PRIMAL_CACHE_CONFIG'] = str(cfgpath)
    os.environ['PRIMAL_CACHE_CONFIG_SHA256'] = b.sha(cfgpath)
    cfg = b.config()
    b.write=bounded_write
    b.verify_freeze()
    process.apply_limits()  # Prospective copy preserves 7 GiB AS and applies 512 MiB soft/hard file size.
    out = Path(a.out).resolve()
    require(not out.is_relative_to(ROOT) and out.parent.is_dir() and not out.exists(),
        'Fresh candidate-only output required')
    budget = storage()
    whole_admission = local.admit_whole(out.parent)
    require(whole_admission['block_bytes']==4096,'Whole storage bound requires reviewed 4-KiB filesystem')
    out.mkdir()
    checkpoints = local.Checkpoints(out, reference, deadline)
    state = dict(schema='adaptive-line-integer-phase/v1', run_directory=str(out), passed=False, outcome='running',
        quality_failed=False, final_upper_admitted=False, physical_dc_lower_bound_certified=False,
        lower_domain=no_shedding.DOMAIN, comparator_authorized=False, trace=[], lower_records=[],
        carry_preparations=[],mechanism_tested=False,mechanism_failed=False,subset_model_complete=False,advancement_qualified=False,
        cut_batches=0, cut_nnz=0, terminal_archive_acknowledged=False, terminal_local_checkpoint_verified=False,
        cloud_archive_status='optional_external_archival', remotely_durable=False, locally_complete=False, whole_cap_seconds=WHOLE_CAP,
        source_manifest_sha256=a.source_manifest_sha256, arm_manifest_sha256=a.arm_manifest_sha256,
        whole_run_storage_admission=whole_admission)
    ledger = Ledger()
    last_receipt = {'available': False}
    best = None
    costs = {}

    def save():
        state['ledger'] = ledger.record()
        state['whole_seconds_before_write'] = time.monotonic()-START
        state['storage_admissions']=list(IO_ADMISSIONS)
        state['native_output_limits']=list(NATIVE_LIMIT_RECORDS)
        f.write_json(out, 'STATE.json', state, costs)

    def archive(point, kind, accepted=False):
        start_output_phase(out,'stage metadata before '+point)
        save()
        snapshot = out / ('checkpoint-state-%02d.json' % (len(state.get('local_checkpoints', [])) + 1))
        b.write(snapshot, state, fresh=True)
        files = sorted(p for p in out.rglob('*') if p.is_file()
            and 'durability' not in p.relative_to(out).parts and 'environment' not in p.relative_to(out).parts
            and p.name != 'STATE.json' and p != snapshot and not p.name.endswith('.partial'))
        receipt_path = checkpoints.seal(point_id=point, stage_kind=kind,
            state=('unvalidated' if kind == 'post_native_solve' else 'validated' if accepted else 'check_failed'),
            artifacts=[local.Artifact('state_snapshot', snapshot)] + [local.Artifact('output_'+str(i),p) for i,p in enumerate(files)],
            measurements={'solver_process_wall_seconds':ledger.spent, 'integer_target': state.get('integer_target_identity_sha256')},
            cleanup_receipt=last_receipt)
        state.setdefault('local_checkpoints',[]).append(receipt_path)
        require(time.monotonic() < deadline, 'Whole deadline during local checkpoint')
        return receipt_path

    try:
        with Path(cfg['numerical_lock']).open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
            manifest,paths,identities = verify_manifest(a.arm_manifest,a.arm_manifest_sha256,deadline)
            alloc = ledger.allocation('seed',0,deadline-time.monotonic())
            require(alloc > 1, 'No seed process window')
            seedout = out/'seed'
            command = [cfg['python'],'-B','-s','-m','current_scuc.seed',
                '--out',str(seedout),'--manifest',a.arm_manifest,'--manifest-sha256',a.arm_manifest_sha256,
                '--deadline',str(time.monotonic()+alloc-1.)]
            budget=storage()
            start_output_phase(out,'seed worker launch',[
                budget.WriteBound(out/'seed.log',512*1024**2,'Python seed stdout','prospective512MiB process file limit'),
                budget.WriteBound(seedout/'native.log',budget.NATIVE_FILE_LIMIT,'seed synchronous native log','temporary64MiB native-only soft file limit')])
            last_receipt = process.run(command,out/'seed.log',out,alloc)
            debit_ok = ledger.debit('seed',alloc,last_receipt)
            b.write(out/'seed.process.json',last_receipt,fresh=True)
            state['seed_native_archive'] = archive('seed','post_native_solve')
            process.require_clean(last_receipt)
            require(debit_ok,'Seed process/600 ledger exceeded')
            seed = read_complete(seedout)
            seed_eligible(seed)
            require(seed['verified_manifest_sha256'] == a.arm_manifest_sha256,'Seed binding mismatch')
            state['seed'] = seed
            state['seed_checked_archive'] = archive('seed','post_full_check',True)
            # Deliberately repeat factors in this process; saved factors never enter.
            require(ledger.allocation('mip',1,deadline-time.monotonic()) > PROCESS_RESERVE, 'No MIP preparation window')
            start_output_phase(out,'fresh parent topology preparation')
            model,projection,capi,qa,oracle,original,projected,metadata,data = prepare(paths,manifest,deadline-FINAL_RESERVE)
            state['loaded_runtime'] = f.verify_loaded_runtime(identities)
            master = module('_integer_master', BASE/'master.py')
            require(seed['original_model_hashes'] == model.model_hashes(original) and seed['full_scope'] == metadata['full_scope'],
                'Seed/current target mismatch')
            batches = read_bundle(seedout,seed['batches_artifact'])
            require(len(batches) == 2,'Exactly two fresh seed batches required')
            balance_nnz = int(metadata['balance_nonzeros'])
            runtime=common.ADAPTIVE_RUNTIME=adaptive.Runtime(oracle,metadata,out)
            runtime.prior_requests=seed['adaptive_cache']['requests']
            runtime.check_requests()
            for batch in batches:
                projected,metadata,_=adaptive.install(projected,metadata,batch)
                runtime.adopt(batch)
                state['cut_batches'] += 1
                state['cut_nnz'] += batch['nnz']
            runtime.expected=projected
            state['seed_promotion']=dict(installed_batches=2,evaluations=adaptive.activation(metadata).evaluations,
                promoted_map_hash=metadata['map_hash'],promoted_matrix_identity=metadata['matrix_identity'],
                second_seed_lower_remains_one_batch=True,extra_LP_calls=0,extra_point_evaluations=0)
            initial = master.restore_integrality(projected,metadata,original)
            target = initial['identity']['integer_target_identity_sha256']
            state['integer_target_identity_sha256'] = target
            state['integer_target'] = initial['identity']
            for lower in seed['exact_lp_lowers']:
                require(lower['sense'] == 1 and lower['offset'] == 0 and
                    lower['full_scope_identity_sha256'] == metadata['full_scope_identity_sha256'] and
                    lower['hard_zero_subset_identity_sha256'] == metadata['hard_zero_subset']['identity_sha256'] and
                    lower['lower_domain'] == no_shedding.DOMAIN and seed['hard_zero_subset'] == metadata['hard_zero_subset'], 'Seed lower target mismatch')
                state['lower_records'].append(dict(lower,integer_target_identity_sha256=target,
                    source_manifest_sha256=a.source_manifest_sha256, arm_manifest_sha256=a.arm_manifest_sha256))
            cut_prefix=[dict(source='seed',artifact=seed['batches_artifact'])]
            previous_matrix = None
            for call in range(1,MAX_CALLS+1):
                alloc = ledger.allocation('mip',call,deadline-time.monotonic())
                if alloc <= PROCESS_RESERVE:
                    state['outcome'] = 'fixed_budget_stop'; break
                rd = out/f'mip-{call:02d}'; rd.mkdir()
                restored = master.restore_integrality(projected,metadata,original)
                require(restored['identity']['integer_target_identity_sha256'] == target,'Integer target changed')
                current_hash = model.model_hashes(restored['expected'])
                if current_hash == previous_matrix:
                    require(call==2 and 'discovery_proof_transition' in state,'Unchanged master rerun forbidden')
                    carry.validate_transition(state,call,stage='scheduled')
                exported = master.export_master(restored,rd/'master.mps',paths['library'])
                if call==2 and 'discovery_proof_transition' in state:
                    carry.same_transition_master(state['trace'][0]['master_identity'],exported['identity'])
                start = None; prepared = None; request_path = None; request_sha = None
                if call > 1:
                    state['pending_master']=dict(call=call,identity=exported['identity'],
                        cut_batches=state['cut_batches'],cut_prefix=list(cut_prefix))
                    prep_alloc=ledger.allocation('carry',call,deadline-time.monotonic())
                    if prep_alloc <= 1.:
                        state['outcome']='carry_resource_stop_before_preparation';break
                    prep_record=dict(target_call=call,allocation_seconds=prep_alloc)
                    state['carry_preparations'].append(prep_record)
                    save()
                    snapshot=rd/'carry-state.json';b.write(snapshot,state,fresh=True)
                    request=dict(schema=carry.SCHEMA,run_directory=str(out),state_path=str(snapshot),
                        state_sha256=f.sha256(snapshot),source_manifest_path=str(freeze),
                        source_manifest_sha256=a.source_manifest_sha256,arm_manifest_path=str(Path(a.arm_manifest).resolve()),
                        arm_manifest_sha256=a.arm_manifest_sha256,target_call=call,pending_master=state['pending_master'],
                        seed_result_path=str(seedout/'result.json'),seed_result_sha256=f.sha256(seedout/'result.json'))
                    request_path=rd/'carry-request.json';b.write(request_path,request,fresh=True);request_sha=f.sha256(request_path)
                    prep_record.update(request_path=str(request_path),request_sha256=request_sha)
                    try:
                        prep_out=rd/'carry'
                        command=[cfg['python'],'-B','-s','-m','current_scuc.carry',
                            '--request',str(request_path),'--request-sha256',request_sha,'--out',str(prep_out),
                            '--deadline',str(time.monotonic()+prep_alloc-1.)]
                        start_output_phase(rd,'carry Python worker launch',[budget.WriteBound(rd/'carry.log',512*1024**2,
                            'Python carry stdout','prospective512MiB process file limit')])
                        last_receipt=process.run(command,rd/'carry.log',out,prep_alloc)
                        debit_ok=ledger.debit('carry',prep_alloc,last_receipt)
                        prep_record['process']=last_receipt;b.write(rd/'carry.process.json',last_receipt,fresh=True)
                        process.require_clean(last_receipt);require(debit_ok,'carry process/600 ledger exceeded')
                        prepared=read_complete(prep_out);prep_record['preparation']=prepared
                        start=carry.verify_prepared(prepared,request_path,request_sha,exported['identity'])
                    except BaseException as exc:
                        prep_record['error']=type(exc).__name__+': '+str(exc)
                        prep_record['storage_admission_failure']=getattr(exc,'receipt',{})
                        state.update(quality_failed=True,mechanism_failed=True,outcome='carry_preparation_failed')
                        break
                role = options.role_for_call(call)
                optpath = rd/'solver.options'; optpath.write_text(options.option_text(role))
                common.verify_source_freeze(freeze,a.source_manifest_sha256)
                # Take the final allocation after export; probe overhead remains
                # whole-arm charged. Stop if it consumes the reserved window.
                alloc = ledger.allocation('mip',call,deadline-time.monotonic())
                if alloc <= PROCESS_RESERVE:
                    state['outcome'] = 'window_exhausted_after_export'; break
                native = alloc-PROCESS_RESERVE
                probe = options.probe(cfg,optpath,native,start=start,role=role)
                if ledger.allocation('mip',call,deadline-time.monotonic()) < alloc:
                    state['outcome'] = 'window_exhausted_after_options'; break
                b.write(rd/'options-readback.json',probe,fresh=True)
                if call==2 and 'discovery_proof_transition' in state:
                    carry.verify_transition_proof(state,exported['identity'],probe,start)
                solution = rd/'solution.sol'
                command = options.command(cfg,rd/'master.mps',optpath,solution,native,start=start,role=role)
                row = dict(call=call,role=role,cut_batches=state['cut_batches'],native_limit_seconds=native,
                    allocation_seconds=alloc,incumbent_input=(str(start) if start else None),no_basis_or_search_state_input=True,master_identity=exported['identity'],command=command,
                    options_artifacts=dict(options_path=str(optpath),options_sha256=f.sha256(optpath),
                        readback_path=str(rd/'options-readback.json'),readback_sha256=f.sha256(rd/'options-readback.json')))
                state['trace'].append(row); save()
                verify_export(exported['identity'])
                require(f.sha256(optpath) == probe['options_sha256'],'Changed proof options')
                if start is not None:
                    carry.verify_prepared(prepared,request_path,request_sha,exported['identity'])
                if ledger.allocation('mip',call,deadline-time.monotonic()) < alloc:
                    row['launch_outcome'] = 'reserved_window_exhausted_before_launch'
                    state['outcome'] = 'window_exhausted_before_launch'
                    break
                row['native_output_shape']=native_shape_guard(exported['expected'],production=True)
                if call==2 and 'discovery_proof_transition' in state:
                    state['discovery_proof_transition']['outcome']='proof_attempted'
                wrapped,limit_evidence=native_command(command,rd,cfg,solver=True)
                row['native_limit_request']=limit_evidence
                start_output_phase(rd,'native MIP CLI',[budget.WriteBound(rd/name,budget.NATIVE_FILE_LIMIT,
                    'three fixed native CLI outputs','native exec64MiB file limit') for name in ('solver.log','Highs.log','solution.sol')])
                last_receipt = process.run(wrapped,rd/'solver.log',out,alloc,solver=False)
                last_receipt['native_limit_request']=limit_evidence
                debit_ok = ledger.debit('mip',alloc,last_receipt)
                b.write(rd/'solver.process.json',last_receipt,fresh=True)
                row['process'] = last_receipt
                row['native_archive'] = archive(f'mip-{call:02d}','post_native_solve')
                process.require_clean(last_receipt)
                row['native_limit_receipt']=native_receipt(rd,limit_evidence,last_receipt)
                last_receipt['native_limit_receipt']=row['native_limit_receipt']
                require(debit_ok,'MIP process/600 ledger exceeded')
                verify_export(exported['identity'])
                require(f.sha256(optpath) == probe['options_sha256'],'Changed proof options after native process')
                common.verify_source_freeze(freeze,a.source_manifest_sha256)
                if start is not None:
                    try:
                        carry.verify_prepared(prepared,request_path,request_sha,exported['identity'])
                        row['start_admission']=admission.check_admission((rd/'solver.log').read_text(),
                            carry.g.unrat(prepared['exact_check']['projected_objective_exact']))
                        state['mechanism_tested']=True
                    except BaseException as exc:
                        row['start_admission_error']=type(exc).__name__+': '+str(exc)
                        row['start_admission_failure_evidence']=getattr(exc,'evidence',None)
                        state.update(quality_failed=True,mechanism_failed=True,outcome='carry_initial_admission_failed')
                        break
                io = module('_integer_frozen_io',b.CORE/'canonical_mps_export/io_announcements.py')
                clean,row['io_filter'] = io.filter_known_io((rd/'solver.log').read_text(),rd/'master.mps',solution,solver=True)
                from current_scuc.core.driver.primal_and_bound import solver_report
                from current_scuc.contracts import LIBRARY
                preliminary_report = solver_report(clean,last_receipt,'mip',rd/'master.mps',LIBRARY,identities_valid=True)
                clean,row['advisory_filter'] = filter_scaling_advisories(clean, mip_report=preliminary_report,
                    measurement=last_receipt, model_path=rd/'master.mps', role=role)
                require(len(re.findall(r'^Solving report[ \t]*$',clean,re.M)) == 1,'Ambiguous top-level MIP reports')
                report = solver_report(clean,last_receipt,'mip',rd/'master.mps',LIBRARY,identities_valid=True)
                report = admit_report(report, role=role)
                row['report'] = report
                if report.get('bound_status_valid') is True:
                    state['lower_records'].append(lower_record(report,exported['identity'],state['cut_batches'],target_identity=target))
                require(solution.is_file(),'Missing native solution output is not explicit no-primal')
                parsed = master.parse_solution(solution,exported['expected'],role=role)
                if parsed is None:
                    state['outcome'] = 'no_usable_incumbent'; break
                require(parsed['status'] == report['status'],'Native report/point status mismatch')
                check = master.check_integer_point(exported['expected'],parsed,role=role)
                require(check['passed'] is True,'Current integer master QA failed')
                x = check.pop('x'); row['master_quality'] = check
                start_output_phase(rd,'full original oracle/lift evaluation')
                batch,evaluated = evaluate_point(x,original,metadata,oracle,rd,call+1,deadline-FINAL_RESERVE,
                    projection=projection,qa=qa,integer=True,master=master,persist_batch=False)
                row['evaluation'] = evaluated
                selected = best_lower(state['lower_records'],target)
                provisional = interval(selected['lower'],evaluated['provisional_upper'])
                require(provisional['passed'],'Invalid provisional interval')
                row['provisional_interval'] = provisional
                point = dict(directory=str(rd),evaluation=evaluated,master_identity=exported['identity'],call=call)
                if best is None or no_shedding.selection_key(point) < no_shedding.selection_key(best):
                    best = point
                row['selected_endpoint_interval'] = interval(selected['lower'],best['evaluation']['provisional_upper'])
                require(row['selected_endpoint_interval']['passed'],'Invalid selected endpoint interval')
                row['selected_endpoint_call'] = best['call']
                row['checked_archive'] = archive(f'mip-{call:02d}','post_full_check',True)
                row['checked_stage_binding']=carry.bind_checked_stage(row['checked_archive'],out,call,a.source_manifest_sha256,expected_row=row)
                if call==2 and 'discovery_proof_transition' in state:
                    state['discovery_proof_transition']['outcome']='proof_checked'
                previous_matrix = current_hash
                if no_shedding.stop_eligible(best['evaluation'], row['selected_endpoint_interval']):
                    metadata=adaptive.terminal(projected,metadata,batch)
                    state['outcome'] = 'provisional_target_met'; break
                if call == MAX_CALLS:
                    metadata=adaptive.terminal(projected,metadata,batch)
                    state['outcome'] = 'fixed_call_stop'; break
                row['continuation_support'] = no_shedding.excluding_support(batch, metadata, x, runtime.bank)
                if not row['continuation_support']['passed']:
                    if call==1 and report['discovery_stop_activated'] and row['selected_endpoint_interval']['gap']>.01:
                        prep_alloc=ledger.allocation('carry',2,deadline-time.monotonic())
                        proof_alloc=max(0.,min(180.,SOLVER_CAP-ledger.spent-prep_alloc,
                            deadline-time.monotonic()-FINAL_RESERVE-prep_alloc))
                        if prep_alloc>1. and proof_alloc>PROCESS_RESERVE:
                            state['ledger']=ledger.record()
                            carry.schedule_transition(state,cut_prefix,carry_allocation=prep_alloc,proof_allocation=proof_alloc)
                            metadata=adaptive.terminal(projected,metadata,batch)
                            save()
                            continue
                    metadata=adaptive.terminal(projected,metadata,batch)
                    state['outcome'] = 'no_materially_violated_new_network_support'; break
                require(state['cut_batches'] < 4,'Fixed schedule exceeds four batches')
                row['inserted_batch_artifact'] = evaluated['adaptive_support_artifact']
                cut_prefix.append(dict(source_call=call,artifact=row['inserted_batch_artifact']))
                projected,metadata,_=adaptive.install(projected,metadata,batch)
                runtime.expected=projected;runtime.adopt(batch)
                state['cut_batches'] += 1; state['cut_nnz'] += batch['nnz']
                state['adaptive_map_hash']=metadata['map_hash']
                state['combined_elementary_requests']=runtime.check_requests()
            if 'discovery_proof_transition' in state:
                state['discovery_proof_transition']['continuation_outcome']=state['outcome']
            if physical_worker_allowed(state,best,deadline-time.monotonic()):
                physical = module('_integer_physical',BASE/'physical.py')
                ev = best['evaluation']
                request = dict(source_path=str(paths['source']),source_sha256=f.sha256(paths['source']),
                    expected_path=str(paths['expected']),expected_sha256=f.sha256(paths['expected']),
                    mps_path=str(paths['mps']),mps_sha256=f.sha256(paths['mps']),mapping_pairs=[list(p) for p in f.PAIRS],
                    stored_lift_directory=best['directory'],stored_lift_artifact=ev['stored_lift_artifact'],
                    full_scope=metadata['full_scope'],full_literal_check=ev['full_source_quality'],
                    integer_target_identity=state['integer_target']['integer_target'],integer_target_identity_sha256=target,
                    source_binary_authority=metadata['source_binary_authority'],oracle_objective=ev['oracle_objective'],
                    provisional_upper=ev['provisional_upper'],hours=36,
                    retained_original_columns=ev['retained_original_columns'],retained_values_sha256=ev['retained_values_sha256'])
                reqpath = out/'physical-request.json'; b.write(reqpath,request,fresh=True)
                physout = out/'physical'
                physout.mkdir()
                allocation = min(300.,deadline-time.monotonic()-60.)
                command = [cfg['python'],'-B','-s','-m','current_scuc.physical',
                    '--request',str(reqpath),'--request-sha256',f.sha256(reqpath),'--out',str(physout)]
                start_output_phase(out,'final physical Python worker launch',[budget.WriteBound(out/'physical.log',512*1024**2,
                    'Python physical stdout','prospective512MiB process file limit')])
                last_receipt = process.run(command,out/'physical.log',out,allocation)
                b.write(out/'physical.process.json',last_receipt,fresh=True)
                process.require_clean(last_receipt)
                checked = physical.read_result(physout,reqpath,f.sha256(reqpath))
                require(checked.get('passed') is True,'Final direct physical quality failed')
                state['physical'] = checked
                state['numerical_target_witness_checked'] = True
                state['interval'] = interval(best_lower(state['lower_records'],target)['lower'],checked['checked_upper'])
                require(state['interval']['passed'],'Final endpoint ordering failed')
                state['subset_model_complete']=state['interval']['qualified']
                state['positive_slack_totals_MWh']={k:v['positive_sum_MWh'] for k,v in checked['slack_metrics'].items()}
                state['negligible_slack_guard']=all(finite(v) and 0<=v<=1e-5 for v in state['positive_slack_totals_MWh'].values())
                state['final_upper_admitted'] = state['negligible_slack_guard']
                state['selected_point_role'] = 'production_quality_endpoint' if state['final_upper_admitted'] else 'diagnostic_target_feasible_only'
                state['advancement_qualified']=(state['subset_model_complete'] and state['negligible_slack_guard']
                    and not state['quality_failed'] and not state['mechanism_failed'])
                state['selected_final_call']=best['call']
                if not state['mechanism_failed']:
                    state['outcome'] = ('target_met_pending_local_receipt' if state['advancement_qualified'] else
                        'hard_zero_subset_complete_material_overflow' if state['subset_model_complete'] else 'checked_open_interval')
            else:
                state.setdefault('outcome','no_checked_upper')
            state['terminal_stage_receipt'] = archive('terminal','post_full_check',state['final_upper_admitted'])
            state['terminal_local_checkpoint_verified'] = True
    except BaseException as exc:
        state.update(quality_failed=True,passed=False,outcome='failed_or_incomplete',error=type(exc).__name__+': '+str(exc),
            storage_admission_failure=getattr(exc,'receipt',{}))
        try:
            state['failure_metadata_receipt'] = local.failure_metadata(out, exc)
        except BaseException as sub:
            state['failure_archive_error'] = type(sub).__name__+': '+str(sub)
            state['failure_archive_admission'] = getattr(sub,'receipt',{})
    finally:
        state['ledger'] = ledger.record()
        state['whole_phase_seconds'] = time.monotonic()-START
        state['passed'] = terminal_gate(state,whole_seconds=state['whole_phase_seconds'])
        state['local_numerical_passed'] = state['passed']
        state['locally_complete'] = state['terminal_local_checkpoint_verified']
        state['cloud_archive_status'] = 'optional_external_archival'
        state['remotely_durable'] = False
        if state['passed']:
            state['outcome'] = 'checked_one_percent_integer_interval'
        if 'discovery_proof_transition' in state:
            state['discovery_proof_transition']['terminal_outcome']=state['outcome']
        state['mechanism_status']=('failed' if state['mechanism_failed'] else
            'actual_feasible_start_admitted' if state['mechanism_tested'] else 'carry_untested')
        state['result_complete'] = True
        try:
            start_output_phase(out,'terminal state/result writes')
            save(); f.write_json(out,'result.json',state,costs)
            if time.monotonic() >= deadline:
                state.update(passed=False,local_numerical_passed=False,outcome='whole_deadline_during_terminal_write')
                f.write_json(out,'result.json',state,costs)
            f.write_json(out,'completion.json',dict(result_sha256=f.sha256(out/'result.json'),passed=state['passed'],
                parent_process_start_through_reap_is_authoritative=True),costs)
        except BaseException as terminal_error:
            state['passed']=False
            state['local_numerical_passed']=False
            # Bounded failure evidence only; preserve every original and partial.
            storage().terminal_failure_json(out/'failure-admission.json',dict(schema='discovery-storage-failure-v1',passed=False,
                phase='terminal writes',error_type=type(terminal_error).__name__,
                admission=getattr(terminal_error,'receipt',{}),whole_seconds=time.monotonic()-START),
                all_children_reaped=(not process.slot_envelope.children_of(os.getpid())))
    return 0 if state['passed'] else 2


if __name__ == '__main__':
    budget=storage()
    with budget.active_writer_reservations([budget.WriteBound(Path('/proc/self/fd/1').resolve(),512*1024**2,
            'Python phase stdout','prospective512MiB process file limit')]):
        raise SystemExit(main())
