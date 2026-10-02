#!/usr/bin/env python3
"""Serial fixed A cold-integer versus B combined screening. No implicit launch."""
import argparse
import datetime
import os
from pathlib import Path
import resource
import sys
import time
from contracts import *
from pair_codec import PackedPairs, write_pairs, read_pairs
from resource_guard import apply_process_limit, ARM_CONTAINMENT_SECONDS, guard_storage
from policy import ARMS, arm_record, schedule, confirmation_gate
from primal_and_bound import certificate, definition_diagnostics, solver_report

def options_text(kind, root_credit=False):
    if type(root_credit) is not bool: raise ContractError("Root credit option must be bool")
    common=['threads = 2','parallel = off','presolve = on','write_solution_to_file = true',
            'write_solution_style = 0','log_dev_level = 1','highs_analysis_level = 128']
    if kind=='lp': return '\n'.join(common+['solver = simplex','simplex_strategy = 1'])+'\n'
    if kind!='mip': raise ContractError('Unknown options kind')
    return '\n'.join(common+['mip_rel_gap = 0.01','mip_improving_solution_save = false',
            'mip_lp_solver = choose','mip_ipm_solver = choose','mip_heuristic_outer_gap = true',
            'mip_heuristic_outer_gap_log = true','mip_initial_root_ipx = false',
            'mip_heuristic_near_target_root_budget = '+str(root_credit).lower(),
            'mip_heuristic_near_target_root_budget_log = true'])+'\n'

def environment():
    from portable_runtime import minimal_environment
    return minimal_environment(HERE)

def execute(command,log,env,watchdog):
    measurement=module(HIGHS/'process_measure.py','cold_screen_process_measure')
    def limit(): resource.setrlimit(resource.RLIMIT_AS,(MEMORY_BYTES,MEMORY_BYTES))
    start=time.monotonic()
    try:
        with Path(log).open('x') as stream:
            result=measurement.run_measured(command,stream=stream,env=env,preexec_fn=limit,timeout=watchdog)
        return {key.removeprefix('solver_'):value for key,value in result.items()}
    except BaseException as exc:
        # The frozen helper kills the whole process group and wait4-reaps on cancellation.
        return dict(returncode=None,hard_watchdog_killed=False,process_wall_seconds=time.monotonic()-start,
                    interrupted=isinstance(exc,(KeyboardInterrupt,SystemExit)),launch_or_measurement_error=f'{type(exc).__name__}: {exc}')

def validate_stage(result,kind,eligible,active):
    report=result['report']; checked=result.get('check')
    if report.get('model_definition_diagnostics') or not report.get('loaded_library_identity_valid') or not report.get('identities_valid'):
        raise ContractError('Solver model/runtime identity or definition failed')
    if checked is None or not checked.get('primal_present'): return None,PackedPairs(eligible)
    if checked.get('kind')!=kind or checked['matrix_check'].get('passed') is not True:
        raise ContractError('Stage primal/matrix identity failed')
    new=pairs(checked['new_pairs'],eligible)
    if new.intersects(active): raise ContractError('Already-active pair violation')
    if kind=='lp' and (checked.get('upper_bound_eligible') or checked.get('certificate_bound_eligible') or checked.get('full_source_primal_pass')):
        raise ContractError('Fractional LP improperly presented as source incumbent or bound')
    return checked,new

