"""Literal small fixture used by the full-projection arithmetic tests."""
import math
import numpy as np
from scipy.sparse import coo_matrix
from model import validate_model

def expected(names,lo,up,cost,rows,*,integrality=None,offset=0.,sense=1):
    rr=[];cc=[];vv=[];lower=[];upper=[]
    for r,(terms,l,u) in enumerate(rows):
        for j,v in terms:
            if v:rr.append(r);cc.append(j);vv.append(v)
        lower.append(l);upper.append(u)
    a=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(names))).tocsc()
    return validate_model({'num_col':len(names),'num_row':len(rows),'num_nz':int(a.nnz),'sense':sense,'offset':offset,
      'col_names':names,'row_names':[f'R{r}' for r in range(len(rows))],
      'col_lower':lo,'col_upper':up,'col_cost':cost,'row_lower':lower,'row_upper':upper,
      'integrality':np.zeros(len(names),dtype=np.int32) if integrality is None else integrality,
      'a_start':a.indptr,'a_index':a.indices,'a_value':a.data})


def tiny_source():
    H=2
    d={'Parameters':{'Time horizon (h)':H},
       'Buses':{'b1':{'Load (MW)':[0.,0.]},'b2':{'Load (MW)':[.1,.2]},'b3':{'Load (MW)':[.2,.4]}},
       'Generators':{'g1':{'Bus':'b1','Production cost curve (MW)':[0,12]},'g2':{'Bus':'b3','Production cost curve (MW)':[0,8]}},
       'Transmission lines':{f'l{i+1}':{'Source bus':a,'Target bus':b,'Susceptance (S)':w,'Normal flow limit (MW)':.05,'Emergency flow limit (MW)':.1} for i,(a,b,w) in enumerate([('b1','b2',2.),('b2','b3',3.),('b3','b1',4.)])},
       'Contingencies':{'o1':{'Affected lines':['l1']},'o2':{'Affected lines':['l2']}}}
    names=[];lb=[];ub=[];cost=[];integ=[];rows=[];ix={}
    def var(name,lo,up,c,i=0):
        j=len(names);ix[name]=j;names.append(name);lb.append(lo);ub.append(up);cost.append(c);integ.append(i);return j
    for g,gd in d['Generators'].items():
        for t in range(H):var(f'p_{g}_{t}',0.,gd['Production cost curve (MW)'][-1],1.)
    u=var('u_g1_0',0.,1.,.75,1);seg=var('seg_g1_0_0',0.,3.,2.);sc=var('sc_g1_0',0.,math.inf,1.);reserve=var('reserve_r1_g1_0',0.,3.,0.);short=var('short_r1_0',0.,math.inf,100.)
    for b,bd in d['Buses'].items():
        for t in range(H):var(f'shed_{b}_{t}',0.,bd['Load (MW)'][t],1000.)
    rows.extend([([(ix['p_g1_0'],1.),(u,-12.)],-math.inf,0.), ([(seg,1.),(sc,-1.)],-math.inf,1.), ([(reserve,1.),(short,1.)],1.,math.inf)])
    for b in d['Buses']:
        for t in range(H):var(f'theta_{b}_{t}',0. if b=='b1' else -math.inf,0. if b=='b1' else math.inf,0.)
    for l,ld in d['Transmission lines'].items():
        for t in range(H):
            f=var(f'f_{l}_{t}',-math.inf,math.inf,0.);over=var(f'over_{l}_{t}',0.,math.inf,5000.)
            rows.append(([(f,1.),(ix[f'theta_{ld["Source bus"]}_{t}'],-ld['Susceptance (S)']),(ix[f'theta_{ld["Target bus"]}_{t}'],ld['Susceptance (S)'])],0.,0.))
            for sign in (1.,-1.):rows.append(([(f,sign),(over,-1.)],-math.inf,.05))
    for b,bd in d['Buses'].items():
        for t in range(H):
            terms=[(ix[f'p_{g}_{t}'],1.) for g,gd in d['Generators'].items() if gd['Bus']==b]+[(ix[f'shed_{b}_{t}'],1.)]
            terms.extend((ix[f'f_{l}_{t}'],-1. if ld['Source bus']==b else 1.) for l,ld in d['Transmission lines'].items() if b in (ld['Source bus'],ld['Target bus']))
            rows.append((terms,bd['Load (MW)'][t],bd['Load (MW)'][t]))
    pairs=((0,1),(2,0));lodf={(0,1):.25,(2,0):-.75}
    for l,k in pairs:
        for t in range(H):
            for sign in (1.,-1.):rows.append(([(ix[f'f_l{l+1}_{t}'],sign),(ix[f'f_l{k+1}_{t}'],sign*lodf[l,k]),(ix[f'over_l{l+1}_{t}'],-1.)],-math.inf,.1))
    return d,expected(names,lb,ub,cost,rows,integrality=integ,offset=7.5),H,pairs,lodf


