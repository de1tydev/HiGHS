#!/usr/bin/env python3
"""Custom sparse MILP export from a STRICT supported subset of UC.jl v0.3 JSON.
No solver is imported or called. See README.md for formulation/differences.
"""
import argparse, array, gzip, hashlib, json, math, pathlib, time
import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import splu


def at(x,t): return float(x[t] if isinstance(x,list) else x)
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f: return json.load(f)

def check_schema(d,T):
    assert d['Parameters']['Version']=='0.3'
    assert d['Parameters'].get('Time step (min)',60)==60,'Only hourly input supported'
    assert not d.get('Price-sensitive loads')
    assert set(d)<=set(['SOURCE','Parameters','Generators','Transmission lines','Contingencies','Buses','Reserves'])
    for b in d['Buses'].values():
        assert all(at(b['Load (MW)'],t)>=0 for t in range(T)), 'Negative load unsupported'
    for g in d['Generators'].values():
        p=g['Production cost curve (MW)'];c=g['Production cost curve ($)']
        assert len(p)==len(c) and len(p)>=2
        assert not any(isinstance(v,list) for v in p+c),'Time-varying cost curves unsupported'
        assert all(p[i+1]>p[i] for i in range(len(p)-1))
        slopes=np.diff(c)/np.diff(p)
        assert min(np.diff(slopes),default=0)>=-1e-8,'Nonconvex costs unsupported'
        cs=g.get('Startup costs ($)',[0]);ds=g.get('Startup delays (h)',[g.get('Minimum downtime (h)',1)])
        assert len(cs)==len(ds) and all(v>=0 for v in cs)
        assert all(cs[i+1]>=cs[i] for i in range(len(cs)-1)),'Nonmonotone startup costs unsupported'
        assert all(ds[i+1]>ds[i] for i in range(len(ds)-1))
        assert ds[0]==g.get('Minimum downtime (h)',1)
        assert g['Initial status (h)']!=0 and all(float(x).is_integer() for x in ds+[g['Initial status (h)'],g.get('Minimum uptime (h)',1),g.get('Minimum downtime (h)',1)])
    for r in d.get('Reserves',{}).values(): assert r['Type'].lower()=='spinning','Only spinning reserves supported'
    for c in d.get('Contingencies',{}).values():
        assert not c.get('Affected generators') and not c.get('Affected units'), 'Generator/unit contingencies unsupported'
        assert len(c.get('Affected lines',[]))==1, 'Only single-line outages supported'


def factors(d,require_nonislanding=True):
    buses=list(d['Buses']);lines=list(d['Transmission lines']);bi={x:i for i,x in enumerate(buses)}
    lr=[];bc=[];av=[]
    for i,l in enumerate(d['Transmission lines'].values()):
        lr += [i,i];bc += [bi[l['Source bus']],bi[l['Target bus']]];av += [1.,-1.]
    A=coo_matrix((av,(lr,bc)),shape=(len(lines),len(buses))).tocsr()
    w=np.array([l['Susceptance (S)'] for l in d['Transmission lines'].values()])
    Ar=A[:,1:];B=(Ar.T@diags(w)@Ar).tocsc();lu=splu(B)
    H=(diags(w)@Ar)@lu.solve(Ar.T.toarray())
    outages=[lines.index(c['Affected lines'][0]) for c in d['Contingencies'].values()]
    den=1-H.diagonal()
    if require_nonislanding:
        for k in outages: assert abs(den[k])>1e-9,f'Islanding/numerically singular outage {lines[k]}'
    lodf=np.zeros_like(H)
    valid=[k for k in outages if abs(den[k])>1e-9]
    lodf[:,valid]=H[:,valid]/den[valid]
    for k in outages: lodf[k,k]=-1
    return buses,lines,A,w,outages,lodf, min((float(abs(den[k])) for k in outages),default=None)

