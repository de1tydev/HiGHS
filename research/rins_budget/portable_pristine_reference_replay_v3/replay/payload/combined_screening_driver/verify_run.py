"""Offline receipt/hash/debit/numerical-certificate consistency; no solve or API."""
import argparse
import json
from common import *
from trial_policy import Budget,DISCOVERY,PROOF,certificate,report_for_role,validate_options
from consumer_launch import outer_ok

def persisted_check(stage,directory):
    projected=stage.get('check')
    if projected is None:return None
    artifact=projected['check_artifact'];path=directory/'check.json'
    if Path(artifact['path']).resolve()!=path.resolve() or sha(path)!=artifact['sha256']:raise ContractError('Raw check artifact identity changed')
    raw=read_json(path);expected=dict(raw,check_artifact=artifact)
    if stage['role']==DISCOVERY:
        expected.update(role=DISCOVERY,upper_bound_eligible=False,certificate_bound_eligible=False,
            checked_upper=None,discovery_source_secure=raw.get('full_source_primal_pass',False))
    if projected!=expected:raise ContractError('Summary check differs from its exact raw check/role projection')
    return raw

def stage_evidence(stage,directory,arm_out,plan):
    saved=read_json(directory/'record.json')
    extras={'accepted_new_pairs','discovery_transition','discovery_point_usable'}
    if set(stage)-set(saved)-extras or any(stage.get(k)!=v for k,v in saved.items()):raise ContractError('Full stage record differs from summary')
    measured=read_json(directory/'measurement.json')
    if measured!=stage['solver']:raise ContractError('Measured process receipt differs')
    before_path=directory/'record.before_solve.json';before=read_json(before_path)
    if sha(before_path)!=stage['record_sha256_before_solve'] or Path(stage['record_before_solve_path'])!=before_path:
        raise ContractError('Before-solve receipt changed')
    role=stage['role'];model=directory/'master.mps';solution=directory/'solution.sol';options=arm_out/(role+'.options')
    expected=[str(BINARY),str(model),'--options_file',str(options),'--time_limit',format(stage['allocation'],'.17g'),
              '--random_seed',str(plan['seed']),'--solution_file',str(solution)]
    if stage['solver_command']!=expected or before['solver_command']!=expected:raise ContractError('Actual solver command/source/seed/options binding changed')
    for key in before:
        if before[key]!=stage.get(key):raise ContractError('Before-solve field changed: '+key)
    if role==DISCOVERY and (stage.get('discovery_transition')!='fresh cold proof' or
        stage.get('discovery_point_usable')!=bool(stage.get('check') and stage['check'].get('primal_present'))):
        raise ContractError('Discovery transition evidence changed')

