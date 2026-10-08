"""Read-only independent pilot audit. Never imports or calls HiGHS or its checker.
Parses the frozen original MPS directly and recomputes arithmetic with Decimal.
Writes only distinct audit reports. Run after the serialized solver cohort ends.
"""
from pathlib import Path
from decimal import Decimal, getcontext
import json, hashlib, re, sys
if not __debug__:
 raise SystemExit('Replay audit requires assertions: do not use Python -O or -OO')
getcontext().prec = 50
M=None
D=Decimal
ZERO=D(0)
INF=D('Infinity')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jread(p):return json.loads(Path(p).read_text())
def number(s):
 x=D(s)
 assert x.is_finite(),s
 return x

def parse_mps():
 section=None;rows={};cols={};rhs={};integer=False;markers=[];sections=[];bounds=[]
 for lineno,line in enumerate(M.read_text().splitlines(),1):
  if not line.strip() or line.startswith('*'):continue
  a=line.split()
  if not line.startswith(' '):
   section=a[0];assert section in ['NAME','ROWS','COLUMNS','RHS','BOUNDS','ENDATA'],(lineno,section)
   sections.append(section);continue
  if section=='ROWS':
   assert len(a)==2 and a[0] in ['N','E','L','G'] and a[1] not in rows
   rows[a[1]]=a[0]
  elif section=='COLUMNS':
   if len(a)==3 and a[1]=="'MARKER'":
    assert a[2] in ["'INTORG'","'INTEND'"]
    integer=a[2]=="'INTORG'";markers.append(a);continue
   assert len(a) in [3,5]
   if a[0] not in cols:cols[a[0]]={'a':{},'lo':ZERO,'up':INF,'int':integer}
   c=cols[a[0]];assert c['int']==integer
   for k in range(1,len(a),2):
    assert a[k] in rows
    c['a'][a[k]]=c['a'].get(a[k],ZERO)+number(a[k+1])
  elif section=='RHS':
   assert a[0]=='RHS1' and len(a) in [3,5]
   for k in range(1,len(a),2):
    assert a[k] in rows and a[k] not in rhs
    rhs[a[k]]=number(a[k+1])
  elif section=='BOUNDS':
   assert a[0] in ['BV','MI','FX','UP'] and a[1]=='BND1' and a[2] in cols
   c=cols[a[2]];bounds.append(a)
   if a[0]=='BV':assert len(a)==3;c.update(lo=ZERO,up=D(1),int=True)
   elif a[0]=='MI':assert len(a)==3;c['lo']=-INF
   elif a[0]=='FX':assert len(a)==4;c.update(lo=number(a[3]),up=number(a[3]))
   elif a[0]=='UP':assert len(a)==4;c['up']=number(a[3])
  else:raise AssertionError((lineno,line))
 assert sections==['NAME','ROWS','COLUMNS','RHS','BOUNDS','ENDATA']
 assert [k for k,v in rows.items() if v=='N']==['OBJ'] and rhs.get('OBJ',ZERO)==0
 assert not integer
 return rows,cols,rhs,bounds,markers

def compare_expected(rows,cols,rhs):
 expected=jread(M.with_suffix('.mps.expected.json'))
 assert expected['sense']==1 and expected['offset']==0
 assert list(cols)==expected['col_names']
 rnames=[r for r,t in rows.items() if t!='N'];assert rnames==expected['row_names']
 assert len(cols)==expected['num_col'] and len(rnames)==expected['num_row']
 def conv(x):return '+inf' if x==INF else '-inf' if x==-INF else float(x)
 nz=0
 for i,(c,v) in enumerate(cols.items()):
  assert conv(v['lo'])==expected['col_lower'][i] and conv(v['up'])==expected['col_upper'][i]
  assert int(v['int'])==expected['integrality'][i]
  assert float(v['a'].get('OBJ',ZERO))==expected['col_cost'][i]
  actual={r:float(coef) for r,coef in v['a'].items() if r!='OBJ' and coef!=0}
  observed={rnames[expected['a_index'][k]]:expected['a_value'][k] for k in range(expected['a_start'][i],expected['a_start'][i+1])}
  assert actual==observed,c;nz+=len(actual)
 for i,r in enumerate(rnames):
  b=rhs.get(r,ZERO);t=rows[r]
  lo=b if t in ['E','G'] else -INF;up=b if t in ['E','L'] else INF
  assert conv(lo)==expected['row_lower'][i] and conv(up)==expected['row_upper'][i],r
 assert nz==expected['num_nz']
 return {'columns':len(cols),'rows':len(rnames),'nonzeros':nz,'integer_columns':sum(c['int'] for c in cols.values()),'source_expected_exact_binary64_match':True}

