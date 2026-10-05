"""Fixed synthetic three-bus, two-hour fixture; contains no case data."""
def fixture():
    data={'Parameters':{'Version':'0.3','Time horizon (h)':2,'Time step (min)':60,
                        'Power balance penalty ($/MW)':1000},
          'Buses':{b:{'Load (MW)':[1.,1.]} for b in ('b0','b1','b2')},
          'Generators':{},'Reserves':{},
          'Transmission lines':{
              'l0':{'Source bus':'b0','Target bus':'b1','Susceptance (S)':2.,
                    'Normal flow limit (MW)':.25,'Emergency flow limit (MW)':.125,
                    'Flow limit penalty ($/MW)':5000},
              'l1':{'Source bus':'b1','Target bus':'b2','Susceptance (S)':3.,
                    'Normal flow limit (MW)':.5,'Emergency flow limit (MW)':.25,
                    'Flow limit penalty ($/MW)':5000},
              'l2':{'Source bus':'b2','Target bus':'b0','Susceptance (S)':5.}},
          'Contingencies':{f'c{k}':{'Affected lines':[f'l{k}']} for k in range(3)}}
    for g,b,cost in [('g0','b0',42.),('g1','b1',66.)]:
        data['Generators'][g]={'Bus':b,'Production cost curve (MW)':[0.,6.],
              'Production cost curve ($)':[0.,cost],'Initial status (h)':-24,
              'Initial power (MW)':0.,'Minimum uptime (h)':1,'Minimum downtime (h)':1,
              'Ramp up limit (MW)':6.,'Ramp down limit (MW)':6.,
              'Startup limit (MW)':6.,'Shutdown limit (MW)':6.,
              'Startup costs ($)':[0.],'Startup delays (h)':[1], 'Reserve eligibility':[]}
    return data,((0,1),(1,2))


FULL_TINY_PAIRS = ((0, 1), (0, 2), (1, 0), (1, 2))
