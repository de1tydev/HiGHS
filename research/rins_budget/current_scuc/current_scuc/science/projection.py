"""Exact stored-model network-family removal, source signature checks, eta bounds.

No factorization, LODF recomputation, generator, optimizer or original mutation.
The caller supplies the scope-pinned literal LODF bits and exact expected arrays.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from collections import deque
from fractions import Fraction as Q
import hashlib
import math
import struct
import numpy as np
from scipy.sparse import csc_matrix, coo_matrix, hstack, vstack
from current_scuc.science.model import require, validate_model, matrix, model_hashes, digest, load_expected

JUNE_PAIRS=((1201,830),(1378,274))


def exact(x):
    x=float(x);require(math.isfinite(x),'Nonfinite exact operand');return Q.from_float(x)


def up(q):
    x=float(q);require(math.isfinite(x),'Bound conversion overflow')
    if exact(x)<q:x=math.nextafter(x,math.inf)
    require(math.isfinite(x),'Bound overflow');return x


def rat(q):return [str(q.numerator),str(q.denominator)]
def at(x,t):return float(x[t] if isinstance(x,list) else x)


def transform_expected(expected, source, hours, exact_pairs, stored_lodf):
    """Return projected CSC dictionary and complete reversible index metadata.

    This function constructs a model. Call on the real case only after release.
    Tiny source dictionaries use the same schema and validation path.
    """
    e=validate_model(expected);require(e['sense']==1,'Projection is minimization only')
    require(type(hours) is int and 1<=hours<=int(source['Parameters']['Time horizon (h)']),'Invalid hours')
    bs=list(source['Buses']);ls=list(source['Transmission lines']);gs=list(source['Generators'])
    B,L,G=len(bs),len(ls),len(gs);require(B>=2 and L>=1 and G>=1,'Empty source network')
    bi={b:i for i,b in enumerate(bs)};namecol={v:i for i,v in enumerate(e['col_names'])}
    pairs=tuple(tuple(p) for p in exact_pairs)
    require(len(set(pairs))==len(pairs),'Duplicate security pair')
    outage_names={c['Affected lines'][0] for c in source.get('Contingencies',{}).values() if len(c.get('Affected lines',[]))==1}
    outage_ids={ls.index(k) for k in outage_names}
    rated=[i for i,l in enumerate(ls) if any(math.isfinite(at(source['Transmission lines'][l].get(k,math.inf),t)) for k in ('Normal flow limit (MW)','Emergency flow limit (MW)') for t in range(hours))]
    require(all(type(l) is int and type(k) is int and 0<=l<L and 0<=k<L and l in rated and k in outage_ids and l!=k for l,k in pairs),'Pair outside exact source scope')
    ds={}
    for l,k in pairs:
        d=float(stored_lodf[l,k]);require(math.isfinite(d),'Nonfinite literal LODF');ds[l,k]=d
    normal=np.array([[at(source['Transmission lines'][l].get('Normal flow limit (MW)',math.inf),t) for l in ls] for t in range(hours)])
    emergency=np.array([[at(source['Transmission lines'][l].get('Emergency flow limit (MW)',math.inf),t) for l in ls] for t in range(hours)])
    require(not np.any(np.isnan(normal)) and not np.any(np.isnan(emergency)) and np.all(normal>=0) and np.all(emergency>=0),'Invalid source ratings')
    endpoints=[];w=[];adj=[[] for _ in bs];incident=[[] for _ in bs]
    for l,name in enumerate(ls):
        ld=source['Transmission lines'][name];a,b=bi[ld['Source bus']],bi[ld['Target bus']]
        require(a!=b,'Self-loop not supported');ww=float(ld['Susceptance (S)']);require(math.isfinite(ww) and ww>0,'Positive finite susceptance required')
        endpoints.append((a,b));w.append(ww);adj[a].append(b);adj[b].append(a);incident[a].append((l,-1.));incident[b].append((l,1.))
    visited={0};queue=deque([0])
    while queue:
        for b in adj[queue.popleft()]:
            if b not in visited:visited.add(b);queue.append(b)
    require(len(visited)==B,'Disconnected source network')
    def cols(kind,names):
        result=np.array([[namecol[f'{kind}_{name}_{t}'] for name in names] for t in range(hours)],dtype=np.int32)
        return result
    p,shed,theta,f=(cols(k,n) for k,n in (('p',gs),('shed',bs),('theta',bs),('f',ls)))
    over=np.full((hours,L),-1,dtype=np.int32)
    for l in rated:
        for t in range(hours):over[t,l]=namecol[f'over_{ls[l]}_{t}']
    removed=np.sort(np.concatenate([theta.ravel(),f.ravel(),over[over>=0]]))
    require(len(np.unique(removed))==len(removed),'Overlapping removed variable maps')
    name_removed=[j for j,name in enumerate(e['col_names']) if name.startswith(('theta_','f_','over_'))]
    require(np.array_equal(removed,np.asarray(name_removed)),'Unexpected/missing network-family columns')
    require(np.all(e['integrality'][removed]==0),'Network columns must be continuous')
    for t in range(hours):
        require(e['col_lower'][theta[t,0]]==e['col_upper'][theta[t,0]]==0,'Reference angle not fixed zero')
        require(np.all(e['col_lower'][theta[t,1:]]==-np.inf) and np.all(e['col_upper'][theta[t,1:]]==np.inf),'Unexpected angle bound')
        require(np.all(e['col_lower'][f[t]]==-np.inf) and np.all(e['col_upper'][f[t]]==np.inf),'Unexpected flow bound')
        require(np.all(e['col_cost'][theta[t]]==0) and np.all(e['col_cost'][f[t]]==0),'Unexpected network objective')
        oo=over[t,over[t]>=0]
        require(np.all(e['col_lower'][oo]==0) and np.all(e['col_upper'][oo]==np.inf) and np.all(e['col_cost'][oo]==5000),'Shared overload domain/price mismatch')
        for l in rated:require(at(source['Transmission lines'][ls[l]].get('Flow limit penalty ($/MW)',5000),t)==5000,'Eta MW requires uniform 5000 price')
        for gi,g in enumerate(gs):
            pmax=float(source['Generators'][g]['Production cost curve (MW)'][-1])
            require(math.isfinite(pmax) and pmax>=0 and e['col_lower'][p[t,gi]]==0 and e['col_upper'][p[t,gi]]==pmax,'Production/source box mismatch')
        for b in range(B):
            load=at(source['Buses'][bs[b]]['Load (MW)'],t)
            require(math.isfinite(load) and load>=0 and e['col_lower'][shed[t,b]]==0 and e['col_upper'][shed[t,b]]==load,'Shedding/source box mismatch')
    normal_count=2*int(np.count_nonzero(np.isfinite(normal)))
    security_count=2*sum(math.isfinite(emergency[t,l]) for l,k in pairs for t in range(hours))
    network_count=hours*(L+B)+normal_count+security_count
    first_network=e['num_row']-network_count;require(first_network>=0,'Too few rows for exact network scope')
    aa=matrix(e).tocsr();ri=first_network;signature=hashlib.sha256();counts={'flow':0,'normal':0,'nodal_balance':0,'security':0}
    # Exact signatures prove all and only removed rows are the intended source rows.
    def row(terms,lo,hi,kind):
        nonlocal ri
        acc={}
        for j,v in terms:acc[int(j)]=acc.get(int(j),0.)+float(v)
        want=sorted((j,v) for j,v in acc.items() if v!=0)
        start,end=aa.indptr[ri:ri+2];actual=list(zip(aa.indices[start:end].tolist(),aa.data[start:end].tolist()))
        require(actual==want and e['row_lower'][ri]==lo and e['row_upper'][ri]==hi,'Original network row signature mismatch at '+str(ri)+' '+kind)
        signature.update(struct.pack('<idd',ri,lo,hi))
        for j,v in want:signature.update(struct.pack('<id',j,v))
        counts[kind]+=1;ri+=1
    for l,name in enumerate(ls):
        a,b=endpoints[l]
        for t in range(hours):
            row([(f[t,l],1),(theta[t,a],-w[l]),(theta[t,b],w[l])],0.,0.,'flow')
            if math.isfinite(normal[t,l]):
                for sign in (1.,-1.):row([(f[t,l],sign),(over[t,l],-1.)],-math.inf,normal[t,l],'normal')
    bus_g=[[gi for gi,g in enumerate(gs) if source['Generators'][g]['Bus']==b] for b in bs]
    balance_rhs=[]
    for b,name in enumerate(bs):
        for t in range(hours):
            terms=[(p[t,gi],1.) for gi in bus_g[b]]+[(shed[t,b],1.)]+[(f[t,l],s) for l,s in incident[b]]
            load=at(source['Buses'][name]['Load (MW)'],t)
            row(terms,load,load,'nodal_balance')
    for l,k in pairs:
        for t in range(hours):
            if math.isfinite(emergency[t,l]):
                for sign in (1.,-1.):row([(f[t,l],sign),(f[t,k],sign*ds[l,k]),(over[t,l],-1.)],-math.inf,emergency[t,l],'security')
    require(ri==e['num_row'],'Network signature did not cover suffix')
    require(aa[:first_network,removed].nnz==0,'Collateral removed-column dependency outside network rows')
    keepmask=np.ones(e['num_col'],dtype=bool);keepmask[removed]=False;retained=np.flatnonzero(keepmask).astype(np.int32)
    oldnew=np.full(e['num_col'],-1,dtype=np.int32);oldnew[retained]=np.arange(len(retained),dtype=np.int32)
    nret=len(retained);eta=np.arange(nret,nret+hours,dtype=np.int32);fixed=np.array([nret+hours,nret+hours+1],dtype=np.int32)
    require(fixed[0]!=fixed[1],'Balance auxiliaries must be distinct')
    # Exact-rational source bounds and the two-binary64 aggregate RHS encoding.
    pmaxsum=sum((exact(source['Generators'][g]['Production cost curve (MW)'][-1]) for g in gs),Q(0))
    eta_bounds=[];bound_records=[];balance_records=[];rr=[];cc=[];vv=[];balance_nz=0
    byline={l:[k for ll,k in pairs if ll==l] for l in rated}
    for t in range(hours):
        S=sum((exact(at(source['Buses'][b]['Load (MW)'],t)) for b in bs),Q(0));F=min(pmaxsum,S)
        U=Q(0);term_hash=hashlib.sha256()
        for l in rated:
            terms=[Q(0)]
            if math.isfinite(normal[t,l]):terms.append(F-exact(normal[t,l]))
            if math.isfinite(emergency[t,l]):terms.extend((1+abs(exact(ds[l,k])))*F-exact(emergency[t,l]) for k in byline[l])
            E=max(terms);U+=E;term_hash.update(f'{l}:{E.numerator}/{E.denominator}\n'.encode())
        bound=up(U);eta_bounds.append(bound)
        bound_records.append({'hour':t,'source_F_exact':rat(F),'Ueta_exact':rat(U),'eta_upper_binary64':bound,'line_Emax_sha256':term_hash.hexdigest()})
        H=float(S);low=S-exact(H);K=Q(1,1024);kl=float(K+low)
        require(exact(kl)==K+low and exact(H)+exact(kl)-K==S,'Exact two-term balance encoding unavailable')
        retained_balance=np.concatenate([p[t],shed[t]])
        omit=[int(j) for j in retained_balance if e['col_lower'][j]==e['col_upper'][j]==0.]
        active=[int(j) for j in retained_balance if not e['col_lower'][j]==e['col_upper'][j]==0.]
        terms=[(int(oldnew[j]),1.) for j in active]+[(int(fixed[0]),-kl),(int(fixed[1]),float(K))]
        for j,v in terms:rr.append(t);cc.append(j);vv.append(v)
        balance_nz+=len(terms);balance_rhs.append(H)
        balance_records.append({'hour':t,'exact_rhs':rat(S),'H':H,'L_exact':rat(low),'K':float(K),'K_plus_L':kl,'omitted_only_fixed_zero_original_columns':omit,'nnz':len(terms)})
    nnew=nret+hours+2
    kept=aa[:first_network,retained].tocsc()
    top=hstack([kept,csc_matrix((first_network,hours+2))],format='csc')
    bottom=coo_matrix((vv,(rr,cc)),shape=(hours,nnew)).tocsc()
    result_matrix=vstack([top,bottom],format='csc');result_matrix.sort_indices()
    out={'num_col':nnew,'num_row':first_network+hours,'num_nz':int(result_matrix.nnz),'sense':e['sense'],'offset':e['offset'],
         'col_names':[e['col_names'][j] for j in retained]+[f'eta_MW_{t}' for t in range(hours)]+['aggregate_one_plus','aggregate_one_minus'],
         'row_names':e['row_names'][:first_network]+[f'aggregate_balance_{t}' for t in range(hours)],
         'col_lower':np.concatenate([e['col_lower'][retained],np.zeros(hours),np.ones(2)]),
         'col_upper':np.concatenate([e['col_upper'][retained],np.asarray(eta_bounds),np.ones(2)]),
         'col_cost':np.concatenate([e['col_cost'][retained],np.full(hours,5000.),np.zeros(2)]),
         'row_lower':np.concatenate([e['row_lower'][:first_network],balance_rhs]),'row_upper':np.concatenate([e['row_upper'][:first_network],balance_rhs]),
         'integrality':np.zeros(nnew,dtype=np.int32),'a_start':result_matrix.indptr,'a_index':result_matrix.indices,'a_value':result_matrix.data}
    out=validate_model(out)
    # Independent slice equality ensures temporal coefficients/costs/bounds did not drift.
    preserved=matrix(out)[:first_network,:nret].tocsc()
    require(np.array_equal(preserved.indptr,kept.indptr) and np.array_equal(preserved.indices,kept.indices) and np.array_equal(preserved.data,kept.data),'Retained matrix drift')
    for k in ('col_lower','col_upper','col_cost'):require(np.array_equal(out[k][:nret],e[k][retained]),'Retained column drift '+k)
    for k in ('row_lower','row_upper'):require(np.array_equal(out[k][:first_network],e[k][:first_network]),'Retained row drift '+k)
    metadata={'schema':'network-projection-lp-core-v1','original_num_col':e['num_col'],'original_num_row':e['num_row'],
      'projected_num_col':out['num_col'],'retained_original_columns':retained,'original_to_projected':oldnew,'removed_columns':removed,
      'eta_columns':eta,'balance_columns':fixed,'eta_upper_bounds':np.asarray(eta_bounds),'hours':hours,
      'source_maps':{'production':p,'shedding':shed,'theta':theta,'flow':f,'overload':over},
      'exact_pairs':pairs,'literal_lodf':[{'monitored':l,'outage':k,'value':ds[l,k],'hex':ds[l,k].hex()} for l,k in pairs],
      'original_hashes':model_hashes(e),'projected_hashes':model_hashes(out),'network_row_signature_sha256':signature.hexdigest(),
      'retained_original_columns_sha256':digest(retained),'original_to_projected_sha256':digest(oldnew),
      'removed_row_range':[first_network,e['num_row']],'network_row_counts':counts,
      'removed_columns_by_family':{'theta':int(theta.size),'flow':int(f.size),'overload':int(np.count_nonzero(over>=0))},
      'original_integer_columns_cleared':int(np.count_nonzero(e['integrality'])),'all_continuous':True,
      'balance_rows_added':hours,'balance_nonzeros':balance_nz,'balance_records':balance_records,
      'eta_bound_records':bound_records,'network_objective_ceiling_upper':up(5000*sum((exact(v) for v in eta_bounds),Q(0))),
      'retained_matrix_nonzeros':int(kept.nnz),'removed_matrix_nonzeros':e['num_nz']-int(kept.nnz),
      'delta':{'columns':out['num_col']-e['num_col'],'rows':out['num_row']-e['num_row'],'nonzeros':out['num_nz']-e['num_nz']},
      'eta_bound_qualification':'Optimization-redundant for valid underestimating cuts on source-feasible retained points; not a retained historical bound',
      'eta_bound_formula':'F=min(sum Pmax,sum stored nodal loads); U=sum_l max(0,F-N_l,max_exact_pairs (1+abs(d_lk))*F-E_l); eta<=up(U)',
      'projection_scope':'all finite normal rows plus exact listed pairs; declared literal LODF model',
      'physical_dc_lower_bound_certified':False}
    return out,metadata


def restore_retained(projected_x, metadata):
    """Original order; removed slots deliberately NaN until network recovery."""
    x=np.asarray(projected_x,dtype=np.float64);require(x.shape==(metadata['projected_num_col'],) and np.all(np.isfinite(x)),'Invalid projected point')
    restored=np.full(metadata['original_num_col'],np.nan)
    ids=np.asarray(metadata['retained_original_columns'],dtype=np.int32)
    restored[ids]=x[:len(ids)]
    require(np.array_equal(restored[ids].view(np.uint64),x[:len(ids)].view(np.uint64)),'Retained mapping changed bits')
    return restored
