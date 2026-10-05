#!/usr/bin/env python3
"""Solver-free, source-row network value enclosure and global lower-cut certificate.

This evaluates one retained point. It neither solves nor constructs an LP/MIP.
All exact fields refer to the real values of stored binary64 coefficients.
"""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS',
           'VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_k] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
sys.dont_write_bytecode = True
import argparse
from collections import deque
from fractions import Fraction as Q
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import time
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu
from threadpoolctl import threadpool_info, threadpool_limits

GEN_SHA = 'ef326c80ea99d2f6dd7ee7da1ed8938444b66579a879d0bf04bc06c282f8ada3'

BLOCK = 64
DROP = 1e-9
PRICE = 5000


def require(v, msg):
    if not v: raise ValueError(msg)


def exact(x):
    y = float(x)
    require(math.isfinite(y), 'Nonfinite exact operand')
    return Q.from_float(y)


def up(x):
    """Correct upward conversion of an exact rational, including subnormals."""
    y = float(x)
    require(math.isfinite(y), 'Certificate conversion overflow')
    if exact(y) < x: y = math.nextafter(y, math.inf)
    require(math.isfinite(y), 'Certificate upper bound overflow')
    return y


def down(x):
    return -up(-x)


def rat(x):
    return [str(x.numerator), str(x.denominator)]


def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024**2), b''): h.update(b)
    return h.hexdigest()








def check_finite_source(obj, key=''):
    if isinstance(obj,dict):
        for k,v in obj.items(): check_finite_source(v,k)
    elif isinstance(obj,list):
        for v in obj: check_finite_source(v,key)
    elif type(obj) in (float,int):
        require(math.isfinite(float(obj)) or (key in ('Normal flow limit (MW)','Emergency flow limit (MW)') and not math.isnan(float(obj))), 'Nonfinite source '+key)


def source_names(d, hours, rated):
    """Literal variable ordering from frozen generate.build, without building rows."""
    n=[]
    for g,gd in d['Generators'].items():
        for t in range(hours):
            n.extend(f'{k}_{g}_{t}' for k in ('u','y','z','p','sc'))
            n.extend(f'seg_{g}_{t}_{k}' for k in range(len(gd['Production cost curve (MW)'])-1))
            n.extend(f'reserve_{r}_{g}_{t}' for r in gd.get('Reserve eligibility',[]))
    n.extend(f'shed_{b}_{t}' for b in d['Buses'] for t in range(hours))
    n.extend(f'short_{r}_{t}' for r in d.get('Reserves',{}) for t in range(hours))
    n.extend(f'theta_{b}_{t}' for b in d['Buses'] for t in range(hours))
    rated=set(rated)
    for l,name in enumerate(d['Transmission lines']):
        for t in range(hours):
            n.append(f'f_{name}_{t}')
            if l in rated: n.append(f'over_{name}_{t}')
    return n


def geometry(n, endpoints, weights):
    require(n>=2 and len(endpoints)==len(weights), 'Invalid network shape')
    require(np.all(np.isfinite(weights)) and np.all(np.asarray(weights)>0), 'Positive finite weights required')
    adj=[[] for _ in range(n)]
    for i,(a,b) in enumerate(endpoints):
        a,b=int(a),int(b)
        require(0<=a<n and 0<=b<n and a!=b, 'Invalid line endpoints')
        adj[a].append((b,i)); adj[b].append((a,i))
    distance=[None]*n; distance[0]=0.; parent=[None]*n; queue=deque([0])
    while queue:
        a=queue.popleft()
        for b,i in adj[a]:
            if distance[b] is None:
                # Each reciprocal and path addition has its own outward rounding.
                reciprocal=up(1/exact(weights[i]))
                distance[b]=up(exact(distance[a])+exact(reciprocal))
                parent[b]=(a,i); queue.append(b)
    require(all(x is not None for x in distance), 'Disconnected network')
    return distance,parent


def balanced_probe(raw):
    raw=list(raw); require(len(raw)>0, 'Empty q')
    require(all(isinstance(x,Q) for x in raw), 'q must be exact rational')
    imbalance=sum(raw,Q(0)); q=raw.copy(); q[0]=-sum(q[1:],Q(0))
    require(sum(q,Q(0))==0, 'Unbalanced synthetic qstar')
    return q,imbalance,-imbalance


def certificate_bound(source_F,qstar):
    """Fixed per-cut superset bound; does not alter original p/shed boxes.

    All original feasible injections have Qplus<=source_F. Enlarging to include
    this arbitrary balanced query only weakens the certified affine cut.
    """
    require(isinstance(source_F,Q) and source_F>=0,'Invalid source flow bound')
    require(all(isinstance(v,Q) for v in qstar) and sum(qstar,Q(0))==0,'Unbalanced certificate query')
    return max(source_F,sum((max(v,Q(0)) for v in qstar),Q(0)))


def incidence_transpose(values,endpoints,n):
    out=[Q(0) for _ in range(n)]
    for z,(a,b) in zip(values,endpoints): out[int(a)]+=z; out[int(b)]-=z
    return out


