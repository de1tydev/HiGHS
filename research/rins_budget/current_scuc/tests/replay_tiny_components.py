#!/usr/bin/env python3
"""TEST ONLY: Fixed existing triangle: two fresh LP seed solves, checked carried-start integer cut iteration,
explicit full-integer reference and both independent physical checks.

Invoke only through tests.run_tiny_components after explicit execution approval.
No real-case model is constructed and no result is reused. A passing test
requires the candidate to fail the unchanged production slack-quality stop.
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
from current_scuc import binding as b, process_runner as process


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True)
    ap.add_argument('--worker-source-sha256', required=True)
    ap.add_argument('--fixture-source-sha256', required=True)
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
        runtime_qualification=runtime_qualification)
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
            require((metadata['first_start_family']['row_count'],metadata['fixed_family_nnz']) == (4,10),
                    'Tiny complete-family rows not exercised')
            status['first_start_family']=metadata['first_start_family']
            status['hard_zero_subset']=metadata['hard_zero_subset']
            require(metadata['hard_zero_subset']['changed_shed_upper_bounds'] == 6 and
                metadata['hard_zero_subset']['reserve_shortfall_columns'] == 0, 'Tiny hard-zero inventory')
            metadata['source_binary_authority']=master.source_binary_authority(data,2)
            seedout=out/'seed';seedout.mkdir()
            with GuardedLP(capi.PersistentLP,cfg['library'],seedout/'native.log') as lp:
                lp.pass_model(projected)
                seeded=run_seed(lp,oracle,original,metadata,seedout,deadline,model=model,projection=projection,qa=qa)
                require(seeded['calls']==2 and seeded['retained_batches']==2,'Tiny seed schedule changed')
                status['seed']=seeded
            seeded.update(projection_artifact=f.bundle(seedout,'projection',metadata,{}),
                original_model_hashes=model.model_hashes(original))
            f.write_json(seedout,'result.json',seeded,{})
            tiny_arm={'inputs':{role:{'path':str(path),'sha256':f.sha256(path)} for role,path in
                [('source',source),('expected',expected_path),('library',Path(cfg['library']))]}}
            tiny_arm_path=out/'tiny-arm.json';f.write_json(out,'tiny-arm.json',tiny_arm,{})
            state=dict(run_directory=str(out),source_manifest_sha256=f.sha256(__file__),
                arm_manifest_sha256=f.sha256(tiny_arm_path),seed=seeded,trace=[])
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

            def solve(expected,path,tag,start=None,prepared=None,role=options.PROOF_ROLE):
                rd=path.parent; solution=rd/'solution.sol';opt=rd/'solver.options';opt.write_text(options.option_text(role))
                probe=options.probe(cfg,opt,20.,start=start,role=role)
                command=options.command(cfg,path,opt,solution,20.,start=start,role=role)
                b.verify_freeze()
                shape=native_shape_guard(expected)
                wrapped,limit_evidence=native_command(command,rd,cfg,solver=True)
                budget=storage();start_output_phase(rd,'tiny native CLI',[budget.WriteBound(rd/name,budget.NATIVE_FILE_LIMIT,
                    'three fixed native CLI outputs','native exec64MiB file limit') for name in ('solver.log','Highs.log','solution.sol')])
                receipt=process.run(wrapped,rd/'solver.log',out,80.,solver=False)
                receipt.update(native_limit_request=limit_evidence,native_output_shape=shape)
                process.require_clean(receipt)
                receipt['native_limit_receipt']=native_receipt(rd,limit_evidence,receipt)
                b.verify_freeze()
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
                return checked.pop('x'),dict(tag=tag,role=role,report=report,point_check=checked,process=receipt,
                    options_readback=probe,io_filter=io_receipt,advisory_filter=advisory,start_admission=start_admission,
                    initial_start_objective=(prepared['exact_check']['projected_objective'] if prepared else None))

            best=None
            target=None
            base_empty_columns=seeded['rounds'][0]['activation_before_solve']['nret']+2
            status['empty_to_active_columns_created']=projected['num_col']-base_empty_columns
            require(status['empty_to_active_columns_created']>0,'Tiny never activated adaptive line columns')
            for index in range(3):
                rd=out/f'mip-{index+1:02d}';rd.mkdir()
                restored=master.restore_integrality(projected,metadata,original)
                exported=master.export_master(restored,rd/'master.mps',cfg['library'])
                target=restored['identity']
                state['integer_target_identity_sha256']=restored['identity']['integer_target_identity_sha256']
                prepared=None;start=None
                if index:
                    state['pending_master']=dict(call=index+1,identity=exported['identity'],cut_batches=index+2,cut_prefix=list(cut_prefix))
                    snapshot=rd/'carry-state.json';b.write(snapshot,state,fresh=True)
                    request=dict(schema=carry.SCHEMA,run_directory=str(out),state_path=str(snapshot),state_sha256=f.sha256(snapshot),
                        source_manifest_path=str(Path(__file__).resolve()),source_manifest_sha256=f.sha256(__file__),
                        arm_manifest_path=str(tiny_arm_path),arm_manifest_sha256=f.sha256(tiny_arm_path),target_call=index+1,
                        pending_master=state['pending_master'],seed_result_path=str(seedout/'result.json'),seed_result_sha256=f.sha256(seedout/'result.json'))
                    request_path=rd/'carry-request.json';b.write(request_path,request,fresh=True)
                    prepout=rd/'carry';prepout.mkdir();prepared=carry.prepare(request,prepout,min(deadline,time.monotonic()+30.),production=False)
                    prepared['request_sha256']=f.sha256(request_path);b.write(prepout/'result.json',prepared,fresh=True)
                    start=carry.verify_prepared(prepared,request_path,f.sha256(request_path),exported['identity'])
                    status.setdefault('carry_preparations',[]).append(prepared)
                x,row=solve(exported['expected'],rd/'master.mps','candidate',start,prepared,options.role_for_call(index+1))
                if prepared:
                    require(prepared['mapping']['binary_values_rounded'] is False,'Tiny carry repaired binaries')
                batch,evaluation=evaluate_point(x,original,metadata,oracle,rd,index+2,deadline,
                    projection=projection,qa=qa,integer=True,master=master,persist_batch=False)
                lower=seeded['lower_exact_lp'] if index==0 else max(seeded['lower_exact_lp'],row['report']['global_lower'])
                span=diagnostics.interval(lower,evaluation['provisional_upper'])
                require(span['passed'],'Tiny endpoint ordering')
                row.update(evaluation=evaluation,interval=span,model_hashes=model.model_hashes(projected))
                status['trace'].append(row)
                point=dict(evaluation=evaluation,call=index+1)
                prior=dict(evaluation=best[1],call=int(best[0].name.split('-')[-1])) if best else None
                if best is None or no_shedding.selection_key(point)<no_shedding.selection_key(prior):best=(rd,evaluation,span)
                row['production_stop_eligible']=no_shedding.stop_eligible(evaluation,span)
                proof=rd/'tiny-point-check.json';b.write(proof,evaluation,fresh=True)
                state['trace'].append(dict(call=index+1,evaluation=evaluation,master_identity=exported['identity'],checked_archive=str(proof)))
                # This unchanged fixture necessarily has material overflow: under
                # outage l2, bus b2 forces 1 MW on l1 against its .25 MW rating.
                # Keep its inherited mechanism/reference stop, never a production pass.
                if span['qualified']:
                    preterminal_metadata=copy.deepcopy(metadata)
                    terminal_support=batch
                    metadata=adaptive.terminal(projected,metadata,batch)
                    break
                require(index<2,'Tiny candidate fixed-call interval remained open')
                row['continuation_support']=no_shedding.excluding_support(batch,metadata,x,runtime.bank)
                require(row['continuation_support']['passed'],'Tiny no materially violated new network support')
                artifact=evaluation['adaptive_support_artifact']
                state['trace'][-1]['inserted_batch_artifact']=artifact
                cut_prefix.append(dict(source_call=index+1,artifact=artifact))
                before_lines=set(adaptive.activation(metadata).active)
                projected,metadata,_=adaptive.install(projected,metadata,batch)
                runtime.expected=projected;runtime.adopt(batch)
                status.setdefault('integer_activated_lines',[]).extend(l for l in adaptive.activation(metadata).active if l not in before_lines)
            require(span['qualified'],'Tiny candidate not qualified')
            if len(status['trace'])==1:
                # Separate, bounded mechanism check after natural candidate
                # stopping. Its objective/bound is never a candidate endpoint.
                rd=out/'mip-02';rd.mkdir()
                component,component_meta,_=adaptive.install(projected,preterminal_metadata,terminal_support)
                require(model.model_hashes(component)!=model.model_hashes(projected),'Tiny component unchanged master')
                restored=master.restore_integrality(component,component_meta,original)
                exported=master.export_master(restored,rd/'master.mps',cfg['library'])
                state['trace'][0]['inserted_batch_artifact']=state['trace'][0]['evaluation']['adaptive_support_artifact']
                component_prefix=cut_prefix+[dict(source_call=1,artifact=state['trace'][0]['inserted_batch_artifact'])]
                state['pending_master']=dict(call=2,identity=exported['identity'],cut_batches=3,cut_prefix=component_prefix)
                snapshot=rd/'carry-state.json';b.write(snapshot,state,fresh=True)
                request=dict(schema=carry.SCHEMA,run_directory=str(out),state_path=str(snapshot),state_sha256=f.sha256(snapshot),
                    source_manifest_path=str(Path(__file__).resolve()),source_manifest_sha256=f.sha256(__file__),
                    arm_manifest_path=str(tiny_arm_path),arm_manifest_sha256=f.sha256(tiny_arm_path),target_call=2,
                    pending_master=state['pending_master'],seed_result_path=str(seedout/'result.json'),seed_result_sha256=f.sha256(seedout/'result.json'))
                request_path=rd/'carry-request.json';b.write(request_path,request,fresh=True)
                prepout=rd/'carry';prepout.mkdir()
                prepared=carry.prepare(request,prepout,min(deadline,time.monotonic()+30.),production=False)
                prepared['request_sha256']=f.sha256(request_path);b.write(prepout/'result.json',prepared,fresh=True)
                start=carry.verify_prepared(prepared,request_path,f.sha256(request_path),exported['identity'])
                _,component_row=solve(exported['expected'],rd/'master.mps','current_map_carry_component',start,prepared,options.PROOF_ROLE)
                require(component_row['start_admission']['passed'],'Tiny component actual CLI start admission')
                status['component_carry']=dict(scope='bounded tiny mechanism only, after natural candidate stop',
                    candidate_endpoint_eligible=False,extra_point_evaluations=0,changed_master=True,
                    preparation=prepared,solve=component_row)
            else:
                require(status['trace'][0]['model_hashes'] != status['trace'][1]['model_hashes'],'Tiny unchanged master rerun')
                require(status.get('carry_preparations') and all(r['start_admission']['passed'] for r in status['trace'][1:]),
                    'Tiny actual carried-start admission untested')
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
            require(abs(objective-best[1]['provisional_upper'])<=max(1e-5,1e-9*abs(objective)),'Tiny full-integer parity failed')
            status['full_integer_reference']=ref
            rd,ev,_=best
            span=diagnostics.interval(max([seeded['lower_exact_lp']]+[r['report']['global_lower'] for r in status['trace'] if r['report']['bound_status_valid']]),ev['provisional_upper'])
            require(span['qualified'],'Tiny best checked original witness interval not qualified')
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
            quality=no_shedding.slack_quality(original,common.read_bundle(rd,ev['stored_lift_artifact'])['values'])
            require(not quality['passed'] and quality['positive_slack_totals_MWh']['shared_overflow'] >= 1.5-1e-5,
                'Unchanged tiny must expose unavoidable material overflow')
            require(not no_shedding.stop_eligible(ev,span),'Tiny falsely passed production quality stop')
            fixture_module.require_expected_quality(quality)
            status.update(candidate_passed=False, candidate_expected_nonpass_verified=True,
                candidate_outcome='material_shared_overflow', expected_shared_overflow_MWh=2.25)
            require(status['trace'][0]['role']==options.DISCOVERY and status['trace'][0]['options_readback']['options']['mip_max_improving_sols']==1, 'Tiny first role/options mismatch')
            require(all(row['role']==options.PROOF_ROLE and row['options_readback']['options']['mip_max_improving_sols']==2147483647 for row in status['trace'][1:]),'Tiny later defaults changed')
            b.verify_freeze()
            status['loaded_python_runtime']=local_runtime.verify_loaded_runtime(cfg['python_distribution_files'])
            status['loaded_native_runtime']=local_runtime.verify_native_mappings(installed)
            status.update(test_passed=True, test_outcome='expected_candidate_nonpass_components_passed',
                discovery_bound_excluded=True, discovery_stop_activated=status['trace'][0]['report']['discovery_stop_activated'],
                event_stop_claim=("activated" if status['trace'][0]['report']['discovery_stop_activated'] else "untested; legitimate Optimal/TimeLimit workflow only"),
                physical=physical_result,passed=True,genuine_second_master=True,exact_original_binary_count=12,adaptive_changed_master_carry_exercised=True,
                candidate_stopped_naturally=True, production_advancement_qualified=False,
                fixture_stop_rule='tiny target-gap mechanism/reference only; production requires all three positive slack totals',
                target_subset_quality_verified=True,quality=quality,component_calls=(1 if 'component_carry' in status else 0),
                full_integer_reference_objective=objective,candidate_interval=span)
    except BaseException as exc:
        status['error']=type(exc).__name__+': '+str(exc)
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
