#!/usr/bin/env python3
"""TEST ONLY: Fixed triangle: two seed LPs, discovery, production transition/carry, proof,
one full-integer reference and independent original/physical parity checks.

Invoke only through tests.run_tiny_components --suite transition after explicit
execution approval. No real-case model is constructed or historical result reused.
A passing test requires the unchanged production slack-quality stop to fail.
"""
import time
START = time.monotonic()
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import sys
from current_scuc.common import ROOT, helpers, module, require, append_batch, evaluate_point, GuardedLP, native_command, native_receipt, native_shape_guard, bounded_write, start_output_phase, storage
import current_scuc.diagnostics as diagnostics
import current_scuc.options as options
import current_scuc.carry as carry
import current_scuc.admission as admission
import current_scuc.adaptive as adaptive
import current_scuc.common as common
import current_scuc.no_shedding as no_shedding
from current_scuc.seed import run_seed
from tests import fixed_triangle as fixture_module
from tests import fixed_triangle as tiny_harness
from current_scuc import binding as b, process_runner as process
from current_scuc.native_exec import parse_solver_random_seed


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True)
    ap.add_argument('--worker-source-sha256', required=True)
    ap.add_argument('--fixture-source-sha256', required=True)
    ap.add_argument('--seed', type=parse_solver_random_seed, choices=(0, 1), default=0)
    a=ap.parse_args(argv)
    require(sys.dont_write_bytecode and __debug__,'Run tiny Python -B with assertions')
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key]='1'
    require(b.sha(__file__) == a.worker_source_sha256, 'Tiny worker source changed')
    require(b.sha(fixture_module.__file__) == a.fixture_source_sha256, 'Tiny fixture source changed')
    frozen=b.verify_freeze()
    f=helpers(); deadline=START+170.
    cfg=b.config()
    b.write=bounded_write
    process.apply_limits()
    from current_scuc import runtime as local_runtime
    from current_scuc.common import native_call_guard
    installed=local_runtime.discover_runtime(cfg['binary'],cfg['runtime_manifest'])
    with native_call_guard('tiny runtime ABI qualification'):
        runtime_qualification=local_runtime.qualify_capi(installed)
    out=Path(a.out).absolute()
    require(out.parent.is_dir() and not out.exists() and not out.is_relative_to(ROOT),
        'Fresh bounded tiny output outside the package required')
    out.mkdir()
    status=dict(passed=False,fixture_fixed_before_outcomes=True,production_result=False,
        production_comparator_authorized=False,real_case_constructed=False,trace=[],source_freeze=frozen,
        solver_random_seed=a.seed)
    try:
        with Path(cfg['numerical_lock']).open('a+') as lock:
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            model,old_projection,old_capi,qa,oracle_module=f.load_modules()
            projection,capi=adaptive.adapter(),adaptive.native()
            generator=module('_integer_tiny_generator',ROOT/'core/scuc/generate.py')
            exporter=module('_integer_tiny_exporter',ROOT/'core/canonical_mps_export/export_v2.py')
            master=module('_integer_master',ROOT/'master.py')
            data,pairs=fixture_module.fixture()
            # Fixed pre-solve family delta retained from the existing tiny source.
            require(list(data['Generators']) == ['g0','g1'], 'Fixed family fixture units')
            for unit in data['Generators'].values():
                require(unit['Startup costs ($)'] == [0.] and unit['Startup delays (h)'] == [1]
                        and unit['Initial status (h)'] == -24, 'Fixed family fixture source changed')
                unit['Startup costs ($)'] = [1.]
            source=out/'source.json';source.write_text(json.dumps(data,indent=2)+'\n')
            require(b.sha(source)==cfg['inputs']['current']['sha256'], 'Fixed fixture source differs from launch input')
            built,_=generator.build(data,2,'n1',security_pairs=pairs)
            original=model.validate_model(exporter.intended_model(built))
            mps=out/'original-subset.mps';exporter.write_model(built,mps)
            expected_path=out/'original.expected.json'
            expected_path.write_text(json.dumps(master.json_value(original),allow_nan=False)+'\n')
            oracle=oracle_module.PreparedOracle(data,original,pairs,generator,dict(fixture='fixed-existing-triangle',
                source_sha256=f.sha256(source),expected_sha256=f.sha256(expected_path),mps_sha256=f.sha256(mps),
                generator_sha256=f.sha256(generator.__file__)),
                production_scope=False,deadline=deadline)
            oracle.source_data=data
            projected,metadata,_=adaptive.make_base(original,data,2,pairs,oracle.lodf,
                oracle.pins['source_sha256'],oracle.full_scope)
            require(len(metadata['retained_original_columns']) == 30 and sum(original['integrality']) == 12,
                'Tiny original retained-column or binary inventory changed')
            require((metadata['first_start_family']['row_count'],metadata['fixed_family_nnz']) == (4,10),
                    'Tiny complete-family rows not exercised')
            status['first_start_family']=metadata['first_start_family']
            status['hard_zero_subset']=metadata['hard_zero_subset']
            require(metadata['hard_zero_subset']['changed_shed_upper_bounds'] == 6 and
                metadata['hard_zero_subset']['reserve_shortfall_columns'] == 0, 'Tiny hard-zero inventory')
            metadata['source_binary_authority']=master.source_binary_authority(data,2)
            seedout=out/'seed';seedout.mkdir()
            with GuardedLP(capi.PersistentLP,cfg['library'],seedout/'native.log',a.seed) as lp:
                lp.pass_model(projected)
                seeded=run_seed(lp,oracle,original,metadata,seedout,deadline,model=model,projection=projection,qa=qa)
                require(seeded['calls']==2 and seeded['retained_batches']==2 and seeded['oracle_evaluations']==2,
                    'Tiny seed schedule changed')
                require(type(lp.options.get('random_seed')) is int and lp.options['random_seed'] == a.seed,
                    'Tiny LP effective solver seed disagrees with launch')
                seeded.update(solver_random_seed=a.seed, native_options=dict(lp.options))
                status['seed']=seeded
            seeded.update(projection_artifact=f.bundle(seedout,'projection',metadata,{}),
                original_model_hashes=model.model_hashes(original))
            f.write_json(seedout,'result.json',seeded,{})
            tiny_arm={'solver_random_seed':a.seed,'inputs':{role:{'path':str(path),'sha256':f.sha256(path)} for role,path in
                [('source',source),('expected',expected_path),('library',Path(cfg['library']))]}}
            tiny_arm_path=out/'tiny-arm.json';f.write_json(out,'tiny-arm.json',tiny_arm,{})
            state=dict(run_directory=str(out),source_manifest_sha256=b.sha(__file__),
                arm_manifest_sha256=f.sha256(tiny_arm_path),solver_random_seed=a.seed,seed=seeded,trace=[],
                quality_failed=False,mechanism_failed=False,carry_preparations=[],cut_batches=2)
            cut_prefix=[dict(source='seed',artifact=seeded['batches_artifact'])]
            from current_scuc.common import read_bundle
            batches=read_bundle(seedout,seeded['batches_artifact'])
            # Tiny reuses its fresh process-local cache; production prepares a
            # separate fresh parent cache and debits seed requests explicitly.
            runtime=common.ADAPTIVE_RUNTIME
            runtime.bank=[]
            for batch in batches:
                projected,metadata,_=adaptive.install(projected,metadata,batch)
                runtime.adopt(batch)
            runtime.expected=projected
            io=module('_integer_frozen_io',b.CORE/'canonical_mps_export/io_announcements.py')
            from current_scuc.core.driver.primal_and_bound import solver_report
            from current_scuc.contracts import LIBRARY

            def solve(expected,path,tag,start=None,prepared=None,role=options.PROOF_ROLE,
                      *,transition_state=None,target_identity=None,carry_request=None):
                rd=path.parent; solution=rd/'solution.sol';opt=rd/'solver.options';opt.write_text(options.option_text(role))
                probe=options.probe(cfg,opt,20.,start=start,role=role,solver_random_seed=a.seed)
                require(type(probe['options'].get('random_seed')) is int
                    and probe['options']['random_seed'] == a.seed
                    and type(probe.get('solver_random_seed')) is int and probe['solver_random_seed'] == a.seed,
                    'Tiny MIP effective solver seed disagrees with launch')
                b.write(rd/'options-readback.json',probe,fresh=True)
                if transition_state is not None:
                    carry.verify_transition_proof(transition_state,target_identity,probe,start,production=False)
                command=options.command(cfg,path,opt,solution,20.,start=start,role=role,solver_random_seed=a.seed)
                b.verify_freeze()
                require(b.sha(fixture_module.__file__)==a.fixture_source_sha256,'Tiny fixture changed')
                if prepared is not None:
                    carry.verify_prepared(prepared,carry_request,f.sha256(carry_request),target_identity)
                shape=native_shape_guard(expected)
                wrapped,limit_evidence=native_command(command,rd,cfg,solver=True)
                budget=storage();start_output_phase(rd,'tiny native CLI',[budget.WriteBound(rd/name,budget.NATIVE_FILE_LIMIT,
                    'three fixed native CLI outputs','native exec64MiB file limit') for name in ('solver.log','Highs.log','solution.sol')])
                require(deadline-time.monotonic()>80.,'Tiny whole window cannot contain the fixed CLI slot')
                receipt=process.run(wrapped,rd/'solver.log',out,80.,solver=False)
                receipt.update(native_limit_request=limit_evidence,native_output_shape=shape)
                process.require_clean(receipt)
                receipt['native_limit_receipt']=native_receipt(rd,limit_evidence,receipt)
                b.verify_freeze()
                require(b.sha(fixture_module.__file__)==a.fixture_source_sha256,'Tiny fixture changed')
                if prepared is not None:
                    carry.verify_prepared(prepared,carry_request,f.sha256(carry_request),target_identity)
                b.write(rd/'solver.process.json',receipt,fresh=True);process.require_clean(receipt)
                start_admission=(admission.check_admission((rd/'solver.log').read_text(),
                    carry.g.unrat(prepared['exact_check']['projected_objective_exact'])) if start else None)
                clean,io_receipt=io.filter_known_io((rd/'solver.log').read_text(),path,solution,solver=True)
                preliminary_report=solver_report(clean,receipt,'mip',path,LIBRARY,identities_valid=True)
                clean,advisory=diagnostics.filter_scaling_advisories(clean,mip_report=preliminary_report,
                    measurement=receipt,model_path=path,role=role)
                require(len(re.findall(r'^Solving report[ \t]*$',clean,re.M))==1,'Tiny ambiguous top-level report')
                report=solver_report(clean,receipt,'mip',path,LIBRARY,identities_valid=True)
                report=diagnostics.admit_report(report,role=role)
                if role==options.DISCOVERY:
                    require(report['global_lower'] is None and not report['bound_status_valid'] and
                        not report['certificate_bound_eligible'] and not report['upper_bound_eligible'],'Tiny discovery bound leak')
                else:
                    require(report['bound_status_valid'] and report['status']=='Optimal','Tiny clean finite global bound required')
                parsed=master.parse_solution(solution,expected,role=role)
                require(parsed is not None,'Tiny usable incumbent absent')
                require(parsed['status']==report['status'],'Tiny point/report status mismatch')
                checked=master.check_integer_point(expected,parsed,role=role)
                require(checked['passed'],'Tiny integer point failed')
                return checked.pop('x'),dict(tag=tag,role=role,solver_random_seed=a.seed,report=report,point_check=checked,master_quality=checked,process=receipt,
                    options_readback=probe,io_filter=io_receipt,advisory_filter=advisory,start_admission=start_admission,
                    incumbent_input=(str(start) if start else None),no_basis_or_search_state_input=True,
                    native_limit_seconds=20.,allocation_seconds=80.,command=command,
                    native_limit_request=limit_evidence,native_limit_receipt=receipt['native_limit_receipt'],
                    initial_start_objective=(prepared['exact_check']['projected_objective'] if prepared else None))

            best=None
            target=None
            base_empty_columns=seeded['rounds'][0]['activation_before_solve']['nret']+2
            status['empty_to_active_columns_created']=projected['num_col']-base_empty_columns
            require(status['empty_to_active_columns_created']>0,'Tiny never activated adaptive line columns')
            require(adaptive.activation(metadata).admitted==2 and adaptive.activation(metadata).evaluations==2,
                'Tiny seed prefix accounting changed')
            for call in (1,2):
                rd=out/f'mip-{call:02d}';rd.mkdir()
                restored=master.restore_integrality(projected,metadata,original)
                exported=master.export_master(restored,rd/'master.mps',cfg['library'])
                target=restored['identity']
                state['integer_target_identity_sha256']=target['integer_target_identity_sha256']
                prepared=None;start=None;request_path=None
                if call==2:
                    # This invokes the production prefix branch: two installed seeds,
                    # then precisely the checked non-installed discovery evaluation.
                    state['pending_master']=dict(call=2,identity=exported['identity'],cut_batches=2,cut_prefix=list(cut_prefix))
                    prep_alloc=min(30.,deadline-time.monotonic()-80.)
                    require(prep_alloc>1.,'Tiny carry allocation exhausted; transition stays consumed')
                    prep_record=dict(target_call=2,allocation_seconds=prep_alloc)
                    state['carry_preparations'].append(prep_record)
                    snapshot=rd/'carry-state.json';b.write(snapshot,state,fresh=True)
                    request=dict(schema=carry.SCHEMA,run_directory=str(out),state_path=str(snapshot),state_sha256=f.sha256(snapshot),
                        source_manifest_path=str(Path(__file__).resolve()),source_manifest_sha256=b.sha(__file__),
                        arm_manifest_path=str(tiny_arm_path),arm_manifest_sha256=f.sha256(tiny_arm_path),target_call=2,
                        pending_master=state['pending_master'],seed_result_path=str(seedout/'result.json'),seed_result_sha256=f.sha256(seedout/'result.json'))
                    request_path=rd/'carry-request.json';b.write(request_path,request,fresh=True)
                    prepout=rd/'carry';prepout.mkdir()
                    prep_started=time.monotonic()
                    try:
                        prepared=carry.prepare(request,prepout,min(deadline,time.monotonic()+prep_alloc),production=False)
                    finally:
                        prep_record['process_wall_seconds']=time.monotonic()-prep_started
                    require(prep_record['process_wall_seconds']<=prep_alloc,'Tiny carry allocation exceeded')
                    prepared['request_sha256']=f.sha256(request_path);b.write(prepout/'result.json',prepared,fresh=True)
                    start=carry.verify_prepared(prepared,request_path,f.sha256(request_path),exported['identity'])
                    prep_record['preparation']=prepared
                    status['carry_preparations']=state['carry_preparations']
                    require(prepared['mapping']['binary_values_rounded'] is False,'Tiny carry repaired binaries')
                x,row=solve(exported['expected'],rd/'master.mps','candidate',start,prepared,options.role_for_call(call),
                    transition_state=(state if call==2 else None),target_identity=exported['identity'],carry_request=request_path)
                batch,evaluation=evaluate_point(x,original,metadata,oracle,rd,call+1,deadline,
                    projection=projection,qa=qa,integer=True,master=master,persist_batch=False)
                lower=seeded['lower_exact_lp'] if call==1 else max(seeded['lower_exact_lp'],row['report']['global_lower'])
                span=diagnostics.interval(lower,evaluation['provisional_upper'])
                require(span['passed'],'Tiny endpoint ordering')
                point=dict(evaluation=evaluation,call=call,directory=str(rd))
                if best is None or no_shedding.selection_key(point)<no_shedding.selection_key(best):best=point
                selected_span=diagnostics.interval(lower,best['evaluation']['provisional_upper'])
                require(selected_span['passed'],'Tiny selected endpoint ordering')
                row.update(call=call,evaluation=evaluation,interval=span,provisional_interval=span,
                    selected_endpoint_interval=selected_span,selected_endpoint_call=best['call'],
                    master_identity=exported['identity'],model_hashes=model.model_hashes(projected),cut_batches=2,
                    options_artifacts=dict(options_path=str(rd/'solver.options'),options_sha256=f.sha256(rd/'solver.options'),
                        readback_path=str(rd/'options-readback.json'),readback_sha256=f.sha256(rd/'options-readback.json')))
                row['production_stop_eligible']=no_shedding.stop_eligible(best['evaluation'],selected_span)
                proof=rd/'tiny-point-check.json';b.write(proof,evaluation,fresh=True)
                row.update(checked_archive=str(proof),checked_stage_binding=dict(path=str(proof),sha256=f.sha256(proof)))
                row['continuation_support']=no_shedding.excluding_support(batch,metadata,x,runtime.bank)
                state['trace'].append(row);status['trace'].append(row)
                require(row['production_stop_eligible'] is False,'Known material-overflow tiny became a production endpoint')
                require(row['continuation_support']['passed'] is False and
                    row['continuation_support']['materially_violated_rows']==0,
                    'Fixed tiny unexpectedly needs a new support; no replacement fixture or extra call is allowed')
                if call==1:
                    remaining=deadline-time.monotonic()
                    carry_allocation=min(30.,remaining-80.)
                    transition=carry.schedule_transition(state,cut_prefix,
                        carry_allocation=carry_allocation,proof_allocation=min(80.,remaining-carry_allocation),
                        production=False)
                    status['discovery_proof_transition']=transition
                else:
                    require(row['start_admission']['passed'],'Tiny proof actual CLI start admission')
                before=copy.deepcopy(metadata)
                metadata=adaptive.terminal(projected,metadata,batch)
                require(adaptive.activation(metadata).admitted==2 and adaptive.activation(metadata).evaluations==call+2,
                    'Tiny non-installed evaluation accounting changed')
                require(before['projected_hashes']==metadata['projected_hashes'] and
                    before['map_hash']==metadata['map_hash'] and before['line_caps']==metadata['line_caps'],
                    'Tiny non-installed evaluation changed the master')
            require(len(status['trace'])==2 and len(state['carry_preparations'])==1,'Tiny fixed discovery/proof schedule changed')
            require(status['trace'][0]['model_hashes']==status['trace'][1]['model_hashes'],'Tiny transition changed the master')
            require(best['call']==2,'Tiny proof did not supply the independently checked parity point')
            status['transition_outcome']='proof_checked_no_new_support'
            state['discovery_proof_transition']['outcome']=status['transition_outcome']
            status['production_prefix_preparation_called']=True
            # Explicit full integer reference is authorized only in this tiny.
            reference,_=generator.build(data,2,'n1',security_pairs=fixture_module.FULL_TINY_PAIRS)
            reference_original=model.validate_model(exporter.intended_model(reference))
            reference_expected,reference_subset=no_shedding.target_model(reference_original,model)
            reference.ub=list(reference_expected['col_upper'])
            require(model.compare_models(reference_expected,model.validate_model(exporter.intended_model(reference)))['passed'],
                'Tiny reference exact hard-zero transform failed')
            require(sum(reference_expected['integrality'])==sum(original['integrality'])==12,'Tiny original binaries lost')
            rr=out/'full-integer-reference';rr.mkdir();refpath=rr/'master.mps'
            exporter.write_model(reference,refpath)
            (rr/'expected.json').write_text(json.dumps(master.json_value(reference_expected),allow_nan=False)+'\n')
            mh=master.helpers()
            from current_scuc.common import native_call_guard
            with native_call_guard('tiny reference native readback',rr/'readback.log') as guard:
                api=mh.readback.verify_expected(reference_expected,refpath,cfg['library'],rr/'readback.log')
            api['native_output_limit']=guard
            f.write_json(rr,'readback.json',api,{})
            require(api['passed'],'Tiny explicit full integer readback failed')
            rx,ref=solve(reference_expected,refpath,'full_integer_reference')
            ref['hard_zero_subset']=reference_subset
            ref['target_subset_quality']=no_shedding.point_check(reference_original,rx,reference_subset,model)
            objective=ref['point_check']['linear_objective']
            parity_value=best['evaluation']['provisional_upper']
            require(abs(objective-parity_value)<=max(1e-5,1e-9*abs(objective)),'Tiny full-integer parity failed')
            status['reference_parity']=dict(passed=True,reference_original_objective=objective,compared_objective=parity_value,
                comparison='proof independently checked original upper',production_endpoint_eligible=False,
                original_lift_performed=True,production_prefix_preparation_called=True)
            status['full_integer_reference']=ref
            rd=Path(best['directory']);ev=best['evaluation']
            span=diagnostics.interval(max([seeded['lower_exact_lp']]+[r['report']['global_lower'] for r in status['trace'] if r['report']['bound_status_valid']]),ev['provisional_upper'])
            require(span['qualified'],'Tiny proof/reference interval remained open')
            status['physical_validation_point']='proof_checked_original_lift'
            request=dict(source_path=str(source),source_sha256=f.sha256(source),expected_path=str(expected_path),
                expected_sha256=f.sha256(expected_path),mps_path=str(mps),mps_sha256=f.sha256(mps),mapping_pairs=[list(p) for p in pairs],
                stored_lift_directory=str(rd),stored_lift_artifact=ev['stored_lift_artifact'],full_scope=metadata['full_scope'],
                full_literal_check=ev['full_source_quality'],integer_target_identity=target['integer_target'],
                integer_target_identity_sha256=target['integer_target_identity_sha256'],source_binary_authority=metadata['source_binary_authority'],
                oracle_objective=ev['oracle_objective'],provisional_upper=ev['provisional_upper'],hours=2,
                retained_values_sha256=ev['retained_values_sha256'])
            f.write_json(out,'physical-request.json',request,{})
            physical=module('_integer_physical',ROOT/'physical.py')
            po=out/'physical';po.mkdir()
            physical_result=physical.run(request,po,production=False)
            require(physical_result['passed'],'Tiny independent direct physical checks failed')
            require(abs(physical_result['checked_upper']-objective)<=max(1e-5,1e-9*abs(objective)),
                'Tiny final physical/full-reference parity failed')
            status['physical_reference_parity']=dict(passed=True,checked_upper=physical_result['checked_upper'],
                reference_original_objective=objective,tolerance=max(1e-5,1e-9*abs(objective)),
                candidate_endpoint_promoted=False)
            quality=no_shedding.slack_quality(original,common.read_bundle(rd,ev['stored_lift_artifact'])['values'])
            tiny_harness.require_expected_quality(quality)
            require(not no_shedding.stop_eligible(ev,span),'Tiny falsely passed production quality stop')
            status.update(candidate_passed=False, candidate_expected_nonpass_verified=True,
                candidate_outcome='material_shared_overflow', expected_shared_overflow_MWh=2.25)
            require(status['trace'][0]['role']==options.DISCOVERY and status['trace'][0]['options_readback']['options']['mip_max_improving_sols']==1, 'Tiny first role/options mismatch')
            require(status['trace'][1]['role']==options.PROOF_ROLE and status['trace'][1]['options_readback']['options']['mip_max_improving_sols']==2147483647,'Tiny proof defaults changed')
            require(status['trace'][0]['report']['discovery_stop_activated'] is True,'Tiny discovery did not activate solution limit')
            require(adaptive.activation(metadata).evaluations==4 and adaptive.activation(metadata).admitted==2,
                'Tiny final installed/evaluation counts changed')
            b.verify_freeze()
            require(b.sha(fixture_module.__file__)==a.fixture_source_sha256,'Tiny fixture changed')
            status['loaded_python_runtime']=local_runtime.verify_loaded_runtime(cfg['python_distribution_files'])
            status['loaded_native_runtime']=local_runtime.verify_native_mappings(installed)
            status.update(test_passed=True, test_outcome='expected_candidate_nonpass_components_passed',
                runtime_qualification=runtime_qualification, discovery_bound_excluded=True,discovery_stop_activated=True,event_stop_claim='activated',
                physical=physical_result,passed=True,genuine_second_master=False,exact_original_binary_count=12,
                exact_original_retained_column_count=30,
                adaptive_new_line_carry_exercised=False,unchanged_master_production_transition_exercised=True,
                candidate_stopped_naturally=True,production_advancement_qualified=False,
                fixture_stop_rule='exactly discovery then one production transition/proof, full reference, and known overflow failure',
                target_subset_quality_verified=True,quality=quality,
                point_evaluations=seeded['oracle_evaluations']+sum(r['evaluation']['oracle_evaluations'] for r in status['trace']),
                installed_batches=2,
                final_physical_passes=1,component_calls=0,seed_lp_calls=2,candidate_mip_calls=2,reference_mip_calls=1,
                full_integer_reference_objective=objective,candidate_interval=span)
    except BaseException as exc:
        status['error']=type(exc).__name__+': '+str(exc)
        if 'discovery_proof_transition' in status:
            status['transition_outcome']='failed_or_incomplete'
            status['discovery_proof_transition']['outcome']=status['transition_outcome']
        raise
    finally:
        from current_scuc.common import NATIVE_LIMIT_RECORDS
        status['native_output_limits']=list(NATIVE_LIMIT_RECORDS)
        status['whole_seconds_before_serialization']=time.monotonic()-START
        f.write_json(out,'result.json',status,{})
    print(json.dumps({'test_passed':status['test_passed'],'candidate_passed':status['candidate_passed'],
        'candidate_calls':len(status['trace']),
        'reference_objective':status['full_integer_reference_objective'],'whole_seconds':time.monotonic()-START}))


if __name__=='__main__': main()
