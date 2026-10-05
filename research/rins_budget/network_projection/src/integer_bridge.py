"""Source-derived restoration and original-matrix binary checks, extracted from v2.

This module does not solve a MIP or certify a physical-DC lower bound.
"""
import hashlib
import json
import math
import numpy as np
from types import SimpleNamespace
import model
import qa
INTEGRAL_TOLERANCE = 1e-6
PRIMAL_TOLERANCE = 1e-5

def helpers():
    return SimpleNamespace(model=model, qa=qa)

def require(value, message):
    if not value:
        raise ValueError(message)


def json_value(value):
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        require(not math.isnan(value), 'NaN artifact value')
        return '+inf' if value > 0 else '-inf'
    return value


def object_hash(value):
    return hashlib.sha256(json.dumps(json_value(value), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source_binary_authority(source, hours):
    """Mandatory source-derived authority, never inferred from original flags."""
    require(type(hours) is int and 0 < hours <= source['Parameters']['Time horizon (h)'], 'Invalid source hours')
    generators = list(source['Generators'])
    require(generators and all(isinstance(g, str) and g for g in generators), 'Invalid source generators')
    names = [f'{kind}_{generator}_{hour}' for generator in generators for hour in range(hours) for kind in ('u', 'y', 'z')]
    require(len(names) == len(set(names)), 'Duplicate source binary name')
    authority = dict(schema='source-u-y-z-authority-v1', hours=hours, ordered_generator_ids=generators,
                     source_object_sha256=object_hash(source), names=names, count=len(names))
    authority['identity_sha256'] = object_hash(authority)
    return authority


def _indices(raw, size, label):
    values = np.asarray(raw)
    require(values.ndim == 1 and values.dtype.kind in 'iu' and np.all(values >= 0) and np.all(values < size), 'Invalid ' + label)
    require(len(set(values.tolist())) == len(values), 'Duplicate ' + label)
    return values.astype(np.int32)


def _same(a, b, label):
    aa, bb = np.asarray(a), np.asarray(b)
    require(aa.shape == bb.shape and aa.dtype == bb.dtype and aa.tobytes() == bb.tobytes(), 'Changed ' + label)


def restore_integrality(lp_expected, metadata, original_expected):
    """Restore mapped original types; validate independent source and all fields.

    metadata['source_binary_authority'] must come from the actual source object.
    The full-scope descriptor remains unchanged and explicitly continuous.
    """
    model = helpers().model
    lp, original = model.validate_model(lp_expected), model.validate_model(original_expected)
    require(lp['sense'] == original['sense'] == 1 and lp['offset'] == original['offset'] == 0., 'Only minimization with zero offset is supported')
    require(not np.any(lp['integrality']), 'Input must be the continuous projected master')
    require(model.model_hashes(original) == metadata['original_hashes'], 'Original model identity changed')
    require((original['num_col'], original['num_row'], lp['num_col']) == (metadata['original_num_col'], metadata['original_num_row'], metadata['projected_num_col']), 'Mapped dimensions changed')
    retained = _indices(metadata['retained_original_columns'], original['num_col'], 'retained map')
    removed = _indices(metadata['removed_columns'], original['num_col'], 'removed map')
    want_removed = np.asarray([j for j, name in enumerate(original['col_names']) if name.startswith(('theta_', 'f_', 'over_'))], dtype=np.int32)
    _same(removed, want_removed, 'removed network-family map')
    removed_set = set(removed.tolist())
    want_retained = np.asarray([j for j in range(original['num_col']) if j not in removed_set], dtype=np.int32)
    _same(retained, want_retained, 'retained map')
    require(np.all(original['integrality'][removed] == 0), 'Removed network column was not continuous')
    inverse = np.full(original['num_col'], -1, dtype=np.int32)
    inverse[retained] = np.arange(len(retained), dtype=np.int32)
    supplied_inverse = np.asarray(metadata['original_to_projected'])
    require(supplied_inverse.dtype.kind in 'iu' and np.all(supplied_inverse >= -1) and np.all(supplied_inverse < lp['num_col']), 'Invalid inverse retained map')
    _same(supplied_inverse.astype(np.int32), inverse, 'inverse retained map')
    require(model.digest(retained) == metadata['retained_original_columns_sha256'] and model.digest(inverse) == metadata['original_to_projected_sha256'], 'Retained-map digest changed')
    nret, hours = len(retained), metadata['hours']
    require(lp['num_col'] == nret + hours + 2, 'Unexpected projected auxiliaries')
    require(lp['col_names'] == [original['col_names'][j] for j in retained] + [f'eta_MW_{t}' for t in range(hours)] + ['aggregate_one_plus', 'aggregate_one_minus'], 'Projected column names/order changed')
    _same(_indices(metadata['eta_columns'], lp['num_col'], 'eta map'), np.arange(nret, nret + hours, dtype=np.int32), 'eta map')
    _same(_indices(metadata['balance_columns'], lp['num_col'], 'balance map'), np.arange(nret + hours, lp['num_col'], dtype=np.int32), 'balance map')
    for field in ('col_lower', 'col_upper', 'col_cost'):
        _same(lp[field][:nret], original[field][retained], 'retained ' + field)
    first, end = metadata['removed_row_range']
    require(type(first) is int and type(end) is int and 0 <= first <= end == original['num_row'], 'Invalid original row range')
    require(lp['num_row'] >= first + hours and lp['row_names'][:first] == original['row_names'][:first], 'Retained row names changed')
    for field in ('row_lower', 'row_upper'):
        _same(lp[field][:first], original[field][:first], 'retained ' + field)
    a, b = model.matrix(lp)[:first, :nret].tocsc(), model.matrix(original)[:first, retained].tocsc()
    for field in ('indptr', 'indices', 'data'):
        _same(getattr(a, field), getattr(b, field), 'retained matrix ' + field)
    # Check the full continuous base, including balance encoding and eta caps,
    # while allowing only appended cut rows from this fresh arm.
    base = dict(lp)
    matrix = model.matrix(lp)[:first + hours].tocsc()
    base.update(num_row=first + hours, num_nz=int(matrix.nnz), a_start=matrix.indptr, a_index=matrix.indices, a_value=matrix.data,
                row_names=lp['row_names'][:first + hours], row_lower=lp['row_lower'][:first + hours], row_upper=lp['row_upper'][:first + hours])
    require(model.model_hashes(base) == metadata['projected_hashes'], 'Continuous projected base identity changed')
    scope = metadata['full_scope']
    scope_id = scope['identity_sha256']
    require(scope_id == scope['full_scope_identity_sha256'] == metadata['full_scope_identity_sha256'] and scope_id == object_hash({k: v for k, v in scope.items() if k not in ('identity_sha256', 'full_scope_identity_sha256')}), 'Full oracle scope identity changed')
    authority = metadata['source_binary_authority']
    require(authority['identity_sha256'] == object_hash({k: v for k, v in authority.items() if k != 'identity_sha256'}), 'Source binary authority identity changed')
    names = [f'{kind}_{generator}_{hour}' for generator in scope['ordered_generator_ids'] for hour in range(hours) for kind in ('u', 'y', 'z')]
    require(authority['source_object_sha256'] == scope['source_object_sha256'] and authority['ordered_generator_ids'] == scope['ordered_generator_ids'] and authority['hours'] == hours and authority['names'] == names and authority['count'] == len(names), 'Source binary authority does not match full source scope')
    require(len(names) == len(set(names)) and len(names) > 0, 'Invalid source binary inventory')
    original_names = {name: j for j, name in enumerate(original['col_names'])}
    require({original['col_names'][j] for j in np.flatnonzero(original['integrality'])} == set(names), 'Original binary set differs from independent source authority')
    inventory = []
    for name in names:
        j = original_names[name]
        lo, hi = float(original['col_lower'][j]), float(original['col_upper'][j])
        require((lo, hi) in ((0., 1.), (0., 0.), (1., 1.)) and inverse[j] >= 0, 'Unsupported/lost source binary ' + name)
        inventory.append(dict(name=name, original_column=j, projected_column=int(inverse[j]), integrality=1, lower=lo, upper=hi))
    if scope.get('production_scope'):
        require(hours == 36 and len(scope['ordered_generator_ids']) == 260 and len(inventory) == 28080, 'Approved June binary scope changed')
    restored = dict(lp)
    restored['integrality'] = np.concatenate((original['integrality'][retained], np.zeros(hours + 2, dtype=np.int32)))
    restored_hashes, lp_hashes = model.model_hashes(restored), model.model_hashes(lp)
    for field in model.SCALAR_FIELDS + model.ARRAY_FIELDS + ('col_names', 'row_names'):
        if field != 'integrality':
            require(restored_hashes[field] == lp_hashes[field], 'Restoration changed non-type field ' + field)
    require(int(np.count_nonzero(restored['integrality'])) == len(inventory) and np.all(restored['integrality'][nret:] == 0), 'Incomplete restored binary inventory')
    target = dict(schema='integer-network-projection-target-v1', network_oracle_identity_sha256=scope_id,
        source_object_sha256=authority['source_object_sha256'], source_binary_authority_sha256=authority['identity_sha256'],
        original_model_hashes=model.model_hashes(original), retained_original_columns_sha256=model.digest(retained),
        source_binary_inventory_sha256=object_hash(inventory), binary_count=len(inventory),
        lower_domain='original_integer_full_literal_lodf_model', physical_dc_lower_bound_certified=False)
    identity = dict(target, integer_target=target, integer_target_identity_sha256=object_hash(target), master_hashes=restored_hashes,
                    continuous_input_hashes=lp_hashes, retained_numeric_fields_unchanged=True,
                    removed_columns_continuous=True, auxiliaries_continuous=True)
    return dict(expected=restored, identity=identity, source_binary_inventory=inventory)


def _check_values(expected, values):
    h = helpers()
    e = h.model.validate_model(expected)
    require(e['sense'] == 1 and e['offset'] == 0., 'Point scope requires minimization and zero offset')
    require(set(values) == set(e['col_names']), 'Point column-name mismatch')
    x = np.asarray([values[name] for name in e['col_names']], dtype=np.float64)
    require(np.all(np.isfinite(x)), 'Nonfinite point')
    binaries = np.flatnonzero(e['integrality'])
    require(len(binaries) > 0, 'Integer point check requires restored binary declarations')
    require(all((e['col_lower'][j], e['col_upper'][j]) in ((0., 1.), (0., 0.), (1., 1.)) for j in binaries), 'Nonbinary integer domain')
    primal = h.qa.check_primal(e, x, tolerance=PRIMAL_TOLERANCE)
    failures = list(primal['failures'])
    residual = np.abs(x[binaries] - np.rint(x[binaries]))
    maximum = float(np.max(residual))
    if maximum > INTEGRAL_TOLERANCE:
        failures.append('independent binary integrality infeasibility')
    activities = primal.pop('activities', None)
    report = dict(passed=not failures, failures=failures, x=x, primal=primal,
        linear_objective=primal.get('objective_recomputed'), maximum_integrality_residual=maximum,
        binary_count=len(binaries), integrality_tolerance=INTEGRAL_TOLERANCE,
        primal_tolerance=PRIMAL_TOLERANCE, integrality_checked=True, point_rounded=False)
    return report, activities


def check_integer_values(expected, values):
    """Original-lift matrix/type QA, without claiming native status or rows."""
    report, _ = _check_values(expected, values)
    return report