def solution_audit(d,rows,cols,rhs):
 text=(d/'solution.sol').read_text();log=(d/'solver.log').read_text()
 head,tail=text.split('# Primal solution values\n',1)
 assert re.fullmatch(r'Model status\n(?:Optimal|Time limit reached)\n\n',head)
 p=tail.split('# Dual solution values',1)[0]
 assert p.startswith('Feasible\n')
 obj=number(re.findall(r'^Objective (\S+)$',p,re.M)[0])
 before,body=p.split('# Columns ',1);count,body=body.split('\n',1)
 assert int(count)==len(cols)
 values={}
 for line in body.splitlines():
  if line.startswith('#'):break
  if not line.strip():continue
  c,s=line.split();assert c not in values;values[c]=number(s)
 assert set(values)==set(cols)
 activity={r:ZERO for r,t in rows.items() if t!='N'};objective=ZERO
 maxres={'row':(ZERO,None),'lower':(ZERO,None),'upper':(ZERO,None),'integrality':(ZERO,None)}
 def update(k,v,n):
  if v>maxres[k][0]:maxres[k]=(v,n)
 for c,v in cols.items():
  x=values[c]
  update('lower',v['lo']-x,c);update('upper',x-v['up'],c)
  if v['int']:update('integrality',abs(x-x.to_integral_value()),c)
  for r,a in v['a'].items():
   if r=='OBJ':objective+=a*x
   else:activity[r]+=a*x
 for r,x in activity.items():
  t=rows[r];b=rhs.get(r,ZERO)
  update('row',abs(x-b) if t=='E' else x-b if t=='L' else b-x,r)
 assert all(v[0]<=D('1e-5') for v in maxres.values()),maxres
 objtol=max(D('1e-5'),abs(objective)*D('1e-9'))
 assert abs(objective-obj)<=objtol
 parent=log.rsplit('Solving report',1)[1]
 def field(name):
  x=re.findall(r'^  '+re.escape(name)+r'[ \t]+(.+)$',parent,re.M);assert len(x)==1,(name,x);return x[0].strip()
 upper=number(field('Primal bound'));lower=number(field('Dual bound'))
 assert field('Status') in ['Optimal','Time limit reached'] and field('Status')==head.splitlines()[1]
 assert field('Model')=='master' and field('Solution status')=='feasible'
 assert abs(upper-objective)<=objtol
 allowance=(D(10)**(lower.adjusted()-11))/2+max(D('1e-5'),abs(lower)*D('1e-11'))
 conservative=lower-allowance;gap=(objective-conservative)/max(abs(objective),D('1e-10'))
 assert conservative<=objective and gap<=D('0.01')
 g=re.fullmatch(r'([0-9.eE+-]+)% \(tolerance: 1%\)',field('Gap'));assert g
 assert abs(gap-number(g[1])/100)<=D('0.000005')+allowance/max(abs(objective),D('1e-10'))
 events=re.findall(r'^MIP-AC decision=(launch|skip) submip=(\d+) depth=(\d+)$',log,re.M)
 counts={'main_launch':0,'main_skip':0,'child_launch':0,'child_skip':0}
 for action,sub,depth in events:
  assert (sub=='0')==(depth=='0');counts[('main_' if sub=='0' else 'child_')+action]+=1
 omitted=int(d.name[-2:]) in [2,3]
 assert counts['main_launch'] and not counts['main_skip']
 assert (counts['child_skip'] and not counts['child_launch']) if omitted else (counts['child_launch'] and not counts['child_skip'])
 child_before=len(re.findall(r'Before run\(\) for\s+(?:sub-)?MIP at depth',log))
 child_after=len(re.findall(r'After  run\(\) for\s+(?:sub-)?MIP at depth',log))
 assert child_before and child_before==child_after
 accepted=re.findall(r'^\s*([A-Za-z])\s+\d+\s+\d+\s+\d+.*$',log,re.M)
 assert accepted
 profiling=[l for l in log.splitlines() if re.match(r'^(?:IPX \(AC\)|Simplex|Sub-MIP|MIP\s|\s*(?:Sub-MIP|Heuristics|LP iterations|Nodes))',l)]
 assert log.count('completed analytic centre synch')>0
 ipx=[l for l in log.splitlines() if re.match(r'^IPX \(AC\)\s+\d+\s+[0-9.eE+-]+\s+[0-9.eE+-]+',l)]
 assert ipx and any(int(l.split()[2])>0 and D(l.split()[3])>0 for l in ipx)
 assert not re.search(r'WARNING|ERROR',log)
 return {'status':field('Status'),'objective_decimal':str(objective),'printed_objective':str(obj),'objective_print_error':str(abs(objective-obj)),'reported_primal_bound':str(upper),'reported_dual_bound':str(lower),'dual_display_allowance':str(allowance),'conservative_numerical_gap':str(gap),'violations':{k:{'value':str(v),'name':n} for k,(v,n) in maxres.items()},'absolute_feasibility_tolerance':'0.00001','objective_tolerance':str(objtol),'nodes':field('Nodes'),'lp_iterations':field('LP iterations'),'ac_decisions':counts,'completed_main_sync_count':log.count('completed analytic centre synch'),'child_before_count':child_before,'child_after_count':child_after,'incumbent_source_events':accepted,'native_profile_rows':profiling,'solution_sha256':sha(d/'solution.sol'),'log_sha256':sha(d/'solver.log'),'passed':True}