class Model:
    def __init__(self):
        self.names=[];self.lb=[];self.ub=[];self.obj=[];self.binary=[]
        self.ri=array.array('i');self.ci=array.array('i');self.val=array.array('d');self.rhs=array.array('d');self.sense=[]
    def var(self,n,lo=0.,up=math.inf,c=0.,binary=False):
        j=len(self.names);self.names.append(n);self.lb.append(float(lo));self.ub.append(float(up));self.obj.append(float(c));self.binary.append(binary);return j
    def row(self,terms,sense,rhs):
        i=len(self.rhs);self.sense.append(sense);self.rhs.append(float(rhs))
        # Combine repeated columns, preserving exact nonzero coefficients.
        acc={}
        for j,v in terms: acc[j]=acc.get(j,0.)+v
        for j,v in acc.items():
            if v!=0: self.ri.append(i);self.ci.append(j);self.val.append(float(v))
    def write(self,path,meta):
        n=len(self.names);m=len(self.rhs)
        a=coo_matrix((np.frombuffer(self.val,dtype=np.float64),(np.frombuffer(self.ri,dtype=np.int32),np.frombuffer(self.ci,dtype=np.int32))),shape=(m,n)).tocsc()
        with open(path,'w') as f:
            f.write('NAME          SCUCBENCH\nROWS\n N  OBJ\n')
            for i,s in enumerate(self.sense): f.write(f' {s}  R{i}\n')
            f.write('COLUMNS\n');isint=False;marker=0
            for j,name in enumerate(self.names):
                if self.binary[j]!=isint:
                    isint=self.binary[j];f.write(f"    MARK{marker}  'MARKER'  '{'INTORG' if isint else 'INTEND'}'\n");marker+=1
                f.write(f'    {name}  OBJ  {self.obj[j]:.17g}\n')
                for z in range(a.indptr[j],a.indptr[j+1]): f.write(f'    {name}  R{a.indices[z]}  {a.data[z]:.17g}\n')
            if isint: f.write(f"    MARK{marker}  'MARKER'  'INTEND'\n")
            f.write('RHS\n')
            for i,r in enumerate(self.rhs):
                if r: f.write(f'    RHS1  R{i}  {r:.17g}\n')
            f.write('BOUNDS\n')
            for j,name in enumerate(self.names):
                lo,up=self.lb[j],self.ub[j]
                if self.binary[j]: f.write(f' BV BND1  {name}\n')
                if lo==up: f.write(f' FX BND1  {name}  {lo:.17g}\n')
                else:
                    if lo==-math.inf: f.write(f' MI BND1  {name}\n')
                    elif lo!=0: f.write(f' LO BND1  {name}  {lo:.17g}\n')
                    if up!=math.inf and not(self.binary[j] and up==1): f.write(f' UP BND1  {name}  {up:.17g}\n')
            f.write('ENDATA\n')
        meta.update(rows=m,columns=n,binaries=sum(self.binary),nonzeros=len(self.val),mps_bytes=pathlib.Path(path).stat().st_size,mps_sha256=sha(path))
        pathlib.Path(str(path)+'.meta.json').write_text(json.dumps(meta,indent=2)+'\n')
        return meta

