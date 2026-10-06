"""Serial official-baseline diagnostics; no core optimization or leaderboard claim."""
import argparse, hashlib, json, os, re, resource, shutil, signal, sys
from pathlib import Path


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser(); p.add_argument('--source',type=Path,required=True); p.add_argument('--build',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
 a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=False)
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'current_scuc'))
 from current_scuc import slot_envelope as envelope
 resource.setrlimit(resource.RLIMIT_CORE,(0,0)); resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3)); resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP): signal.signal(sig,envelope.request_stop)
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',LD_LIBRARY_PATH=str(a.build/'lib'))
 exe=a.build/'bin/highs'; results=[]
 panel=[('egout',1,True),('flugpl',1,True),('p0033',1,True)]
 for model in ('dcmulti','gesa2'):
  for seed in (1,2):
   for prof in ((False,True) if seed==1 else (True,False)): panel.append((model,seed,prof))
 for model,seed,prof in panel:
  case=a.source/'check/instances'/(model+'.mps'); name=f'{model}-s{seed}-profile{int(prof)}'
  item=dict(model=model,seed=seed,profile=prof,binary_sha256=sha(exe),kernel_modified=False)
  if not case.is_file():
   item['outcome']='missing_input'; results.append(item); continue
  item['model_sha256']=sha(case)
  opts=a.out/(name+'.options'); solution=a.out/(name+'.sol'); log=a.out/(name+'.log')
  opts.write_text(f'time_limit = 60\nthreads = 2\nparallel = off\nrandom_seed = {seed}\nmip_rel_gap = 0.0001\nlog_dev_level = {int(prof)}\nhighs_analysis_level = {128 if prof else 0}\nwrite_solution_to_file = true\nsolution_file = {solution}\n')
  def health():
   mem=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
   assert mem>=2*1024**3 and shutil.disk_usage(a.out).free>=2*1024**3,'headroom failed'
   assert log.stat().st_size<63*1024**2,'log cap'
  receipt=envelope.supervise([str(exe),str(case),'--options_file',str(opts)],env,log,timeout=75,health_check=health)
  item['process']=receipt; item['log_sha256']=sha(log)
  txt=log.read_text(errors='replace')
  for key,pattern in [('status',r'^\s*Status\s+(.+)$'),('primal_bound',r'^\s*Primal bound\s+(.+)$'),('dual_bound',r'^\s*Dual bound\s+(.+)$'),('gap',r'^\s*Gap\s+(.+)$')]:
   m=re.findall(pattern,txt,re.M); item[key]=m[-1].strip() if m else None
  item['outcome']='completed' if receipt['runner_returncode']==0 and receipt['total_slot_within_timeout'] and not receipt['error'] and not receipt['interruption'] and not receipt['adopted_checks_killed_and_reaped'] else 'failed_or_interrupted'
  if solution.exists(): item['solution_sha256']=sha(solution)
  results.append(item); (a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n'); print(json.dumps({k:item.get(k) for k in ('model','seed','profile','status','outcome')}),flush=True)
  if item['outcome']!='completed': break
 (a.out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__': main()
