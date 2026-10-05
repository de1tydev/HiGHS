"""Bounded synthetic helpers copied from the frozen subset tests, never source data."""
from fractions import Fraction as Q
import math
import numpy as np
from scipy.sparse import coo_matrix
import oracle as o

class TinyGenerator:
    def __init__(self, lodf=None):
        self.calls = 0
        self.lodf = np.asarray(lodf if lodf is not None else [[-1., .5, -.25], [.75, -1., .125], [-.5, .25, -1.]])

    def check_schema(self, data, hours):
        if hours < 1:
            raise ValueError('Invalid horizon')

    def factors(self, data):
        self.calls += 1
        A = coo_matrix(([1., -1., 1., -1., 1., -1.], ([0, 0, 1, 1, 2, 2], [0, 1, 1, 2, 2, 0])), shape=(3, 3)).tocsr()
        return list(data['Buses']), list(data['Transmission lines']), A, np.asarray([2., 3., 5.]), [0, 1, 2], self.lodf.copy(), 1.


def fixture(hours=2, pairs=((0, 1), (1, 2)), lodf=None, zero_shed=False):
    generator = TinyGenerator(lodf)
    data = {
        'Parameters': {'Time horizon (h)': hours},
        'Buses': {b: {'Load (MW)': [0. if zero_shed and b == 'b2' else 1.] * hours} for b in ('b0', 'b1', 'b2')},
        'Generators': {'g0': {'Bus': 'b0', 'Production cost curve (MW)': [0., 6.]},
                       'g1': {'Bus': 'b1', 'Production cost curve (MW)': [0., 6.]}},
        'Transmission lines': {
            'l0': {'Source bus': 'b0', 'Target bus': 'b1', 'Susceptance (S)': 2., 'Normal flow limit (MW)': .25, 'Emergency flow limit (MW)': .125},
            'l1': {'Source bus': 'b1', 'Target bus': 'b2', 'Susceptance (S)': 3., 'Normal flow limit (MW)': .5, 'Emergency flow limit (MW)': .25},
            'l2': {'Source bus': 'b2', 'Target bus': 'b0', 'Susceptance (S)': 5.}},
        'Contingencies': {f'c{k}': {'Affected lines': [f'l{k}']} for k in range(3)},
    }
    names = o.v2.source_names(data, hours, [0, 1])
    ix = {name: j for j, name in enumerate(names)}
    expected = dict(num_col=len(names), col_names=names, col_lower=[0.] * len(names),
                    col_upper=[math.inf] * len(names), col_cost=[0.] * len(names), sense=1, offset=0.)
    for name, j in ix.items():
        if name.startswith('p_'):
            expected['col_upper'][j] = 6.
            expected['col_cost'][j] = 7. if 'g0' in name else 11.
        if name.startswith('shed_'):
            expected['col_upper'][j] = 0. if zero_shed and 'b2' in name else 1.
            expected['col_cost'][j] = 1000.
        if name.startswith('over_'):
            expected['col_cost'][j] = 5000.
        if name.startswith('f_') or name.startswith('theta_'):
            expected['col_lower'][j] = -math.inf
        if name.startswith('theta_b0_'):
            expected['col_lower'][j] = expected['col_upper'][j] = 0.
    rows = []
    for l in (0, 1):
        for t in range(hours):
            for s in (1., -1.):
                rows.append(({ix[f'f_l{l}_{t}']: s, ix[f'over_l{l}_{t}']: -1.}, [.25, .5][l]))
    for l, k in pairs:
        for t in range(hours):
            for s in (1., -1.):
                terms = {ix[f'f_l{l}_{t}']: s, ix[f'over_l{l}_{t}']: -1.}
                if generator.lodf[l, k] != 0:
                    terms[ix[f'f_l{k}_{t}']] = s * generator.lodf[l, k]
                rows.append((terms, [.125, .25][l]))
    starts, indices, vals = [0], [], []
    for j in range(len(names)):
        for r, (terms, _) in enumerate(rows):
            if j in terms:
                indices.append(r); vals.append(terms[j])
        starts.append(len(indices))
    expected.update(num_row=len(rows), num_nz=len(vals), a_start=starts, a_index=indices,
                    a_value=vals, row_lower=[-math.inf] * len(rows), row_upper=[h for _, h in rows])
    return data, expected, generator


def prepare_tiny(hours=2, pairs=((0, 1), (1, 2)), lodf=None, zero_shed=False):
    data, expected, generator = fixture(hours, pairs, lodf, zero_shed)
    prepared = o.PreparedOracle(data, expected, pairs, generator, {'fixture': 'tiny-only'}, production_scope=False)
    x = np.full(len(prepared.names), np.nan)
    x[prepared.retained_indices] = 0.
    for t in range(hours):
        x[prepared.p_indices[t, 0]] = float(sum(prepared.loads[t]))
    return prepared, x, expected, generator


def exact_scoped_value(flow, pairs, d, normal, emergency):
    values = [Q(0)] * len(flow)
    for l in range(len(flow)):
        if math.isfinite(normal[l]):
            values[l] = max(Q(0), abs(flow[l]) - o.exact(normal[l]))
    for l, k in pairs:
        if math.isfinite(emergency[l]):
            values[l] = max(values[l], abs(flow[l] + o.exact(d[l, k]) * flow[k]) - o.exact(emergency[l]))
    return sum(values, Q(0)), values


def tiny_exact_flow(q, endpoints, weights):
    # Independent exact 2x2 elimination for this three-bus fixture.
    matrix = [[Q(0) for _ in range(3)] for _ in range(3)]
    for (a, b), w in zip(endpoints, weights):
        w = o.exact(w)
        matrix[a][a] += w; matrix[b][b] += w
        matrix[a][b] -= w; matrix[b][a] -= w
    a, b = matrix[1][1:]; c, d = matrix[2][1:]
    det = a * d - b * c
    theta = [Q(0), (q[1] * d - b * q[2]) / det, (a * q[2] - q[1] * c) / det]
    return [o.exact(w) * (theta[a] - theta[b]) for (a, b), w in zip(endpoints, weights)]