def build(d,T,mode,security_pairs=None):
    check_schema(d,T);m=Model();gs=list(d['Generators']);bs=list(d['Buses']);ls=list(d['Transmission lines']);rs=list(d.get('Reserves',{}))
    ix={};v=lambda *k:ix[k]
    for g in gs:
        gd=d['Generators'][g];p=gd['Production cost curve (MW)'];c=gd['Production cost curve ($)'];initial=int(gd['Initial status (h)']);U=gd.get('Minimum uptime (h)',1);D=gd.get('Minimum downtime (h)',1)
        for t in range(T):
            fix=(1 if initial>0 else 0) if t<max(0,(U-initial if initial>0 else D+initial)) else None
            if at(gd.get('Must run?',False),t):
                assert fix!=0, 'Must-run conflicts with residual initial downtime'
                fix=1
            for kind in ['u','y','z']:
                lo=up=fix if kind=='u' and fix is not None else None
                ix[kind,g,t]=m.var(f'{kind}_{g}_{t}',lo=0 if lo is None else lo,up=1 if up is None else up,c=c[0] if kind=='u' else 0,binary=True)
            ix['p',g,t]=m.var(f'p_{g}_{t}',up=p[-1]);ix['sc',g,t]=m.var(f'sc_{g}_{t}',c=1)
            for k in range(len(p)-1):ix['seg',g,t,k]=m.var(f'seg_{g}_{t}_{k}',up=p[k+1]-p[k],c=(c[k+1]-c[k])/(p[k+1]-p[k]))
            for r in gd.get('Reserve eligibility',[]):
                assert r in rs;ix['reserve',r,g,t]=m.var(f'reserve_{r}_{g}_{t}')
    for b in bs:
        for t in range(T): ix['shed',b,t]=m.var(f'shed_{b}_{t}',up=at(d['Buses'][b]['Load (MW)'],t),c=at(d['Parameters'].get('Power balance penalty ($/MW)',1000),t))
    for r in rs:
        rd=d['Reserves'][r]
        for t in range(T):
            penalty=at(rd.get('Shortfall penalty ($/MW)',-1),t);ix['short',r,t]=m.var(f'short_{r}_{t}',up=0 if penalty<0 else math.inf,c=max(0,penalty))
    for g in gs:
        gd=d['Generators'][g];p=gd['Production cost curve (MW)'];pmin,pmax=p[0],p[-1];initial=int(gd['Initial status (h)']);on0=int(initial>0);p0=gd['Initial power (MW)'];U=int(gd.get('Minimum uptime (h)',1));D=int(gd.get('Minimum downtime (h)',1))
        ru=gd.get('Ramp up limit (MW)',pmax);rd=gd.get('Ramp down limit (MW)',pmax);su=min(gd.get('Startup limit (MW)',pmax),pmax);sd=min(gd.get('Shutdown limit (MW)',pmax),pmax)
        res=lambda t:[(v('reserve',r,g,t),1) for r in gd.get('Reserve eligibility',[])]
        for t in range(T):
            u,y,z,pp=v('u',g,t),v('y',g,t),v('z',g,t),v('p',g,t)
            m.row([(u,1),(y,-1),(z,1)]+([(v('u',g,t-1),-1)] if t else []),'E',on0 if t==0 else 0)
            m.row([(y,1),(z,1)],'L',1)
            m.row([(v('y',g,i),1) for i in range(max(0,t-U+1),t+1)]+[(u,-1)],'L',0)
            m.row([(v('z',g,i),1) for i in range(max(0,t-D+1),t+1)]+[(u,1)],'L',1)
            m.row([(pp,1),(u,-pmin)]+[(v('seg',g,t,k),-1) for k in range(len(p)-1)],'E',0)
            for k in range(len(p)-1):m.row([(v('seg',g,t,k),1),(u,-(p[k+1]-p[k]))],'L',0)
            m.row([(pp,1),(u,-pmax)]+res(t),'L',0)
            m.row([(pp,1),(u,-pmax),(y,pmax-su)]+res(t),'L',0)
            if t<T-1:m.row([(pp,1),(u,-pmax),(v('z',g,t+1),pmax-sd)]+res(t),'L',0)
            m.row([(pp,1),(y,-su)]+res(t)+([(v('p',g,t-1),-1),(v('u',g,t-1),-ru)] if t else []),'L',p0+ru*on0 if t==0 else 0)
            m.row([(pp,-1),(u,-rd),(z,-sd)]+([(v('p',g,t-1),1)]+res(t-1) if t else []),'L',-p0 if t==0 else 0)
            for cost,delay in zip(gd.get('Startup costs ($)',[0]),gd.get('Startup delays (h)',[D])):
                lo=t-int(delay)+1;hi=t-1
                virtual=1 if initial<0 and lo<=initial<=hi else 0
                m.row([(v('sc',g,t),1),(y,-cost)]+[(v('z',g,i),cost) for i in range(max(0,lo),hi+1)],'G',-cost*virtual)
    for r in rs:
        rd=d['Reserves'][r]
        for t in range(T):m.row([(v('reserve',r,g,t),1) for g in gs if r in d['Generators'][g].get('Reserve eligibility',[])]+[(v('short',r,t),1)],'G',at(rd['Amount (MW)'],t))
    netinfo={}
    if mode=='uc':
        for t in range(T):m.row([(v('p',g,t),1) for g in gs]+[(v('shed',b,t),1) for b in bs],'E',sum(at(d['Buses'][b]['Load (MW)'],t) for b in bs))
    else:
        bs,ls,A,w,outages,lodf,minden=factors(d,require_nonislanding=(mode=='n1'))
        for b in bs:
            for t in range(T):ix['theta',b,t]=m.var(f'theta_{b}_{t}',lo=0 if b==bs[0] else -math.inf,up=0 if b==bs[0] else math.inf)
        rated=[i for i,l in enumerate(ls) if any(math.isfinite(at(d['Transmission lines'][l].get('Normal flow limit (MW)',math.inf),t)) or math.isfinite(at(d['Transmission lines'][l].get('Emergency flow limit (MW)',math.inf),t)) for t in range(T))]
        for i,l in enumerate(ls):
            ld=d['Transmission lines'][l]
            for t in range(T):
                ix['f',l,t]=m.var(f'f_{l}_{t}',lo=-math.inf)
                if i in rated:ix['over',l,t]=m.var(f'over_{l}_{t}',c=at(ld.get('Flow limit penalty ($/MW)',5000),t))
                m.row([(v('f',l,t),1),(v('theta',ld['Source bus'],t),-w[i]),(v('theta',ld['Target bus'],t),w[i])],'E',0)
                lim=at(ld.get('Normal flow limit (MW)',math.inf),t)
                if math.isfinite(lim):
                    for sign in [1,-1]:m.row([(v('f',l,t),sign),(v('over',l,t),-1)],'L',lim)
        for b in bs:
            for t in range(T):m.row([(v('p',g,t),1) for g in gs if d['Generators'][g]['Bus']==b]+[(v('shed',b,t),1)]+[(v('f',l,t),-1 if d['Transmission lines'][l]['Source bus']==b else 1) for l in ls if b in (d['Transmission lines'][l]['Source bus'],d['Transmission lines'][l]['Target bus'])],'E',at(d['Buses'][b]['Load (MW)'],t))
        paircount=0
        if mode=='n1':
            pairs=security_pairs if security_pairs is not None else [(l,k) for l in rated for k in outages if l!=k]
            for l,k in pairs:
                assert 0<=l<len(ls) and l in rated and k in outages and l!=k
                for t in range(T):
                    lim=at(d['Transmission lines'][ls[l]].get('Emergency flow limit (MW)',math.inf),t)
                    if math.isfinite(lim):
                        for sign in [1,-1]:m.row([(v('f',ls[l],t),sign),(v('f',ls[k],t),sign*lodf[l,k]),(v('over',ls[l],t),-1)],'L',lim)
                paircount+=1
        netinfo={'finite_rated_lines':len(rated),'eligible_outages':len(outages),'security_pairs':paircount,'all_security_pairs':sum(l!=k for l in rated for k in outages),'lodf_cutoff':0,'minimum_outage_denominator':minden}
    return m,netinfo

