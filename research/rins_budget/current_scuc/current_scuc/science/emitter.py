"""Solver-free adaptive per-line affine emission and exact debit algebra.

No preparation, factorization, optimization, native API or historical-data load
occurs here. Geometry and referenced potentials must be supplied by the caller.
The frozen v2 residual/drop certificate is reused, never divided among lines.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha

from fractions import Fraction as Q
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import MappingProxyType
import numpy as np

ROOT = PACKAGE_ROOT
V2_SHA = source_sha('network-value-oracle-v2/oracle.py')
PRICE = 5000
HOURS = 36
BALANCE_NNZ = 31788
NNZ_CAP = 1048576
ROW_NNZ = 881
MAX_BATCHES = 4
MAX_EVALUATIONS = 5
ACTIVE_CAP = (NNZ_CAP - BALANCE_NNZ) // (MAX_BATCHES * HOURS * ROW_NNZ)
SLOT_DOLLARS = Q(100, HOURS * ACTIVE_CAP)
MAX_ADJOINTS = MAX_EVALUATIONS * HOURS * ACTIVE_CAP
MAX_PI_BYTES = 15598080
MAX_CACHE_METADATA_BYTES = 1048576


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load_pinned(name, relative, digest):
    path = ROOT / relative
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'Local dependency changed: ' + relative)
    return load_module(name, path)


v2 = load_pinned('_adaptive_v2_math', 'science/value_oracle.py', V2_SHA)
exact, up, rat = v2.exact, v2.up, v2.rat


def rational(value):
    """Fractions stay exact; binary64 values are interpreted as stored bits."""
    return value if isinstance(value, Q) else exact(value)


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def selected_terms(selected, *, line, rated, outages, lodf, normal, emergency):
    """One monitored-line budget, including signed and weighted supports."""
    m = len(normal)
    require(type(line) is int and line in rated, 'Unmonitored line')
    require(len(emergency) == m and np.asarray(lodf).shape == (m, m), 'Coefficient dimensions')
    c = [Q(0)] * m
    lh = Q(0)
    budget = Q(0)
    for row in selected:
        require(row['monitored'] == line, 'Mixed monitored-line support')
        weight = rational(row['multiplier'])
        require(weight >= 0, 'Negative multiplier')
        budget += weight
        sign = row['sign']
        require(type(sign) is int and sign in (-1, 1), 'Invalid selected sign')
        kind, k = row['kind'], row['outage']
        require(kind in ('normal', 'contingency'), 'Invalid selected kind')
        if kind == 'normal':
            require(k == -1, 'Normal row has outage')
            limit = normal[line]
        else:
            require(type(k) is int and k in outages and k != line, 'Invalid selected outage')
            limit = emergency[line]
            c[k] += weight * sign * exact(lodf[line, k])
        require(math.isfinite(float(limit)) and limit >= 0, 'Selected absent/invalid rating')
        c[line] += weight * sign
        lh += weight * exact(limit)
    require(budget <= 1, 'Shared monitored-line multiplier budget exceeded')
    return c, lh


def positive_lines(hour_supports, rated):
    """Validate complete support budgets before returning the whole union."""
    found = set()
    for selected in hour_supports:
        budgets = {}
        for row in selected:
            l = row['monitored']
            require(type(l) is int and l in rated, 'Support outside monitored scope')
            w = rational(row['multiplier'])
            require(w >= 0, 'Negative multiplier')
            budgets[l] = budgets.get(l, Q(0)) + w
            if w > 0:
                found.add(l)
        require(all(w <= 1 for w in budgets.values()), 'Shared monitored-line multiplier budget exceeded')
    return tuple(sorted(found))


class Activation:
    """Small append-only identity ledger; no solver/controller operations."""
    def __init__(self, nret, hours, rated, source_identity, scope_identity):
        require(type(nret) is int and nret > 0 and type(hours) is int and 0 < hours <= HOURS, 'Invalid map dimensions')
        require(len(set(rated)) == len(rated) and tuple(sorted(rated)) == tuple(rated), 'Source monitored order')
        self.nret, self.hours, self.rated = nret, hours, tuple(rated)
        self.source_identity, self.scope_identity = source_identity, scope_identity
        self.active = ()
        self.evaluations = self.admitted = self.cut_nnz = 0

    @property
    def fixed(self):
        return (self.nret, self.nret + 1)

    @property
    def columns(self):
        return {(l, t): self.nret + 2 + b * self.hours + t
                for b, l in enumerate(self.active) for t in range(self.hours)}

    @property
    def inverse(self):
        return {j: pair for pair, j in self.columns.items()}

    @property
    def num_col(self):
        return self.nret + 2 + len(self.active) * self.hours

    @property
    def map_hash(self):
        return identity(dict(source=self.source_identity, scope=self.scope_identity,
                             retained=self.nret, hours=self.hours, fixed=self.fixed,
                             activation=self.active, columns=[[l, t, j] for (l, t), j in self.columns.items()]))

    def preflight(self, hour_supports, *, admit=True):
        require(len(hour_supports) == self.hours, 'Missing hour supports')
        require(self.evaluations < MAX_EVALUATIONS, 'Fifth evaluation already consumed')
        require(not admit or self.admitted < MAX_BATCHES, 'Four admitted batches already consumed')
        new = tuple(l for l in positive_lines(hour_supports, self.rated) if l not in self.active)
        proposed = self.active + new
        require(len(proposed) <= ACTIVE_CAP, 'Ninth line: atomic stop before emission')
        # The token binds the exact support metadata and prior map version.
        serial = [[[r['monitored'], r['kind'], r['outage'], r['sign'], rat(rational(r['multiplier']))]
                   for r in selected] for selected in hour_supports]
        return MappingProxyType(dict(before=self.map_hash, evaluations=self.evaluations, admitted=self.admitted,
                    new=new, active=proposed, admit=bool(admit), support_hash=identity(serial),
                    positive_slots=tuple((l, t) for t, selected in enumerate(hour_supports)
                                         for l in positive_lines([selected], self.rated))))

    def commit(self, token, *, actual_cut_nnz=0, balance_nnz=BALANCE_NNZ):
        require(isinstance(token, MappingProxyType), 'Mutable/unissued activation token')
        require(token['before'] == self.map_hash and token['evaluations'] == self.evaluations
                and token['admitted'] == self.admitted, 'Stale activation preflight')
        require(type(actual_cut_nnz) is int and actual_cut_nnz >= 0, 'Invalid cut count')
        require(tuple(token['active']) == self.active + tuple(token['new'])
                and tuple(sorted(set(token['new']))) == tuple(token['new'])
                and not set(token['new']).intersection(self.active)
                and set(token['new']).issubset(self.rated)
                and len(token['active']) <= ACTIVE_CAP, 'Malformed activation token')
        require(self.evaluations < MAX_EVALUATIONS and (not token['admit'] or self.admitted < MAX_BATCHES), 'Evaluation/admission limit')
        proposed_nnz = self.cut_nnz + (actual_cut_nnz if token['admit'] else 0)
        require(balance_nnz + proposed_nnz <= NNZ_CAP, 'Balance-plus-cut nnz guard')
        require(actual_cut_nnz <= self.hours * len(token['active']) * ROW_NNZ, 'Per-evaluation cut nnz guard')
        # Terminal evaluations are cap checked but install neither columns nor rows.
        if token['admit']:
            self.active = tuple(token['active'])
            self.admitted += 1
            self.cut_nnz = proposed_nnz
        self.evaluations += 1


def emit_line(prepared, hour, line, selected, pi, original_x, qstar):
    """Emit one affine lower support, with original-column coordinates.

    ``prepared`` uses existing PreparedOracle geometry/maps. This function never
    solves for pi. Fixed-zero shedding omission is certified at this raw anchor.
    """
    require(0 <= hour < prepared.hours, 'Invalid hour')
    c, lh = selected_terms(selected, line=line, rated=prepared.rated, outages=prepared.outages,
                          lodf=prepared.lodf, normal=prepared.normal[hour], emergency=prepared.emergency[hour])
    require(len(qstar) == len(prepared.loads[hour]), 'Query bus dimensions')
    qstar = list(map(rational, qstar))
    Fcert = v2.certificate_bound(prepared.source_F[hour], qstar)
    cert = v2.cut_certificate(c, lh, pi, prepared.endpoints, prepared.weights,
                             prepared.path_upper, Fcert, prepared.loads[hour], qstar)
    original_x = np.asarray(original_x)
    require(original_x.dtype == np.float64 and original_x.shape == (len(prepared.names),), 'Original point dimension/type')
    indices, values = [], []
    for j, bus in zip(prepared.p_indices[hour], prepared.generator_bus):
        value = float(cert['pi'][bus])
        if value != 0:
            indices.append(int(j)); values.append(value)
    omission = Q(0)
    for bus, j in enumerate(prepared.shed_indices[hour]):
        value = float(cert['pi'][bus])
        if prepared.fixed_zero_shed[hour, bus]:
            omission += exact(value) * exact(original_x[j])
        elif value != 0:
            indices.append(int(j)); values.append(value)
    require(len(set(indices)) == len(indices), 'Duplicate retained coefficient')
    pairs = sorted(zip(indices, values))
    Cexact = exact(cert['constant']) + max(Q(0), -omission)
    C = up(Cexact)
    row = dict(line=line, hour=hour, original_indices=tuple(j for j, _ in pairs),
               coefficients=tuple(v for _, v in pairs), upper=C, eta_coefficient=-1.)
    at_raw = affine_value(row, original_x)
    require(at_raw == cert['emitted_cut_at_qstar'] - (exact(C) - exact(cert['constant'])) - omission,
            'Raw retained/probe coordinate mismatch')
    require(at_raw <= cert['emitted_cut_at_qstar'], 'Sparse omission correction failed')
    row['certificate'] = dict(F_certificate=Fcert, delta=cert['delta'], residual=tuple(cert['residual']),
        c=tuple(c), lambda_h=lh, pi_load=cert['pi_load'], omitted_fixed_zero_value=omission,
        omission_debit=max(Q(0), -omission), constant_rounding=exact(C)-Cexact,
        v2_constant_rounding=cert['constant_rounding_loss'], zeroed_count=cert['zeroed_count'],
        emitted_at_anchor=at_raw, validity_domain='declared_literal_binary64_LODF_source_domain',
        physical_dc_lower_bound_certified=False)
    return row


def affine_value(row, original_x):
    require(row.get('eta_coefficient', -1.) == -1., 'Unnormalized eta coefficient')
    ids, values = row['original_indices'], row['coefficients']
    require(len(ids) == len(values) and len(set(ids)) == len(ids), 'Affine coordinate mismatch')
    return sum((exact(a) * rational(original_x[j]) for j, a in zip(ids, values)), Q(0)) - row_constant(row)


def normalize_row(indices, coefficients, upper, *, eta_column, retained_to_original, fixed_ones=()):
    """Normalize old/new sparse rows to eta >= a*x-C in one original map."""
    require(len(indices) == len(coefficients) and len(set(indices)) == len(indices), 'Malformed source row')
    require(eta_column not in retained_to_original and eta_column not in fixed_ones, 'Eta/map overlap')
    require(len(set(retained_to_original.values())) == len(retained_to_original), 'Noninjective retained map')
    C = exact(upper)
    out = {}
    seen_eta = False
    for j, value in zip(indices, coefficients):
        a = exact(value)
        if j == eta_column:
            require(a == -1, 'Unnormalized eta coefficient'); seen_eta = True
        elif j in fixed_ones:
            C -= a
        else:
            require(j in retained_to_original, 'Unmapped nonretained coefficient')
            out[retained_to_original[j]] = float(value)
    require(seen_eta, 'Missing eta coefficient')
    # Folding two fixed-one terms may not be representable in binary64. The
    # affine algebra accepts this exact C without rounding via constant_exact.
    return dict(original_indices=tuple(sorted(out)), coefficients=tuple(out[j] for j in sorted(out)),
                upper=up(C), constant_exact=C, eta_coefficient=-1.)


def row_constant(row):
    return row.get('constant_exact', exact(row['upper']))


def _difference(old, lines):
    """Return old a minus summed line a and summed line C minus old C."""
    require(old.get('eta_coefficient', -1.) == -1. and all(r.get('eta_coefficient', -1.) == -1. for r in lines), 'Unnormalized eta')
    d = {}
    for row, sign in [(old, 1)] + [(r, -1) for r in lines]:
        require(len(row['original_indices']) == len(row['coefficients']) and len(set(row['original_indices'])) == len(row['original_indices']), 'Malformed affine coordinates')
        for j, a in zip(row['original_indices'], row['coefficients']):
            d[j] = d.get(j, Q(0)) + sign * exact(a)
    return d, sum((row_constant(r) for r in lines), Q(0)) - row_constant(old)


def dominance_box_debit(old, lines, lower, upper):
    d, constant = _difference(old, lines)
    return max(Q(0), constant + sum((max(a * exact(lower[j]), a * exact(upper[j]))
                                                    for j, a in d.items() if a), Q(0)))


def dominance_point_debit(old, lines, raw_original_x):
    d, constant = _difference(old, lines)
    return max(Q(0), constant + sum((a * exact(raw_original_x[j]) for j, a in d.items()), Q(0)))


def anchor_gap(rows, full_line_upper, raw_original_x, *, rated, hours):
    """Per evaluation: all monitored/hour upper residue, including zero rows."""
    require(set(full_line_upper) == {(l, t) for l in rated for t in range(hours)}, 'Incomplete all-monitored/hour upper coverage')
    require(all(rational(v) >= 0 for v in full_line_upper.values()), 'Negative upper value')
    supports = {}
    for row in rows:
        key = (row['line'], row['hour'])
        require(key not in supports, 'Duplicate line/hour row in anchor')
        supports[key] = affine_value(row, raw_original_x)
        gap = PRICE * (rational(full_line_upper[key]) - supports[key])
        require(0 <= gap <= SLOT_DOLLARS, 'Per-slot support-gap allocation exceeded')
    require(set(supports).issubset(full_line_upper), 'Missing upper coverage')
    total = PRICE * (sum(map(rational, full_line_upper.values()), Q(0)) - sum(supports.values(), Q(0)))
    require(0 <= total <= 100, 'Full all-line/hour anchor gap exceeds $100')
    return total


def bank_value(rows_by_anchor, raw_original_x, hours):
    values = {}
    for rows in rows_by_anchor:
        for row in rows:
            key = (row['line'], row['hour'])
            require(0 <= key[1] < hours, 'Bank hour outside scope')
            values[key] = max(values.get(key, Q(0)), affine_value(row, raw_original_x))
    return PRICE * sum(values.values(), Q(0))


def cross_query_debit(emitted_dollars, ideal_upper_dollars):
    """Exact raw-point bank loss, separate from source-box validity."""
    debit = max(Q(0), rational(ideal_upper_dollars) - rational(emitted_dollars))
    require(debit <= 100, 'Whole-bank raw-query debit exceeds $100')
    return debit


def bank_dominance_debits(old_rows_by_anchor, line_rows_by_anchor, lower, upper,
                          raw_original_x, hours):
    """Sum over hours of max over the same anchors, zero included, in dollars.

    This is algebra on normalized supports, not installation of a large bank.
    The box debit certifies the source domain; point debit only this raw point.
    """
    require(len(old_rows_by_anchor) == len(line_rows_by_anchor), 'Unmatched anchor banks')
    box = [Q(0)] * hours
    point = [Q(0)] * hours
    for olds, news in zip(old_rows_by_anchor, line_rows_by_anchor):
        require(len(olds) == hours and {r['hour'] for r in olds} == set(range(hours)), 'Missing aggregate hour rows')
        for old in olds:
            t = old['hour']
            lines = [r for r in news if r['hour'] == t]
            require(len({r['line'] for r in lines}) == len(lines), 'Duplicate anchor line support')
            box[t] = max(box[t], dominance_box_debit(old, lines, lower, upper))
            point[t] = max(point[t], dominance_point_debit(old, lines, raw_original_x))
    return dict(box_dollars=PRICE * sum(box, Q(0)), raw_point_dollars=PRICE * sum(point, Q(0)),
                box_by_hour_MW=tuple(box), point_by_hour_MW=tuple(point))


def objective_reprice(original_cost, original_x, retained_original_columns,
                      emitted_network_dollars, offset=0.):
    """Absolute reprice; never infer a zero native-eta contribution."""
    require(len(set(retained_original_columns)) == len(retained_original_columns), 'Duplicate retained objective coordinate')
    return (exact(offset) + sum((exact(original_cost[j]) * exact(original_x[j])
                                for j in retained_original_columns), Q(0))
            + rational(emitted_network_dollars))


def emit_batch(state, prepared, hour_supports, original_x, qstars,
               full_line_upper, pi_provider, *, admit=True):
    """Preflight the entire union before the first adjoint/cache allocation.

    ``pi_provider(selected, c)`` supplies a fresh-run potential. The function
    returns an uncommitted batch; append_batch owns the one atomic model edit.
    The caller may commit an uninstalled terminal token with zero matrix edit.
    """
    token = state.preflight(hour_supports, admit=admit)
    require(prepared.hours == state.hours and tuple(prepared.rated) == state.rated,
            'Prepared geometry/activation scope mismatch')
    require(getattr(prepared, 'full_scope_identity_sha256', None) == state.scope_identity,
            'Prepared full-scope identity mismatch')
    source_identity = getattr(prepared, 'source_identity', getattr(prepared, 'pins', {}).get('source_sha256'))
    require(source_identity == state.source_identity, 'Prepared source identity mismatch')
    require(len(qstars) == state.hours, 'Missing query hours')
    require(set(full_line_upper) == {(l, t) for l in state.rated for t in range(state.hours)},
            'Incomplete all-monitored/hour upper coverage')
    work = []
    for t, selected in enumerate(hour_supports):
        for l in sorted({r['monitored'] for r in selected}):
            selected_terms([r for r in selected if r['monitored'] == l], line=l,
                rated=prepared.rated, outages=prepared.outages, lodf=prepared.lodf,
                normal=prepared.normal[t], emergency=prepared.emergency[t])
        for l in positive_lines([selected], state.rated):
            part = [r for r in selected if r['monitored'] == l and rational(r['multiplier']) > 0]
            c, _ = selected_terms(part, line=l, rated=prepared.rated, outages=prepared.outages,
                lodf=prepared.lodf, normal=prepared.normal[t], emergency=prepared.emergency[t])
            work.append((t, l, part, c))
    rows = [emit_line(prepared, t, l, part, pi_provider(part, c), original_x, qstars[t])
            for t, l, part, c in work]
    gap = anchor_gap(rows, full_line_upper, original_x, rated=state.rated, hours=state.hours)
    return dict(token=token, rows=rows, anchor_gap_dollars=gap,
                actual_cut_nnz=sum(len(row['coefficients']) + 1 for row in rows))


class ElementaryAdjoints:
    """Bounded fresh-run cache for the current singleton multiplier-one selector."""
    def __init__(self, *, run_identity, source_identity, scope_identity, topology_identity,
                 coefficient_identity, buses, solve):
        require(all(isinstance(v, str) and v for v in (run_identity, source_identity, scope_identity, topology_identity, coefficient_identity)), 'Missing fresh cache identity')
        require(type(buses) is int and buses >= 2, 'Invalid bus dimension')
        self.context = (run_identity, source_identity, scope_identity, topology_identity, coefficient_identity)
        self.buses, self.solve = buses, solve
        self.cache = {}
        self.geometry_hash = None
        self.requests = self.raw_bytes = self.metadata_bytes = 0

    def get(self, selected, c, endpoints, weights):
        require(len(selected) == 1 and rational(selected[0]['multiplier']) == 1, 'Cache requires singleton multiplier-one support')
        require(self.requests < MAX_ADJOINTS, 'Adjoint request bound exceeded')
        row = selected[0]
        e = np.asarray(endpoints)
        w = np.asarray(weights, dtype='<f8')
        require(e.shape == (len(c), 2) and e.dtype.kind in 'iu' and w.shape == (len(c),)
                and np.all(e >= 0) and np.all(e < self.buses) and np.all(np.isfinite(w))
                and np.all(w > 0), 'Adjoint geometry dimensions/values')
        geometry_hash = identity(dict(endpoints=hashlib.sha256(e.astype('<i8').tobytes()).hexdigest(),
                                      weights=hashlib.sha256(w.tobytes()).hexdigest()))
        require(self.geometry_hash in (None, geometry_hash), 'Fresh-run geometry changed')
        key = identity(dict(context=self.context, row=[row['monitored'], row['kind'], row['outage'], row['sign']],
                            geometry=geometry_hash, c=[rat(rational(v)) for v in c], reference_bus=0, drop=v2.DROP.hex()))
        if key not in self.cache:
            require(len(self.cache) < MAX_ADJOINTS and self.raw_bytes + self.buses * 8 <= MAX_PI_BYTES, 'Adjoint cache raw-byte bound')
            key_bytes = len(key.encode()) + 128
            require(self.metadata_bytes + key_bytes <= MAX_CACHE_METADATA_BYTES, 'Adjoint cache metadata bound')
            rhs = v2.incidence_transpose([exact(w) * rational(cc) for w, cc in zip(weights, c)], endpoints, self.buses)
            pi = np.zeros(self.buses)
            pi[1:] = self.solve(np.asarray([float(v) for v in rhs[1:]]))
            require(np.all(np.isfinite(pi)) and pi[0] == 0, 'Invalid referenced adjoint')
            pi.flags.writeable = False
            self.cache[key] = pi
            self.raw_bytes += pi.nbytes
            self.metadata_bytes += key_bytes
        self.geometry_hash = geometry_hash
        self.requests += 1
        return self.cache[key]
