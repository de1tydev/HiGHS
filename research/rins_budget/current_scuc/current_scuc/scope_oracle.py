"""One-arm reusable adapter for the frozen two-pair continuous network scope.

No point files, solver calls, model generation, or historical cuts are accepted.
Preparation is numerical work and must run inside the parent's charged process.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha

import os
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
             'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_key] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
sys.dont_write_bytecode = True
from collections import Counter
from fractions import Fraction as Q
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu
from threadpoolctl import threadpool_info, threadpool_limits

V2_SHA = source_sha('network-value-oracle-v2/oracle.py')
GENERATOR_SHA = source_sha('primal-cache-replay-v4.1/core/scuc/generate.py')
# Production input identities come from the same frozen held-out record.
import current_scuc.heldout as heldout
REQUIRED_PINS = heldout.LazyPins(suffix=True)

APPROVED_PAIRS = ()
APPROVED_PAIR_NAMES = ()


def _digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 ** 2), b''):
            h.update(block)
    return h.hexdigest()


_v2_path = PACKAGE_ROOT / 'science/value_oracle.py'
if _digest(_v2_path) != V2_SHA:
    raise ValueError('Frozen v2 oracle SHA mismatch')
v2 = load_module('value_oracle', _v2_path)
require, exact, up, down, rat = v2.require, v2.exact, v2.up, v2.down, v2.rat


def _readonly(values, dtype=None):
    arr = np.array(values, dtype=dtype, copy=True)
    arr.setflags(write=False)
    return arr


def _at(value, hour):
    return float(value[hour] if isinstance(value, list) else value)


def validate_pairs(pairs, line_count, rated, outages):
    """A pair is an ordered source identity, never an outage-only selection."""
    result = []
    for pair in pairs:
        require(isinstance(pair, (tuple, list)) and len(pair) == 2, 'Invalid explicit pair')
        l, k = pair
        require(type(l) is int and type(k) is int, 'Pair indices must be integers')
        require(0 <= l < line_count and 0 <= k < line_count and l != k, 'Invalid pair indices')
        require(l in rated and k in outages, 'Pair not in source rated/outage scope')
        result.append((l, k))
    require(len(set(result)) == len(result), 'Duplicate explicit pair')
    # Source monitored/outage order determines the same tie choice as v2.
    outage_order = {k: i for i, k in enumerate(outages)}
    return tuple(sorted(result, key=lambda x: (x[0], outage_order[x[1]])))


def row_scan(flow, qres, rated, pairs, lodf, normal, emergency):
    """Frozen normal scan plus exactly the explicitly named contingency pairs.

    Pair arithmetic is exact: |f_l + d_lk f_k| +/- (1+|d_lk|) Qres.
    Outward conversions are applied only to the resulting exact endpoints.
    This is the same v2 error enclosure, with no cross-product row admission.
    """
    scan = v2.row_scan(flow, qres, rated, [], lodf, normal, emergency)
    for l, k in pairs:
        h = float(emergency[l])
        if not math.isfinite(h):
            continue
        d = exact(lodf[l, k])
        z = flow[l] + d * flow[k]
        err = (1 + abs(d)) * qres
        lo = max(Q(0), abs(z) - err - exact(h))
        hi = max(Q(0), abs(z) + err - exact(h))
        scan['lower'][l] = max(scan['lower'][l], down(lo))
        scan['upper'][l] = max(scan['upper'][l], up(hi))
        nominal = float(flow[l]) + float(lodf[l, k]) * float(flow[k])
        candidate = abs(nominal) - h
        require(math.isfinite(nominal) and math.isfinite(candidate), 'Nonfinite pair arithmetic')
        if candidate > scan['nominal'][l]:
            scan['nominal'][l] = candidate
            scan['kind'][l] = 2
            scan['outage'][l] = k
            scan['sign'][l] = 1 if nominal >= 0 else -1
    require(np.all(scan['lower'] <= scan['upper']), 'Invalid scoped enclosure')
    return scan


def selected_terms(scan, lodf, normal, emergency, rated, pairs):
    allowed = set(pairs)
    for l, kind in enumerate(scan['kind']):
        if kind == 2:
            require((l, int(scan['outage'][l])) in allowed, 'Selected pair outside explicit scope')
    return v2.selected_terms(scan, lodf, normal, emergency, rated, [k for _, k in pairs])


def _row_signature(l, hour, rhs, terms):
    return (int(l), int(hour), float(rhs).hex(),
            tuple(sorted((int(k), float(v).hex()) for k, v in terms if v != 0)))


def verify_scope_rows(expected, lines, hours, rated, pairs, lodf, normal, emergency):
    """Verify the complete signed multiset, including omitted zero LODF terms."""
    names = expected['col_names']
    require(len(names) == len(set(names)), 'Duplicate original column name')
    ix = {name: j for j, name in enumerate(names)}
    starts, indices, vals = (expected[k] for k in ('a_start', 'a_index', 'a_value'))
    soft = {}
    for l in rated:
        for t in range(hours):
            j = ix[f'over_{lines[l]}_{t}']
            for z in range(starts[j], starts[j + 1]):
                r = int(indices[z])
                require(float(vals[z]) == -1 and r not in soft, 'Shared-overload coefficient mismatch')
                require(float(expected['row_lower'][r]) == -math.inf, 'Soft-row lower sense mismatch')
                h = float(expected['row_upper'][r])
                require(math.isfinite(h), 'Soft-row finite upper bound required')
                soft[r] = [l, t, h, []]
    flow_columns = {ix[f'f_{name}_{t}']: (l, t) for l, name in enumerate(lines) for t in range(hours)}
    over_columns = {ix[f'over_{lines[l]}_{t}'] for l in rated for t in range(hours)}
    for j in range(len(names)):
        if j in over_columns:
            continue
        for z in range(starts[j], starts[j + 1]):
            r = int(indices[z])
            if r not in soft:
                continue
            require(j in flow_columns, 'Nonflow coefficient in original soft row')
            l, t = flow_columns[j]
            require(t == soft[r][1], 'Cross-hour original soft row')
            soft[r][3].append((l, float(vals[z])))
    actual = Counter(_row_signature(*row) for row in soft.values())
    wanted = Counter()
    normal_count = seed_count = 0
    for l in rated:
        for t in range(hours):
            if math.isfinite(normal[t, l]):
                for sign in (1., -1.):
                    wanted[_row_signature(l, t, normal[t, l], [(l, sign)])] += 1
                    normal_count += 1
    for l, k in pairs:
        for t in range(hours):
            if math.isfinite(emergency[t, l]):
                for sign in (1., -1.):
                    wanted[_row_signature(l, t, emergency[t, l], [(l, sign), (k, sign * lodf[l, k])])] += 1
                    seed_count += 1
    require(actual == wanted, 'Original signed soft rows differ from exact explicit-pair scope/coefficient bits')
    scope_hash = hashlib.sha256()
    # Include declared pair identities even when a zero LODF omits its column.
    scope_hash.update(json.dumps({'hours': hours, 'line_ids': list(lines), 'pairs': pairs},
                                separators=(',', ':')).encode() + b'\n')
    for signature, multiplicity in sorted(wanted.items()):
        scope_hash.update(json.dumps([signature, multiplicity], separators=(',', ':')).encode() + b'\n')
    return dict(normal_signed_rows=normal_count, seed_signed_rows=seed_count,
                retained_soft_rows_checked=sum(actual.values()), row_scope_sha256=scope_hash.hexdigest())


def _exact_overflow(flow, rated, normal):
    """Canonical shared slack for the literal, already-rounded supplied flows."""
    result = [Q(0) for _ in flow]
    for l in rated:
        if math.isfinite(normal[l]):
            result[l] = max(Q(0), abs(flow[l]) - exact(normal[l]))
    return result


class PreparedOracle:
    """Immutable geometry/factors, mutable evaluation count; no query history."""
    def __init__(self, data, expected, pairs, generator, pins, *, production_scope):
        started = time.monotonic()
        self.pins = dict(pins)
        self.production_scope = production_scope
        v2.check_finite_source(data)
        self.hours = int(data['Parameters']['Time horizon (h)'])
        require(self.hours > 0, 'Invalid source horizon')
        generator.check_schema(data, self.hours)
        self.buses = tuple(data['Buses'])
        self.lines = tuple(data['Transmission lines'])
        self.generators = tuple(data['Generators'])
        n, m, H = len(self.buses), len(self.lines), self.hours
        self.bus_index = {b: i for i, b in enumerate(self.buses)}
        endpoints = [(self.bus_index[v['Source bus']], self.bus_index[v['Target bus']]) for v in data['Transmission lines'].values()]
        self.endpoints = _readonly(endpoints, np.int32)
        self.weights = _readonly([v['Susceptance (S)'] for v in data['Transmission lines'].values()], np.float64)
        path, parent = v2.geometry(n, self.endpoints, self.weights)
        self.path_upper, self.bfs_parent = tuple(path), tuple(parent)
        self.normal = _readonly([[_at(v.get('Normal flow limit (MW)', math.inf), t) for v in data['Transmission lines'].values()] for t in range(H)])
        self.emergency = _readonly([[_at(v.get('Emergency flow limit (MW)', math.inf), t) for v in data['Transmission lines'].values()] for t in range(H)])
        self.rated = tuple(int(v) for v in np.flatnonzero(np.any(np.isfinite(self.normal) | np.isfinite(self.emergency), axis=0)))
        self.loads = tuple(tuple(exact(_at(data['Buses'][b]['Load (MW)'], t)) for b in self.buses) for t in range(H))
        pmax = tuple(exact(data['Generators'][g]['Production cost curve (MW)'][-1]) for g in self.generators)
        require(all(v >= 0 for v in pmax) and all(v >= 0 for row in self.loads for v in row), 'Negative source bound')
        self.source_F = tuple(min(sum(pmax, Q(0)), sum(row, Q(0))) for row in self.loads)
        for l in self.rated:
            require(all(_at(data['Transmission lines'][self.lines[l]].get('Flow limit penalty ($/MW)', 5000), t) == v2.PRICE for t in range(H)), 'Nonuniform overload price')
        self.names = tuple(expected['col_names'])
        require(list(self.names) == v2.source_names(data, H, self.rated), 'Original source column ordering mismatch')
        require(len(self.names) == expected['num_col'] and len(set(self.names)) == len(self.names), 'Original column count/name mismatch')
        ix = {name: j for j, name in enumerate(self.names)}
        self.p_indices = _readonly([[ix[f'p_{g}_{t}'] for g in self.generators] for t in range(H)], np.int64)
        self.shed_indices = _readonly([[ix[f'shed_{b}_{t}'] for b in self.buses] for t in range(H)], np.int64)
        self.theta_indices = _readonly([[ix[f'theta_{b}_{t}'] for b in self.buses] for t in range(H)], np.int64)
        self.flow_indices = _readonly([[ix[f'f_{l}_{t}'] for l in self.lines] for t in range(H)], np.int64)
        self.over_indices = _readonly([[ix[f'over_{self.lines[l]}_{t}'] for l in self.rated] for t in range(H)], np.int64)
        self.generator_bus = _readonly([self.bus_index[data['Generators'][g]['Bus']] for g in self.generators], np.int32)
        removed = set(self.theta_indices.flat) | set(self.flow_indices.flat) | set(self.over_indices.flat)
        self.retained_indices = _readonly([j for j in range(len(self.names)) if j not in removed], np.int64)
        self.removed_indices = _readonly(sorted(removed), np.int64)
        self.cost = _readonly(expected['col_cost'], np.float64)
        self.offset = float(expected['offset'])
        require(expected['sense'] == 1 and self.offset == 0 and np.all(np.isfinite(self.cost)), 'Original minimization cost mismatch')
        self.fixed_zero_shed = np.zeros((H, n), dtype=bool)
        for t in range(H):
            for g, maximum, j in zip(self.generators, pmax, self.p_indices[t]):
                require(exact(expected['col_lower'][j]) == 0 and exact(expected['col_upper'][j]) == maximum, 'Original p bound mismatch')
            for b, load, j in zip(self.buses, self.loads[t], self.shed_indices[t]):
                require(exact(expected['col_lower'][j]) == 0 and exact(expected['col_upper'][j]) == load, 'Original shed bound mismatch')
                self.fixed_zero_shed[t, self.bus_index[b]] = load == 0
            require(np.all(self.cost[self.over_indices[t]] == v2.PRICE), 'Original overload cost mismatch')
            require(np.all(self.cost[self.theta_indices[t]] == 0) and np.all(self.cost[self.flow_indices[t]] == 0), 'Unexpected theta/flow cost')
        self.fixed_zero_shed.setflags(write=False)
        self.times = {'source_geometry_mapping_seconds': time.monotonic() - started}
        wanted_outages = [self.lines.index(v['Affected lines'][0]) for v in data['Contingencies'].values()]
        require(len(wanted_outages) == len(set(wanted_outages)), 'Duplicate source outage')
        self.pairs = validate_pairs(pairs, m, self.rated, wanted_outages)
        if production_scope:
            import current_scuc.heldout as heldout
            heldout.check_inputs(pins, data=data, expected=expected)
            heldout.check_scope_shape(H, n, m, len(self.rated), len(wanted_outages))
            require(set(self.pairs) == set(APPROVED_PAIRS), 'Unapproved pair scope')
            require(tuple((self.lines[l], self.lines[k]) for l, k in APPROVED_PAIRS) == APPROVED_PAIR_NAMES, 'Approved pair names changed')
        tick = time.monotonic()
        bs, ls, A, w, outages, lodf, minden = generator.factors(data)
        require(tuple(bs) == self.buses and tuple(ls) == self.lines and np.array_equal(w, self.weights), 'Literal factor source ordering/weight mismatch')
        require(outages == wanted_outages and lodf.shape == (m, m) and np.all(np.isfinite(lodf)), 'Literal factor outage/LODF mismatch')
        require(A.shape == (m, n) and A.nnz == 2 * m, 'Literal incidence shape mismatch')
        for l, (a, b) in enumerate(self.endpoints):
            row = A.getrow(l)
            require(dict(zip(row.indices.tolist(), row.data.tolist())) == {int(a): 1., int(b): -1.}, 'Literal incidence coefficient mismatch')
        self.lodf = _readonly(lodf, np.float64)
        self.outages = tuple(outages)
        self.scope = verify_scope_rows(expected, self.lines, H, self.rated, self.pairs, self.lodf, self.normal, self.emergency)
        if production_scope:
            heldout.check_mapping_scope(self.scope)
        self.times['fresh_literal_factors_and_scope_seconds'] = time.monotonic() - tick
        tick = time.monotonic()
        Ar = A[:, 1:]
        self.lu = splu((Ar.T @ diags(self.weights) @ Ar).tocsc())
        self.times['fresh_equivalent_factorization_seconds'] = time.monotonic() - tick
        self.factorization = dict(literal_factorizations=1, second_factorizations=1,
                                  lu_L_nnz=self.lu.L.nnz, lu_U_nnz=self.lu.U.nnz,
                                  minimum_outage_denominator=minden,
                                  lodf_binary64_C_sha256=hashlib.sha256(self.lodf.tobytes(order='C')).hexdigest(),
                                  **self.scope)
        self.prepare_seconds = time.monotonic() - started
        self.evaluation_count = 0

    def factor_arrays(self):
        """Persist once per arm. Arrays are immutable; no per-round duplication."""
        return dict(lodf=self.lodf, endpoints=self.endpoints, weights=self.weights,
                    rated=np.asarray(self.rated, dtype=np.int32), outages=np.asarray(self.outages, dtype=np.int32),
                    pairs=np.asarray(self.pairs, dtype=np.int32), normal_limits=self.normal,
                    emergency_limits=self.emergency, path_resistance_upper=np.asarray(self.path_upper))

    def _retained_vector(self, retained_values):
        if isinstance(retained_values, dict):
            wanted = {self.names[j] for j in self.retained_indices}
            require(set(retained_values) == wanted, 'Expected all and only original retained values')
            x = np.full(len(self.names), np.nan)
            for j in self.retained_indices:
                x[j] = retained_values[self.names[j]]
        else:
            x = np.array(retained_values, dtype=np.float64, copy=True)
            require(x.ndim == 1 and len(x) == len(self.names), 'Original-shaped retained vector required')
            require(np.all(np.isnan(x[self.removed_indices])), 'Removed slots must be NaN; historical network points prohibited')
        require(np.all(np.isfinite(x[self.retained_indices])), 'Incomplete/nonfinite retained values')
        return x

    def evaluate(self, retained_values):
        started = time.monotonic()
        with threadpool_limits(limits=1):
            require(all(v.get('num_threads', 1) == 1 for v in threadpool_info()), 'BLAS thread limit ineffective')
            return self._evaluate(retained_values, started)

    def _evaluate(self, retained_values, started):
        x = self._retained_vector(retained_values)
        retained_bits = x[self.retained_indices].view(np.uint64).copy()
        self.evaluation_count += 1
        H, n, m = self.hours, len(self.buses), len(self.lines)
        theta_rows, flow_rows, over_rows, hour_records, cuts = [], [], [], [], []
        pis, constants, line_lower, line_upper = [], [], [], []
        gap_total = Q(0)
        raw_max = Q(0)
        lift_balance_max = Q(0)
        flow_equation_max = Q(0)
        for t in range(H):
            raw = [exact(x[j]) - load for j, load in zip(self.shed_indices[t], self.loads[t])]
            for j, bus in zip(self.p_indices[t], self.generator_bus):
                raw[int(bus)] += exact(x[j])
            q, imbalance, reference_delta = v2.balanced_probe(raw)
            raw_max = max(raw_max, abs(imbalance))
            Fcert = v2.certificate_bound(self.source_F[t], q)
            theta = np.zeros(n)
            theta[1:] = self.lu.solve(np.asarray([float(v) for v in q[1:]]))
            f, forward_residual, qres = v2.forward_certificate(q, theta, self.endpoints, self.weights)
            scan = row_scan(f, qres, self.rated, self.pairs, self.lodf, self.normal[t], self.emergency[t])
            c, lh, selected = selected_terms(scan, self.lodf, self.normal[t], self.emergency[t], self.rated, self.pairs)
            rhs = v2.incidence_transpose([exact(w) * cc for w, cc in zip(self.weights, c)], self.endpoints, n)
            pi = np.zeros(n)
            if selected:
                pi[1:] = self.lu.solve(np.asarray([float(v) for v in rhs[1:]]))
            cert = v2.cut_certificate(c, lh, pi, self.endpoints, self.weights, self.path_upper,
                                      Fcert, self.loads[t], q)
            vlo = sum((exact(v) for v in scan['lower']), Q(0))
            vhi = sum((exact(v) for v in scan['upper']), Q(0))
            # Omitted columns are exactly zero on the source domain, but a
            # numerical native snapshot may be slightly outside that bound.
            # Charge its exact omission value and, when negative, weaken the
            # constant enough that actual sparse support cannot exceed v2's.
            fixed_omission = sum((exact(cert['pi'][bus]) * exact(x[j]) for bus, j in enumerate(self.shed_indices[t]) if self.fixed_zero_shed[t, bus]), Q(0))
            omission_debit = max(Q(0), -fixed_omission)
            emitted_constant_exact = exact(cert['constant']) + omission_debit
            emitted_constant = up(emitted_constant_exact)
            full_support = cert['emitted_cut_at_qstar'] - (exact(emitted_constant) - exact(cert['constant']))
            actual_sparse_support = full_support - fixed_omission
            require(actual_sparse_support <= cert['emitted_cut_at_qstar'], 'Omission correction failed to preserve probe support')
            gap = v2.PRICE * (vhi - actual_sparse_support)
            require(gap >= 0, 'Cut exceeds certified upper value')
            gap_total += gap
            for r in selected:
                r['monitored_id'] = self.lines[r['monitored']]
                r['outage_id'] = None if r['outage'] < 0 else self.lines[r['outage']]
            # Serialize original flows to binary64, then cover THEIR literal rows
            # as well as the balanced-query value enclosure. Retained p/shed stay.
            fhat = np.asarray([float(v) for v in f])
            fe = [exact(v) for v in fhat]
            exact_over = _exact_overflow(fe, self.rated, self.normal[t])
            for l, k in self.pairs:
                if math.isfinite(self.emergency[t, l]):
                    exact_over[l] = max(exact_over[l], abs(fe[l] + exact(self.lodf[l, k]) * fe[k]) - exact(self.emergency[t, l]))
            over = np.asarray([up(max(exact(scan['upper'][l]), exact_over[l])) for l in range(m)])
            actual_lhs = v2.incidence_transpose(fe, self.endpoints, n)
            residual = [a - b for a, b in zip(raw, actual_lhs)]
            lift_balance_max = max(lift_balance_max, max(map(abs, residual)))
            flow_equation_max = max(flow_equation_max, max(abs(a - b) for a, b in zip(fe, f)))
            x[self.theta_indices[t]] = theta
            x[self.flow_indices[t]] = fhat
            x[self.over_indices[t]] = over[list(self.rated)]
            indices, coefficients = [], []
            for j, bus in zip(self.p_indices[t], self.generator_bus):
                value = float(cert['pi'][bus])
                if value != 0:
                    indices.append(int(j)); coefficients.append(value)
            for bus, j in enumerate(self.shed_indices[t]):
                value = float(cert['pi'][bus])
                if value != 0 and not self.fixed_zero_shed[t, bus]:
                    indices.append(int(j)); coefficients.append(value)
            cut = dict(hour=t, original_indices=np.asarray(indices, dtype=np.int64),
                       coefficients=np.asarray(coefficients, dtype=np.float64), upper=emitted_constant,
                       eta_coefficient=-1., nnz=len(indices) + 1)
            cuts.append(cut)
            # Since pi(reference)=0, the cut at raw p/s equals the synthetic
            # query cut. Fixed-zero omissions are valid on the original boxes.
            emitted_at_retained = sum((exact(a) * exact(x[j]) for j, a in zip(indices, coefficients)), Q(0)) - exact(emitted_constant)
            require(emitted_at_retained == actual_sparse_support, 'Retained cut/source coefficient mapping mismatch')
            hour_records.append(dict(hour=t,
                probe_label='synthetic_exactly_balanced_evaluation_only_not_original_feasible_upper',
                qstar=[rat(v) for v in q], raw_imbalance=rat(imbalance), reference_delta=rat(reference_delta),
                source_lift_balance_residual=[rat(v) for v in residual],
                Qplus=rat(sum((max(v, Q(0)) for v in q), Q(0))), F_source=rat(self.source_F[t]),
                F_certificate=rat(Fcert), probe_domain_excess=rat(Fcert - self.source_F[t]),
                forward_residual=[rat(v) for v in forward_residual], Qres=rat(qres), selected_rows=selected,
                c_sparse=[dict(line=l, value=rat(v)) for l, v in enumerate(c) if v],
                lambda_budget_max=1 if selected else 0,
                dual_residual=[rat(v) for v in cert['residual']], delta=rat(cert['delta']),
                lambda_h=rat(lh), pi_load=rat(cert['pi_load']), zeroed_pi_count=cert['zeroed_count'],
                v2_constant_before_upward_round=rat(cert['constant_exact_before_round']),
                v2_constant_hex=cert['constant'].hex(), v2_constant_rounding_loss=rat(cert['constant_rounding_loss']),
                constant_before_upward_round=rat(emitted_constant_exact),
                constant_hex=emitted_constant.hex(), constant_rounding_loss=rat(exact(emitted_constant) - emitted_constant_exact),
                value_lower_MW=rat(vlo), value_upper_MW=rat(vhi),
                v2_emitted_cut_at_qstar_MW=rat(cert['emitted_cut_at_qstar']),
                emitted_cut_at_qstar_MW=rat(full_support),
                emitted_cut_at_retained_MW=rat(emitted_at_retained),
                omitted_fixed_zero_shed_value=rat(fixed_omission),
                fixed_zero_omission_constant_debit=rat(omission_debit),
                support_gap_dollars=rat(gap), support_gap_dollars_upper=up(gap),
                maximum_excess_upper_MW=float(max(scan['upper'])), actual_cut_nnz=cut['nnz']))
            theta_rows.append(theta); flow_rows.append(fhat); over_rows.append(over)
            pis.append(cert['pi']); constants.append(emitted_constant)
            line_lower.append(scan['lower']); line_upper.append(scan['upper'])
        require(np.array_equal(retained_bits, x[self.retained_indices].view(np.uint64)), 'Recovery mutated retained values')
        require(np.all(np.isfinite(x)), 'Incomplete/nonfinite original lift')
        objective = math.fsum(float(c) * float(v) for c, v in zip(self.cost, x)) + self.offset
        require(math.isfinite(objective), 'Nonfinite recomputed original objective')
        elapsed = time.monotonic() - started
        report = dict(schema='network-projection-scope-oracle-evaluation-v1', evaluation=self.evaluation_count,
            pins=self.pins, frozen_v2_sha256=V2_SHA, **self.scope,
            scope_pairs=[list(p) for p in self.pairs], certificate_valid=True,
            support_gap_dollars=rat(gap_total), support_gap_dollars_upper=up(gap_total),
            support_gap_le_100_dollars=(gap_total <= 100), passed=(gap_total <= 100),
            cut_validity_domain='declared_literal_lodf_row_model', physical_dc_lower_bound_certified=False,
            original_source_feasible_upper_claimed=False, source_checker_required=True,
            eta_objective_coefficient=v2.PRICE, value_unit='summed shared overload MW',
            certificate_bound_rule='max(exact F_source, exact Qplus(qstar)); original source boxes unchanged',
            fresh_factorizations_this_evaluation=0, reused_factorizations_this_evaluation=2,
            fresh_factorizations_at_preparation=2, preparation_seconds=self.prepare_seconds,
            factor_reuse_policy='immutable geometry and two fresh source-equivalent factors within one charged arm',
            actual_cut_nnz=sum(row['nnz'] for row in cuts),
            maximum_excess_upper_MW=max(r['maximum_excess_upper_MW'] for r in hour_records),
            timing={'evaluation_seconds': elapsed}, hour_certificates=hour_records)
        lift = dict(values=x, theta_hat=np.asarray(theta_rows), flow_hat=np.asarray(flow_rows),
                    overload_upper=np.asarray(over_rows),
                    recomputed_original_objective=objective,
                    raw_balance_max_abs=rat(raw_max), raw_balance_max_abs_upper=up(raw_max),
                    source_nodal_balance_max_abs=rat(lift_balance_max), source_nodal_balance_max_abs_upper=up(lift_balance_max),
                    source_flow_equation_max_abs=rat(flow_equation_max), source_flow_equation_max_abs_upper=up(flow_equation_max),
                    network_residual_le_1e_5=(max(lift_balance_max, flow_equation_max) <= exact(1e-5)),
                    retained_bits_unchanged=True, source_checker_required=True, original_feasibility_claimed=False)
        arrays = dict(pi=np.asarray(pis), constant_up=np.asarray(constants),
                      line_value_lower=np.asarray(line_lower), line_value_upper=np.asarray(line_upper))
        return dict(certificate=report, cut_rows=cuts, original_network_lift=lift, arrays=arrays)


def prepare(data, expected, pairs, *, generator, pins):
    """Fresh real-scope preparation. Caller must hash-check input bytes first.

    ``pins`` is the receipt from those reads, not a substitute for checking them.
    No source or expected files are read here. A generator module is permitted
    only when its on-disk implementation has the approved immutable SHA.
    """
    import current_scuc.heldout as heldout
    heldout.check_inputs(pins, data=data, expected=expected)
    require(_digest(generator.__file__) == GENERATOR_SHA, 'Frozen generator implementation mismatch')
    with threadpool_limits(limits=1):
        require(all(v.get('num_threads', 1) == 1 for v in threadpool_info()), 'BLAS thread limit ineffective')
        return PreparedOracle(data, expected, pairs, generator, pins, production_scope=True)
