"""Complete source-only prefix enumeration and unchanged literal proof guards."""
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from fractions import Fraction as F
import gzip
import math
import numpy as np
from current_scuc.common import require



def eligible_units(source):
    result = []
    for g, d in source['Generators'].items():
        costs, delays, initial = d['Startup costs ($)'], d['Startup delays (h)'], d['Initial status (h)']
        require(len(costs) == len(delays) > 0, 'Startup category shape')
        require(all(type(c) in (float, int) and math.isfinite(c) and c >= 0 for c in costs), 'Invalid startup costs')
        require(all(a <= b for a, b in zip(costs, costs[1:])), 'Nonmonotone startup costs')
        require(all(type(t) is int and t >= 0 for t in delays) and all(a < b for a, b in zip(delays, delays[1:])), 'Invalid startup delays')
        require(type(initial) is int and initial != 0, 'Invalid initial history')
        if initial < 0 and -initial >= delays[-1]:
            result.append(g)
    return result


def select(source):
    horizon = source['Parameters']['Time horizon (h)']
    require(type(horizon) is int and horizon > 0, 'Invalid horizon')
    rows = []
    for g in eligible_units(source):
        C = F(source['Generators'][g]['Startup costs ($)'][-1])
        require(C > 0, 'Fixed complete-family source must have positive cold coefficients')
        for t in range(horizon):
            rows.append(dict(unit=g, prefix_end=t, C_hex=float(C).hex(),
                             C_exact=[str(C.numerator),str(C.denominator)], nonzeros=t+2))
    return rows


def source_guards(source, expected, original):
    model, _ = dependencies()
    eligible = eligible_units(source)
    T = source['Parameters']['Time horizon (h)']
    authority = {f'{kind}_{g}_{t}' for g in source['Generators'] for t in range(T) for kind in ('u','y','z')}
    indices = [{name:j for j,name in enumerate(e['col_names'])} for e in (expected, original)]
    require(all(v == 0 for v in expected['integrality']), 'Retained LP not continuous')
    actual_binary = {original['col_names'][j] for j,v in enumerate(original['integrality']) if v == 1}
    require(actual_binary == authority, 'Original binary authority differs from source u/y/z inventory')
    for name in authority:
        for field in ('col_lower', 'col_upper'):
            require(expected[field][indices[0][name]] == original[field][indices[1][name]], 'Retained binary bounds changed')
        j = indices[1][name]
        require(original['col_lower'][j] in (0,1) and original['col_upper'][j] in (0,1), 'Original nonbinary bounds')
    checked = []
    for e, index in zip((expected, original), indices):
        # Match only theorem rows; every other matrix slice is protected separately.
        required = set()
        def key(terms, lo, up):
            return (tuple(sorted((index[n],float(v)) for n,v in terms.items() if v != 0)),float(lo),float(up))
        for g in eligible:
            d = source['Generators'][g]
            cost, delay, initial = float(d['Startup costs ($)'][-1]), d['Startup delays (h)'][-1], d['Initial status (h)']
            for t in range(T):
                u,y,z,sc = (f'{kind}_{g}_{t}' for kind in ('u','y','z','sc'))
                transition = {u:1,y:-1,z:1}
                if t:
                    transition[f'u_{g}_{t-1}'] = -1
                required.add(key(transition,0,0))
                required.add(key({y:1,z:1},-math.inf,1))
                lo, hi = t-delay+1, t-1
                require(not (lo <= initial <= hi), 'Virtual shutdown enters cold window')
                cold = {sc:1,y:-cost,**{f'z_{g}_{s}':cost for s in range(max(0,lo),hi+1)}}
                required.add(key(cold,0,math.inf))
                require(e['col_lower'][index[sc]] == 0 and e['integrality'][index[sc]] == 0, 'Wrong sc domain')
        wanted = len(required)
        a = model.matrix(e).tocsr()
        for r in range(e['num_row']):
            lo,hi = a.indptr[r:r+2]
            k = (tuple(zip(map(int,a.indices[lo:hi]),map(float,a.data[lo:hi]))),float(e['row_lower'][r]),float(e['row_upper'][r]))
            required.discard(k)
        require(not required, 'Missing/changed literal transition, exclusivity, or cold startup rows')
        checked.append(wanted)
    return dict(eligible_units=len(eligible), literal_rows_checked=checked, original_binary_count=len(authority), passed=True)


def append_checked(expected, rows):
    model, _ = dependencies()
    index = {name:j for j,name in enumerate(expected['col_names'])}
    starts, columns, values, names = [0], [], [], []
    for row in rows:
        g,t,C = row['unit'], row['prefix_end'], float.fromhex(row['C_hex'])
        require(F(C) == F(*map(int,row['C_exact'])), 'Inexact cold coefficient')
        require(C > 0, 'Selected row must have positive cold coefficient')
        terms = [(index[f'u_{g}_{t}'],-C)]+[(index[f'sc_{g}_{s}'],1.) for s in range(t+1)]
        terms.sort()
        columns.extend(j for j,v in terms)
        values.extend(v for j,v in terms)
        starts.append(len(columns))
        names.append(f'first_start_{g}_{t}')
    new = model.append_rows(expected, np.zeros(len(rows)), np.full(len(rows),math.inf),np.array(starts,dtype=np.int32),np.array(columns,dtype=np.int32),values,names)
    original_block = model.matrix(new)[:expected['num_row'],:].tocsc()
    for field, value in [('a_start',original_block.indptr),('a_index',original_block.indices),('a_value',original_block.data)]:
        require(expected[field].tobytes() == value.tobytes(), 'Old CSC entries changed: '+field)
    for field in ('col_cost','col_lower','col_upper','integrality'):
        require(new[field].tobytes() == expected[field].tobytes(), 'Old column array changed: '+field)
    for field in ('row_lower','row_upper'):
        require(new[field][:expected['num_row']].tobytes() == expected[field].tobytes(), 'Old row bounds changed')
    require(new['col_names'] == expected['col_names'] and new['row_names'][:expected['num_row']] == expected['row_names'], 'Old names changed')
    require(new['sense'] == expected['sense'] and new['offset'] == expected['offset'], 'Objective changed')
    return new




