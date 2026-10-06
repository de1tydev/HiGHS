"""Small integer bridge for the approved full literal-network projection.

No optimization or original model generation. The unchanged canonical writer
supports minimization, zero offset, ordinary binary/continuous columns and
one-sided/equality rows only; unsupported scopes fail before export.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import numpy as np
from current_scuc.diagnostics import accepted_statuses
from current_scuc.options import PROOF_ROLE

ROOT = PACKAGE_ROOT
INTEGRAL_TOLERANCE = 1e-6
PRIMAL_TOLERANCE = 1e-5
PINS = {
    'science/model.py': source_sha('network-projection-lp-core-v1/model.py'),
    'science/qa.py': source_sha('network-projection-lp-core-v1/qa.py'),
    'core/canonical_mps_export/export_v2.py': source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/export_v2.py'),
    'core/canonical_mps_export/readback.py': source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/readback.py'),
    'core/canonical_mps_export/io_announcements.py': source_sha('primal-cache-replay-v4.1/core/canonical_mps_export/io_announcements.py'),
    'core/driver/primal_and_bound.py': source_sha('primal-cache-replay-v4.1/core/driver/primal_and_bound.py'),
    'binding.py': source_sha('primal-cache-replay-v4.1/adapter/binding.py'),
    'contracts.py': source_sha('primal-cache-replay-v4.1/adapter/contracts.py'),
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


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


def _load(relative, aliases=None):
    path = ROOT / relative
    require(sha256(path) == PINS[relative], 'Local bridge dependency changed: ' + relative)
    return load_module('_integer_bridge_' + path.stem, path)


@lru_cache(maxsize=1)
def helpers():
    model = _load('science/model.py')
    qa = _load('science/qa.py', {'model': model})
    exporter = _load('core/canonical_mps_export/export_v2.py')
    readback = _load('core/canonical_mps_export/readback.py', {'export_v2': exporter})
    import current_scuc.heldout as heldout
    binding = heldout.runtime_binding()
    contracts = _load('contracts.py', {'binding': binding})
    primal = _load('core/driver/primal_and_bound.py', {'contracts': contracts})
    return SimpleNamespace(model=model, qa=qa, exporter=exporter, readback=readback, primal=primal)


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
    import current_scuc.adaptive as adaptive
    state = adaptive.validate_current(lp, metadata, original)
    import current_scuc.no_shedding as no_shedding
    subset = no_shedding.validate_retained(lp, metadata, original, model)
    first, end = metadata['removed_row_range']
    require(type(first) is int and type(end) is int and 0 <= first <= end == original['num_row'], 'Invalid original row range')
    require(lp['num_row'] >= first + hours and lp['row_names'][:first] == original['row_names'][:first], 'Retained row names changed')
    for field in ('row_lower', 'row_upper'):
        _same(lp[field][:first], original[field][:first], 'retained ' + field)
    a, b = model.matrix(lp)[:first, :nret].tocsc(), model.matrix(original)[:first, retained].tocsc()
    for field in ('indptr', 'indices', 'data'):
        _same(getattr(a, field), getattr(b, field), 'retained matrix ' + field)
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
        import current_scuc.heldout as heldout
        heldout.check_binary_scope(hours, scope['ordered_generator_ids'], len(inventory))
    restored = dict(lp)
    restored['integrality'] = np.concatenate((original['integrality'][retained], np.zeros(lp['num_col'] - nret, dtype=np.int32)))
    restored_hashes, lp_hashes = model.model_hashes(restored), model.model_hashes(lp)
    for field in model.SCALAR_FIELDS + model.ARRAY_FIELDS + ('col_names', 'row_names'):
        if field != 'integrality':
            require(restored_hashes[field] == lp_hashes[field], 'Restoration changed non-type field ' + field)
    require(int(np.count_nonzero(restored['integrality'])) == len(inventory) and np.all(restored['integrality'][nret:] == 0), 'Incomplete restored binary inventory')
    target = dict(schema='integer-network-projection-target-v1', network_oracle_identity_sha256=scope_id,
        source_object_sha256=authority['source_object_sha256'], source_binary_authority_sha256=authority['identity_sha256'],
        original_model_hashes=model.model_hashes(original), retained_original_columns_sha256=model.digest(retained),
        source_binary_inventory_sha256=object_hash(inventory), binary_count=len(inventory),
        lower_domain=no_shedding.DOMAIN, hard_zero_subset=subset, physical_dc_lower_bound_certified=False)
    identity = dict(target, integer_target=target, integer_target_identity_sha256=object_hash(target), master_hashes=restored_hashes,
                    continuous_input_hashes=lp_hashes, retained_numeric_fields_unchanged_except_checked_subset=True,
                    removed_columns_continuous=True, auxiliaries_continuous=True,
                    adaptive_map_hash=metadata['map_hash'], adaptive_matrix_identity=metadata['matrix_identity'],
                    adaptive_activation=metadata['activation'], adaptive_line_caps=metadata['line_caps'],
                    first_start_family=metadata['first_start_family'])
    return dict(expected=restored, identity=identity, source_binary_inventory=inventory)


def _write_json(path, value):
    from current_scuc.common import bounded_write
    bounded_write(path,json_value(value),fresh=True)


def export_master(master, output_path, library_path):
    """Canonical .17g writer plus exact sixteen-field native readback, no run."""
    h = helpers()
    for relative, digest in PINS.items():
        require(sha256(ROOT / relative) == digest, 'Frozen bridge dependency changed: ' + relative)
    expected = h.model.validate_model(master['expected'])
    require(expected['sense'] == 1 and expected['offset'] == 0., 'Canonical writer requires minimization and zero offset')
    require(h.model.model_hashes(expected) == master['identity']['master_hashes'], 'Master changed after integrality restoration')
    target = master['identity']['integer_target']
    require(object_hash(target) == master['identity']['integer_target_identity_sha256'], 'Integer target identity changed')
    require(object_hash(master['source_binary_inventory']) == target['source_binary_inventory_sha256'], 'Source binary inventory changed')
    require(sha256(library_path) == runtime_sha('library'), 'Readback library is not pinned pristine HiGHS')
    require(not Path(output_path).is_symlink(), 'Symlink master output')
    output = Path(output_path).resolve()
    paths = {key: Path(str(output) + suffix) for key, suffix in dict(model='', expected='.expected.json', rows='.rows.json', readback='.readback.json', log='.readback.log', meta='.meta.json').items()}
    require(all(not path.exists() and not path.is_symlink() for path in paths.values()), 'Export requires fresh nonsymlink outputs')
    senses, rhs = [], []
    for lo, hi in zip(expected['row_lower'], expected['row_upper']):
        if lo == hi and math.isfinite(lo):
            senses.append('E'); rhs.append(float(lo))
        elif lo == -math.inf and math.isfinite(hi):
            senses.append('L'); rhs.append(float(hi))
        elif hi == math.inf and math.isfinite(lo):
            senses.append('G'); rhs.append(float(lo))
        else:
            raise ValueError('Canonical writer does not support ranged or free rows')
    coo = h.model.matrix(expected).tocoo()
    view = SimpleNamespace(names=expected['col_names'], lb=expected['col_lower'], ub=expected['col_upper'], obj=expected['col_cost'],
        binary=[bool(v) for v in expected['integrality']], sense=senses, rhs=rhs,
        ri=coo.row.tolist(), ci=coo.col.tolist(), val=coo.data.tolist())
    canonical = h.model.validate_model(h.exporter.intended_model(view))
    renamed = dict(expected, row_names=[f'R{i}' for i in range(expected['num_row'])])
    require(h.model.compare_models(renamed, canonical)['passed'], 'Canonical view changed numeric fields or column names')
    sidecar = dict(schema='integer-master-row-names-v1', rows=[dict(index=i, native=f'R{i}', original=name) for i, name in enumerate(expected['row_names'])],
                   original_row_names_sha256=h.model.model_hashes(expected)['row_names'], canonical_row_names_sha256=h.model.model_hashes(canonical)['row_names'])
    from current_scuc.common import start_output_phase, storage, native_shape_guard, native_call_guard
    native_shape_guard(canonical)
    budget=storage()
    from current_scuc.writer_bounds import canonical_mps_reservation, verify_written_mps
    import current_scuc.first_start as first_start
    family=master['identity']['first_start_family']
    first_start.validate(canonical,family,h.model,canonical=True)
    writer_receipt=canonical_mps_reservation(view,canonical,first_start_family=family)
    mps_maximum=writer_receipt['reservation_bytes']
    require(mps_maximum<=budget.STATE_LIMIT,'Canonical MPS writer ceiling')
    start_output_phase(output.parent,'master export',[
        budget.WriteBound(paths['model'],mps_maximum,'Pinned canonical writer: exact counted records and finite .17g widths','source-derived record inventory; preserves prior smaller-model reservation'),
        budget.WriteBound(paths['log'],budget.NATIVE_FILE_LIMIT,'readback native log','temporary native-only 64-MiB soft file limit'),
        *[budget.WriteBound(paths[k],budget.STATE_LIMIT,'128-MiB bounded JSON','bounded atomic_json') for k in ('rows','expected','readback','meta')]])
    _write_json(paths['rows'], sidecar)
    _write_json(paths['expected'], canonical)
    meta = h.exporter.write_model(view, output, expected=canonical)
    verify_written_mps(output,writer_receipt)
    meta['writer_reservation']=writer_receipt
    require(output.stat().st_size<=mps_maximum,'Canonical MPS exceeded proven line bound')
    with native_call_guard('master native readback',paths['log']) as log_guard:
        readback = h.readback.verify_expected(canonical, output, library_path, paths['log'])
    readback['native_output_limit']=log_guard
    _write_json(paths['readback'], readback)
    require(readback['passed'] and len(readback['fields']) == 16 and all(v['passed'] for v in readback['fields'].values()), 'Canonical integer master native readback failed: ' + repr(readback['failures']))
    identity = dict(master['identity'], canonical_master_hashes=h.model.model_hashes(canonical),
        model_path=str(output), model_sha256=sha256(output), expected_path=str(paths['expected']), expected_sha256=sha256(paths['expected']),
        api_report_path=str(paths['readback']), api_report_sha256=sha256(paths['readback']),
        row_sidecar_path=str(paths['rows']), row_sidecar_sha256=sha256(paths['rows']),
        source_binary_inventory=master['source_binary_inventory'], api_fidelity_verified=True)
    _write_json(paths['meta'], dict(meta, identity=identity))
    return dict(expected=canonical, identity=identity, row_sidecar=sidecar, readback=readback)


def parse_solution(path, expected, *, role=PROOF_ROLE):
    """Frozen strict primal columns plus complete, unique canonical row fields."""
    text = Path(path).read_text()
    statuses = re.findall(r'^Model status\s*\n([^\n]+)', text, re.M)
    require(len(statuses) == 1 and statuses[0].strip() in accepted_statuses(role), 'Ineligible native solution status')
    parsed = helpers().primal.parse_primal_text(text, expected['col_names'])
    if parsed is None:
        return None
    require(parsed['status'] in accepted_statuses(role), 'Ineligible native solution status')
    section = text.split('# Primal solution values', 1)[1].split('# Dual solution values', 1)[0]
    headers = list(re.finditer(r'^# Rows (\d+)[ \t]*\r?\n', section, re.M))
    require(len(headers) == 1 and int(headers[0][1]) == expected['num_row'], 'Missing/duplicate/wrong-count primal rows')
    rows = {}
    for raw in section[headers[0].end():].splitlines(keepends=True):
        if not raw.strip():
            continue
        require(raw.endswith('\n'), 'Unterminated primal row tail')
        words = raw.split()
        require(len(words) == 2 and words[0] not in rows, 'Malformed/duplicate primal row')
        value = float(words[1])
        require(math.isfinite(value), 'Nonfinite primal row')
        rows[words[0]] = value
    require(set(rows) == set(expected['row_names']), 'Missing/extra current row names')
    return dict(parsed, row_values=rows, solution_path=str(Path(path).resolve()), solution_sha256=sha256(path))


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


def check_integer_point(expected, parsed, *, role=PROOF_ROLE):
    """Complete parsed native matrix QA; never modifies or rounds the point."""
    require(parsed is not None and parsed.get('status') in accepted_statuses(role), 'No eligible parsed point')
    require(set(parsed['row_values']) == set(expected['row_names']), 'Point row-name mismatch')
    report, activities = _check_values(expected, parsed['values'])
    failures = report['failures']
    row_difference = None
    if activities is not None:
        native_rows = np.asarray([parsed['row_values'][name] for name in expected['row_names']], dtype=np.float64)
        require(np.all(np.isfinite(native_rows)), 'Nonfinite native row values')
        row_difference = float(np.max(np.abs(activities - native_rows))) if len(activities) else 0.
        if row_difference > PRIMAL_TOLERANCE:
            failures.append('native/independent row activity mismatch')
    objective = float(parsed['printed_objective'])
    require(math.isfinite(objective), 'Nonfinite printed objective')
    computed = report['linear_objective']
    allowance = max(PRIMAL_TOLERANCE, 1e-10 * max(abs(objective), abs(computed))) if computed is not None else None
    if computed is None or abs(objective - computed) > allowance:
        failures.append('native/independent objective mismatch')
    report.update(passed=not failures, printed_objective=objective, objective_allowance=allowance,
                  native_row_activity_difference=row_difference)
    return report