def verify_run(out):
    runtime_manifest();out=Path(out).resolve();result=read_json(out/'RESULT.json');plan=read_json(out/'PLAN.json')
    if result['plan']!=plan:raise ContractError('Run plan differs')
    local=read_json(HERE/'CAMPAIGN_PLAN.json');tiny=plan['case']=='tiny_triangle'
    source=TINY if tiny else Path(local['cases'][plan['case']])
    if (plan['source_sha256']!=sha(source) or plan['package_sha256']!=BINDINGS['release_sha256']
        or plan['runtime_manifest_sha256']!=sha(HERE/'RUNTIME_MANIFEST.json')
        or plan['solver_budget_per_arm']!=(10. if tiny else 600.)
        or (tiny and plan['seed']!=0) or (not tiny and plan['seed'] not in (211,212,213))):
        raise ContractError('Plan source/seed/package/runtime/budget binding changed')
    reports={};checked_arms=[]
    for arm,value in result['results'].items():
        path=out/arm/'summary.json';state=read_json(path)
        if value.get('state_sha256')!=sha(path):raise ContractError('Arm state receipt changed')
        if any(state.get(k)!=v for k,v in dict(arm=arm,seed=plan['seed'],hours=2 if tiny else 36,
            source_sha256=plan['source_sha256'],package_sha256=plan['package_sha256'],
            runtime_freeze_sha256=plan['runtime_manifest_sha256'],common_pipeline_arm='A').items()):
            raise ContractError('Arm state binding differs')
        outer=read_json(out/(arm+'.outer.json'))
        if value['outer']!=outer or value['complete_process_e2e_seconds']!=outer['total_slot_elapsed_seconds']:raise ContractError('Outer measurement differs')
        expected_outer=[PYTHON,'-B','-s',str(HERE/'consumer_arm.py'),'--out',str(out/arm),'--source',str(source),
            '--hours',str(2 if tiny else 36),'--seed',str(plan['seed']),'--arm',arm]+(['--tiny'] if tiny else [])
        if outer['command']!=expected_outer:raise ContractError('Containing-arm command binding changed')
        budget=Budget(plan['solver_budget_per_arm']);bounds=[]
        for index,stage in enumerate(state['trace'],1):
            role=stage['role'];measurement=stage.get('solver')
            if role!=(DISCOVERY if arm=='early_candidate' and index==1 else PROOF):raise ContractError('Role order differs')
            directory=out/arm/f'{index:02d}_{role}'
            if Path(stage['stage_directory']).resolve()!=directory:raise ContractError('Stage directory binding changed')
            stage_evidence(stage,directory,out/arm,plan)
            if measurement is None:raise ContractError('Unmeasured stage cannot be verified as completed')
            budget.debit(role,stage['allocation'],measurement)
            if measurement.get('returncode')!=0 or measurement.get('hard_watchdog_killed') or measurement.get('interrupted'):
                if value['complete']:raise ContractError('Failed process marked complete')
                continue
            model=directory/'master.mps';solution=directory/'solution.sol'
            options=out/arm/(role+'.options');validate_options(role,options.read_text())
            for name,digest in [(model,stage['report']['master_identity']['model_sha256']),
                (str(model)+'.expected.json',stage['report']['master_identity']['expected_sha256']),
                (str(model)+'.readback.json',stage['report']['master_identity']['api_report_sha256']),
                (directory/'pairs.json',stage['report']['master_identity']['pair_manifest_sha256']),
                (options,stage['report']['master_identity']['options_sha256'])]:
                if sha(name)!=digest:raise ContractError('Stage input/output identity changed')
            if solution.exists():
                if sha(solution)!=stage.get('solution_sha256'):raise ContractError('Final solution changed')
            elif stage.get('solution_presence')!='missing' or stage.get('check') is not None or stage.get('solution_sha256'):
                raise ContractError('Missing a claimed solution/check')
            api=read_json(str(model)+'.readback.json')
            from contracts import FIDELITY_FIELDS
            if api.get('passed') is not True or set(api['fields'])!=FIDELITY_FIELDS or not all(v['passed'] for v in api['fields'].values()):
                raise ContractError('Original API fidelity receipt failed')
            io=module(EXPORTER/'io_announcements.py','portable_exact_io_announcements')
            log,evidence=io.filter_known_io((directory/'solver.log').read_text(),model,solution,solver=True)
            if evidence!=stage['io_announcement_filter']:raise ContractError('Diagnostic compatibility evidence changed')
            report=report_for_role(log,measurement,model,role);report['master_identity']=stage['report']['master_identity']
            for key in ('scope','role','status','global_lower','printed_lower','bound_status_valid','certificate_bound_eligible','usable_status'):
                if report.get(key)!=stage['report'].get(key):raise ContractError('Retained solver report differs: '+key)
            checked=persisted_check(stage,directory)
            if checked:
                if checked.get('primal_present') and checked.get('matrix_check',{}).get('passed') is not True:raise ContractError('Current matrix check failed')
            if role==PROOF and report['bound_status_valid']:bounds.append(report)
            if role==DISCOVERY and (report['certificate_bound_eligible'] or stage.get('check') and stage['check'].get('upper_bound_eligible')):
                raise ContractError('Discovery certificate leakage')
        if budget.record()!=state['budget']:raise ContractError('Actual process debit ledger mismatch')
        if len(bounds)!=len(state['integer_master_bounds']):raise ContractError('Proof ledger length mismatch')
        upper=None
        if 'best_integer_stage' in state:
            stage=state['trace'][state['best_integer_stage']-1];checked=persisted_check(stage,Path(stage['stage_directory']))
            if state['best_integer_point']!=stage['check']:raise ContractError('Best point differs from selected raw-check projection')
            if stage['role']!=PROOF or not checked.get('upper_bound_eligible') or not checked.get('full_source_primal_pass'):
                raise ContractError('Invalid proof upper provenance')
            source_check=checked['source_check'];matrix=checked['matrix_check']
            if source_check.get('pass_primal') is not True or source_check['violations_by_category']:raise ContractError('Final original source point failed')
            upper=max(source_check['linear_model_cost'],matrix['linear_objective'])
            if upper!=checked['checked_upper']:raise ContractError('Original checked upper differs')
        cert=certificate(upper,bounds,budget.record())
        for key in ('valid','complete','upper','lower','gap'):
            if cert.get(key)!=state['certificate'].get(key):raise ContractError('Numerical certificate mismatch: '+key)
        complete=state['complete'] and outer_ok(value['outer'])
        if complete!=value['complete'] or (complete and not cert['complete']):raise ContractError('Process/certificate completion disagreement')
        checked_arms.append(arm);reports[arm]=dict(certificate_complete=cert['complete'],actual_solver_process_seconds=budget.spent,
            proof_reports=len(bounds),discovery_calls=budget.discovery_calls)
    runtime_manifest()
    return dict(verified=True,checked_arms=checked_arms,arms=reports,all_requested_arms_certified=not result['unrun_arms'] and
        len(checked_arms)==len(plan['arm_order']) and all(v['certificate_complete'] for v in reports.values()),
        scope='Retained artifact/provenance/debit/numerical-certificate consistency; no independent exact dual proof and no new source model/API/solve')

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();limit()
    print(json.dumps(verify_run(a.out),allow_nan=False))

if __name__=='__main__':main()