def forward_certificate(q,theta,endpoints,weights):
    require(len(q)==len(theta) and float(theta[0])==0., 'Referenced forward potential required')
    th=[exact(x) for x in theta]
    f=[exact(w)*(th[int(a)]-th[int(b)]) for (a,b),w in zip(endpoints,weights)]
    lhs=incidence_transpose(f,endpoints,len(q))
    residual=[x-y for x,y in zip(q,lhs)]
    require(sum(residual,Q(0))==0, 'Forward residual must balance exactly')
    qr=sum((max(x,Q(0)) for x in residual),Q(0))
    return f,residual,qr


def row_scan(flow, qres, rated, outages, lodf, normal, emergency):
    """Complete signed row max intervals; source order breaks nominal ties.

    For every row |error| <= (1+|stored LODF|)*Qres, plus an
    outward bound for EACH product/add/subtract. No reduction sum is used.
    Selected rows use nominal binary64 argmax and are not presumed supporting.
    """
    m=len(flow); require(lodf.shape==(m,m), 'LODF shape mismatch')
    require(np.all(np.isfinite(lodf)), 'Nonfinite stored LODF')
    require(qres>=0, 'Negative forward residual allowance')
    fh=np.array([float(x) for x in flow]); gl=np.array([down(x) for x in flow]); gu=np.array([up(x) for x in flow])
    lower=np.zeros(m); upper=np.zeros(m); best=np.zeros(m)
    kind=np.zeros(m,dtype=np.int8); which=np.full(m,-1,dtype=np.int32); sign=np.zeros(m,dtype=np.int8)
    qru=up(qres); pos=np.inf; neg=-np.inf
    # nextafter at each elementary operation contains the exact result of that operation.
    for l in rated:
        h=float(normal[l])
        if not math.isfinite(h): continue
        avlo=max(0., gl[l], -gu[l]); avhi=max(abs(gl[l]),abs(gu[l]))
        lower[l]=max(0.,math.nextafter(math.nextafter(avlo-qru,neg)-h,neg))
        upper[l]=max(0.,math.nextafter(math.nextafter(avhi+qru,pos)-h,pos))
        candidate=abs(fh[l])-h
        if candidate>best[l]: best[l]=candidate; kind[l]=1; sign[l]=1 if fh[l]>=0 else -1
    outages=np.asarray(outages,dtype=np.int32)
    for start in range(0,len(rated),BLOCK):
        ls=np.asarray(rated[start:start+BLOCK],dtype=np.int32)
        ls=ls[np.isfinite(np.asarray(emergency)[ls])]
        if not len(ls) or not len(outages): continue
        d=lodf[np.ix_(ls,outages)]; h=np.asarray(emergency)[ls,None]
        prodlo=np.nextafter(d*np.where(d>=0,gl[outages],gu[outages]),neg)
        prodhi=np.nextafter(d*np.where(d>=0,gu[outages],gl[outages]),pos)
        slo=np.nextafter(gl[ls,None]+prodlo,neg); shi=np.nextafter(gu[ls,None]+prodhi,pos)
        err=np.nextafter(np.nextafter(1.+np.abs(d),pos)*qru,pos)
        alo=np.maximum(0.,np.maximum(slo,-shi)); ahi=np.maximum(np.abs(slo),np.abs(shi))
        vlo=np.nextafter(np.nextafter(alo-err,neg)-h,neg)
        vhi=np.nextafter(np.nextafter(ahi+err,pos)-h,pos)
        nominal=fh[ls,None]+d*fh[outages]
        vals=np.abs(nominal)-h
        allowed=ls[:,None]!=outages[None,:]
        require(np.all(np.isfinite(vlo)) and np.all(np.isfinite(vhi)) and np.all(np.isfinite(vals)), 'Nonfinite row arithmetic')
        vlo=np.where(allowed,vlo,neg); vhi=np.where(allowed,vhi,neg); vals=np.where(allowed,vals,neg)
        lower[ls]=np.maximum(lower[ls],np.max(vlo,axis=1)); upper[ls]=np.maximum(upper[ls],np.max(vhi,axis=1))
        arg=np.argmax(vals,axis=1)
        for i,l in enumerate(ls):
            j=int(arg[i]); candidate=float(vals[i,j])
            if candidate>best[l]:
                best[l]=candidate; kind[l]=2; which[l]=int(outages[j]); sign[l]=1 if nominal[i,j]>=0 else -1
    require(np.all(np.isfinite(lower)) and np.all(np.isfinite(upper)), 'Nonfinite row enclosure')
    require(np.all(0<=lower) and np.all(lower<=upper), 'Invalid value enclosure')
    return dict(lower=lower,upper=upper,kind=kind,outage=which,sign=sign,nominal=best)