def run_pipeline(backend,candidate,*,total=SOLVER_BUDGET,seed_preparation=False):
    """The same MIP loop for both arms. Backend alone performs external numerical work.

    A debit callback is mandatory immediately after each solver is reaped, before
    any check can fail. Failed stages and watchdog overshoot remain charged.
    """
    budget=Budget(total); active=None; bounds=[]; upper=None
    state=dict(arm='lp_discovery' if candidate else 'cold_integer',initial_pairs=[],active_pairs=[],
               warm_start=False,lp_point_carry=False,lp_basis_carry=False,lp_bound_carry=False,
               target_gap=TARGET,complete=False,reason='not started',trace=[])
    def stage(kind):
        allocation=budget.allocation(kind)
        if allocation<=0: return None
        rec={'kind':kind,'active_pairs':backend.pair_manifest(active),'allocation':allocation,
             'upper_bound_eligible':False,'certificate_bound_eligible':False}
        state['trace'].append(rec)
        debit_called=False
        def debit(measured):
            nonlocal debit_called
            if debit_called: raise ContractError('Solver charged twice')
            budget.debit(kind,allocation,measured);debit_called=True
            rec['solver']=measured;state['budget']=budget.record();backend.checkpoint(state)
        result=backend.stage(kind,active,allocation,debit,rec)
        if not debit_called: raise ContractError('Solver process was not charged')
        rec.update(result)
        checked,new=validate_stage(result,kind,backend.eligible,active)
        backend.checkpoint(state)
        return rec,checked,new
    try:
        backend.start(state)
        active=PackedPairs(backend.eligible)
        if seed_preparation:
            if candidate: raise ContractError('Seed replaces LP discovery; stacking is forbidden')
            active=backend.prepare_seed(state)
            if not isinstance(active,PackedPairs) or active.scope_sha256!=backend.eligible['descriptor_sha256']:
                raise ContractError('Seed preparation did not return source-bound pairs')
            state['initial_pairs']=backend.pair_manifest(active)
        if candidate:
            for _ in range(LP_CALLS):
                outcome=stage('lp')
                if outcome is None: break
                rec,checked,new=outcome
                if rec['solver'].get('interrupted'): raise KeyboardInterrupt('LP child interrupted and reaped')
                # A deadline hit retains earlier validated cuts only. Ineligible LP
                # vectors cannot select rows; actual cap overshoot remains flagged.
                if rec['solver'].get('hard_watchdog_killed'):
                    rec['lp_stop']='process deadline';break
                if not rec['report'].get('usable_status'): raise ContractError('Abnormal LP exit/status')
                if checked is None: rec['lp_stop']='no primal';break
                if not new: rec['lp_stop']='no new pair';break
                active=active.merged(new);rec['accepted_new_pairs']=backend.pair_manifest(new)
                if not budget.lp_policy_valid: rec['lp_stop']='actual LP policy cap exceeded';break
        state['lp_seed_pairs']=backend.pair_manifest(active)
        while budget.allocation('mip')>0:
            outcome=stage('mip')
            if outcome is None: break
            rec,checked,new=outcome
            if rec['solver'].get('interrupted'): raise KeyboardInterrupt('MIP child interrupted and reaped')
            if checked and checked.get('upper_bound_eligible') is True:
                if checked.get('full_source_primal_pass') is not True or new or not finite(checked.get('checked_upper')):
                    raise ContractError('Unchecked integer upper bound')
                value=checked['checked_upper']
                if upper is None or value<upper:
                    upper=value;state['best_integer_point']=checked;state['best_integer_stage']=len(state['trace'])
            if rec['solver'].get('hard_watchdog_killed'):
                state['reason']='ordinary solver containment deadline; no certificate';break
            if not rec['report'].get('bound_status_valid'):
                if (rec['report'].get('usable_status') and rec['report'].get('parent_report_identity_valid')
                    and rec['report'].get('status')=='Time limit reached'):
                    state['reason']='normal time limit without finite eligible bound';break
                raise ContractError('No eligible exact original-MIP report')
            bounds.append(rec['report'])
            cert=certificate(upper,bounds,budget.record());state['certificate']=cert
            if 'best_integer_point' in state:
                cert['upper_provenance']={'stage':state['best_integer_stage'],
                    'identity':state['best_integer_point'].get('identity'),
                    'check_artifact':state['best_integer_point'].get('check_artifact')}
            if cert.get('complete'):
                state.update(complete=True,reason='full original-source 1% numerical certificate');break
            if checked is None: state['reason']='normal exit without complete primal';break
            if not new:
                state['reason']='source-secure point but independently computed certificate misses fixed policy';break
            active=active.merged(new);rec['accepted_new_pairs']=backend.pair_manifest(new)
            state['reason']='solver process budget exhausted'
    except BaseException as exc:
        # Preserve a reaped child's cancellation even if later artifact handling
        # raises a different exception. The pair must not start another arm.
        interrupted=isinstance(exc,(KeyboardInterrupt,SystemExit)) or any(
            rec.get('solver',{}).get('interrupted') for rec in state['trace'])
        state.update(complete=False,reason=f'{type(exc).__name__}: {exc}',interrupted=bool(interrupted),
                     failure_class='cancellation' if interrupted else 'integrity_or_resource',stop_campaign=True)
    finally:
        state.update(active_pairs=backend.pair_manifest(active) if active is not None else None,budget=budget.record(),integer_master_bounds=bounds)
        state.setdefault('certificate',certificate(upper,bounds,budget.record()))
        if not budget.record()['in_budget'] or not budget.lp_policy_valid: state['complete']=False
        backend.checkpoint(state)
    return state

