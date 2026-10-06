"""Pure expected-matrix/map adaptation, never a native model/controller.

Reuses the frozen exact network-family removal and aggregate-balance encoding.
Original retained integrality is restored before returning any adaptive model.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha

import copy
from fractions import Fraction as Q
import math
import numpy as np
from scipy.sparse import csc_matrix, hstack
from current_scuc.science.emitter import load_pinned, require, exact, up, identity, Activation, PRICE, NNZ_CAP, ROW_NNZ, ACTIVE_CAP, MAX_BATCHES

fp = load_pinned('_adaptive_full_projection', 'science/prep_full_projection.py',
                 source_sha('network-projection-full-oracle-v1/full_projection.py'))
core = fp._core()
from current_scuc.science import model


def line_caps(source, hours, lodf, active):
    """Canonical shared-overflow cap, never a sum of outage slack charges."""
    names, rated, outages, normal, emergency = fp.source_scope_arrays(source, hours)
    d = np.asarray(lodf)
    require(d.dtype == np.float64 and d.shape == (len(names), len(names)) and np.all(np.isfinite(d)), 'Invalid literal LODF')
    require(len(set(active)) == len(active) and set(active).issubset(rated), 'Invalid active cap scope')
    for l in rated:
        spec = source['Transmission lines'][names[l]]
        require(all(fp._at(spec.get('Flow limit penalty ($/MW)', PRICE), t) == PRICE for t in range(hours)), 'Nonuniform 5000 overflow cost')
    pmax = [exact(g['Production cost curve (MW)'][-1]) for g in source['Generators'].values()]
    require(all(v >= 0 for v in pmax), 'Negative production cap')
    G = sum(pmax, Q(0))
    bounds = {}
    for l in active:
        ks = [k for k in outages if k != l]
        D = max((abs(exact(d[l, k])) for k in ks), default=Q(0))
        for t in range(hours):
            loads = [exact(fp._at(b['Load (MW)'], t)) for b in source['Buses'].values()]
            require(all(v >= 0 for v in loads), 'Negative load')
            F = min(G, sum(loads, Q(0)))
            terms = [Q(0)]
            if math.isfinite(normal[t, l]):
                terms.append(F - exact(normal[t, l]))
            if ks and math.isfinite(emergency[t, l]):
                terms.append((1 + D) * F - exact(emergency[t, l]))
            bounds[l, t] = up(max(terms))
    return bounds


def _install_matrix(out, A):
    A = A.tocsc(); A.sort_indices()
    out.update(num_col=int(A.shape[1]), num_row=int(A.shape[0]), num_nz=int(A.nnz),
               a_start=A.indptr, a_index=A.indices, a_value=A.data)
    return model.validate_model(out)


def matrix_identity(expected, meta, state):
    return identity(dict(matrix=model.model_hashes(expected), map=state.map_hash,
        source=meta['source_identity'], scope=meta['scope_identity'],
        retained_original=meta['retained_original_columns'].tolist(),
        original_to_retained=sorted(meta['original_to_retained'].items()), lineage=meta['lineage']))


def make_base(expected, source, hours, pairs, lodf, source_identity, scope_identity):
    e = model.validate_model(expected)
    projected, old = core.transform_expected(e, source, hours, pairs, lodf)
    retained = old['retained_original_columns'].copy()
    nret = len(retained)
    select = np.concatenate([np.arange(nret), old['balance_columns']]).astype(np.int32)
    out = dict(projected)
    for key in ('col_lower', 'col_upper', 'col_cost', 'integrality'):
        out[key] = projected[key][select].copy()
    out['integrality'][:nret] = e['integrality'][retained]
    out['col_names'] = [projected['col_names'][j] for j in select]
    out = _install_matrix(out, model.matrix(projected)[:, select])
    lines, rated, _, _, _ = fp.source_scope_arrays(source, hours)
    # Validate uniform price even before the first line is activated.
    line_caps(source, hours, lodf, ())
    mapping = {int(j): i for i, j in enumerate(retained)}
    state = Activation(nret, hours, rated, source_identity, scope_identity)
    meta = dict(source_identity=source_identity, scope_identity=scope_identity,
        retained_original_columns=retained, original_to_retained=mapping,
        original_num_col=e['num_col'], original_integrality_sha256=model.digest(e['integrality']),
        retained_integrality_sha256=model.digest(out['integrality'][:nret]),
        retained_integer_count=int(np.count_nonzero(out['integrality'][:nret])),
        source_lines=lines, hours=hours, rated=rated, fixed_columns=state.fixed,
        balance_nnz=old['balance_nonzeros'], retained_matrix_nnz=old['retained_matrix_nonzeros'],
        base_row_count=out['num_row'], base_num_col=out['num_col'], lineage=[],
        original_hashes=model.model_hashes(e), legacy_network_removal=old['network_row_signature_sha256'])
    for key in ('col_lower', 'col_upper', 'col_cost', 'integrality'):
        require(out[key][:nret].tobytes() == e[key][retained].tobytes(), 'Retained bits changed: ' + key)
    meta['matrix_identity'] = matrix_identity(out, meta, state)
    meta['map_hash'] = state.map_hash
    return out, meta


def append_batch(expected, meta, state, token, rows, caps):
    """Validate a complete proposed edit before committing append-only state."""
    require(token['admit'], 'Terminal evaluation cannot append columns/rows')
    require(meta['original_to_retained'] == {int(j): i for i, j in enumerate(meta['retained_original_columns'])},
            'Retained inverse map mismatch')
    require(meta['matrix_identity'] == matrix_identity(expected, meta, state)
            and meta['map_hash'] == state.map_hash, 'Current matrix/map identity mismatch')
    require(token['before'] == state.map_hash, 'Stale activation token')
    proposed = copy.deepcopy(state)
    proposed.active = tuple(token['active'])
    require(set(caps) == {(l, t) for l in proposed.active for t in range(state.hours)}, 'Incomplete current line cap map')
    require(all(math.isfinite(v) and v >= 0 for v in caps.values()), 'Invalid line cap')
    added = len(token['new']) * state.hours
    out = dict(expected)
    out['col_names'] = list(expected['col_names']) + [f'eta_line_{l}_MW_{t}' for l in token['new'] for t in range(state.hours)]
    for key, tail in (('col_lower', np.zeros(added)), ('col_upper', np.asarray([caps[l, t] for l in token['new'] for t in range(state.hours)])),
                      ('col_cost', np.full(added, PRICE)), ('integrality', np.zeros(added, dtype=np.int32))):
        out[key] = np.concatenate([expected[key], tail])
    out = _install_matrix(out, hstack([model.matrix(expected), csc_matrix((expected['num_row'], added))], format='csc'))
    seen = set(); starts = [0]; indices = []; values = []; bounds = []; names = []
    for row in rows:
        pair = row['line'], row['hour']
        require(pair in proposed.columns and pair not in seen, 'Missing/duplicate current line-hour map')
        seen.add(pair)
        require(row.get('eta_coefficient') == -1., 'Unnormalized emitted eta')
        require(len(row['original_indices']) == len(row['coefficients']) and len(set(row['original_indices'])) == len(row['original_indices']), 'Malformed emitted row')
        require(len(row['coefficients']) + 1 <= ROW_NNZ, 'Per-row nnz guard')
        for j, a in zip(row['original_indices'], row['coefficients']):
            require(j in meta['original_to_retained'], 'Support references removed original column')
            indices.append(meta['original_to_retained'][j]); values.append(a)
        indices.append(proposed.columns[pair]); values.append(-1.)
        starts.append(len(indices)); bounds.append(row['upper'])
        names.append(f'line_support_{state.admitted}_{pair[0]}_{pair[1]}')
    require(len(rows) <= state.hours * len(proposed.active), 'Batch row guard')
    require(seen == set(token['positive_slots']), 'Partial positive-support batch forbidden')
    # Catch every structural/cap/count failure on a copy before touching state.
    probe = copy.deepcopy(state)
    probe.commit(token, actual_cut_nnz=len(indices), balance_nnz=meta['balance_nnz'])
    require(meta['balance_nnz'] + probe.cut_nnz <= NNZ_CAP, 'Balance-plus-cut nnz guard')
    if rows:
        out = model.append_rows(out, [-math.inf] * len(rows), bounds, np.asarray(starts, dtype=np.int32),
            np.asarray(indices, dtype=np.int32), np.asarray(values), names)
    for (l, t), j in state.columns.items():
        require(exact(expected['col_upper'][j]) == exact(caps[l, t]), 'Existing line cap changed')
    require(out['num_row'] <= meta['base_row_count'] + MAX_BATCHES * state.hours * ACTIVE_CAP, 'Total row guard')
    require(out['num_nz'] == meta['retained_matrix_nnz'] + meta['balance_nnz'] + meta.get('fixed_family_nnz', 0) + probe.cut_nnz, 'Matrix nnz accounting mismatch')
    updated = dict(meta)
    updated['lineage'] = list(meta['lineage']) + [dict(support_hash=token['support_hash'], added_lines=list(token['new']),
                                                    rows=len(rows), nnz=len(indices))]
    updated['map_hash'] = probe.map_hash
    updated['matrix_identity'] = matrix_identity(out, updated, probe)
    state.commit(token, actual_cut_nnz=len(indices), balance_nnz=meta['balance_nnz'])
    return out, updated


def check_start(expected, meta, state, receipt, tolerance=1e-6, integer_tolerance=1e-6):
    require(receipt.get('matrix_identity') == meta['matrix_identity'] == matrix_identity(expected, meta, state), 'Start matrix identity mismatch')
    require(receipt.get('map_hash') == meta['map_hash'] == state.map_hash, 'Start map identity mismatch')
    require(receipt.get('full_scope_identity') == meta['scope_identity'] == state.scope_identity, 'Start full-scope identity mismatch')
    x = np.asarray(receipt['values'])
    require(x.dtype == np.float64 and x.shape == (state.num_col,) and np.all(np.isfinite(x)), 'Incomplete/nonfinite start')
    tol = exact(tolerance); itol = exact(integer_tolerance)
    require(0 <= tol <= exact(1e-6) and 0 <= itol <= exact(1e-6), 'Carry tolerance cannot exceed frozen 1e-6')
    for j, value in enumerate(x):
        q = exact(value)
        if math.isfinite(expected['col_lower'][j]):
            require(q >= exact(expected['col_lower'][j]) - tol, 'Start lower bound failed')
        if math.isfinite(expected['col_upper'][j]):
            require(q <= exact(expected['col_upper'][j]) + tol, 'Start upper bound failed')
        if expected['integrality'][j]:
            require(abs(q - round(q)) <= itol, 'Start integer condition failed')
    require(all(x[j] == 1. for j in state.fixed), 'Start fixed-one mismatch')
    activity = [Q(0)] * expected['num_row']
    for j, value in enumerate(x):
        for k in range(expected['a_start'][j], expected['a_start'][j + 1]):
            activity[int(expected['a_index'][k])] += exact(expected['a_value'][k]) * exact(value)
    for r, value in enumerate(activity):
        if math.isfinite(expected['row_lower'][r]):
            require(value >= exact(expected['row_lower'][r]) - tol, 'Start row lower failed')
        if math.isfinite(expected['row_upper'][r]):
            require(value <= exact(expected['row_upper'][r]) + tol, 'Start row upper failed')
    return True


def canonical_start(expected, meta, state, retained_values, canonical_full_line_upper, scope_identity):
    require(scope_identity == meta['scope_identity'] == state.scope_identity, 'Start full-scope mismatch')
    require(set(canonical_full_line_upper) == {(l, t) for l in state.rated for t in range(state.hours)}, 'Incomplete canonical full-line costs')
    retained = np.asarray(retained_values)
    require(retained.dtype == np.float64 and retained.shape == (state.nret,) and np.all(np.isfinite(retained)), 'Retained start dimension/type')
    require(all(math.isfinite(float(v)) and v >= 0 for v in canonical_full_line_upper.values()), 'Invalid canonical line cost')
    x = np.empty(state.num_col, dtype=np.float64)
    x[:state.nret] = retained
    x[list(state.fixed)] = 1.
    for pair, j in state.columns.items():
        value = canonical_full_line_upper[pair]
        x[j] = up(value if isinstance(value, Q) else exact(value))
        require(0 <= exact(x[j]) <= exact(expected['col_upper'][j]), 'Canonical eta exceeds exact current cap')
    require(x[:state.nret].tobytes() == retained.tobytes(), 'Retained start bits changed')
    receipt = dict(values=x, matrix_identity=meta['matrix_identity'], map_hash=state.map_hash,
                   full_scope_identity=scope_identity, canonical_full_line_cost_dollars=PRICE * sum((v if isinstance(v, Q) else exact(v) for v in canonical_full_line_upper.values()), Q(0)))
    check_start(expected, meta, state, receipt)
    return receipt
