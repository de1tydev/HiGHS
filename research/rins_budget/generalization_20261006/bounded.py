"""Standalone exact-reap wrapper for one research command. No retry."""
import argparse,json,os,resource,shutil,signal,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=float,required=True);p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'current_scuc'))
from current_scuc import slot_envelope as envelope
resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_AS,(7*1024**3,7*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(512*1024**2,512*1024**2))
for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,envelope.request_stop)
def health():
 mem=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024
 assert mem>=2*1024**3 and shutil.disk_usage(a.out).free>=2*1024**3,'headroom failed'
 todo=[os.getpid()];seen=set();rss=0
 while todo:
  pid=todo.pop()
  if pid in seen:continue
  seen.add(pid);todo.extend(envelope.children_of(pid))
  try:lines=Path(f'/proc/{pid}/status').read_text().splitlines()
  except FileNotFoundError:continue
  rss+=sum(int(s.split()[1])*1024 for s in lines if s.startswith('VmRSS:'))
 assert rss<=6*1024**3,'RSS limit'
command=a.command[1:] if a.command and a.command[0]=='--' else a.command
r=envelope.supervise(command,dict(os.environ),a.out/'stdout.log',timeout=a.seconds-1,health_check=health)
(a.out/'receipt.json').write_text(json.dumps(r,indent=2)+'\n')
passed=r['runner_returncode']==0 and r['total_slot_within_timeout'] and not r['error'] and not r['interruption'] and not r['adopted_checks_killed_and_reaped']
print(json.dumps(dict(passed=passed,receipt=str(a.out/'receipt.json'))))
raise SystemExit(0 if passed else 2)