class RuntimeBackend:
    def __init__(self,out,source,hours,seed,*,tiny=False,arm='A'):
        self.out=Path(out);self.source=Path(source);self.hours=hours;self.seed=seed;self.tiny=tiny;self.arm=ARMS[arm];self.root_credit=self.arm.root_credit
        self.eligible=None;self.stages=0;self.env=environment();self.tracked={};self.aux=[]
        self.mip_grace=2. if tiny else MIP_GRACE
        self.aux_watchdog=20. if tiny else AUX_WATCHDOG

    def start(self,state):
        # Caller starts E2E before construction/preflight and creates exclusive dir.
        freeze=runtime_manifest();self.tracked=dict(freeze['artifact_sha256'])
        if str(self.source.resolve()) not in self.tracked: raise ContractError('Unpinned source')
        scope_record={}
        checked=self.auxiliary('scope',None,self.out,None,None,None,scope_record)
        scope=checked['scope'];dimensions=checked['dimensions']
        if not self.tiny:
            reserved=read_json(HERE/'CAMPAIGN_PLAN.json')['allowed_sources'].get(str(self.source),{})
            if reserved.get('scope')!=scope or reserved.get('dimensions')!=dimensions:
                raise ContractError('Not the exact source-only frozen case/scope')
        state['scope_preparation']=scope_record
        self.eligible=scope
        state.update(arm=self.arm.name,arm_record=arm_record(self.arm.name),root_child_credit_enabled=self.root_credit,
                     lp_discovery_required=self.arm.lp_discovery,source_scope=scope,source_sha256=sha(self.source),seed=self.seed,hours=self.hours,
                     memory_limit_bytes=MEMORY_BYTES,auxiliary_watchdog_seconds=self.aux_watchdog,mip_watchdog_grace_seconds=self.mip_grace,
                     runtime_freeze_sha256=sha(HERE/'RUNTIME_MANIFEST.json'),environment_overrides={k:self.env[k] for k in
                     ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','PYTHONHASHSEED','LD_LIBRARY_PATH')})
        write_json(self.out/'initial_pairs.json',self.pair_manifest(PackedPairs(scope)),fresh=True)
        for kind in ('lp','mip'):
            options=self.out/(kind+'.options');options.write_text(options_text(kind,self.root_credit))
            self.tracked[str(options)]=sha(options)
        state['initial_pairs_sha256']=sha(self.out/'initial_pairs.json')
        self.tracked[str(self.out/'initial_pairs.json')]=state['initial_pairs_sha256']
        self.checkpoint(state)

    def prepare_seed(self,state):
        started=time.monotonic()
        from seed_stage import prepare_seed
        return prepare_seed(self,state,stage_started=started)

    def pair_manifest(self, active):
        directory=self.out/'pairs';directory.mkdir(exist_ok=True)
        path=directory/(active.content_sha256()+'.u32')
        if not path.exists():
            manifest=write_pairs(path,active)
            write_json(str(path)+'.json',manifest,fresh=True)
        manifest=read_json(str(path)+'.json')
        if read_pairs(manifest,self.eligible)!=active: raise ContractError('Pair sidecar content mismatch')
        return manifest

    def checkpoint(self,state):
        guard_storage(self.out)
        write_json(self.out/'summary.json',state)

    def auxiliary(self,action,kind,rd,model,pair_path,solution,rec):
        result=rd/(action+'.json');log=rd/(action+'.log')
        receipt=rd/(action+'.selector.json')
        command=[sys.executable,'-B','-s',str(HERE/'stage_child.py'),action,
                 '--plan',str(HERE/'CAMPAIGN_PLAN.json'),'--plan-sha256',sha(HERE/'CAMPAIGN_PLAN.json'),
                 '--arm',self.arm.name,'--source',str(self.source),'--hours',str(self.hours),
                 '--result',str(result),'--receipt',str(receipt)]
        if action!='scope': command+=['--pairs',str(pair_path),'--kind',kind,'--model',str(model)]
        if action=='check': command+=['--solution',str(solution)]
        rec[action+'_command']=command
        measured=execute(command,log,self.env,self.aux_watchdog);rec[action+'_process']=measured
        self.aux.append({'kind':kind,'action':action,**measured})
        if measured.get('interrupted'): raise KeyboardInterrupt(action+' interrupted')
        if measured.get('returncode')!=0 or measured.get('hard_watchdog_killed'):
            raise ContractError(action+' failed/watchdog: '+(result.read_text() if result.exists() else 'no result'))
        selected=read_json(receipt)
        if (selected.get('passed') is not True or selected.get('arm_record')!=arm_record(self.arm.name)
            or selected.get('arm')!=self.arm.name or selected.get('action')!=action
            or selected.get('output_sha256')!=sha(result)
            or selected.get('plan_sha256')!=sha(HERE/'CAMPAIGN_PLAN.json')
            or selected.get('loaded_python_modules',{}).get('fractional_separator',{}).get('sha256')!=SEPARATOR_SHA256[self.arm.name]):
            raise ContractError('Selector receipt mismatch')
        from stage_child import input_identity
        if (selected.get('kind')!=kind or selected.get('source')!=str(self.source)
            or selected.get('hours')!=self.hours
            or selected.get('runtime_manifest_sha256')!=sha(HERE/'RUNTIME_MANIFEST.json')
            or selected.get('input_identity')!=input_identity(self.source,pair_path,model,solution)):
            raise ContractError('Selector input identity mismatch')
        plan=read_json(HERE/'CAMPAIGN_PLAN.json')
        expected_paths={**plan['common_module_paths'],'fractional_separator':str(SEPARATOR_PATHS[self.arm.name])}
        expected_loaded={name:{'path':path,'sha256':plan['module_sha256'][path],
            'loading':'compile exact pinned source bytes'} for name,path in expected_paths.items()}
        if selected.get('loaded_python_modules')!=expected_loaded: raise ContractError('Selected module provenance mismatch')
        rec[action+'_selector']=selected
        self.tracked[str(receipt)]=sha(receipt)
        return read_json(result)

    def stage(self,kind,active,allocation,debit,rec):
        verify(self.tracked);self.stages+=1
        rd=self.out/f'{self.stages:02d}_{kind}';rd.mkdir(exist_ok=False)
        pair_path=rd/'pairs.json';model=rd/'master.mps';solution=rd/'solution.sol'
        write_json(pair_path,self.pair_manifest(active),fresh=True)
        rec.update(stage_directory=str(rd),pairs_sha256=sha(pair_path))
        meta=self.auxiliary('generate',kind,rd,model,pair_path,solution,rec)
        rec['model_metadata']=meta
        local=dict(self.tracked,**{str(p):sha(p) for p in (pair_path,model,Path(str(model)+'.expected.json'),
                                      Path(str(model)+'.readback.json'),Path(str(model)+'.meta.json'),Path(str(model)+'.readback.log'))})
        verify(local)
        command=[str(BINARY),str(model),'--options_file',str(self.out/(kind+'.options')),
                 '--time_limit',format(allocation,'.17g'),'--random_seed',str(self.seed),'--solution_file',str(solution)]
        rec['solver_command']=command;rec['solver_watchdog_seconds']=allocation if kind=='lp' else allocation+self.mip_grace
        write_json(rd/'record.before_solve.json',rec,fresh=True)
        before_solve_sha256=sha(rd/'record.before_solve.json')
        write_json(rd/'record.json',rec)
        env=dict(self.env,LD_DEBUG='libs')
        measured=execute(command,rd/'solver.log',env,rec['solver_watchdog_seconds'])
        debit(measured)
        if measured.get('interrupted'):
            raise KeyboardInterrupt('Solver child interrupted, charged and reaped')
        verify(local)
        text=(rd/'solver.log').read_text() if (rd/'solver.log').exists() else ''
        report=solver_report(text,measured,kind,model,LIBRARY,identities_valid=True)
        if kind=='mip':
            from credit_events import parse_credit_events
            try:
                rec['root_child_credit']=parse_credit_events(text,self.root_credit)
            except ValueError as exc:
                if not measured.get('hard_watchdog_killed'): raise
                # A confirmed killed/reaped solver may end mid-record or mid-call.
                # Preserve the strict parser error, but no activation/completion
                # claim can be drawn from this censored solver observation.
                rec['root_child_credit_censored']={'reason':str(exc),'solver_log_sha256':sha(rd/'solver.log'),
                    'confirmed_hard_watchdog_killed':True,'telemetry_valid':False,'activation_eligible':False}
        report['master_identity']=dict(kind=kind,stage_index=self.stages,stage_directory=str(rd),model_path=str(model),
            hours=self.hours,objective_scope=meta['objective_scope'],source_sha256=sha(self.source),model_sha256=sha(model),
            expected_sha256=sha(str(model)+'.expected.json'),pair_manifest_sha256=sha(pair_path),
            api_report_sha256=sha(str(model)+'.readback.json'),options_sha256=sha(self.out/(kind+'.options')),
            executable_sha256=sha(BINARY),generator_sha256=sha(GENERATOR),checker_sha256=sha(CHECKER),
            runtime_manifest_sha256=sha(HERE/'RUNTIME_MANIFEST.json'))
        rec['report']=report
        write_json(rd/'record.json',rec)
        checked=None
        if solution.exists():
            local[str(solution)]=sha(solution);rec['solution_sha256']=sha(solution)
            # Any killed output is retained/hashed but ineligible; never parse a partial file.
            # All normally emitted MIP primals still face complete independent checks.
            if not measured.get('hard_watchdog_killed') and (kind=='mip' or report.get('usable_status')):
                checked=self.auxiliary('check',kind,rd,model,pair_path,solution,rec)
                checked['check_artifact']={'path':str(rd/'check.json'),'sha256':sha(rd/'check.json')}
                local[str(rd/'check.json')]=sha(rd/'check.json')
                local[str(rd/'check.log')]=sha(rd/'check.log')
                if checked.get('primal_present') and checked.get('status')!=report.get('status'):
                    raise ContractError('Solution and solver status disagree')
        verify(local)
        result=dict(report=report,check=checked,solution_presence='file' if solution.exists() else 'missing',
                    record_sha256_before_solve=before_solve_sha256,record_before_solve_path=str(rd/'record.before_solve.json'))
        rec.update(result);write_json(rd/'record.json',rec)
        return result

def run_arm(out,source,hours,seed,*,tiny=False,total=SOLVER_BUDGET,common_setup_seconds=0.,arm='A',process_startup_seconds=0.):
    apply_process_limit()
    started=time.monotonic();parent_cpu=time.process_time()
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    backend=RuntimeBackend(out,source,hours,seed,tiny=tiny,arm=arm)
    state=run_pipeline(backend,ARMS[arm].lp_discovery,total=total,seed_preparation=arm=='C')
    state['auxiliary_processes']=backend.aux
    measurements=[rec['solver'] for rec in state['trace'] if 'solver' in rec]+backend.aux
    state['child_user_cpu_seconds']=sum(m.get('user_cpu_seconds',0) for m in measurements)
    state['child_system_cpu_seconds']=sum(m.get('system_cpu_seconds',0) for m in measurements)
    state['child_peak_rss_KiB']=max((m.get('peak_rss_KiB',0) for m in measurements),default=0)
    state['child_resource_accounting_complete']=all(all(key in m for key in
        ('user_cpu_seconds','system_cpu_seconds','peak_rss_KiB')) for m in measurements)
    state['parent_cpu_seconds']=time.process_time()-parent_cpu
    state['parent_process_cumulative_peak_rss_KiB']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    state['parent_rss_scope']='cumulative lifetime peak of shared pair Python parent; second arm may inherit an earlier peak'
    state['stage_wall_seconds']={label:sum(m['process_wall_seconds'] for m in backend.aux if
        (m['action']=='generate' if label=='generation_readback' else m['action']=='check' and m['kind']==('lp' if label=='lp_separation' else 'mip')))
        for label in ('generation_readback','lp_separation','integer_checks')}
    state['stage_wall_seconds']['scope_preparation']=sum(m['process_wall_seconds'] for m in backend.aux if m['action']=='scope')
    state['stage_wall_seconds']['seed_preparation']=sum(m['process_wall_seconds'] for m in backend.aux if m['action']=='seed')
    state['stage_wall_seconds'].update(lp_solving=state['budget']['lp_process_wall_seconds'],
        integer_solving=state['budget']['solver_process_wall_seconds']-state['budget']['lp_process_wall_seconds'])
    try:
        verify(backend.tracked)
    except Exception as exc:
        state.update(complete=False,stop_campaign=True,failure_class='integrity_or_resource',reason=f'Final identity verification failed: {type(exc).__name__}: {exc}')
    if not state['child_resource_accounting_complete']:
        state.update(complete=False,stop_campaign=True,failure_class='integrity_or_resource',reason='Incomplete child resource accounting')
    backend.checkpoint(state)
    # This stop is AFTER final identity checks and fsynced durable summary.
    elapsed=time.monotonic()-started
    accounted=sum(state['stage_wall_seconds'].values())
    receipt=dict(end_to_end_seconds=elapsed,remaining_arm_overhead_seconds=elapsed-accounted,summary_sha256=sha(out/'summary.json'),
                 common_setup_seconds=common_setup_seconds,process_startup_seconds=process_startup_seconds,standalone_equivalent_e2e_seconds=common_setup_seconds+process_startup_seconds+elapsed,
                 timing='starts before source/runtime verification; stops after all checks and durable summary; this timing receipt is pair archival',
                 complete=state['complete'],solver_process_wall_seconds=state['budget']['solver_process_wall_seconds'])
    write_json(out/'completion_receipt.json',receipt,fresh=True)
    return state,receipt

def compare_pair(results):
    """Censored incomplete arms never produce a time-to-target speed ratio."""
    if set(results)!={'A','B'} or not all(r['state']['complete'] for r in results.values()):
        return {'valid_comparison':False,'development_gate_pass':False,'reason':'Incomplete arms are censored; no speedup ratio'}
    baseline=results['A']['receipt'];candidate=results['B']['receipt']
    comparisons={}
    for field in ('standalone_equivalent_e2e_seconds','solver_process_wall_seconds'):
        a,b=baseline[field],candidate[field]
        if not finite(a) or not finite(b) or a<=0 or b<0: raise ContractError('Invalid completed comparison timing')
        comparisons[field]={'baseline':a,'candidate':b,'reduction_fraction':1-b/a}
    return {'valid_comparison':True,'metrics':comparisons,
            'development_gate_pass':all(v['reduction_fraction']>=.20 for v in comparisons.values()),
            'e2e_comparison_scope':'common source/runtime archival and Python-definition startup charged in full to each standalone-equivalent arm'}

def mechanism_summary(results):
    summary={}
    for name,item in results.items():
        traces=[r['root_child_credit'] for r in item['state'].get('trace',[]) if r.get('kind')=='mip' and 'root_child_credit' in r]
        summary[name]={'call_count':sum(t['call_count'] for t in traces),
                      'applied_caps':sum(t['applied_caps'] for t in traces),
                      'applied_skips':sum(t['applied_skips'] for t in traces),
                      'root_origins_observed':sorted(set().union(*(set(t['root_origins_observed']) for t in traces)))}
    candidate=summary.get('B',{})
    summary['candidate_mechanism_activated']=candidate.get('applied_caps',0)+candidate.get('applied_skips',0)>0
    summary['scope']='Source-pinned heuristic telemetry only; never a global lower bound or separate process-time debit'
    return summary


def run_pair(out,case,seed,order,*,tiny=False):
    start=time.monotonic();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    freeze=runtime_manifest();write_json(out/'runtime_freeze.json',freeze,fresh=True)
    # Definition-only setup is charged fully to both arms. No source parse or
    # selected separator import occurs in this common setup interval.
    from model_stage import source_data
    from stage_child import input_identity
    source=HERE/'tiny_triangle.json' if tiny else source_case(case)
    hours=2 if tiny else HOURS;budget=20. if tiny else SOLVER_BUDGET
    plan=dict(case=case,source=str(source),hours=hours,seed=seed,arm_order=list(order),
              campaign_plan_sha256=sha(HERE/'CAMPAIGN_PLAN.json'),runtime_freeze_sha256=sha(HERE/'RUNTIME_MANIFEST.json'),
              arms={name:arm_record(name) for name in ('A','B')},solver_budget_per_arm=budget,
              initial_pairs=[],lp_max_calls=3,lp_call_process_cap=10.,lp_total_process_cap=30.,
              mip_watchdog_grace_seconds=2. if tiny else MIP_GRACE,auxiliary_watchdog_seconds=20. if tiny else AUX_WATCHDOG,
              mip_options_by_arm={name:options_text('mip',ARMS[name].root_credit) for name in ('A','B')},
              lp_options=options_text('lp'),fresh_source_restoration=True,no_warm_starts=True)
    write_json(out/'plan.json',plan,fresh=True);setup=time.monotonic()-start
    results={}
    for name in plan['arm_order']:
        state,receipt=run_arm(out/name,source,hours,seed,tiny=tiny,total=budget,common_setup_seconds=setup,arm=name)
        results[name]={'state':state,'receipt':receipt}
        if state.get('interrupted') or state.get('stop_campaign'): break
    pair={'case':case,'seed':seed,'arm_order':list(order),'plan_sha256':sha(out/'plan.json'),
          'runtime_freeze_sha256':sha(HERE/'RUNTIME_MANIFEST.json'),
          'campaign_plan_sha256':sha(HERE/'CAMPAIGN_PLAN.json'),'common_setup_seconds':setup,'results':results,
          'numerical_run':True,'stop_campaign':any(r['state'].get('stop_campaign',False) for r in results.values())}
    pair['comparison']=compare_pair(results)
    pair['root_child_credit_mechanism']=mechanism_summary(results)
    pair['comparison']['timing_gate_pass']=pair['comparison'].get('development_gate_pass',False)
    pair['comparison']['development_gate_pass']=bool(pair['comparison']['timing_gate_pass'] and pair['root_child_credit_mechanism']['candidate_mechanism_activated'])
    pair['pair_e2e_before_pair_serialization_seconds']=time.monotonic()-start
    write_json(out/'pair.json',pair,fresh=True)
    write_json(out/'pair_archival_receipt.json',{'pair_sha256':sha(out/'pair.json'),
        'pair_e2e_including_pair_serialization_seconds':time.monotonic()-start,
        'scope':'Ends after durable pair.json; this final administrative receipt is excluded'},fresh=True)
    return pair


def main():
    # This entrypoint deliberately cannot release May measurement. The final
    # reviewed W1 choice/protocol and per-arm containing launcher are required.
    raise ContractError('May performance entrypoint unreleased: final reviewed protocol/runtime release required')

if __name__=='__main__': raise SystemExit(main())
