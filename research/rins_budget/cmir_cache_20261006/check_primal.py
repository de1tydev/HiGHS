"""Independent arithmetic on original native model readback; no solver call.

This verifies primals, not parser independence or global dual correctness.
"""
import json,math
from pathlib import Path

def check(matrix,solution):
 m=json.loads(Path(matrix).read_text());lines=Path(solution).read_text().splitlines();values={};active=False
 for line in lines:
  if line.startswith('# Columns '):active=True;continue
  if active and line.startswith('#'):break
  if active:
   pair=line.split()
   if len(pair)!=2:continue
   if pair[0] in values:raise ValueError('Duplicate solution column')
   values[pair[0]]=float(pair[1])
 if set(values)!=set(m['names']):return dict(passed=False,error='Missing or extra solution columns')
 x=[values[n] for n in m['names']]
 if not all(math.isfinite(v) for v in x):return dict(passed=False,error='Nonfinite point')
 integer=m['integer'] or [0]*len(x)
 if any(k not in (0,1) for k in integer):raise ValueError('Unsupported integrality type')
 bound=max([0.]+[max(float(lo)-v,v-float(hi)) for lo,hi,v in zip(m['lower'],m['upper'],x)])
 intvio=max([0.]+[abs(v-round(v)) for v,k in zip(x,integer) if k==1])
 rows=[[] for _ in m['row_lower']]
 for j,v in enumerate(x):
  for k in range(int(m['start'][j]),int(m['start'][j+1])):rows[int(m['index'][k])].append(m['value'][k]*v)
 activity=[math.fsum(row) for row in rows]
 rowvio=max([0.]+[max(float(lo)-v,v-float(hi)) for lo,hi,v in zip(m['row_lower'],m['row_upper'],activity)])
 cost=math.fsum(c*v for c,v in zip(m['cost'],x))+float(m['offset'])
 objectives=[float(s.split()[1]) for s in lines if s.startswith('Objective ')]
 objective_error=abs(cost-objectives[0]) if objectives else math.inf
 tol=1e-6
 return dict(passed=bound<=tol and intvio<=tol and rowvio<=tol and objective_error<=max(tol,abs(cost)*5e-12),cost=cost,bound_violation=bound,integrality_violation=intvio,row_violation=rowvio,objective_error=objective_error,primal_tolerance=tol,columns=len(x),rows=len(rows),dual_proof=False)