def selected_terms(scan,lodf,normal,emergency,rated,outages):
    m=len(scan['kind']); c=[Q(0) for _ in range(m)]; lh=Q(0); selected=[]
    rated=set(rated); outages=set(outages)
    for l,kind in enumerate(scan['kind']):
        if not kind: continue
        require(l in rated, 'Selected monitored line is not source-rated')
        s=int(scan['sign'][l]); require(s in (-1,1), 'Invalid selected sign')
        require(kind in (1,2), 'Invalid selected kind')
        h=float(normal[l] if kind==1 else emergency[l]); require(math.isfinite(h), 'Selected absent row')
        c[l]+=s; lh+=exact(h)
        k=-1
        if kind==2:
            k=int(scan['outage'][l]); require(k!=l and 0<=k<m and k in outages, 'Invalid or unlisted selected outage')
            c[k]+=s*exact(lodf[l,k])
        selected.append(dict(monitored=l,kind='normal' if kind==1 else 'contingency',outage=k,sign=s,multiplier=1))
    validate_multipliers(selected)
    return c,lh,selected


def retained_network_rows(expected,lines,H,rated):
    """Read retained soft-row coefficients only, without a matrix/checker run."""
    names={v:i for i,v in enumerate(expected['col_names'])}
    starts=expected['a_start']; indices=expected['a_index']; vals=expected['a_value']
    rows={}
    for l in rated:
        for t in range(H):
            j=names[f'over_{lines[l]}_{t}']
            for z in range(starts[j],starts[j+1]):
                r=indices[z]
                require(vals[z]==-1. and r not in rows,'Retained shared-overload row mismatch')
                require(expected['row_lower'][r]=='-inf' and math.isfinite(float(expected['row_upper'][r])), 'Retained soft-row sense/RHS mismatch')
                rows[r]=[l,t,float(expected['row_upper'][r]),[]]
    for k,line in enumerate(lines):
        for t in range(H):
            j=names[f'f_{line}_{t}']
            for z in range(starts[j],starts[j+1]):
                if indices[z] in rows:
                    rec=rows[indices[z]]; require(rec[1]==t,'Retained cross-hour soft row')
                    rec[3].append((k,float(vals[z])))
    return list(rows.values())


def verify_retained_rows(rows,lodf,normal,emergency,outages):
    count=0; hashes=hashlib.sha256(); outages=set(outages)
    for l,t,h,terms in rows:
        require(1<=len(terms)<=2,'Retained soft-row flow support mismatch')
        terms=dict(terms); require(l in terms and terms[l] in (-1.,1.),'Retained monitored coefficient mismatch')
        sign=terms.pop(l)
        if terms:
            k,v=next(iter(terms.items()))
            require(k in outages and k!=l and v==sign*lodf[l,k] and h==emergency[t,l], 'Fresh LODF bits mismatch retained security coefficient')
            count+=1; hashes.update(f'{l},{k},{t},{sign.hex()},{v.hex()},{h.hex()}\n'.encode())
        else:
            # A security coefficient exactly zero is omitted by source Model.row;
            # such a singleton can coincide with a normal row or emergency row.
            require(h==normal[t,l] or (h==emergency[t,l] and any(k!=l and lodf[l,k]==0 for k in outages)), 'Retained single-flow soft row mismatch')
    return dict(retained_soft_rows_checked=len(rows),retained_nonzero_security_rows_checked=count,
                retained_security_coefficients_sha256=hashes.hexdigest(),full_historical_LODF_bit_parity_claimed=False)


def validate_multipliers(selected):
    budgets={}
    for row in selected:
        value=Q(row['multiplier']); require(value>=0, 'Negative multiplier')
        l=row['monitored']; budgets[l]=budgets.get(l,Q(0))+value
    require(all(v<=1 for v in budgets.values()), 'Shared overload multiplier budget exceeded')
    return budgets


def cut_certificate(c,lh,pi,endpoints,weights,path_upper,F,load,q):
    require(F>=0 and sum(q,Q(0))==0, 'Invalid cut domain')
    require(sum((max(v,Q(0)) for v in q),Q(0))<=F, 'Synthetic probe exceeds source flow bound')
    pi=np.array(pi,dtype=np.float64,copy=True)
    require(np.all(np.isfinite(pi)) and pi[0]==0., 'Finite referenced potential required')
    before=pi.copy(); pi[np.abs(pi)<=DROP]=0.
    pe=[exact(v) for v in pi]
    edge=[exact(w)*(v-pe[int(a)]+pe[int(b)]) for v,(a,b),w in zip(c,endpoints,weights)]
    residual=incidence_transpose(edge,endpoints,len(pi))
    require(sum(residual,Q(0))==0, 'Dual residual must balance exactly')
    T=[up(F*exact(v)) for v in path_upper]
    delta=sum((abs(r)*exact(t) for r,t in zip(residual,T)),Q(0))
    pd=sum((p*d for p,d in zip(pe,load)),Q(0)); C=pd+lh+delta; emitted=up(C)
    cut=sum((p*(x+d) for p,x,d in zip(pe,q,load)),Q(0))-exact(emitted)
    return dict(pi=pi,constant=emitted,residual=residual,T=T,delta=delta,lambda_h=lh,
                pi_load=pd,constant_exact_before_round=C,constant_rounding_loss=exact(emitted)-C,
                emitted_cut_at_qstar=cut,zeroed_count=int(np.count_nonzero(before!=pi)))