def main():
 import argparse
 parser=argparse.ArgumentParser(description='Offline evidence replay only; never starts a solver')
 parser.add_argument('evidence_root',type=Path,help='Extracted retained pilot capsule')
 parser.add_argument('--output',type=Path,help='Optional NEW report path')
 args=parser.parse_args();root=args.evidence_root.resolve()
 published=jread(Path(__file__).with_name('RESULTS.json'))
 global M
 M=root/'frozen-inputs/master.mps'
 assert sha(M)==published['input']['sha256']
 assert sha(M.with_suffix('.mps.expected.json'))==published['input']['expected_sha256']
 rows,cols,rhs,bounds,markers=parse_mps();model=compare_expected(rows,cols,rhs)
 reports=[];measurements=[]
 for entry in published['runs']:
  d=root/('run-%02d'%entry['run'])
  for file,key in [('measurement.json','measurement_sha256'),('solution.sol','solution_sha256'),('solver.log','log_sha256'),('options.txt','options_sha256'),('OPTIONS_READBACK.json','options_readback_sha256')]:
   assert sha(d/file)==entry[key],(entry['run'],file)
  m=jread(d/'measurement.json');assert m['returncode']==0 and not m['watchdog_killed'] and not m['signals'] and m['interrupted'] is None and m['descendants_clean']
  assert 0<m['process_wall_seconds']<=150 and m['experiment_elapsed_seconds']<=900
  assert m['user_cpu_seconds']>=0 and m['system_cpu_seconds']>=0
  measurements.append(m);assert abs(m['aggregate_process_seconds']-sum(v['process_wall_seconds'] for v in measurements))<1e-8
  reports.append(solution_audit(d,rows,cols,rhs))
 assert len(reports)==4 and sum(m['process_wall_seconds'] for m in measurements)<=600
 pairs=[]
 for on,off in [(2,1),(3,4)]:
  a,b=measurements[on-1],measurements[off-1]
  wall=a['process_wall_seconds']/b['process_wall_seconds'];cpu=(a['user_cpu_seconds']+a['system_cpu_seconds'])/(b['user_cpu_seconds']+b['system_cpu_seconds'])
  pairs.append({'on':on,'off':off,'wall_ratio':wall,'cpu_ratio':cpu,'wall_pass':wall<=.85,'cpu_pass':cpu<=1.05})
 advance=all(p['wall_pass'] and p['cpu_pass'] for p in pairs);assert advance is False
 result={'scope':'Offline original-MPS/primal arithmetic and retained receipt replay; no solver, historical host-state revalidation, or exact dual certificate','model':model,'runs':reports,'pairs':pairs,'advance':advance,'decision':'NO-GO'}
 if args.output:
  with args.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({'runs':4,'pairs':pairs,'advance':advance,'decision':'NO-GO'},indent=2))
if __name__=='__main__':main()
