"""Small CSC expected-model utilities. No solver, generator or factorization."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from scipy.sparse import csc_matrix, csr_matrix, vstack

ARRAY_FIELDS = ('col_lower','col_upper','col_cost','row_lower','row_upper','integrality','a_start','a_index','a_value')
SCALAR_FIELDS = ('num_col','num_row','num_nz','sense','offset')
INT_FIELDS = ('integrality','a_start','a_index')


def require(ok, message):
    if not ok: raise ValueError(message)


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def digest(a):
    a=np.asarray(a)
    return hashlib.sha256(a.astype('<i4' if a.dtype.kind in 'biu' else '<f8',copy=False).tobytes()).hexdigest()


def validate_model(e):
    """Reject malformed indices before coercion can wrap; exact sorted CSC only."""
    for k in ('num_col','num_row','num_nz'):
        require(type(e[k]) is int and 0<=e[k]<2**31,'Invalid 32-bit dimension '+k)
    n,m,nz=(e[k] for k in ('num_col','num_row','num_nz'))
    require(n>0 and e['sense'] in (1,-1) and math.isfinite(e['offset']),'Invalid objective')
    sizes={'col_lower':n,'col_upper':n,'col_cost':n,'row_lower':m,'row_upper':m,'integrality':n,'a_start':n+1,'a_index':nz,'a_value':nz}
    out={k:e[k] for k in SCALAR_FIELDS}
    for k,size in sizes.items():
        a=np.asarray(e[k]); require(a.shape==(size,),'Invalid array shape '+k)
        if k in INT_FIELDS:
            require(a.dtype.kind in 'biu' and np.all(a>=0) and np.all(a<2**31),'Invalid integer array '+k)
        out[k]=np.ascontiguousarray(a,dtype=np.int32 if k in INT_FIELDS else np.float64)
    for k,size in (('col_names',n),('row_names',m)):
        names=list(e[k]); require(len(names)==size and len(set(names))==size,'Bad names '+k)
        require(all(isinstance(x,str) and x and len(x.encode())<4096 and '\x00' not in x for x in names),'Unsafe names '+k)
        out[k]=names
    require(np.all(np.isfinite(out['col_cost'])) and np.all(np.isfinite(out['a_value'])) and np.all(out['a_value']!=0),'Bad coefficients')
    for pre in ('col','row'):
        lo,up=(out[pre+'_'+v] for v in ('lower','upper'))
        require(not np.any(np.isnan(lo)|np.isnan(up)) and np.all(lo<=up) and not np.any(lo==np.inf) and not np.any(up==-np.inf),'Bad '+pre+' bounds')
    require(np.all(np.isin(out['integrality'],[0,1])),'Only ordinary continuous/integer domains supported')
    s,i=out['a_start'],out['a_index']
    require(s[0]==0 and s[-1]==nz and np.all(s[1:]>=s[:-1]) and np.all(i<m),'Bad CSC endpoints/indices')
    # A decreasing/equal adjacent row index is forbidden except at a column boundary.
    if nz>1:
        bad=i[1:]<=i[:-1]; boundary=np.unique(s[1:-1]); boundary=boundary[(boundary>0)&(boundary<nz)]
        bad[boundary-1]=False
        require(not np.any(bad),'Unsorted or duplicate CSC entry')
    return out


def load_expected(path, expected_sha256=None):
    if expected_sha256 is not None: require(sha256(path)==expected_sha256,'Expected input hash mismatch')
    def unique(items):
        d={}
        for k,v in items:
            require(k not in d,'Duplicate JSON key '+k);d[k]=v
        return d
    with open(path) as f: e=json.load(f,object_pairs_hook=unique)
    return validate_model(e)


def matrix(e):
    return csc_matrix((e['a_value'],e['a_index'],e['a_start']),shape=(e['num_row'],e['num_col']))


def model_hashes(e):
    return {**{k:e[k] for k in SCALAR_FIELDS},**{k:digest(e[k]) for k in ARRAY_FIELDS},
            **{k:hashlib.sha256('\n'.join(e[k]).encode()).hexdigest() for k in ('col_names','row_names')}}


def compare_models(expected, actual, infinity=math.inf, compare_names=True):
    failures=[]
    for k in SCALAR_FIELDS:
        if expected[k]!=actual[k]: failures.append(k)
    for k in ARRAY_FIELDS:
        a=np.asarray(expected[k]);b=np.asarray(actual[k])
        if k in ('col_lower','col_upper','row_lower','row_upper'):
            a=np.where(a==np.inf,infinity,np.where(a==-np.inf,-infinity,a))
        if a.shape!=b.shape or not np.array_equal(a,b): failures.append(k)
    if compare_names:
        for k in ('col_names','row_names'):
            if expected[k]!=actual[k]:failures.append(k)
    return {'passed':not failures,'failures':failures,'comparison':'exact elementwise, API infinity normalized only',
            'expected_hashes':model_hashes(expected),'actual_hashes':model_hashes(actual)}


def append_rows(e, lower, upper, starts, index, value, names=None):
    """Return intended CSC after a supported addRows batch; no native call."""
    lo=np.asarray(lower,dtype=np.float64);up=np.asarray(upper,dtype=np.float64)
    require(lo.ndim==1 and lo.size>0 and up.shape==lo.shape,'Invalid new row bounds')
    nadd=len(lo);vv=np.asarray(value,dtype=np.float64);ii=np.asarray(index);ss=np.asarray(starts)
    require(ii.dtype.kind in 'iu' and ss.dtype.kind in 'iu','Noninteger CSR indices')
    require(ss.shape in ((nadd,),(nadd+1,)),'CSR starts length')
    if len(ss)==nadd:ss=np.append(ss,len(vv))
    require(ss[0]==0 and ss[-1]==len(vv) and np.all(ss[1:]>=ss[:-1]),'Invalid CSR starts')
    require(ii.shape==vv.shape and np.all(ii>=0) and np.all(ii<e['num_col']),'Invalid CSR columns')
    require(np.all(np.isfinite(vv)) and np.all(vv!=0),'Nonfinite or zero row entries')
    require(len(vv)<2**31 and e['num_nz']+len(vv)<2**31,'32-bit nnz overflow')
    # Reject duplicates rather than silently sum them on behalf of the cut author.
    for r in range(nadd):require(len(set(ii[ss[r]:ss[r+1]].tolist()))==ss[r+1]-ss[r],'Duplicate new row entry')
    new=csr_matrix((vv,ii.astype(np.int32),ss.astype(np.int32)),shape=(nadd,e['num_col']))
    aa=vstack([matrix(e),new],format='csc');aa.sort_indices()
    out=dict(e);out.update(num_row=e['num_row']+nadd,num_nz=int(aa.nnz),row_lower=np.concatenate([e['row_lower'],lo]),row_upper=np.concatenate([e['row_upper'],up]),a_start=aa.indptr,a_index=aa.indices,a_value=aa.data,
        row_names=e['row_names']+(names if names is not None else [f'added_{e["num_row"]+r}' for r in range(nadd)]))
    return validate_model(out)
