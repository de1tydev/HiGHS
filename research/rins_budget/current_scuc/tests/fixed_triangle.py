"""Fixed pre-existing two-hour triangle; no solver imports or execution."""
import json
from pathlib import Path

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

FULL_TINY_PAIRS = ((0,1),(0,2),(1,0),(1,2))


def family_fixture():
    """The already declared first-start fixture delta, independent of outcomes."""
    data, pairs = fixture()
    assert list(data['Generators']) == ['g0', 'g1']
    for unit in data['Generators'].values():
        assert unit['Startup costs ($)'] == [0.]
        assert unit['Startup delays (h)'] == [1] and unit['Initial status (h)'] == -24
        unit['Startup costs ($)'] = [1.]
    return data, pairs


def write_source(path):
    data, _ = family_fixture()
    path = Path(path)
    with path.open('x') as stream:
        stream.write(json.dumps(data, indent=2)+'\n')
    return path


def require_expected_quality(quality):
    """The same fixture must retain its known 2.25 MWh quality failure."""
    from current_scuc.common import finite, require
    totals=quality['positive_slack_totals_MWh']
    require(quality['passed'] is False and quality['tolerance_MWh']==1e-5 and
        all(finite(totals.get(k)) for k in ('load_shedding','reserve_shortfall','shared_overflow')),
        'Tiny expected material-overflow quality result changed')
    require(0<=totals['load_shedding']<=1e-5 and 0<=totals['reserve_shortfall']<=1e-5 and
        abs(totals['shared_overflow']-2.25)<=1e-5,
        'Fixed tiny must preserve zero shedding/reserve and 2.25 MWh shared overflow')
    return True
