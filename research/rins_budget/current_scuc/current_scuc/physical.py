"""Original integer and two independent direct-DC checks of a persisted lift.

This worker never constructs an optimization model, calls HiGHS, or substitutes
literal LODF feasibility for outage physics. The parent owns process/resource
containment and the whole-arm deadline. Imports alone perform no numerical work.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import current_scuc.common as c

TOLERANCE = 1e-5
INTEGER_TOLERANCE = 1e-6
SCHEMA = 'integer-network-projection-physical-v1'
BASE_RESIDUALS = {'reduced_system_MW', 'full_nodal_balance_MW', 'system_balance_MW',
    'reference_angle', 'direct_base_flow_MW', 'phase_angle_flow_MW', 'primal_full_nodal_balance_MW'}
SOURCE_RESIDUALS = {'binary', 'transition', 'exclusive_transition', 'dispatch_bounds',
    'startup_power', 'ramp_up', 'ramp_down', 'dispatch_nonnegative', 'startup_cost_nonnegative',
    'system_balance', 'reference_angle', 'overflow_nonnegative', 'direct_base_flow',
    'phase_angle_flow', 'normal_line_limit', 'emergency_line_limit', 'segment_dispatch', 'shed_bounds'}


class PhysicalGateFailure(ValueError):
    """Carry completed checker evidence even when final physical admission fails."""
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def require_digest(value, label):
    c.require(type(value) is str and len(value) == 64 and all(ch in '0123456789abcdef' for ch in value), 'Invalid ' + label)


def finite_tree(value, label='report'):
    if isinstance(value, dict):
        for key, item in value.items(): finite_tree(item, label + '.' + key)
    elif isinstance(value, (list, tuple)):
        for item in value: finite_tree(item, label)
    elif isinstance(value, float):
        c.require(math.isfinite(value), 'Nonfinite ' + label)


def modules():
    """Import frozen checks only; no solver/native optimizer is imported here."""
    root = c.ROOT
    import current_scuc.heldout as heldout
    heldout.runtime_binding()
    stage = c.module('model_stage', root/'core/driver/model_stage.py')
    checks = c.module('primal_and_bound', root/'core/driver/primal_and_bound.py')
    separator = c.module('fractional_separator', root/'core/driver/fractional_separator.py')
    source_checker = c.module('_integer_frozen_source_checker', root/'core/scuc/check_solution.py')
    model = c.module('model', root/'science/model.py')
    qa = c.module('qa', root/'science/qa.py')
    full = c.module('_full_projection_v1', root/'full_projection.py')
    return stage, checks, separator, source_checker, model, qa, full


def binary_gate(expected, data, hours, values, authority):
    """Independent complete source-name authority, including y/z and fixed u."""
    import numpy as np
    names = [f'{kind}_{generator}_{hour}' for generator in data['Generators']
             for hour in range(hours) for kind in ('u', 'y', 'z')]
    positions = {name: j for j, name in enumerate(expected['col_names'])}
    c.require(len(set(names)) == len(names), 'Duplicate source binary names')
    indices = []
    for name in names:
        c.require(name in positions, 'Missing source binary: ' + name)
        j = positions[name]
        c.require(expected['integrality'][j] == 1 and
            (expected['col_lower'][j], expected['col_upper'][j]) in ((0., 1.), (0., 0.), (1., 1.)),
            'Original binary type/bounds lost: ' + name)
        indices.append(j)
    c.require(set(np.flatnonzero(expected['integrality'])) == set(indices), 'Unexpected original integer declarations')
    # The authority is generated independently by the master bridge. Compare its
    # whole declared object rather than accepting a binary count as authority.
    bridge = c.module('_integer_master', Path(__file__).with_name('master.py'))
    c.require(authority == bridge.source_binary_authority(data, hours), 'Declared source binary authority mismatch')
    binary_values = np.asarray(values)[indices]
    c.require(np.all(np.isfinite(binary_values)), 'Nonfinite original binaries')
    residual = float(np.max(np.abs(binary_values - np.rint(binary_values)), initial=0.))
    c.require(residual <= INTEGER_TOLERANCE, 'Original u/y/z integrality exceeds 1e-6')
    return dict(passed=True, count=len(indices), counts_by_kind={kind: len(names)//3 for kind in ('u', 'y', 'z')},
        tolerance=INTEGER_TOLERANCE, maximum_residual=residual, all_original_types_and_bounds_verified=True,
        fixed_binaries_included=True, rounding_performed=False, authority_sha256=object_hash(authority))


def scope_gate(request, expected, data, scope, full):
    """Bind the unchanged network descriptor to source, matrix, and coverage."""
    import numpy as np
    descriptor = request['full_scope']
    full.verify_full_scope(descriptor)
    c.require(descriptor['source_object_sha256'] == full._json_hash(data), 'Full scope source mismatch')
    c.require(descriptor['physical_dc_lower_bound_certified'] is False and descriptor['all_continuous'] is True,
        'Inherited network descriptor was relabeled')
    lines, rated, outages, normal, emergency = full.source_scope_arrays(data, request['hours'])
    c.require(descriptor['ordered_bus_ids'] == list(data['Buses']) and
        descriptor['ordered_generator_ids'] == list(data['Generators']) and
        descriptor['ordered_line_ids'] == list(lines) and descriptor['ordered_monitored_indices'] == list(rated) and
        descriptor['ordered_outage_indices'] == list(outages) and
        descriptor['ordered_outage_ids'] == scope['outage_line_ids'], 'Full scope ordered source identity mismatch')
    c.require(descriptor['coverage_by_hour'] == full.coverage_records(request['hours'], rated, outages, normal, emergency),
        'Full scope per-hour coverage mismatch')
    for field, array in (('normal_limit_binary64_sha256', normal), ('emergency_limit_binary64_sha256', emergency)):
        c.require(descriptor[field] == full._array_hash(array), 'Full scope rating mismatch')
    for field, array in (('normal_finite_mask_sha256', normal), ('emergency_finite_mask_sha256', emergency)):
        c.require(descriptor[field] == full._array_hash(np.isfinite(array), 'u1'), 'Full scope finite rating mask mismatch')
    for field, digest in descriptor['subset_mapping_matrix_hashes'].items():
        actual = full._json_hash(list(expected[field])) if field in ('col_names', 'row_names') else full._array_hash(
            expected[field], '<i8' if field in ('integrality', 'a_start', 'a_index') else '<f8')
        c.require(actual == digest, 'Full scope original matrix mismatch: ' + field)
    c.require(set(descriptor['subset_mapping_matrix_hashes']) == {
        'col_lower','col_upper','col_cost','row_lower','row_upper','integrality','a_start','a_index','a_value','col_names','row_names'},
        'Incomplete full-scope matrix binding')
    c.require(descriptor['subset_mapping_scalars'] == {k: expected[k] for k in ('num_col','num_row','num_nz','sense','offset')},
        'Full scope original matrix scalar mismatch')
    c.require(descriptor['unsigned_security_pair_hours'] == scope['eligible_pair_hours'] and
        descriptor['signed_security_rows'] == 2 * scope['eligible_pair_hours'], 'Full scope pair-hour mismatch')
    for role in ('source', 'expected', 'mps'):
        c.require(descriptor['pins'][role + '_sha256'] == request[role + '_sha256'], 'Full scope pinned ' + role + ' mismatch')


def write_raw_solution(path, expected, values, activities, objective, checks):
    """17-digit raw primal with every original row activity, then strict readback."""
    import numpy as np
    c.require(values.shape == (expected['num_col'],) and activities.shape == (expected['num_row'],), 'Raw primal shape mismatch')
    c.require(np.all(np.isfinite(values)) and np.all(np.isfinite(activities)) and c.finite(objective), 'Nonfinite raw primal')
    for name in expected['col_names'] + expected['row_names']:
        c.require(name and not any(ch.isspace() for ch in name), 'Unsafe raw solution name')
    maximum=sum(len(name.encode())+33 for name in expected['col_names']+expected['row_names'])+65536
    budget=c.storage()
    witness = Path(path).parent/'direct-witnesses'
    c.start_output_phase(Path(path).parent,'full original raw point and direct witness outputs',[
        budget.WriteBound(path,maximum,'complete original .17g columns and rows with finite values','source-derived fixed serializer bound'),
        *[budget.WriteBound(witness/name,budget.PYTHON_FILE_LIMIT,'single frozen WitnessSink output','prospective512MiB process file limit')
          for name in ('spill.sqlite3','witnesses.jsonl')],
        budget.WriteBound(witness/'violated_pairs.bin',32*1024**2,'frozen packed pair output','WitnessSink MAX_PAIR_BYTES'),
        budget.WriteBound(witness/'FAILED.json',4096,'frozen bounded witness failure evidence','WitnessSink FAILURE_RESERVE_BYTES')])
    with Path(path).open('x') as stream:
        stream.write('Model status\nFeasible\n# Primal solution values\nFeasible\nObjective ' + format(objective, '.17g') + '\n')
        stream.write('# Columns ' + str(expected['num_col']) + '\n')
        for name, value in zip(expected['col_names'], values): stream.write(name + ' ' + format(float(value), '.17g') + '\n')
        stream.write('# Rows ' + str(expected['num_row']) + '\n')
        for name, value in zip(expected['row_names'], activities): stream.write(name + ' ' + format(float(value), '.17g') + '\n')
        stream.write('# Dual solution values\nNone\n')
    c.require(Path(path).stat().st_size<=maximum,'Original solution serialization ceiling')
    parsed = checks.read_primal(path, expected['col_names'])
    stored = np.asarray([parsed['values'][name] for name in expected['col_names']], dtype=np.float64)
    c.require(stored.tobytes() == values.tobytes() and parsed['printed_objective'] == objective, 'Raw retained point bit roundtrip failed')
    # Existing parser deliberately ignores raw rows; independently read and bind
    # this required section, so no fabricated zero-activity row can pass.
    text = Path(path).read_text()
    rows = text.split('# Rows ' + str(expected['num_row']) + '\n', 1)[1].split('# Dual solution values\n', 1)[0].splitlines()
    c.require(len(rows) == expected['num_row'], 'Raw row count mismatch')
    stored_rows = []
    for row, name in zip(rows, expected['row_names']):
        fields = row.split(); c.require(len(fields) == 2 and fields[0] == name, 'Raw row identity mismatch')
        stored_rows.append(float(fields[1]))
    c.require(np.asarray(stored_rows, dtype=np.float64).tobytes() == activities.tobytes(), 'Raw row activity bit roundtrip failed')
    return parsed


def measurement_metrics(data, values, scope, hours):
    """Independent slack quantities and original source penalty costs."""
    def at(value, hour): return float(value[hour] if isinstance(value, list) else value)
    groups = {
        'load_shedding': [(values[f'shed_{name}_{hour}'], at(data['Parameters'].get('Power balance penalty ($/MW)', 1000), hour))
            for name in data['Buses'] for hour in range(hours)],
        'reserve_shortfall': [(values[f'short_{name}_{hour}'], max(0., at(reserve.get('Shortfall penalty ($/MW)', -1), hour)))
            for name, reserve in data.get('Reserves', {}).items() for hour in range(hours)],
        'shared_overflow': [(values[f'over_{scope["lines"][index]}_{hour}'], at(data['Transmission lines'][scope['lines'][index]].get('Flow limit penalty ($/MW)', 5000), hour))
            for index in scope['rated_line_indices'] for hour in range(hours)]}
    result = {name: dict(sum_MWh=math.fsum(v for v, _ in items), positive_sum_MWh=math.fsum(max(0.,v) for v, _ in items), max_MW=max([0., *(v for v, _ in items)]),
        cost=math.fsum(v * penalty for v, penalty in items)) for name, items in groups.items()}
    finite_tree(result)
    return result


def validate_reports(result, request, scope, checks):
    """Fail-closed admission, also used by the persisted result reader."""
    finite_tree(result)
    c.require(result['schema'] == SCHEMA and result['physical_dc_lower_bound_certified'] is False and
        result['optimization_called'] is False, 'Invalid physical report domain')
    identity = result['identity']
    for role in ('source', 'expected', 'mps'):
        key = 'model_sha256' if role == 'mps' else role + '_sha256'
        c.require(identity[key] == request[role + '_sha256'], 'Physical report input mismatch')
    c.require(result['integer_target_identity_sha256'] == request['integer_target_identity_sha256'] and
        result['full_scope_identity_sha256'] == request['full_scope']['identity_sha256'] and
        result['stored_lift_binary64_sha256'] == request['stored_lift_artifact']['readback_values_sha256'], 'Physical point/target identity mismatch')
    binary, matrix, accurate = result['binary_check'], result['matrix_check'], result['accurate_original_primal_check']
    c.require(binary['passed'] is True and binary['count'] == 3 * len(scope['generators']) * request['hours'] and
        binary['tolerance'] == INTEGER_TOLERANCE and 0 <= binary['maximum_residual'] <= INTEGER_TOLERANCE and
        binary['rounding_performed'] is False, 'Invalid all-binary gate')
    c.require(matrix['passed'] is True and matrix['exact_column_names'] is True and matrix['violations_by_category'] == {} and
        matrix['integrality_scope'] == 'original_integer' and matrix['tolerance'] == TOLERANCE and
        matrix['max_violation_by_category']['integrality'] <= INTEGER_TOLERANCE and
        accurate['passed'] is True and accurate['failures'] == [] and accurate['tolerance'] == TOLERANCE,
        'Failed original matrix/accurate row gate')
    c.require(set(matrix['max_violation_by_category']) == {'row','lower_bound','upper_bound','integrality'}, 'Incomplete matrix residual categories')
    for field in ('model_sha256','expected_sha256','source_sha256','solution_sha256','pair_manifest_sha256'):
        c.require(matrix[field] == identity[field], 'Matrix identity mismatch: ' + field)
    for value in matrix['max_violation_by_category'].values(): c.require(0 <= value <= TOLERANCE, 'Failed matrix residual')
    for key in ('row', 'bound'): c.require(0 <= accurate[key]['max'] <= TOLERANCE, 'Failed accurate residual')
    s, source = result['separation'], result['source_check']
    for field in ('source_sha256','source_data_sha256','model_sha256','expected_sha256','solution_sha256','pair_manifest_sha256'):
        c.require(s[field] == identity[field], 'Direct separator identity mismatch: ' + field)
    c.require(s['matrix_check'] == matrix and s['hours'] == request['hours'] and s['tolerance'] == TOLERANCE and
        s['integrality_scope'] == 'original_integer' and s['scope_sha256'] == scope['descriptor_sha256'] and
        s['checked_outage_ids'] == scope['checked_outage_ids'] and s['outage_line_ids'] == scope['outage_line_ids'] and
        s['outage_indices'] == scope['outage_indices'] and s['outages_checked'] == len(scope['checked_outage_ids']) and
        s['checked_pair_hours'] == scope['eligible_pair_hours'] and s['eligible_pair_count'] == scope['eligible_pair_count'] and
        s['factorizations_per_call'] == len(scope['checked_outage_ids']) + 1, 'Incomplete direct separator coverage')
    c.require(set(s['base_residuals']) == BASE_RESIDUALS, 'Missing base DC residual')
    for value in s['base_residuals'].values(): c.require(0 <= value <= TOLERANCE, 'Base DC residual failure')
    c.require(len(s['outage_residuals']) == len(scope['checked_outage_ids']), 'Missing direct outage residual')
    for row, outage_id, line, index in zip(s['outage_residuals'], scope['checked_outage_ids'], scope['outage_line_ids'], scope['outage_indices']):
        c.require(row['outage_id'] == outage_id and row['outage_line_id'] == line and row['outage_index'] == index and
            0 <= row['reduced_system_MW'] <= TOLERANCE and 0 <= row['full_nodal_balance_MW'] <= TOLERANCE, 'Failed direct outage residual/identity')
    c.require(source['source_sha256'] == identity['source_sha256'] and source['solution_sha256'] == identity['solution_sha256'] and
        source['hours'] == request['hours'] and source['mode'] == 'n1' and source['tolerance'] == TOLERANCE and
        source['pass_primal'] is True and source['violations_by_category'] == {}, 'Failed frozen original source check')
    c.require(SOURCE_RESIDUALS <= set(source['max_violation_by_category']), 'Incomplete frozen source residual categories')
    for value in source['max_violation_by_category'].values(): c.require(0 <= value <= TOLERANCE, 'Failed original source residual')
    security = source['security']
    c.require(security['outages_checked'] == len(scope['checked_outage_ids']) and security['violated_pairs'] == [] and
        security['violated_line_hours'] == 0 and s['violated_line_hours'] == 0 and
        result['direct_violated_pair_count'] == 0, 'Missing coverage or post-slack security violation')
    for a, b in ((s['max_violation_after_shared_slack_MW'], security['max_violation_after_shared_slack_MW']),
                 (s['max_unrelaxed_overload_MW'], security['max_unrelaxed_overload_MW']),
                 (s['base_unrelaxed_overload_MW'], source['base_unrelaxed_overload_MW'])):
        c.require(abs(a - b) <= TOLERANCE, 'Direct physical checker disagreement')
    c.require(0 <= s['max_violation_after_shared_slack_MW'] <= TOLERANCE and
        0 <= s['base_max_after_shared_slack_MW'] <= TOLERANCE and
        0 <= security['max_violation_after_shared_slack_MW'] <= TOLERANCE, 'Post-slack physical overload')
    costs = [matrix['linear_objective'], accurate['objective_recomputed'], s['linear_model_cost'], source['linear_model_cost'],
             request['oracle_objective'], request['provisional_upper']]
    c.require(all(c.finite(v) and checks.objective_consistent(v, costs[0]) for v in costs), 'Oracle/source/matrix objective mismatch')
    true, linear, overpayment = (source[k] for k in ('true_source_cost','linear_model_cost','objective_overpayment'))
    c.require(checks.objective_consistent(linear - true, overpayment) and
        true <= linear + max(TOLERANCE, max(abs(true), abs(linear)) * 1e-9), 'True source cost/overpayment inconsistency')
    c.require(result['target_subset_quality']['passed'] is True and
        result['target_subset_quality']['subset_identity_sha256'] == request['integer_target_identity']['hard_zero_subset']['identity_sha256'],
        'Physical point missing hard-zero subset gate')
    metrics = result['slack_metrics']
    for group, component in (('load_shedding','shedding'), ('reserve_shortfall','reserve_shortfall'), ('shared_overflow','shared_overflow')):
        c.require(checks.objective_consistent(metrics[group]['cost'], s['linear_cost_components'][component]), 'Slack cost mismatch')
    c.require(abs(metrics['load_shedding']['sum_MWh'] - source['total_shed_MWh']) <= TOLERANCE and
        abs(metrics['load_shedding']['sum_MWh'] - s['total_shed_MWh']) <= TOLERANCE and
        abs(metrics['shared_overflow']['sum_MWh'] - s['total_shared_overflow_MW_hours']) <= TOLERANCE and
        abs(metrics['shared_overflow']['max_MW'] - source['max_overflow_MW']) <= TOLERANCE and
        abs(metrics['shared_overflow']['max_MW'] - s['max_overflow_MW']) <= TOLERANCE, 'Slack quantity disagreement')
    coverage = result['source_checker_coverage']
    c.require(coverage == dict(checked_outage_ids=scope['checked_outage_ids'], checked_pair_hours=scope['eligible_pair_hours'],
        derivation='Pinned frozen n1/all-security loop over exact source order and all finite emergency ratings; checker directly reports outage count',
        reported_outages_checked=security['outages_checked']), 'Incomplete source checker coverage evidence')
    return max(costs)


def run(request, out, *, production=True):
    import numpy as np
    started = time.monotonic()
    f = c.helpers(); out = Path(out).resolve()
    c.require(out.is_dir() and not any(out.iterdir()), 'Physical output must be fresh and empty')
    stage, checks, separator, checker, model, qa, full = modules()
    for role in ('source', 'expected', 'mps'):
        require_digest(request[role + '_sha256'], role + ' hash')
        c.require(f.sha256(request[role + '_path']) == request[role + '_sha256'], 'Changed physical input ' + role)
        if production: c.require(request[role + '_sha256'] == f.INPUT_PINS[role], 'Unapproved production input ' + role)
    data = stage.source_data(request['source_path'])
    expected = model.load_expected(request['expected_path'], request['expected_sha256'])
    hours = request['hours']; c.require(type(hours) is int and hours > 0, 'Invalid physical horizon')
    c.require(expected['sense'] == 1 and expected['offset'] == 0, 'Changed original objective')
    scope = separator.source_scope(data, hours, source_sha256=request['source_sha256'])
    if production:
        import current_scuc.heldout as heldout
        heldout.check_physical_scope(hours, expected, data, scope)
    scope_gate(request, expected, data, scope, full)
    target = request['integer_target_identity']
    require_digest(request['integer_target_identity_sha256'], 'integer target identity')
    c.require(object_hash(target) == request['integer_target_identity_sha256'], 'Integer target identity changed')
    persisted = c.read_bundle(request['stored_lift_directory'], request['stored_lift_artifact'])
    c.require(set(persisted) == {'values'}, 'Incomplete/extra original lift fields')
    values = persisted['values']
    c.require(isinstance(values, np.ndarray) and values.dtype == np.float64 and values.shape == (expected['num_col'],) and
        np.all(np.isfinite(values)), 'Incomplete or nonfinite original lift')
    lift_hash = hashlib.sha256(values.tobytes()).hexdigest()
    c.require(lift_hash == request['stored_lift_artifact']['readback_values_sha256'], 'Stored original lift hash mismatch')
    c.require(f.full_lift_gate(request['full_literal_check'], request['full_scope'], lift_hash), 'Missing persisted full literal-row gate')
    retained = np.asarray([j for j, name in enumerate(expected['col_names']) if not name.startswith(('theta_', 'f_', 'over_'))], dtype=np.int64)
    c.require(hashlib.sha256(retained.astype('<i8').tobytes()).hexdigest() == request['full_scope']['retained_original_columns_sha256'], 'Retained original map mismatch')
    require_digest(request['retained_values_sha256'], 'parsed retained values hash')
    c.require(hashlib.sha256(values[retained].tobytes()).hexdigest() == request['retained_values_sha256'], 'Lift changed retained parsed values')
    binary = binary_gate(expected, data, hours, values, request['source_binary_authority'])
    positions = {name: j for j, name in enumerate(expected['col_names'])}
    inverse = {int(j): index for index, j in enumerate(retained)}
    inventory = [dict(name=name, original_column=positions[name], projected_column=inverse[positions[name]],
        integrality=1, lower=float(expected['col_lower'][positions[name]]), upper=float(expected['col_upper'][positions[name]]))
        for name in request['source_binary_authority']['names']]
    import current_scuc.no_shedding as no_shedding
    _, subset = no_shedding.target_model(expected, model, production=production)
    subset_point = no_shedding.point_check(expected, values, subset, model, production=production)
    c.require(target == dict(schema='integer-network-projection-target-v1',
        network_oracle_identity_sha256=request['full_scope']['identity_sha256'], source_object_sha256=full._json_hash(data),
        source_binary_authority_sha256=request['source_binary_authority']['identity_sha256'],
        original_model_hashes=model.model_hashes(expected), retained_original_columns_sha256=model.digest(retained.astype(np.int32)),
        source_binary_inventory_sha256=object_hash(inventory), binary_count=binary['count'],
        lower_domain=no_shedding.DOMAIN, hard_zero_subset=subset, physical_dc_lower_bound_certified=False),
        'Integer target disagrees with original source/type/map identity')
    accurate = qa.check_primal(expected, values, tolerance=TOLERANCE)
    c.require(accurate['passed'] is True, 'Accurate original rows/bounds failed')
    raw_path = out/'original.sol'
    parsed = write_raw_solution(raw_path, expected, values, accurate.pop('activities'), accurate['objective_recomputed'], checks)
    pair_path = out/'mapping-pairs.json'
    if production: c.require(request['mapping_pairs'] == [list(p) for p in f.PAIRS], 'Changed original mapping pairs')
    c.bounded_write(pair_path,request['mapping_pairs'],fresh=True)
    from current_scuc.core.driver.pair_codec import PackedPairs, read_pairs
    active = PackedPairs(scope, request['mapping_pairs'])
    identity = dict(source_sha256=request['source_sha256'], source_data_sha256=separator.source_data_sha256(data),
        model_sha256=request['mps_sha256'], expected_sha256=request['expected_sha256'], solution_sha256=f.sha256(raw_path),
        pair_manifest_sha256=f.sha256(pair_path), hours=hours, active_pairs_sha256=active.content_sha256())
    matrix = checks.matrix_check(expected, parsed['values'], 'mip', identity, tolerance=TOLERANCE)
    c.require(matrix['passed'] is True and matrix['max_violation_by_category']['integrality'] <= INTEGER_TOLERANCE, 'Original integer matrix check failed')
    c.require(checks.objective_consistent(matrix['linear_objective'], parsed['printed_objective']), 'Raw objective mismatch')
    identity['matrix_check'] = matrix
    tick = time.monotonic()
    separation = separator.separate_integer_network(data, parsed['values'], hours, active,
        tolerance=TOLERANCE, identity=identity, witness_directory=out/'direct-witnesses')
    separator_seconds = time.monotonic() - tick
    violated = read_pairs(separation['violated_pairs'], scope)
    tick = time.monotonic()
    source, normalizations = stage.normalize_source_measurements(checker.check(request['source_path'], raw_path, 'n1', hours, TOLERANCE, True))
    checker_seconds = time.monotonic() - tick
    source['security']['violated_pairs'] = [list(pair) for pair in source['security']['violated_pairs']]
    result = dict(schema=SCHEMA, passed=False, numerical_physical_witness=False, upper_bound_eligible=False,
        physical_dc_lower_bound_certified=False, optimization_called=False, no_binary_rounding=True,
        original_column_count=expected['num_col'], original_row_count=expected['num_row'], identity=identity,
        integer_target_identity_sha256=request['integer_target_identity_sha256'], full_scope_identity_sha256=request['full_scope']['identity_sha256'],
        stored_lift_binary64_sha256=lift_hash, retained_values_sha256=request['retained_values_sha256'], binary_check=binary,
        matrix_check=matrix, accurate_original_primal_check=accurate, separation=separation, source_check=source,
        source_scalar_normalizations=normalizations, direct_violated_pair_count=len(violated),
        source_checker_coverage=dict(checked_outage_ids=scope['checked_outage_ids'], checked_pair_hours=scope['eligible_pair_hours'],
            derivation='Pinned frozen n1/all-security loop over exact source order and all finite emergency ratings; checker directly reports outage count',
            reported_outages_checked=source['security']['outages_checked']),
        target_subset_quality=subset_point,
        slack_metrics=measurement_metrics(data, parsed['values'], scope, hours),
        literal_row_check_passed=True, direct_dc_check_passed=False,
        direct_separator_seconds=separator_seconds, independent_source_checker_seconds=checker_seconds,
        physical_checker_sha256=f.sha256(checker.__file__), direct_separator_sha256=f.sha256(separator.__file__))
    try:
        c.require(PackedPairs(scope, source['security']['violated_pairs']) == violated, 'Direct violated pair disagreement')
        upper = validate_reports(result, request, scope, checks)
    except Exception as exc:
        result.update(error=type(exc).__name__ + ': ' + str(exc), physical_worker_seconds=time.monotonic() - started)
        raise PhysicalGateFailure(str(exc), result) from exc
    for role in ('source', 'expected', 'mps'):
        c.require(f.sha256(request[role + '_path']) == request[role + '_sha256'], 'Physical input changed during checks')
    c.require(f.sha256(raw_path) == identity['solution_sha256'], 'Raw witness changed during physical checks')
    result.update(passed=True, numerical_physical_witness=True, upper_bound_eligible=True, direct_dc_check_passed=True,
        checked_upper=upper, physical_worker_seconds=time.monotonic() - started)
    return result


def read_result(out, request_path, request_sha256):
    """No factorization: authenticate output, point, identities and both gates."""
    f = c.helpers(); out = Path(out)
    c.require(f.sha256(request_path) == request_sha256, 'Changed physical request')
    request = f.strict_json(request_path); completion = f.strict_json(out/'completion.json')
    c.require(completion['request_sha256'] == request_sha256 and completion['complete'] is True, 'Incomplete physical worker')
    c.require(f.sha256(out/'result.json') == completion['result_sha256'], 'Changed physical result')
    result = f.strict_json(out/'result.json')
    c.require(result['passed'] is True and result['upper_bound_eligible'] is True and
        result['numerical_physical_witness'] is True and result['direct_dc_check_passed'] is True, 'Physical result not accepted')
    stage, checks, separator, checker, model, _, full = modules()
    for role in ('source','expected','mps'):
        c.require(f.sha256(request[role + '_path']) == request[role + '_sha256'], 'Changed physical input')
    c.require(f.sha256(out/'original.sol') == result['identity']['solution_sha256'] and
        f.sha256(out/'mapping-pairs.json') == result['identity']['pair_manifest_sha256'], 'Changed physical witness')
    c.require(f.sha256(checker.__file__) == result['physical_checker_sha256'] and
        f.sha256(separator.__file__) == result['direct_separator_sha256'], 'Physical checker source changed')
    data = stage.source_data(request['source_path']); scope = separator.source_scope(data, request['hours'], source_sha256=request['source_sha256'])
    expected = model.load_expected(request['expected_path'], request['expected_sha256'])
    scope_gate(request, expected, data, scope, full)
    from current_scuc.core.driver.pair_codec import read_pairs
    c.require(len(read_pairs(result['separation']['violated_pairs'], scope)) == result['direct_violated_pair_count'] == 0, 'Changed violated pair artifact')
    values = c.read_bundle(request['stored_lift_directory'], request['stored_lift_artifact'])['values']
    c.require(hashlib.sha256(values.tobytes()).hexdigest() == result['stored_lift_binary64_sha256'], 'Changed stored lift')
    import numpy as np
    parsed = checks.read_primal(out/'original.sol', expected['col_names'])
    c.require(parsed is not None and np.asarray([parsed['values'][name] for name in expected['col_names']], dtype=np.float64).tobytes() == values.tobytes(),
        'Physical raw witness is not the persisted lift')
    c.require(separator.point_sha256(parsed['values']) == result['matrix_check']['point_sha256'], 'Physical matrix point mismatch')
    c.require(binary_gate(expected, data, request['hours'], values, request['source_binary_authority']) == result['binary_check'], 'Changed binary audit')
    retained = [j for j, name in enumerate(expected['col_names']) if not name.startswith(('theta_', 'f_', 'over_'))]
    c.require(hashlib.sha256(values[retained].tobytes()).hexdigest() == result['retained_values_sha256'] == request['retained_values_sha256'],
        'Changed retained values binding')
    c.require(f.full_lift_gate(request['full_literal_check'], request['full_scope'], result['stored_lift_binary64_sha256']) and
        result['literal_row_check_passed'] is True and object_hash(request['integer_target_identity']) == request['integer_target_identity_sha256'],
        'Changed literal or integer target binding')
    import current_scuc.no_shedding as no_shedding
    c.require(no_shedding.point_check(expected, values, request['integer_target_identity']['hard_zero_subset'], model,
        production=request['full_scope']['production_scope']) == result['target_subset_quality'], 'Changed subset point check')
    c.require(measurement_metrics(data, parsed['values'], scope, request['hours']) == result['slack_metrics'], 'Changed slack metrics')
    upper = validate_reports(result, request, scope, checks)
    c.require(result['checked_upper'] == upper, 'Changed admitted upper')
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', required=True); p.add_argument('--request-sha256', required=True); p.add_argument('--out', required=True)
    a = p.parse_args(argv); f = c.helpers(); out = Path(a.out).resolve()
    c.require(sys.dont_write_bytecode and __debug__, 'Python -B and assertions required')
    c.require(not out.is_relative_to(c.ROOT), 'Physical output must be outside source package')
    c.require(out.is_dir() and not any(out.iterdir()), 'Fresh physical output directory required')
    c.require(f.sha256(a.request) == a.request_sha256, 'Physical request hash mismatch')
    request = f.strict_json(a.request)
    try:
        result = run(request, out)
    except Exception as exc:
        result = getattr(exc, 'report', None) or dict(schema=SCHEMA, passed=False, upper_bound_eligible=False, numerical_physical_witness=False,
            physical_dc_lower_bound_certified=False, optimization_called=False, error=type(exc).__name__ + ': ' + str(exc))
    finite_tree(result)
    c.bounded_write(out/'result.json',result,fresh=True)
    c.bounded_write(out/'completion.json',dict(complete=True,passed=result['passed'],request_sha256=a.request_sha256,
        result_sha256=f.sha256(out/'result.json')),fresh=True)
    if result['passed']: read_result(out, a.request, a.request_sha256)
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    budget=c.storage()
    with budget.active_writer_reservations([budget.WriteBound(Path('/proc/self/fd/1').resolve(),512*1024**2,
            'Python physical stdout','prospective512MiB process file limit')]):
        raise SystemExit(main())
