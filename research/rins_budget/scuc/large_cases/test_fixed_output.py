import importlib.util,pathlib,numpy as np
P=pathlib.Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('network_v2',P/'generate_network_only.py');g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g)
d={'Parameters':{'Version':'0.3','Time horizon (h)':2},'Buses':{'a':{'Load (MW)':[2500.,2500.]},'b':{'Load (MW)':[0.,0.]}},'Generators':{'g':{'Bus':'a','Production cost curve (MW)':[2500.],'Production cost curve ($)':[10.],'Startup costs ($)':[20.],'Startup delays (h)':[1],'Minimum uptime (h)':1,'Minimum downtime (h)':1,'Initial status (h)':24,'Initial power (MW)':2500.,'Ramp up limit (MW)':1750.,'Ramp down limit (MW)':1750.,'Startup limit (MW)':2500.,'Shutdown limit (MW)':1750.,'Reserve eligibility':[]}},'Transmission lines':{'l':{'Source bus':'a','Target bus':'b','Susceptance (S)':1.,'Normal flow limit (MW)':10.,'Emergency flow limit (MW)':10.}},'Contingencies':{},'Reserves':{}}
m,info=g.build(d,2,'network');x=np.zeros(len(m.names))
for t in range(2):x[m.names.index(f'u_g_{t}')]=1.;x[m.names.index(f'p_g_{t}')]=2500.
activity=np.zeros(len(m.rhs))
for r,c,v in zip(m.ri,m.ci,m.val):activity[r]+=v*x[c]
for i,(sense,rhs) in enumerate(zip(m.sense,m.rhs)):
 assert abs(activity[i]-rhs)<1e-8 if sense=='E' else activity[i]<=rhs+1e-8 if sense=='L' else activity[i]>=rhs-1e-8
assert not any(n.startswith('seg_') for n in m.names)
assert sum(o*v for o,v in zip(m.obj,x))==20.
assert info['minimum_outage_denominator'] is None
print('fixed-output single-point curve: exact production/no segments/objective/sparse-network test PASS')
