"""Report every fixed pair, with censoring rather than fabricated speedups."""
import argparse,json,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=json.loads(a.results.read_text());pairs=[];groups={}
for row in r:groups.setdefault((row['model'],row['seed']),{})[row['arm']]=row
for (model,seed),arms in groups.items():
 x=dict(model=model,seed=seed)
 if set(arms)!= {'official','candidate'}:x['complete']=False;pairs.append(x);continue
 b,c=arms['official'],arms['candidate'];tb=b['process']['total_slot_elapsed_seconds'];tc=c['process']['total_slot_elapsed_seconds']
 valid=all(v['outcome']=='completed' and v['status']=='Optimal' and v['check']['passed'] for v in (b,c))
 x.update(complete=True,paired_success=valid,official_seconds=tb,candidate_seconds=tc,change_percent=(tc/tb-1)*100 if valid else None,official_status=b['status'],candidate_status=c['status'],official_cost=b['check']['cost'],candidate_cost=c['check']['cost'],same_solution_bytes=b.get('solution_sha256')==c.get('solution_sha256'),same_reported_dual=b['dual']==c['dual'],same_nodes=b['nodes']==c['nodes'],same_iterations=b['iterations']==c['iterations'])
 pairs.append(x)
scored=[x for x in pairs if x.get('paired_success') and x['official_seconds']>=.5]
changes=[x['change_percent'] for x in scored];passed=bool(changes) and statistics.median(changes)<=-5 and max(changes)<=20 and all(x.get('paired_success') for x in pairs) and len(pairs)==21
out=dict(pairs=pairs,complete_pairs=sum(x.get('complete',False) for x in pairs),successful_pairs=sum(x.get('paired_success',False) for x in pairs),scored_pairs=len(scored),median_change_percent=statistics.median(changes) if changes else None,worst_change_percent=max(changes) if changes else None,predeclared_speed_gate_passed=passed,statistics_scope='Exposed small development panel; three seeds are not a reliability estimate; no commercial or SCUC speedup claim')
a.output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='pairs'},indent=2))
for x in pairs:print(x['model'],x['seed'],x.get('official_seconds'),x.get('candidate_seconds'),x.get('change_percent'),x.get('same_solution_bytes'))
