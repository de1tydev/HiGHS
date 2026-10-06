"""Synthetic end-to-end contract check, not a SCUC or acceleration benchmark."""
import argparse, itertools, json, os, resource, signal, sys, time
from pathlib import Path
from history_start import propose


def optimum(demand):
 points=[x for x in itertools.product((0,1),repeat=4) if 2*x[0]+3*x[1]>=demand[0] and 2*x[2]+3*x[3]>=demand[1] and x[0]<=x[2]]
 return min(points,key=lambda x:(sum(c*v for c,v in zip((3,5,3,5),x)),x))


def main():
 p=argparse.ArgumentParser();p.add_argument('--adapter',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(exist_ok=False)
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'current_scuc'))
 from current_scuc import slot_envelope as envelope
 resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,envelope.request_stop)
 label_started=time.perf_counter();names=['u0','u1','u2','u3'];history=[]
 for day,load in enumerate(([2,2],[3,3],[4,4]),1):
  history.append(dict(id=f'train{day}',end=f'2017-01-0{day+1}T12:00:00Z',label_available=f'2017-01-0{day+1}T13:00:00Z',feature=load,columns=names,topology='synthetic-two-period',u=list(optimum(load)),checked=True))
 label_generation_seconds=time.perf_counter()-label_started
 history.append(dict(history[0],id='future',end='2017-01-07T12:00:00Z'))
 query=dict(start='2017-01-06T00:00:00Z',feature=[3,4],columns=names,topology='synthetic-two-period')
 (a.out/'input.json').write_text(json.dumps(dict(history=history,query=query,label_generation_seconds=label_generation_seconds,label_method='exhaustive synthetic enumeration, not a production SCUC label'),indent=2)+'\n')
 model=a.out/'target.lp';model.write_text('min\n obj: 3 u0 + 5 u1 + 3 u2 + 5 u3\nst\n h0: 2 u0 + 3 u1 >= 3\n h1: 2 u2 + 3 u3 >= 4\n up: u0 - u2 <= 0\nbinary\n u0 u1 u2 u3\nend\n')
 target=optimum(query['feature']);cost=sum(c*v for c,v in zip((3,5,3,5),target));records=[]
 for method in ('cold','previous','nearest','consensus','infeasible_start'):
  start=time.perf_counter();prediction=propose(query,history,method,k=2) if method in ('previous','nearest','consensus') else None
  if prediction: assert [x['id'] for x in prediction['excluded']]==['future']
  proposals=prediction['suggestions'] if prediction else ({x:0 for x in names} if method=='infeasible_start' else {})
  path=a.out/(method+'.start');path.write_text(''.join(f'{name} {value}\n' for name,value in proposals.items()));sol=a.out/(method+'.sol');log=a.out/(method+'.log')
  receipt=envelope.supervise([str(a.adapter),str(model),str(path) if proposals else '-',str(sol),'10'],dict(os.environ),log,timeout=20)
  ok=receipt['runner_returncode']==0 and receipt['total_slot_within_timeout'] and not receipt['error'] and not receipt['adopted_checks_killed_and_reaped']
  raw=sol.read_text() if sol.exists() else '';lines=raw.splitlines();values={}
  for line in lines:
   terms=line.split()
   if len(terms)==2 and terms[0] in names:values[terms[0]]=float(terms[1])
  primal=[values.get(n,float('nan')) for n in names]
  valid=all(v in (0.,1.) for v in primal) and 2*primal[0]+3*primal[1]>=3 and 2*primal[2]+3*primal[3]>=4 and primal[0]<=primal[2]
  checked_cost=sum(c*v for c,v in zip((3,5,3,5),primal))
  passed=ok and valid and checked_cost==cost and 'UNRESTRICTED_MODEL_BOUNDS_PRESERVED' in log.read_text()
  records.append(dict(method=method,passed=passed,prediction=prediction,suggestions=proposals,process=receipt,end_to_end_seconds=time.perf_counter()-start,independent_cost=checked_cost,enumerated_global_optimum=cost,synthetic_only=True))
  (a.out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
  if not passed: raise RuntimeError(f'Failed {method}')
 print(json.dumps(dict(passed=all(x['passed'] for x in records),arms=len(records),production_scuc_validated=False)))
if __name__=='__main__':main()
