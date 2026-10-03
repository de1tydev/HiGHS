"""Fresh-output baseline/early/pair CLI; no external approval artifacts."""
import argparse
import fcntl
import json
import signal
from common import *
from portable_runtime import checked_path,fresh_directory

def arm_order(case,seed,mode,*,tiny=False):
    if mode=='baseline':return ['A']
    if mode=='early':return ['early_candidate']
    if mode!='pair':raise ContractError('Unknown arm mode')
    if tiny:return ['A','early_candidate']
    dates=['2017-05-01','2017-06-01','2017-09-01'];seeds=[211,212,213]
    sequence=dates.index(case)*3+seeds.index(seed)+1
    return ['A','early_candidate'] if sequence%2 else ['early_candidate','A']

def outer_ok(v):
    return v.get('runner_returncode')==0 and v.get('total_slot_within_timeout') is True and not any(
        v.get(k) for k in ('error','health_check_error','interruption','hard_watchdog_killed','adopted_checks_killed_and_reaped'))

def compare(results):
    if set(results)!={'A','early_candidate'} or not all(v.get('complete') for v in results.values()):
        return dict(valid_pair=False,reason='Two completed original-source certificates are required; no ratio for single/censored arms')
    metrics={}
    for field in ('solver_process_wall_seconds','complete_process_e2e_seconds'):
        a,b=results['A'][field],results['early_candidate'][field]
        if not finite(a) or not finite(b) or a<=0 or b<0:raise ContractError('Invalid completed timing')
        metrics[field]=dict(baseline=a,candidate=b,reduction_fraction=(a-b)/a)
    return dict(valid_pair=True,metrics=metrics,scope='One local replay pair; no automatic historical-confirmation claim')

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--arm',choices=['baseline','early','pair'],default='pair')
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--tiny',action='store_true');g.add_argument('--case',choices=['2017-05-01','2017-06-01','2017-09-01'])
    p.add_argument('--seed',type=int);a=p.parse_args();limit();runtime_manifest();health()
    plan=read_json(HERE/'CAMPAIGN_PLAN.json');work=Path(BINDINGS['work']);out=checked_path(a.out,exists=False)
    if not out.is_relative_to(work/'runs'):raise ContractError('Output must be fresh below WORK/runs')
    if a.tiny:
        if a.seed is not None:raise ContractError('Tiny has fixed seed0')
        seed=0;source=TINY;hours=2
    else:
        seed=211 if a.seed is None else a.seed
        if seed not in (211,212,213):raise ContractError('Supported seeds are211,212,213')
        source=Path(plan['cases']['case89pegase/'+a.case]);hours=36
    order=arm_order(a.case,seed,a.arm,tiny=a.tiny)
    fresh_directory(str(out),(Path(BINDINGS['package']),Path(BINDINGS['source']),Path(BINDINGS['build']),Path(BINDINGS['data']),HERE))
    metadata=dict(case='tiny_triangle' if a.tiny else 'case89pegase/'+a.case,seed=seed,arm_order=order,source_sha256=sha(source),
        package_sha256=BINDINGS['release_sha256'],runtime_manifest_sha256=sha(HERE/'RUNTIME_MANIFEST.json'),
        solver_budget_per_arm=10. if a.tiny else 600.,arm_containment_seconds=180. if a.tiny else 1800.,
        timing='Per-arm containing-process launch through exact reap; controller-only preflight/archival excluded and not separately charged')
    write_json(out/'PLAN.json',metadata,fresh=True);results={};stopped=None;active=None;outer=None;state={}
    envelope=module(HELPERS/'slot_envelope.py','portable_early_envelope')
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,envelope.request_stop)
    try:
        with (work/'numerical.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            for arm in order:
                active=arm;outer=None;state={};runtime_manifest();health()
                command=[PYTHON,'-B','-s',str(HERE/'consumer_arm.py'),'--out',str(out/arm),'--source',str(source),
                    '--hours',str(hours),'--seed',str(seed),'--arm',arm]+(['--tiny'] if a.tiny else [])
                outer=envelope.supervise(command,environment(),out/(arm+'.outer.log'),timeout=metadata['arm_containment_seconds'],health_check=health)
                write_json(out/(arm+'.outer.json'),outer,fresh=True)
                path=out/arm/'summary.json';state=read_json(path) if path.exists() else {}
                clean=outer_ok(outer) and not state.get('stop_campaign')
                results[arm]=dict(complete=clean and state.get('complete') is True,
                    solver_process_wall_seconds=state.get('budget',{}).get('solver_process_wall_seconds'),
                    complete_process_e2e_seconds=outer['total_slot_elapsed_seconds'],certificate=state.get('certificate'),
                    reason=state.get('reason','No durable arm summary'),state_sha256=sha(path) if path.exists() else None,outer=outer)
                if not clean:stopped=dict(arm=arm,reason=results[arm]['reason']);break
    except BaseException as exc:
        stopped=dict(arm=active,reason=type(exc).__name__+': '+str(exc))
        if active and outer and outer.get('runner_launched'):
            known=state if isinstance(state,dict) else {}
            results[active]=dict(complete=False,solver_process_wall_seconds=known.get('budget',{}).get('solver_process_wall_seconds'),
                complete_process_e2e_seconds=outer['total_slot_elapsed_seconds'],reason=stopped['reason'],outer=outer)
    final=dict(plan=metadata,results=results,comparison=compare(results),stopped=stopped,
        unrun_arms=[arm for arm in order if arm not in results],solver_retries=0)
    write_json(out/'RESULT.json',final,fresh=True)
    print(json.dumps(dict(out=str(out),complete=all(v['complete'] for v in results.values()) and len(results)==len(order),
        comparison=final['comparison'],stopped=stopped),allow_nan=False))
    return 0 if not stopped and len(results)==len(order) and all(v['complete'] for v in results.values()) else 2

if __name__=='__main__':raise SystemExit(main())
