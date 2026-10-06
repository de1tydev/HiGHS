"""Full virtual-row identity and eta caps; frozen subset removal stays unchanged.

Only synthetic fixtures may call this before a separate approved source freeze.
No historical factors, points, cuts or model coefficients are loaded here.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from fractions import Fraction as Q
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import numpy as np

ROOT = PACKAGE_ROOT
CORE_SHA = source_sha('network-projection-lp-core-v1/projection.py')
MODEL_SHA = source_sha('network-projection-lp-core-v1/model.py')
import current_scuc.heldout as heldout
FULL_LODF_SHA = None  # no historical factor hash; current-case check is below


def require(value, message):
    if not value:
        raise ValueError(message)


def deadline_check(deadline):
    if deadline is not None:
        require(math.isfinite(deadline), 'Nonfinite deadline')
        if time.monotonic() >= deadline:
            raise TimeoutError('Full virtual-scope deadline expired')


def exact(value):
    value = float(value)
    require(math.isfinite(value), 'Nonfinite exact operand')
    return Q.from_float(value)


def up(value):
    out = float(value)
    require(math.isfinite(out), 'Bound conversion overflow')
    if exact(out) < value:
        out = math.nextafter(out, math.inf)
    require(math.isfinite(out), 'Bound overflow')
    return out


def rat(value):
    return [str(value.numerator), str(value.denominator)]


def _json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _array_hash(value, dtype='<f8'):
    return hashlib.sha256(np.asarray(value, dtype=dtype).tobytes(order='C')).hexdigest()


def _at(value, t):
    return float(value[t] if isinstance(value, list) else value)


def source_scope_arrays(source, hours):
    require(type(hours) is int and 0 < hours <= int(source['Parameters']['Time horizon (h)']), 'Invalid scope horizon')
    lines = tuple(source['Transmission lines'])
    normal = np.asarray([[_at(v.get('Normal flow limit (MW)', math.inf), t) for v in source['Transmission lines'].values()] for t in range(hours)])
    emergency = np.asarray([[_at(v.get('Emergency flow limit (MW)', math.inf), t) for v in source['Transmission lines'].values()] for t in range(hours)])
    require(not np.any(np.isnan(normal) | np.isnan(emergency)) and np.all(normal >= 0) and np.all(emergency >= 0), 'Invalid full-scope ratings')
    rated = tuple(int(i) for i in np.flatnonzero(np.any(np.isfinite(normal) | np.isfinite(emergency), axis=0)))
    outages = []
    for contingency in source.get('Contingencies', {}).values():
        affected = contingency.get('Affected lines', [])
        require(len(affected) == 1 and affected[0] in lines and not contingency.get('Affected generators') and not contingency.get('Affected units'), 'Only listed single-line outages supported')
        outages.append(lines.index(affected[0]))
    require(len(outages) == len(set(outages)), 'Duplicate source outage')
    return lines, rated, tuple(outages), normal, emergency


def coverage_records(hours, rated, outages, normal, emergency):
    outage_set = set(outages)
    records = []
    for t in range(hours):
        nnormal = sum(math.isfinite(normal[t, l]) for l in rated)
        emergency_lines = [l for l in rated if math.isfinite(emergency[t, l])]
        pairs = sum(len(outages) - (l in outage_set) for l in emergency_lines)
        records.append(dict(hour=t, normal_monitored_lines=nnormal,
            emergency_monitored_lines=len(emergency_lines), listed_outages=len(outages),
            unsigned_security_pairs=pairs, signed_normal_rows=2*nnormal, signed_security_rows=2*pairs,
            conceptual_signed_rows=2*(nnormal+pairs), self_excluded_pairs=sum(l in outage_set for l in emergency_lines)))
    return records


def build_full_scope(source, expected, hours, stored_lodf, subset_scope, *, pins=None,
                     production_scope=False, deadline=None):
    deadline_check(deadline)
    lines, rated, outages, normal, emergency = source_scope_arrays(source, hours)
    lodf = np.asarray(stored_lodf)
    require(lodf.shape == (len(lines), len(lines)) and lodf.dtype == np.float64 and np.all(np.isfinite(lodf)), 'Invalid full LODF bits')
    lodf_hash = _array_hash(lodf)
    if production_scope:
        heldout.check_lodf(lodf_hash)
    records = coverage_records(hours, rated, outages, normal, emergency)
    counts = dict(hours=hours, buses=len(source['Buses']), generators=len(source['Generators']), lines=len(lines),
        finite_rated_lines=len(rated), distinct_listed_single_line_outages=len(outages),
        rated_outage_intersection=len(set(rated).intersection(outages)),
        allowed_pairs_per_hour=len(rated)*len(outages)-len(set(rated).intersection(outages)),
        unsigned_security_pair_hours=sum(r['unsigned_security_pairs'] for r in records),
        signed_normal_rows=sum(r['signed_normal_rows'] for r in records),
        signed_security_rows=sum(r['signed_security_rows'] for r in records))
    counts['signed_soft_rows'] = counts['signed_normal_rows'] + counts['signed_security_rows']
    counts['virtual_full_rows'] = expected['num_row'] - subset_scope['seed_signed_rows'] + counts['signed_security_rows']
    if production_scope:
        heldout.check_counts(counts)
    # Binding the entire subset matrix plus explicit retained membership binds
    # every retained coefficient, sense, bound and objective without recoding it.
    array_fields = ('col_lower', 'col_upper', 'col_cost', 'row_lower', 'row_upper', 'integrality', 'a_start', 'a_index', 'a_value')
    integer_fields = ('integrality', 'a_start', 'a_index')
    subset_hashes = {k: _array_hash(expected[k], '<i8' if k in integer_fields else '<f8') for k in array_fields if k in expected}
    for k in ('col_names', 'row_names'):
        if k in expected:
            subset_hashes[k] = _json_hash(list(expected[k]))
    retained = [i for i, name in enumerate(expected['col_names']) if not name.startswith(('theta_', 'f_', 'over_'))]
    first_network = expected['num_row']-hours*(len(lines)+len(source['Buses']))-subset_scope['normal_signed_rows']-subset_scope['seed_signed_rows']
    if production_scope: require(first_network >= 0, 'Invalid subset network suffix size')
    descriptor = dict(schema='network-projection-full-virtual-scope-v1', production_scope=bool(production_scope),
        pins=dict(pins or {}), source_object_sha256=_json_hash(source), counts=counts,
        ordered_bus_ids=list(source['Buses']), ordered_line_ids=list(lines), ordered_generator_ids=list(source['Generators']),
        ordered_monitored_indices=list(rated), ordered_outage_indices=list(outages),
        ordered_monitored_ids=[lines[l] for l in rated], ordered_outage_ids=[lines[k] for k in outages],
        normal_limit_binary64_sha256=_array_hash(normal), emergency_limit_binary64_sha256=_array_hash(emergency),
        normal_finite_mask_sha256=_array_hash(np.isfinite(normal), 'u1'),
        emergency_finite_mask_sha256=_array_hash(np.isfinite(emergency), 'u1'),
        lodf_binary64_C_sha256=lodf_hash, subset_mapping_scope=dict(subset_scope),
        subset_mapping_matrix_hashes=subset_hashes,
        subset_mapping_scalars={k: expected[k] for k in ('num_col', 'num_row', 'num_nz', 'sense', 'offset')},
        retained_original_columns_sha256=_array_hash(retained, '<i8'),
        retained_nonnetwork_row_prefix_end=first_network if first_network >= 0 else None,
        retained_row_binding='subset expected matrix hashes plus exact unchanged core network suffix removal',
        coverage_by_hour=records, coverage_rule='each hour, finite normal lines; finite emergency lines x every listed outage, excluding self; both signs',
        zero_lodf_rule='retain pair identity and signed row multiplicity; omit zero sparse coefficient only',
        coefficient_rule='literal binary64 f_l + stored d_lk*f_k; no cutoff',
        tie_rule='normal first, then original listed outage order',
        shared_slack_rule='one nonnegative over_l,t shared across normal, both signs and every outage',
        objective_rule='unchanged subset costs/offset; 5000 times shared overload MW',
        domain='original_base_dc_plus_full_literal_virtual_rows',
        lower_domain='declared_literal_lodf_row_model', all_continuous=True,
        physical_dc_lower_bound_certified=False, full_mps_readback_claimed=False)
    if production_scope:
        heldout.check_full_descriptor(descriptor)
    descriptor.update(coverage_rule_complete=True, **{k: counts[k] for k in ('signed_normal_rows', 'signed_security_rows', 'unsigned_security_pair_hours')})
    descriptor['identity_sha256'] = _json_hash(descriptor)
    descriptor['full_scope_identity_sha256'] = descriptor['identity_sha256']
    deadline_check(deadline)
    return descriptor


def verify_full_scope(scope):
    require(isinstance(scope, dict) and isinstance(scope.get('identity_sha256'), str), 'Missing full-scope identity')
    require(scope['identity_sha256'] == scope.get('full_scope_identity_sha256'), 'Full-scope identity alias mismatch')
    require(scope['identity_sha256'] == _json_hash({k: v for k, v in scope.items() if k not in ('identity_sha256', 'full_scope_identity_sha256')}), 'Full-scope descriptor identity mismatch')


def full_eta_caps(source, hours, stored_lodf, *, deadline=None):
    """O(rated*outages + hours*rated) exact work, never pair-hour Fractions."""
    deadline_check(deadline)
    lines, rated, outages, normal, emergency = source_scope_arrays(source, hours)
    lodf = np.asarray(stored_lodf, dtype=np.float64)
    require(lodf.shape == (len(lines), len(lines)) and np.all(np.isfinite(lodf)), 'Invalid full eta LODF')
    # Max over binary64 magnitudes is an exact selection, not an arithmetic reduction.
    ds, witnesses, eligible = {}, {}, {}
    for l in rated:
        deadline_check(deadline)
        ks = np.asarray([k for k in outages if k != l], dtype=np.int32)
        eligible[l] = bool(len(ks))
        if len(ks):
            values = np.abs(lodf[l, ks]); j = int(np.argmax(values))
            D = float(values[j]); require(np.all(values <= D), 'Full eta maxabs dominance failed')
            ds[l], witnesses[l] = exact(D), int(ks[j])
        else:
            ds[l], witnesses[l] = Q(0), None
    pmax = [exact(v['Production cost curve (MW)'][-1]) for v in source['Generators'].values()]
    require(all(v >= 0 for v in pmax), 'Negative production bound')
    ptotal = sum(pmax, Q(0)); records, bounds = [], []
    for t in range(hours):
        deadline_check(deadline)
        loads = [exact(_at(v['Load (MW)'], t)) for v in source['Buses'].values()]
        require(all(v >= 0 for v in loads), 'Negative stored load')
        F = min(ptotal, sum(loads, Q(0))); total = Q(0); line_hash = hashlib.sha256()
        for l in rated:
            terms = [Q(0)]
            if math.isfinite(normal[t, l]): terms.append(F-exact(normal[t, l]))
            if eligible[l] and math.isfinite(emergency[t, l]): terms.append((1+ds[l])*F-exact(emergency[t, l]))
            maximum = max(terms); total += maximum
            line_hash.update(f'{l}:{maximum.numerator}/{maximum.denominator}\n'.encode())
        bound = up(total); require(exact(bound) >= total, 'Full eta upper rounding failure')
        bounds.append(bound)
        records.append(dict(hour=t, source_F_exact=rat(F), Ueta_exact=rat(total), eta_upper_binary64=bound,
                            line_Emax_sha256=line_hash.hexdigest()))
    proof = dict(formula='F=min(sum Pmax,sum stored loads); D_l=max_listed_k_ne_l abs(d_lk); U=sum_l max(0,F-N_l,(1+D_l)*F-E_l), omitting absent terms; eta<=up(U)',
        exact_maxabs_selection=True, exact_cap_arithmetic=True, all_maxabs_coefficients_checked=True,
        maximum_absolute_lodf=[dict(line=l, D_exact=rat(ds[l]), witness_outage=witnesses[l], has_eligible_outage=eligible[l]) for l in rated],
        records=records, bound_rule='canonical shared overflow only; arbitrary excess original slack need not satisfy this cap')
    deadline_check(deadline)
    return np.asarray(bounds), proof


def _core():
    core_dir = ROOT/'science'
    for name, pin in (('projection.py', CORE_SHA), ('model.py', MODEL_SHA)):
        require(hashlib.sha256((core_dir/name).read_bytes()).hexdigest() == pin, 'Local core identity changed ' + name)
    return load_module('projection', core_dir/'projection.py')


def transform_expected(expected, source, hours, exact_pairs, stored_lodf, *, full_scope, deadline=None):
    """Validate/remove only subset rows; replace only eta upper bounds."""
    deadline_check(deadline); verify_full_scope(full_scope)
    core = _core()
    out, metadata = core.transform_expected(expected, source, hours, exact_pairs, stored_lodf)
    deadline_check(deadline)
    rebuilt = build_full_scope(source, expected, hours, stored_lodf, full_scope['subset_mapping_scope'],
        pins=full_scope['pins'], production_scope=full_scope['production_scope'], deadline=deadline)
    require(rebuilt == full_scope, 'Projection/full virtual-scope mismatch')
    bounds, proof = full_eta_caps(source, hours, stored_lodf, deadline=deadline)
    eta = metadata['eta_columns']; previous = out['col_upper'].copy()
    require(np.all(bounds >= previous[eta]), 'Full eta caps must dominate subset caps')
    subset_projected_hashes = dict(metadata['projected_hashes'])
    out['col_upper'] = previous.copy(); out['col_upper'][eta] = bounds
    mask = np.ones(out['num_col'], dtype=bool); mask[eta] = False
    require(np.array_equal(out['col_upper'][mask].view(np.uint64), previous[mask].view(np.uint64)), 'Noneta bounds changed')
    full_hashes = core.model_hashes(out)
    require(all(full_hashes[k] == v for k, v in subset_projected_hashes.items() if k != 'col_upper'), 'Noneta projected fields changed')
    metadata.update(schema='network-projection-full-lp-adapter-v1', full_scope=full_scope,
        full_scope_identity_sha256=full_scope['identity_sha256'], subset_projected_hashes=subset_projected_hashes,
        subset_eta_upper_bounds=metadata['eta_upper_bounds'], subset_eta_bound_records=metadata['eta_bound_records'],
        eta_upper_bounds=bounds, eta_bound_records=proof['records'], full_eta_proof=proof,
        projected_hashes=full_hashes, network_objective_ceiling_upper=up(5000*sum((exact(v) for v in bounds), Q(0))),
        eta_bound_formula=proof['formula'], projection_scope='original_base_dc_plus_full_literal_virtual_rows',
        subset_mapping_readback_only=True, full_mps_readback_claimed=False)
    deadline_check(deadline)
    return out, metadata


def restore_retained(projected_x, metadata):
    return _core().restore_retained(projected_x, metadata)
