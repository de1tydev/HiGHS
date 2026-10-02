#!/usr/bin/env python3
"""Independent source-data checker. Does NOT import generator or its matrix.
Re-factors each outage topology directly, without using generated LODFs.
"""
import argparse, gzip, json, math, pathlib, hashlib
import numpy as np
from scipy.sparse import coo_matrix,diags
from scipy.sparse.linalg import splu

def at(x,t):return float(x[t] if isinstance(x,list) else x)
def read_sol(p):
    if str(p).endswith('.json'):return json.loads(pathlib.Path(p).read_text())
    vals={};active=False
    for line in pathlib.Path(p).read_text().splitlines():
        s=line.strip()
        if s.startswith('# Columns'): active=True;continue
        if s.startswith('#') and active:break
        if active:
            parts=s.split()
            if len(parts)==2:vals[parts[0]]=float(parts[1])
    if not vals:raise ValueError('No column values in solution file')
    return vals

def check(source,solution,mode,T,tol=1e-5,check_all_security=False):
    with (gzip.open(source,'rt') if str(source).endswith('.gz') else open(source)) as stream:d=json.load(stream)
    x=read_sol(solution)
    worst={};counts={};missing=[]
    def val(k):
        if k not in x:missing.append(k);return math.nan
        return x[k]
    def le(cat,excess):
        excess=float(excess)
        if not math.isfinite(excess):worst[cat]=math.inf;counts[cat]=counts.get(cat,0)+1;return
        worst[cat]=max(worst.get(cat,0),max(0,excess))
        if excess>tol:counts[cat]=counts.get(cat,0)+1
    bs=list(d['Buses']);ls=list(d['Transmission lines']);gs=list(d['Generators']);bi={b:i for i,b in enumerate(bs)}
    inject=np.zeros((len(bs),T));production_cost=start_cost=shed_cost=flow_cost=reserve_cost=0.;shed_total=0.;max_over=0.
    for b,bd in d['Buses'].items():
        for t in range(T):
            load=at(bd['Load (MW)'],t);s=val(f'shed_{b}_{t}');le('shed_bounds',max(-s,s-load));inject[bi[b],t]=s-load;shed_cost+=s*at(d['Parameters'].get('Power balance penalty ($/MW)',1000),t);shed_total+=s
    rtot={r:np.zeros(T) for r in d.get('Reserves',{})}
    for g,gd in d['Generators'].items():
        bp=gd['Production cost curve (MW)'];bc=gd['Production cost curve ($)'];pmin,pmax=bp[0],bp[-1];prevon=int(gd['Initial status (h)']>0);duration=abs(int(gd['Initial status (h)']));prevp=gd['Initial power (MW)'];prevr=0.;U=gd.get('Minimum uptime (h)',1);D=gd.get('Minimum downtime (h)',1);ru=gd.get('Ramp up limit (MW)',pmax);rd=gd.get('Ramp down limit (MW)',pmax);su=min(gd.get('Startup limit (MW)',pmax),pmax);sd=min(gd.get('Shutdown limit (MW)',pmax),pmax)
        for t in range(T):
            u=val(f'u_{g}_{t}');y=val(f'y_{g}_{t}');z=val(f'z_{g}_{t}');p=val(f'p_{g}_{t}');on=int(u>=0.5);r=0.
            for a in [u,y,z]:le('binary',max(abs(a-round(a)), -a,a-1))
            le('transition',abs(u-prevon-y+z));le('exclusive_transition',y+z-1)
            if on!=prevon:
                le('minimum_time',(U if prevon else D)-duration)
                if on:
                    cs=gd.get('Startup costs ($)',[0]);ds=gd.get('Startup delays (h)',[D]);eligible=[k for k,delay in enumerate(ds) if delay<=duration];cost=cs[max(eligible)] if eligible else cs[0];start_cost+=cost;le('startup_cost_epigraph',cost-val(f'sc_{g}_{t}'))
                duration=0
            if at(gd.get('Must run?',False),t):le('must_run',1-u)
            for reserve in gd.get('Reserve eligibility',[]):
                rr=val(f'reserve_{reserve}_{g}_{t}');le('reserve_nonnegative',-rr);r+=rr;rtot[reserve][t]+=rr
            le('dispatch_bounds',max(pmin*u-p,p+r-pmax*u));le('startup_power',p+r-pmax*u+(pmax-su)*y)
            le('ramp_up',p+r-prevp-ru*prevon-su*y)
            le('ramp_down',prevp+prevr-p-rd*u-sd*z)
            if t<T-1:le('shutdown_power',p+r-pmax*u+(pmax-sd)*val(f'z_{g}_{t+1}'))
            le('dispatch_nonnegative',-p);le('startup_cost_nonnegative',-val(f'sc_{g}_{t}'))
            if on:production_cost+=float(np.interp(p,bp,bc))
            inject[bi[gd['Bus']],t]+=p;duration+=1;prevon=on;prevp=p;prevr=r
    for r,rd in d.get('Reserves',{}).items():
        for t in range(T):
            short=val(f'short_{r}_{t}');pen=at(rd.get('Shortfall penalty ($/MW)',-1),t);le('reserve_shortfall_bound',max(-short,short if pen<0 else 0));le('reserve_requirement',at(rd['Amount (MW)'],t)-rtot[r][t]-short);reserve_cost+=max(0,pen)*short
    for t in range(T):le('system_balance',abs(inject[:,t].sum()))
    violated_pairs=set();security_excess=0.;security_raw_excess=0.;security_violations=0;base_raw_excess=0.;outages_checked=0;flow_error=0.
    if mode!='uc' or check_all_security:
        if mode!='uc':
            for t in range(T):le('reference_angle',abs(val(f'theta_{bs[0]}_{t}')))
        rows=[];cols=[];data=[]
        for i,l in enumerate(ls):
            ld=d['Transmission lines'][l];rows += [i,i];cols += [bi[ld['Source bus']],bi[ld['Target bus']]];data += [1.,-1.]
        A=coo_matrix((data,(rows,cols)),shape=(len(ls),len(bs))).tocsr();Ar=A[:,1:];weights=np.array([d['Transmission lines'][l]['Susceptance (S)'] for l in ls]);B=(Ar.T@diags(weights)@Ar).tocsc();theta=splu(B).solve(inject[1:]);flows=weights[:,None]*(Ar@theta)
        over=np.zeros_like(flows)
        for i,l in enumerate(ls):
            ld=d['Transmission lines'][l]
            for t in range(T):
                if f'over_{l}_{t}' in x:
                    o=val(f'over_{l}_{t}');over[i,t]=o;le('overflow_nonnegative',-o);flow_cost+=o*at(ld.get('Flow limit penalty ($/MW)',5000),t);max_over=max(max_over,o)
                if mode!='uc':
                    le('direct_base_flow',abs(flows[i,t]-val(f'f_{l}_{t}')))
                    angle=val(f'theta_{ld["Source bus"]}_{t}')-val(f'theta_{ld["Target bus"]}_{t}');le('phase_angle_flow',abs(weights[i]*angle-val(f'f_{l}_{t}')))
                lim=at(ld.get('Normal flow limit (MW)',math.inf),t)
                if math.isfinite(lim):
                    raw=abs(flows[i,t])-lim;base_raw_excess=max(base_raw_excess,raw)
                    if mode!='uc':le('normal_line_limit',raw-over[i,t])
        if mode=='n1' or check_all_security:
            for cname,cont in d['Contingencies'].items():
                assert not cont.get('Affected generators') and not cont.get('Affected units') and len(cont['Affected lines'])==1
                k=ls.index(cont['Affected lines'][0]);w=weights.copy();w[k]=0.;Bk=(Ar.T@diags(w)@Ar).tocsc()
                angles=splu(Bk).solve(inject[1:]);post=w[:,None]*(Ar@angles);outages_checked+=1
                for i,l in enumerate(ls):
                    if i==k:continue
                    ld=d['Transmission lines'][l]
                    for t in range(T):
                        lim=at(ld.get('Emergency flow limit (MW)',math.inf),t)
                        if math.isfinite(lim):
                            raw=abs(post[i,t])-lim;excess=raw-over[i,t];security_raw_excess=max(security_raw_excess,raw);security_excess=max(security_excess,excess)
                            if excess>tol:security_violations+=1;violated_pairs.add((i,k))
                            if mode=='n1':le('emergency_line_limit',excess)
    if missing:raise ValueError('Missing columns: '+str(sorted(set(missing))[:20]))
    true_objective=production_cost+start_cost+shed_cost+flow_cost+reserve_cost
    # Independent recovery of the linear model's objective from original coefficients.
    linear_obj=shed_cost+flow_cost+reserve_cost
    for g,gd in d['Generators'].items():
        bp=gd['Production cost curve (MW)'];bc=gd['Production cost curve ($)']
        for t in range(T):
            linear_obj+=bc[0]*val(f'u_{g}_{t}')+val(f'sc_{g}_{t}')
            segsum=0.
            for k in range(len(bp)-1):
                sv=val(f'seg_{g}_{t}_{k}');le('segment_bounds',max(-sv,sv-(bp[k+1]-bp[k])*val(f'u_{g}_{t}')));segsum+=sv;linear_obj+=(bc[k+1]-bc[k])/(bp[k+1]-bp[k])*sv
            le('segment_dispatch',abs(val(f'p_{g}_{t}')-bp[0]*val(f'u_{g}_{t}')-segsum))
    return dict(pass_primal=not counts,tolerance=tol,mode=mode,hours=T,max_violation_by_category=worst,violations_by_category=counts,true_source_cost=true_objective,linear_model_cost=linear_obj,objective_overpayment=linear_obj-true_objective,total_shed_MWh=shed_total,max_overflow_MW=max_over,base_unrelaxed_overload_MW=max(0,base_raw_excess),security=dict(violated_pairs=sorted(violated_pairs),outages_checked=outages_checked,max_violation_after_shared_slack_MW=max(0,security_excess),max_unrelaxed_overload_MW=max(0,security_raw_excess),violated_line_hours=security_violations),source_sha256=hashlib.sha256(pathlib.Path(source).read_bytes()).hexdigest(),solution_sha256=hashlib.sha256(pathlib.Path(solution).read_bytes()).hexdigest())

def main():
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('solution');p.add_argument('--mode',choices=['uc','network','n1'],required=True);p.add_argument('--hours',type=int,default=36);p.add_argument('--tolerance',type=float,default=1e-5);p.add_argument('--all-security',action='store_true');args=p.parse_args();r=check(args.source,args.solution,args.mode,args.hours,args.tolerance,args.all_security);print(json.dumps(r,indent=2));raise SystemExit(0 if r['pass_primal'] else 1)
if __name__=='__main__':main()
