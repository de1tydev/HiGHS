"""Aggregate disjoint diagnostic call sites, preserving main/sub-MIP scopes."""
import argparse,collections,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();out=[]
for r in json.loads((a.directory/'results.json').read_text()):
 log=a.directory/f"{r['model']}-s{r['seed']}-candidate"/'stdout.log'
 groups=collections.defaultdict(lambda:dict(calls=0,seconds=0.,pool_delta=0,lp_iterations=0))
 for name,submip,depth,seconds,pool,iterations in re.findall(r'SEP_COST name=(\w+) submip=(\d+) depth=(\d+) seconds=([^ ]+) pool_delta=(-?\d+) lp_iterations=(-?\d+)',log.read_text()):
  key=f'{"submip" if int(submip) else "main"}/{name}';g=groups[key];g['calls']+=1;g['seconds']+=float(seconds);g['pool_delta']+=int(pool);g['lp_iterations']+=int(iterations)
 out.append(dict(model=r['model'],seed=r['seed'],outcome=r['outcome'],primal_checked=r.get('check',{}).get('passed'),groups=groups))
(a.directory/'cost-summary.json').write_text(json.dumps(out,indent=2)+'\n')
for r in out:
 print(r['model'],r['seed'], sorted([(k,round(v['seconds'],6),v['pool_delta']) for k,v in r['groups'].items()],key=lambda x:x[1],reverse=True)[:8])
