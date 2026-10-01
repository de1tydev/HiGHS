#!/usr/bin/env python3
"""Finite constraint generation with one GLOBAL wall-clock budget.
Uses source-data direct-topology checks, not the generator's LODFs, for separation.
A screened master is a relaxation, never a standalone full-N-1 benchmark.
"""
import argparse, hashlib, json, math, os, pathlib, re, resource, subprocess, time
import generate
import check_solution

def prepare_output_directory(path):
    """Each run owns new evidence; never silently overwrite an earlier run."""
    out=pathlib.Path(path)
    out.mkdir(parents=True,exist_ok=False)
    return out

def dropped_matrix_coefficients(log_text):
    """Fail closed if the solver reports changing the algebraic matrix."""
    return bool(re.search(r'^WARNING:.*matrix.*(?:ignored|dropped)',log_text,re.I|re.M))

def main():
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--highs',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--budget',type=float,default=300);p.add_argument('--gap',type=float,default=0.01);p.add_argument('--seed',type=int,default=0);p.add_argument('--hours',type=int);p.add_argument('--initial-pairs',help='Same verified initial pair JSON for paired arms; no incumbent is inherited');a=p.parse_args()
    if not math.isfinite(a.budget) or a.budget<=0 or not math.isfinite(a.gap) or a.gap<0:p.error('budget must be finite positive and gap finite nonnegative')
    start=time.monotonic();deadline=start+a.budget
    try:out=prepare_output_directory(a.output_dir)
    except FileExistsError:p.error('output-dir already exists; use a fresh directory for each run')
    d=generate.read(a.input);T=a.hours or int(d['Parameters']['Time horizon (h)']);pairs=set(map(tuple,json.load(open(a.initial_pairs)))) if a.initial_pairs else set();trace=[];global_lb=-math.inf;best_full=None;complete=False;certificate_valid=True;reason='budget exhausted'
    if not 1<=T<=d['Parameters']['Time horizon (h)']:p.error('hours outside input horizon')
    options=out/'options.txt';options.write_text(f'threads = 1\nparallel = off\nmip_rel_gap = {a.gap:.17g}\nwrite_solution_to_file = true\nwrite_solution_style = 0\n')
    iteration=0;last_returncode=None
    while time.monotonic()<deadline-5:
        iteration+=1;mode='n1' if pairs else 'network';stem=out/f'round_{iteration:02d}';mps=str(stem)+'.mps';sol=str(stem)+'.sol';log=str(stem)+'.log';check=str(stem)+'.check.json'
        model,net=generate.build(d,T,mode,sorted(pairs) if pairs else None)
        meta=model.write(mps,dict(input_path=str(pathlib.Path(a.input).resolve()),input_sha256=generate.sha(a.input),generator_sha256=generate.sha(generate.__file__),hours=T,mode=mode,security_scope='selected pairs, independent all-outage check required',network=net))
        del model
        remain=deadline-time.monotonic()-5
        if remain<=0:break
        command=[a.highs,mps,'--options_file',str(options),'--time_limit',str(remain),'--random_seed',str(a.seed),'--solution_file',sol]
        ts=time.monotonic()
        with open(log,'w') as stream:
            try:run=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=max(0.01,deadline-time.monotonic()-4))
            except subprocess.TimeoutExpired:reason='global wall-clock solver deadline';break
        last_returncode=run.returncode;solve_elapsed=time.monotonic()-ts;check_started=time.monotonic()
        txt=pathlib.Path(log).read_text()
        if dropped_matrix_coefficients(txt):
            certificate_valid=False;reason='solver ignored matrix coefficients; original-model bound not certified';break
        match=re.search(r'^  Dual bound\s+(\S+)',txt,re.M);lb=float(match[1]) if match else -math.inf
        if run.returncode!=0 or not math.isfinite(lb):
            reason='solver error or nonfinite lower bound';certificate_valid=False;break
        # Final human-readable solver bounds are rounded; subtract a small conservative print allowance.
        if math.isfinite(lb):lb-=max(1e-5,abs(lb)*1e-11)
        global_lb=max(global_lb,lb)
        try:result=check_solution.check(a.input,sol,mode,T,check_all_security=True)
        except (ValueError,FileNotFoundError) as e:reason='no checkable incumbent: '+str(e);break
        checker_elapsed=time.monotonic()-check_started
        pathlib.Path(check).write_text(json.dumps(result,indent=2)+'\n');new=set(map(tuple,result['security']['violated_pairs']))-pairs
        rec=dict(iteration=iteration,mode=mode,active_pairs=len(pairs),new_pairs=len(new),mps_sha256=meta['mps_sha256'],rows=meta['rows'],columns=meta['columns'],nonzeros=meta['nonzeros'],solver_wall_seconds=solve_elapsed,checker_seconds=checker_elapsed,solver_returncode=run.returncode,master_lower_bound=lb,incumbent_cost=result['linear_model_cost'],all_security_pass=not result['security']['violated_pairs'],primal_check_pass=result['pass_primal'],check_path=check,mps_path=mps,solution_path=sol)
        trace.append(rec);print(json.dumps(rec),flush=True)
        if not result['security']['violated_pairs'] and result['pass_primal']:
            best_full=result['linear_model_cost']
            if not math.isfinite(best_full) or global_lb>best_full:
                reason='inconsistent lower bound exceeds independently validated incumbent';certificate_valid=False;break
            gap=(best_full-global_lb)/max(abs(best_full),1e-10);complete=gap<=a.gap+1e-8 and time.monotonic()<=deadline;reason=('all contingencies verified at target gap' if complete else ('verification crossed global deadline' if time.monotonic()>deadline else 'full feasible incumbent but gap target not reached'));break
        if not new:reason='non-security source checker failure or unchanged active violations';break
        pairs.update(new)
    allpairs=[];lines=list(d['Transmission lines']);outages=[lines.index(c['Affected lines'][0]) for c in d['Contingencies'].values()]
    for i,l in enumerate(lines):
        if any(math.isfinite(generate.at(d['Transmission lines'][l].get('Emergency flow limit (MW)',math.inf),t)) for t in range(T)):
            allpairs.extend((i,k) for k in outages if i!=k)
    for name,pp in [('active_pairs',sorted(pairs)),('omitted_pairs',[x for x in allpairs if x not in pairs])]:
        (out/(name+'.json')).write_text(json.dumps(pp,indent=2)+'\n')
    if complete and time.monotonic()>deadline:complete=False;reason='verification/output crossed global deadline'
    summary=dict(complete=complete,reason=reason,deadline_overrun=time.monotonic()>deadline,input_sha256=generate.sha(a.input),generator_sha256=generate.sha(generate.__file__),checker_sha256=generate.sha(check_solution.__file__),driver_sha256=generate.sha(__file__),solver_sha256=generate.sha(a.highs),solver_returncode=last_returncode,budget_seconds=a.budget,total_wall_seconds=time.monotonic()-start,seed=a.seed,target_gap=a.gap,full_feasible_incumbent=best_full,master_lower_bound=global_lb if math.isfinite(global_lb) else None,certificate_valid=certificate_valid,full_model_gap=None if not certificate_valid or best_full is None or not math.isfinite(global_lb) else (best_full-global_lb)/max(abs(best_full),1e-10),trace=trace,max_child_rss_KiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));return 0 if complete else 2
if __name__=='__main__':raise SystemExit(main())
