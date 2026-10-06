"""Predeclared serial core-cache experiment. Retains every outcome."""
import argparse,hashlib,json,os,re,resource,shutil,signal,subprocess,sys,time
from pathlib import Path
from check_primal import check

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--official',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--triangle',type=Path,required=True);p.add_argument('--exporter',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',choices=['mechanism','default-off','panel','cost-profile'],required=True);a=p.parse_args();a.out.mkdir(exist_ok=False,parents=True)
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'current_scuc'))
 from current_scuc import slot_envelope as e
 resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,e.request_stop)
 models={n:a.source/'check/instances'/(n+'.mps') for n in ('egout','flugpl','dcmulti','gesa2','lseu','gt2')};models['triangle']=a.triangle
 if a.stage=='cost-profile':schedule=[(n,seed,'candidate',False) for n in ('dcmulti','gesa2') for seed in (1,2,3)]
 elif a.stage=='mechanism':schedule=[('gesa2',1,'candidate',True)]
 elif a.stage=='default-off':schedule=[(n,1,arm,False) for n in ('dcmulti','gesa2') for arm in ('official','candidate')]
 else:schedule=[(n,seed,arm,arm=='candidate') for n in models for seed in (1,2,3) for arm in (('official','candidate') if seed%2 else ('candidate','official'))]
 records=[];matrices={}
 for name,seed,arm,enabled in schedule:
  started=time.perf_counter();case=models[name];key=f'{name}-s{seed}-{arm}';directory=a.out/key;directory.mkdir();r=dict(model=name,seed=seed,arm=arm,enabled=enabled,stage=a.stage)
  if not case.is_file():r['outcome']='missing_input';records.append(r);continue
  if name not in matrices:
   matrix=a.out/(name+'-original.json')
   subprocess.run([str(a.exporter),str(case),str(matrix)],check=True,timeout=20,env=dict(os.environ,LD_LIBRARY_PATH=str(a.official/'lib')));matrices[name]=matrix
  r.update(model_sha256=sha(case),matrix_sha256=sha(matrices[name]))
  prefix=a.official if arm=='official' else a.candidate;exe=prefix/'bin/highs';sol=directory/'point.sol';options=directory/'options.txt';log=directory/'stdout.log'
  options.write_text(f'time_limit = 60\nthreads = 2\nparallel = off\nrandom_seed = {seed}\nmip_rel_gap = 0.0001\nwrite_solution_to_file = true\nsolution_file = {sol}\n'+(f'mip_cmir_cache_coefficients = {str(enabled).lower()}\nmip_cmir_cache_log = {str(a.stage=="mechanism").lower()}\n' if arm=='candidate' and a.stage!='cost-profile' else ('log_dev_level = 2\n' if a.stage=='cost-profile' else '')))
  env=dict(os.environ,LD_LIBRARY_PATH=str(prefix/'lib'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
  def health():
   mem=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
   assert mem>=2*1024**3 and shutil.disk_usage(a.out).free>=2*1024**3,'headroom failed'
   todo=[os.getpid()];seen=set();rss=0
   while todo:
    pid=todo.pop()
    if pid in seen:continue
    seen.add(pid);todo.extend(e.children_of(pid))
    try:status=Path(f'/proc/{pid}/status').read_text().splitlines()
    except FileNotFoundError:continue
    rss+=sum(int(s.split()[1])*1024 for s in status if s.startswith('VmRSS:'))
   assert rss<=6*1024**3,'RSS cap'
  receipt=e.supervise([str(exe),str(case),'--options_file',str(options)],env,log,timeout=74,health_check=health)
  r.update(process=receipt,binary_sha256=sha(exe),library_sha256=sha(prefix/'lib/libhighs.so'),log_sha256=sha(log))
  txt=log.read_text(errors='replace')
  for field,pattern in [('status',r'^\s*Status\s+(.+)$'),('primal',r'^\s*Primal bound\s+(.+)$'),('dual',r'^\s*Dual bound\s+(.+)$'),('gap',r'^\s*Gap\s+(.+)$'),('nodes',r'^\s*Nodes\s+(.+)$'),('iterations',r'^\s*LP iterations\s+(.+)$')]:
   matches=re.findall(pattern,txt,re.M);r[field]=matches[-1].strip() if matches else None
  calls=re.findall(r'CMIR_CACHE row=(\d+) integer=(\d+) queries=(\d+) computations=(\d+)',txt)
  r['cache_work']=dict(calls=len(calls),queries=sum(int(x[2]) for x in calls),computations=sum(int(x[3]) for x in calls))
  clean=receipt['runner_returncode'] in (0,1) and receipt['total_slot_within_timeout'] and not any(receipt[x] for x in ('error','interruption','health_check_error','adopted_checks_killed_and_reaped'))
  if sol.exists():r.update(solution_sha256=sha(sol),check=check(matrices[name],sol))
  r['outcome']='completed' if clean and r.get('check',{}).get('passed') else 'failed_or_incomplete';r['whole_arm_seconds']=time.perf_counter()-started
  records.append(r);(a.out/'results.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps({k:r.get(k) for k in ('model','seed','arm','status','outcome','cache_work')}),flush=True)
  if not clean or (r.get('check') and not r['check']['passed']):raise RuntimeError('Resource, process, or primal-check failure; remaining slots unrun')
 (a.out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
if __name__=='__main__':main()
