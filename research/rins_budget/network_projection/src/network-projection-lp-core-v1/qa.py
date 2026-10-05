"""O(nnz) numerical checks in the loaded unscaled model; not exact certificates."""
from __future__ import annotations
import math
import numpy as np
from model import matrix

NATIVE_TOL=1e-7
SOURCE_TOL=1e-5


def _maximum(a):
    if not len(a):return {'max':0.,'index':None}
    j=int(np.argmax(a));return {'max':float(a[j]),'index':j}


def check_primal(e, x, *, tolerance=SOURCE_TOL):
    """Rows, bounds and cost, without integrality; accurate summation per row."""
    x=np.asarray(x,dtype=np.float64)
    if x.shape!=(e['num_col'],) or not np.all(np.isfinite(x)):
        return {'passed':False,'failures':['nonfinite or wrong-sized primal'],'integrality_checked':False}
    a=matrix(e).tocsr()
    activities=np.empty(e['num_row'])
    try:
        for r in range(e['num_row']):
            lo,hi=a.indptr[r:r+2]
            activities[r]=math.fsum(float(a.data[k])*float(x[a.indices[k]]) for k in range(lo,hi))
        objective=math.fsum([float(e['offset']),*(float(c)*float(v) for c,v in zip(e['col_cost'],x))])
    except (ValueError,OverflowError):
        return {'passed':False,'failures':['nonfinite primal arithmetic'],'integrality_checked':False}
    if not np.all(np.isfinite(activities)) or not math.isfinite(objective):
        return {'passed':False,'failures':['nonfinite primal arithmetic'],'integrality_checked':False}
    rows=np.maximum(0.,np.maximum(e['row_lower']-activities,activities-e['row_upper']))
    bounds=np.maximum(0.,np.maximum(e['col_lower']-x,x-e['col_upper']))
    rm,bm=_maximum(rows),_maximum(bounds)
    if rm['index'] is not None:rm['name']=e['row_names'][rm['index']]
    if bm['index'] is not None:bm['name']=e['col_names'][bm['index']]
    failures=[]
    if rm['max']>tolerance:failures.append('independent row infeasibility')
    if bm['max']>tolerance:failures.append('independent bound infeasibility')
    return {'passed':not failures,'failures':failures,'row':rm,'bound':bm,
            'row_violations_over_tolerance':int(np.count_nonzero(rows>tolerance)),
            'bound_violations_over_tolerance':int(np.count_nonzero(bounds>tolerance)),
            'objective_recomputed':objective,'tolerance':tolerance,'integrality_checked':False,
            'summation':'math.fsum of binary64 products, including objective offset',
            'activities':activities}


def check_solution(e, s, *, native_tolerance=NATIVE_TOL, independent_tolerance=SOURCE_TOL):
    """Fail-closed native status + independent numerical primal/stationarity QA."""
    failures=[];info=s.get('info',{});returns=s.get('info_returns',{})
    if s.get('run_status')!=0:failures.append('Highs_run did not return clean OK')
    if s.get('model_status')!=7:failures.append('model is not Optimal')
    if s.get('solution_status')!=0:failures.append('solution getter failed')
    if s.get('basis_status')!=0:failures.append('basis getter failed')
    if s.get('diagnostics',{}).get('fatal'):failures.append('unclassified native diagnostics')
    for name,wanted in (('primal_solution_status',2),('dual_solution_status',2),('basis_validity',1),('num_primal_infeasibilities',0),('num_dual_infeasibilities',0)):
        if returns.get(name)!=0 or info.get(name)!=wanted:failures.append('native '+name)
    for name in ('max_primal_infeasibility','max_dual_infeasibility','primal_dual_objective_error'):
        v=info.get(name)
        if returns.get(name)!=0 or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=native_tolerance:failures.append('native '+name)
    obj=info.get('objective_function_value')
    if returns.get('objective_function_value')!=0 or not isinstance(obj,(int,float)) or not math.isfinite(obj):failures.append('native objective unavailable')
    native={'info':info,'info_nonfinite':s.get('info_nonfinite',{}),'info_returns':returns,'run_status':s.get('run_status'),'model_status':s.get('model_status'),
            'basis_getter_status':s.get('basis_status'),'solution_getter_status':s.get('solution_status'),
            'optional_residual_statistics':{k:{'raw':v,'available':returns.get(k)==0 and isinstance(v,(int,float)) and math.isfinite(v) and v>=0} for k,v in info.items() if 'residual' in k},
            'primal_dual_objective_error_units':'abs(P-D)/(1+abs(P)+abs(D)); not dollars'}
    primal=check_primal(e,s.get('col_value',[]),tolerance=independent_tolerance)
    failures.extend(primal['failures'])
    activities=primal.pop('activities',None)
    y=np.asarray(s.get('row_dual',[]),dtype=np.float64);z=np.asarray(s.get('col_dual',[]),dtype=np.float64)
    stationarity={'max':None,'index':None}
    if y.shape!=(e['num_row'],) or z.shape!=(e['num_col'],) or not np.all(np.isfinite(y)) or not np.all(np.isfinite(z)):
        failures.append('nonfinite or wrong-sized duals')
    else:
        residual=np.empty(e['num_col'])
        try:
            for j in range(e['num_col']):
                lo,hi=e['a_start'][j:j+2]
                residual[j]=abs(math.fsum([float(e['col_cost'][j]),-float(z[j]),*(-float(e['a_value'][k])*float(y[e['a_index'][k]]) for k in range(lo,hi))]))
            if not np.all(np.isfinite(residual)):raise ValueError('nonfinite')
            stationarity=_maximum(residual);stationarity['name']=e['col_names'][stationarity['index']]
            if stationarity['max']>independent_tolerance:failures.append('independent stationarity residual')
        except (OverflowError,ValueError):failures.append('nonfinite stationarity arithmetic')
    col_basis=np.asarray(s.get('col_basis',[]));row_basis=np.asarray(s.get('row_basis',[]))
    if col_basis.shape!=(e['num_col'],) or row_basis.shape!=(e['num_row'],) or not np.all(np.isin(col_basis,range(5))) or not np.all(np.isin(row_basis,range(5))) or int(np.count_nonzero(col_basis==1)+np.count_nonzero(row_basis==1))!=e['num_row']:
        failures.append('invalid basis statuses or basic count')
    activity_difference=None
    if activities is not None:
        native_activity=np.asarray(s.get('row_value',[]),dtype=np.float64)
        if native_activity.shape!=activities.shape or not np.all(np.isfinite(native_activity)):
            failures.append('native row activities unavailable')
        else:
            activity_difference=_maximum(np.abs(activities-native_activity))
            if activity_difference['max']>independent_tolerance:failures.append('native/independent row activity mismatch')
    objective_difference=None;objective_allowance=None
    if 'objective_recomputed' in primal and isinstance(obj,(int,float)) and math.isfinite(obj):
        objective_difference=primal['objective_recomputed']-obj
        objective_allowance=max(1e-5,1e-10*max(abs(obj),abs(primal['objective_recomputed'])))
        if abs(objective_difference)>objective_allowance:failures.append('native/independent objective mismatch')
    return {'passed':not failures,'failures':failures,'native':native,'primal':primal,'stationarity':stationarity,
            'activity_difference':activity_difference,'objective_difference':objective_difference,'objective_allowance':objective_allowance,
            'native_tolerance':native_tolerance,'independent_tolerance':independent_tolerance,
            'stationarity_formula':'c - A^T row_dual - col_dual, original objective units',
            'exact_dual_bound_certified':False,'qualification':'Numerical QA only, not an exact-real primal/dual proof'}