def main():
    a=argparse.ArgumentParser();a.add_argument('input');a.add_argument('--mode',choices=['uc','network','n1'],required=True);a.add_argument('--hours',type=int);a.add_argument('--output',required=True);a.add_argument('--pairs',help='Optional JSON array of zero-indexed [monitored,outage] line indices; screened subset, not full N−1 unless all security checks pass');args=a.parse_args()
    started=time.monotonic();d=read(args.input);T=args.hours or int(d['Parameters']['Time horizon (h)']);assert 1<=T<=d['Parameters']['Time horizon (h)'];pairs=json.load(open(args.pairs)) if args.pairs else None
    model,netinfo=build(d,T,args.mode,pairs)
    meta=dict(input_path=str(pathlib.Path(args.input).resolve()),input_sha256=sha(args.input),generator_sha256=sha(__file__),source_horizon=d['Parameters']['Time horizon (h)'],hours=T,mode=args.mode,security_scope='all listed line outages' if args.mode=='n1' and pairs is None else ('selected line pairs' if pairs is not None else 'none'),formulation='custom-three-binary-convex-segments-startup-epigraph-dc-v1',buses=len(d['Buses']),generators=len(d['Generators']),lines=len(d['Transmission lines']),network=netinfo)
    meta=model.write(args.output,meta);meta['generation_seconds']=time.monotonic()-started;pathlib.Path(args.output+'.meta.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__': main()
