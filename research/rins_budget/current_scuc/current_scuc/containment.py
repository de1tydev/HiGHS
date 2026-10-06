#!/usr/bin/env python3
"""Fresh-lift containment; v3 exact arithmetic and public native assessment.
Never calls an optimizer, presolve, topology preparation or network scanner.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import time
STARTED = time.monotonic()
import argparse
from fractions import Fraction as F
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import signal
import struct
import subprocess
import sys
sys.dont_write_bytecode = True
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = PACKAGE_ROOT
TOL = F(1e-6)


def require(ok, msg):
    if not ok: raise ValueError(msg)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda:stream.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def bits(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def same(a,b,msg):
    a,b=np.asarray(a),np.asarray(b)
    require(a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes(),msg)


def row_bound_equivalence(expected,actual,field):
    """Exact row-bound equality with explicit IEEE signed-zero equivalence only."""
    require(field in ('row_lower','row_upper'),'signed-zero exception outside row bounds')
    a,b=np.asarray(expected),np.asarray(actual)
    require(a.shape==b.shape and a.dtype==b.dtype==np.dtype('float64'),'row-bound shape/dtype mismatch')
    require(not np.isnan(a).any() and not np.isnan(b).any(),'NaN row bound')
    different=a.view(np.uint64)!=b.view(np.uint64)
    zero_pair=(a==0.)&(b==0.)
    require(np.all(~different|zero_pair),'nonzero row-bound bit mismatch')
    a_zero_normalized=a.copy();b_zero_normalized=b.copy()
    a_zero_normalized[zero_pair]=0.;b_zero_normalized[zero_pair]=0.
    same(a_zero_normalized,b_zero_normalized,'row-bound normalized bits mismatch')
    return dict(field=field,zero_sign_difference_count=int(np.count_nonzero(different)),
        expected_negative_to_native_positive=int(np.count_nonzero(different&np.signbit(a)&~np.signbit(b))),
        expected_positive_to_native_negative=int(np.count_nonzero(different&~np.signbit(a)&np.signbit(b))),
        expected_raw_sha256=bits(a),native_raw_sha256=bits(b),
        expected_zero_normalized_sha256=bits(a_zero_normalized),native_zero_normalized_sha256=bits(b_zero_normalized),
        nonzero_values_bitwise_equal=True,numerical_values_exactly_equal=True,
        normalization='signed zero equivalence for row bounds only; neither model nor point modified')


def strict(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            require(k not in d,'duplicate JSON key: '+k);d[k]=v
        return d
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else Path(path).open()) as f:
        return json.load(f,object_pairs_hook=unique)


def write_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')


def load(name, path):
    return load_module(name, path)


def rat(q):return [str(q.numerator),str(q.denominator)]
def unrat(q):return F(int(q[0]),int(q[1]))


def upward(q):
    y=float(q)
    require(math.isfinite(y),'nonfinite outward enclosure')
    if F(y)<q:y=math.nextafter(y,math.inf)
    require(math.isfinite(y) and F(y)>=q,'outward enclosure failed')
    return y


def bundle(directory,receipt):
    """Same frozen bundle contract, with local strict parser and no worker import."""
    def member(item):
        require(Path(item['path']).name==item['path'],'bundle path escape')
        p=directory/item['path']
        require(p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],'bundle hash mismatch '+str(p))
        return p
    raw=strict(member(receipt['document']));arrays={}
    if 'arrays' in receipt:
        ar=receipt['arrays']
        with np.load(member(ar),allow_pickle=False) as z:
            require(set(z.files)==set(ar['array_sha256']),'bundle array inventory')
            for key in z.files:
                a=np.array(z[key],copy=True)
                require(bits(a)==ar['array_sha256'][key],'bundle array hash '+key);arrays[key]=a
    def restore(v):
        if isinstance(v,dict):
            if 'npz_array' in v:
                a=arrays[v['npz_array']]
                require(a.dtype.str==v['dtype'] and list(a.shape)==v['shape'],'bundle array schema');return a
            return {k:restore(x) for k,x in v.items()}
        return [restore(x) for x in v] if isinstance(v,list) else v
    return restore(raw)


def verify_files(records):
    for rel,digest in records.items():
        p=ROOT/rel
        require(p.resolve().is_relative_to(ROOT) and p.is_file() and sha(p)==digest,'frozen hash mismatch '+rel)


def exact_check(model,x,model_module):
    """All products/sums exact for actual binary64 inputs, not rounded products."""
    require(x.dtype==np.dtype('float64') and x.shape==(model['num_col'],) and np.isfinite(x).all(),'point shape/nonfinite')
    xf=[F(float(v)) for v in x]
    a=model_module.matrix(model).tocsr(); acts=np.empty(model['num_row'])
    cache={}; rowmax=F(0); boundmax=F(0); intmax=F(0); rowindex=None;boundindex=None;intindex=None
    badrows=[];badbounds=[];badints=[]
    for r in range(model['num_row']):
        total=F(0)
        for k in range(a.indptr[r],a.indptr[r+1]):
            v=float(a.data[k]);c=cache.get(v)
            if c is None:c=cache[v]=F(v)
            total+=c*xf[a.indices[k]]
        acts[r]=float(total)
        lo,hi=map(float,(model['row_lower'][r],model['row_upper'][r]))
        residual=max(F(0), F(lo)-total if math.isfinite(lo) else F(0), total-F(hi) if math.isfinite(hi) else F(0))
        if residual>rowmax:rowmax,rowindex=residual,r
        if residual>TOL:badrows.append({'index':r,'name':model['row_names'][r],'exact_residual':rat(residual)})
    for j,v in enumerate(xf):
        lo,hi=map(float,(model['col_lower'][j],model['col_upper'][j]))
        residual=max(F(0),F(lo)-v if math.isfinite(lo) else F(0),v-F(hi) if math.isfinite(hi) else F(0))
        if residual>boundmax:boundmax,boundindex=residual,j
        if residual>TOL:badbounds.append(j)
        if model['integrality'][j]:
            residual=abs(v-round(v)) # Inspection only; x is never changed.
            if residual>intmax:intmax,intindex=residual,j
            if residual>TOL:badints.append(j)
    objective=F(float(model['offset']))+sum((F(float(c))*v for c,v in zip(model['col_cost'],xf)),F(0))
    return {'passed':not(badrows or badbounds or badints),'rows_checked':model['num_row'],'columns_checked':model['num_col'],
        'binaries_checked':int(np.count_nonzero(model['integrality'])),'sparse_products':model['num_nz'],
        'arithmetic':'exact rational product and sum of binary64 inputs for every row, bound, binary and objective',
        'tolerance_exact':rat(TOL),'max_row':{'value':float(rowmax),'exact':rat(rowmax),'index':rowindex},
        'max_bound':{'value':float(boundmax),'exact':rat(boundmax),'index':boundindex},
        'max_integrality':{'value':float(intmax),'exact':rat(intmax),'index':intindex},
        'row_failures':badrows,'bound_failures':badbounds,'integrality_failures':badints,
        'projected_objective_exact':rat(objective),'projected_objective':float(objective)},acts


def serialize(path,names,x,objective):
    require(len(names)==len(x) and len(set(names))==len(names),'duplicate/missing column')
    require(all(isinstance(n,str) and n and not any(c.isspace() for c in n) for n in names),'unsafe column name')
    require(np.isfinite(x).all(),'nonfinite column')
    with path.open('x') as f:
        f.write('Model status\nNot Set\n\n# Primal solution values\nFeasible\nObjective '+format(objective,'.17g')+'\n# Columns '+str(len(x))+'\n')
        for n,v in zip(names,x):f.write(n+' '+format(float(v),'.17g')+'\n')
    lines=path.read_text().splitlines()
    require(lines[:7]==['Model status','Not Set','','# Primal solution values','Feasible','Objective '+format(objective,'.17g'),'# Columns '+str(len(x))],'solution header')
    require(len(lines)==7+len(x),'extra/missing serialized columns')
    readnames=[];readvalues=[]
    for line in lines[7:]:
        fields=line.split();require(len(fields)==2,'malformed solution column')
        readnames.append(fields[0]);readvalues.append(float(fields[1]))
    require(readnames==names,'serialized names/order mismatch')
    same(np.array(readvalues,dtype=np.float64),x,'serialized point bits mismatch')


def native_json_metadata(native):
    """Encode only the known HiGHS +infinity metadata; numerical dict unchanged."""
    value=native['infinity']
    require(type(value) is float and struct.pack('>d',value).hex()=='7ff0000000000000',
        'unexpected native infinity metadata type/value')
    encoded=dict(native)
    encoded['infinity']={'type':'IEEE 754 binary64','symbol':'+Infinity',
        'bits_hex':'0x7ff0000000000000'}
    # Strict encoding still rejects NaN and every other nonfinite field.
    json.dumps(encoded,allow_nan=False)
    return encoded


def read_native(path):
    with path.open('rb') as f:
        require(f.read(8)==b'HSCONT01','native dump magic')
        dso_size=struct.unpack('<I',f.read(4))[0];require(dso_size<4096,'DSO path too long');dso=f.read(dso_size).decode()
        n,m,nz,sense,status,valid,integral,feasible,value_valid=struct.unpack('<9i',f.read(36))
        offset,mip_tol,primal_tol,infinity=struct.unpack('<4d',f.read(32))
        require(0<n<1000000 and 0<=m<1000000 and 0<=nz<10000000,'native dimensions unsafe')
        def a(count,dtype):
            size=np.dtype(dtype).itemsize;data=f.read(count*size);require(len(data)==count*size,'truncated native dump');return np.frombuffer(data,dtype=dtype).copy()
        d=dict(num_col=n,num_row=m,num_nz=nz,sense=sense,offset=offset)
        for field,size,dtype in [('col_lower',n,'<f8'),('col_upper',n,'<f8'),('col_cost',n,'<f8'),('row_lower',m,'<f8'),('row_upper',m,'<f8'),('integrality',n,'<i4'),('a_start',n+1,'<i4'),('a_index',nz,'<i4'),('a_value',nz,'<f8')]:d[field]=a(size,dtype)
        for field,count in [('col_names',n),('row_names',m)]:
            d[field]=[]
            for _ in range(count):
                length=struct.unpack('<I',f.read(4))[0];require(length<4096,'native name too long');d[field].append(f.read(length).decode())
        x,rows=a(n,'<f8'),a(m,'<f8');require(not f.read(1),'native trailing data')
    return d,x,rows,dict(status=status,valid=bool(valid),integral=bool(integral),feasible=bool(feasible),value_valid=bool(value_valid),mip_tolerance=mip_tol,primal_row_consistency_tolerance=primal_tol,infinity=infinity,loaded_library_path=dso)


def validate_eta_units(certificate):
    require(certificate['value_unit']=='summed shared overload MW' and certificate['eta_objective_coefficient']==5000,'eta unit/cost')


def mapping_point(original,current,metadata,oracle,lift,evaluation,bridge,*,production=True):
    """Map a checked full canonical lift into the current adaptive integer map.

    The complete current-run support replay is owned by carry.prepare. Its
    current metadata binds the append-only map, caps, matrix and full prefix;
    no saved point's old map determines this destination.
    """
    import current_scuc.adaptive as adaptive
    state=adaptive.activation(metadata)
    adaptive.validate_current(current,metadata,original,canonical=True)
    retained=np.asarray(metadata['retained_original_columns'])
    require(retained.ndim==1 and retained.dtype.kind in 'iu' and
        np.all(retained>=0) and np.all(retained<original['num_col']) and
        len(set(retained.tolist()))==len(retained),'retained map shape/range')
    retained=retained.astype(np.int32)
    hours=metadata['hours'];lines=metadata['full_scope']['ordered_line_ids'];nlines=len(lines)
    nret=len(retained);active=tuple(state.active)
    require(type(hours) is int and 0<hours<=36 and state.hours==hours and state.nret==nret and
        current['num_col']==nret+2+len(active)*hours==state.num_col,'mapped dimensions')
    require(tuple(state.fixed)==(nret,nret+1) and state.columns==
        {(l,t):nret+2+b*hours+t for b,l in enumerate(active) for t in range(hours)},
        'current adaptive column map')
    require(metadata['full_scope']['production_scope'] is production,'scope mode mismatch')
    if production:
        import current_scuc.heldout as heldout
        heldout.check_carry_shape(nret,current['num_col'],hours,nlines,int(np.count_nonzero(original['integrality'])))
    lift=np.asarray(lift)
    require(lift.dtype==np.dtype('float64') and lift.shape==(original['num_col'],) and
        np.isfinite(lift).all(),'original lift shape/nonfinite')
    require(bits(lift)==evaluation['stored_lift_artifact']['readback_values_sha256'],'lift point authority hash')
    same(oracle['original_network_lift']['values'],lift,'oracle vs persisted lift bits')
    require(bits(lift[retained])==evaluation['retained_values_sha256'],'retained point authority')
    require(evaluation['original_integer_quality']['passed'] and not evaluation['original_integer_quality']['point_rounded'],'saved binary check authority')
    require(evaluation['source_quality']['passed'],'saved original-matrix check authority')
    scope=metadata['full_scope'];sid=scope['full_scope_identity_sha256']
    quality=evaluation['full_source_quality']
    require(quality['passed'] and quality['zero_radius'] and quality['full_scope_coverage_complete'] and quality['full_scope_identity_sha256']==sid and quality['stored_lift_binary64_sha256']==bits(lift),'saved full-network point authority')
    certificate=oracle['certificate']
    require(certificate['certificate_valid'] and certificate['full_scope_coverage_complete'] and certificate['full_scope_identity_sha256']==sid and certificate['full_scope']==scope,'oracle full scope')
    validate_eta_units(certificate)
    require((certificate['signed_normal_rows'],certificate['signed_security_rows'])==(scope['signed_normal_rows'],scope['signed_security_rows']),'full coverage counts')
    if production:heldout.check_coverage(scope)
    overload=np.asarray(oracle['original_network_lift']['overload_upper']);line_upper=oracle['arrays']['line_value_upper']
    same(overload,line_upper,'saved canonical overload disagreement')
    require(overload.dtype==np.dtype('float64') and overload.shape==(hours,nlines) and np.isfinite(overload).all() and (overload>=0).all(),'saved overload shape/range')
    rated=scope['ordered_monitored_indices'];lines=scope['ordered_line_ids']
    require(len(rated)>0 and len(set(rated))==len(rated) and
        all(type(i) is int and 0<=i<nlines for i in rated) and tuple(rated)==tuple(state.rated),'rated inventory')
    require(len(set(active))==len(active) and len(active)<=8 and
        all(type(l) is int and l in rated for l in active),'active line inventory')
    if production:heldout.check_rated(rated)
    overmap=np.asarray(metadata['source_maps']['overload'])
    require(overmap.shape==overload.shape and overmap.dtype.kind in 'iu','overload map shape/type')
    require(len(certificate['hour_certificates'])==hours,'saved hourly certificate inventory')
    all_over=set();inactive=F(0);active_set=set(active)
    unrated=sorted(set(range(nlines))-set(rated))
    require(np.all(overmap[:,unrated]==-1),'unmonitored overflow map')
    for t in range(hours):
        for l in rated:
            j=int(overmap[t,l]);require(0<=j<original['num_col'],'overload index')
            require(original['col_names'][j]==f'over_{lines[l]}_{t}' and original['col_cost'][j]==5000. and original['integrality'][j]==0,'original overflow name/cost/type')
            require(j not in all_over,'duplicate original overflow coordinate')
            same(np.asarray([lift[j]]),np.asarray([overload[t,l]]),'saved original overflow bits');all_over.add(j)
            if l not in active_set:inactive+=F(float(overload[t,l]))
        require(np.all(overload[t,unrated]==0),'unmonitored canonical overload nonzero')
        total=sum((F(float(v)) for v in overload[t]),F(0))
        hour=certificate['hour_certificates'][t]
        require(hour['hour']==t and unrat(hour['value_upper_MW'])==total,'saved exact hourly overflow sum')
    require(all_over=={j for j,n in enumerate(original['col_names']) if n.startswith('over_')},'original overflow inventory incomplete')
    require(not all_over.intersection(retained.tolist()),'retained canonical overflow coordinate')
    require(current['col_names'][:nret]==[original['col_names'][j] for j in retained],
        'retained column names')
    require(current['col_names'][nret:nret+2]==['aggregate_one_plus','aggregate_one_minus'],
        'fixed balance auxiliary names')
    require(current['col_names'][nret+2:]==[f'eta_line_{l}_MW_{t}' for l in active for t in range(hours)],
        'current eta names/order')
    caps=metadata['line_caps']
    require(len(caps)==len(state.columns) and all(isinstance(row,(tuple,list)) and len(row)==3 and
        type(row[0]) is int and type(row[1]) is int for row in caps),'current line cap inventory')
    require([(l,t) for l,t,_ in caps]==list(state.columns),'current line cap map/order')
    cap_values=np.asarray([cap for _,_,cap in caps],dtype=np.float64)
    require(np.isfinite(cap_values).all() and np.all(cap_values>=0),'current line cap range')
    require(np.all(current['col_cost'][nret+2:]==5000.),'current eta objective cost')
    same(current['col_upper'][nret+2:],cap_values,'current line eta caps')
    require(np.all(current['col_lower'][nret+2:]==0),'eta lower bounds')
    same(current['integrality'][:nret],original['integrality'][retained],'retained binary flags')
    require(np.all(current['integrality'][nret:]==0),'auxiliary type')
    import current_scuc.no_shedding as no_shedding
    subset = no_shedding.validate_retained(current, metadata, original, bridge.helpers().model)
    target_point = no_shedding.point_check(original, lift, subset, bridge.helpers().model, production=production)
    require(target_point == evaluation['target_subset_quality'], 'Saved target point check changed')
    require(no_shedding.slack_quality(original,lift) == evaluation['negligible_slack_quality'], 'Saved positive slack quality changed')
    require(np.all(current['col_lower'][nret:nret+2]==1) and np.all(current['col_upper'][nret:nret+2]==1) and np.all(current['col_cost'][nret:nret+2]==0),'fixed balance auxiliaries')
    eta=[];rounding=[]
    for l,t in state.columns:
        canonical=F(float(overload[t,l]));value=upward(canonical)
        eta.append(value);rounding.append(F(value)-canonical)
    x=np.concatenate([lift[retained],np.ones(2),np.asarray(eta,dtype=np.float64)])
    same(x[:nret],lift[retained],'retained point changed')
    require(np.all(x[nret+2:]<=current['col_upper'][nret+2:]),'outward eta exceeds current line cap')
    for j in np.flatnonzero(original['integrality']):
        require(abs(F(float(lift[j]))-round(F(float(lift[j]))))<=TOL,'original binary value outside native tolerance')
    original_objective=F(float(original['offset']))+sum((F(float(c))*F(float(v)) for c,v in zip(original['col_cost'],lift) if c),F(0))
    projected_objective=F(float(current['offset']))+sum((F(float(c))*F(float(v)) for c,v in zip(current['col_cost'],x) if c),F(0))
    inactive_dollars=5000*inactive;rounding_dollars=5000*sum(rounding,F(0))
    require(projected_objective==original_objective-inactive_dollars+rounding_dollars,
        'original/adaptive exact objective bridge')
    return x,dict(target_subset_quality=target_point, production_quality_eligible=evaluation['negligible_slack_quality']['passed'], retained_count=nret,retained_values_sha256=bits(x[:nret]),original_values_sha256=bits(lift),
        binary_count=int(np.count_nonzero(original['integrality'])),binary_values_rounded=False,balance_auxiliaries=[1.,1.],
        active_lines=list(active),eta_columns=[[l,t,j] for (l,t),j in state.columns.items()],
        eta_values=eta,eta_exact_rounding_excess_MW=[rat(v) for v in rounding],eta_total_rounding_excess_dollars=rat(rounding_dollars),
        inactive_canonical_penalty_dollars=rat(inactive_dollars),projected_objective_exact=rat(projected_objective),
        current_map_hash=metadata['map_hash'],current_matrix_identity=metadata['matrix_identity'],
        original_saved_numerical_upper=evaluation['provisional_upper'],original_point_exact_objective=rat(original_objective),original_direct_dc_admitted=False,full_scope_identity_sha256=sid)
