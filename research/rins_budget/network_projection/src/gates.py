"""Admission checks and cut mapping extracted from the measured full-scope driver."""
from fractions import Fraction
import math
import hashlib
HOURS = 36
STATIONARITY_FAILURE = 'independent stationarity residual'
FULL_COUNTS = ('signed_normal_rows', 'signed_security_rows', 'unsigned_security_pair_hours')

def require(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def mapped_cuts(cuts, metadata, round_index):
    import numpy as np
    hours = metadata['hours']
    require(type(hours) is int and 0 < hours <= HOURS and len(cuts) == hours, 'Expected one all-hour cut batch')
    require([row['hour'] for row in cuts] == list(range(hours)), 'Missing/duplicate/reordered hour cut')
    mapping = np.asarray(metadata['original_to_projected'])
    eta = np.asarray(metadata['eta_columns'])
    lower, upper, starts, index, value, names = [], [], [0], [], [], []
    for row in cuts:
        original = np.asarray(row['original_indices'])
        coefficients = np.asarray(row['coefficients'])
        require(original.ndim == 1 and original.dtype.kind in 'iu' and coefficients.shape == original.shape, 'Invalid original cut indices')
        require(np.all(original >= 0) and np.all(original < len(mapping)) and np.all(mapping[original] >= 0), 'Cut touches removed or absent original column')
        require(np.all(np.isfinite(coefficients)) and np.all(coefficients != 0), 'Nonfinite or zero cut coefficient')
        require(len(set(original.tolist())) == len(original), 'Duplicate original cut column')
        require(row['eta_coefficient'] == -1. and finite(row['upper']), 'Invalid eta coefficient or cut constant')
        require(row['nnz'] == len(original) + 1, 'Cut nnz receipt mismatch')
        native = mapping[original].tolist() + [int(eta[row['hour']])]
        require(len(set(native)) == len(native), 'Duplicate projected cut column')
        index.extend(native); value.extend(coefficients.tolist() + [-1.])
        starts.append(len(index)); lower.append(-math.inf); upper.append(row['upper'])
        names.append(f'network_cut_{round_index}_{row["hour"]}')
    return {'lower': np.asarray(lower), 'upper': np.asarray(upper),
            'starts': np.asarray(starts, dtype=np.int32), 'index': np.asarray(index, dtype=np.int32),
            'value': np.asarray(value), 'names': names, 'nnz': len(index)}


def verify_retained(retained, lift, metadata):
    import numpy as np
    ids = np.asarray(metadata['retained_original_columns'])
    removed = np.asarray(metadata['removed_columns'])
    require(retained.shape == lift.shape == (metadata['original_num_col'],), 'Recovery shape changed')
    require(np.all(np.isfinite(retained[ids])) and np.all(np.isnan(retained[removed])), 'Retained input contains a network point')
    require(np.all(np.isfinite(lift)), 'Incomplete or nonfinite original recovery')
    require(retained[ids].tobytes() == lift[ids].tobytes(), 'Recovery changed retained-value bits')


def certificate_gate(certificate, full_scope):
    gap = certificate.get('support_gap_dollars_upper')
    exact_gap = certificate.get('support_gap_dollars')
    try:
        rational = Fraction(int(exact_gap[0]), int(exact_gap[1]))
        rational_ok = 0 <= rational <= 100 and Fraction.from_float(float(gap)) >= rational
    except (TypeError, ValueError, ZeroDivisionError, OverflowError, IndexError):
        rational_ok = False
    return (certificate.get('passed') is True and certificate.get('certificate_valid') is True
            and certificate.get('support_gap_le_100_dollars') is True and finite(gap) and 0 <= gap <= 100.
            and rational_ok and certificate.get('cut_validity_domain') == 'declared_literal_lodf_row_model'
            and certificate.get('physical_dc_lower_bound_certified') is False
            and certificate.get('full_scope_identity_sha256') == full_scope.get('full_scope_identity_sha256')
            and valid_full_scope(full_scope)
            and certificate.get('full_scope_coverage_complete') is True
            and certificate.get('full_scope') == full_scope
            and all(type(certificate.get(k)) is int and certificate[k] == full_scope[k] for k in FULL_COUNTS))


def valid_full_scope(scope):
    if not isinstance(scope, dict):
        return False
    identity = scope.get('full_scope_identity_sha256')
    return (type(identity) is str and len(identity) == 64
            and all(c in '0123456789abcdef' for c in identity)
            and scope.get('coverage_rule_complete') is True
            and all(type(scope.get(k)) is int and scope[k] >= 0 for k in FULL_COUNTS)
            and scope['signed_security_rows'] == 2 * scope['unsigned_security_pair_hours'])


def full_lift_gate(check, full_scope, stored_lift_sha256):
    """The subset matrix check cannot substitute for a complete stored-lift scan."""
    if not valid_full_scope(full_scope) or not isinstance(check, dict):
        return False
    excess = check.get('conservative_violation_upper')
    return (check.get('passed') is True and check.get('full_scope_coverage_complete') is True
            and check.get('zero_radius') is True and check.get('unchanged_base_matrix_qa_required') is True
            and check.get('physical_dc_lower_bound_certified') is False
            and type(stored_lift_sha256) is str and len(stored_lift_sha256) == 64
            and check.get('stored_lift_binary64_sha256') == stored_lift_sha256
            and check.get('full_scope_identity_sha256') == full_scope['full_scope_identity_sha256']
            and all(type(check.get(k)) is int and check[k] == full_scope[k] for k in FULL_COUNTS)
            and finite(excess) and 0 <= excess <= 1e-5)


def projected_quality_gate(check, expected, solution, version):
    """Only the named finite stationarity threshold may await an exact proof."""
    import numpy as np
    if not isinstance(check, dict) or type(check.get('passed')) is not bool:
        return False
    failures = check.get('failures')
    if (not isinstance(failures, list) or not all(type(v) is str for v in failures)
            or check['passed'] != (not failures)
            or any(v != STATIONARITY_FAILURE for v in failures)):
        return False
    # The full independent calculation must have succeeded, even when large.
    residual = check.get('stationarity', {}).get('max')
    if not finite(residual) or residual < 0:
        return False
    if solution.get('version') != version or solution.get('run_status') != 0 or solution.get('model_status') != 7:
        return False
    try:
        for field, dimension in (('row_dual', 'num_row'), ('row_value', 'num_row'),
                                 ('col_dual', 'num_col'), ('col_value', 'num_col')):
            vector = np.asarray(solution.get(field, []), dtype=np.float64)
            if vector.shape != (expected[dimension],) or not np.all(np.isfinite(vector)):
                return False
    except (TypeError, ValueError, OverflowError, KeyError):
        return False
    return True


def exact_enclosure(value):
    require(isinstance(value, dict) and value.get('direction_verified') is True,
            'Missing verified exact enclosure')
    pair = value.get('rational')
    require(isinstance(pair, list) and len(pair) == 2 and all(type(v) is str for v in pair),
            'Malformed rational enclosure')
    rational = Fraction(int(pair[0]), int(pair[1]))
    lo, up = value.get('down_binary64'), value.get('up_binary64')
    require(finite(lo) and finite(up) and Fraction.from_float(float(lo)) <= rational <= Fraction.from_float(float(up)),
            'Invalid outward enclosure')
    return rational


def lower_certificate_gate(certificate, expected, row_dual, *, model):
    """Validate result shape, outward direction and CURRENT matrix/dual identity."""
    import numpy as np
    require(isinstance(certificate, dict) and certificate.get('passed') is True
            and certificate.get('exact_projected_matrix_bound_certified') is True,
            'Missing exact projected-matrix certificate')
    require(expected.get('sense') == 1 and certificate.get('original_bound_direction') == 'lower',
            'Candidate certificate is not an original minimization lower bound')
    normalized = exact_enclosure(certificate.get('normalized_lower'))
    original = exact_enclosure(certificate.get('original_bound'))
    contraction = exact_enclosure(certificate.get('selected_lambda'))
    require(0 < contraction <= 1 and original == normalized, 'Invalid certificate contraction or sense mapping')
    require(finite(certificate.get('original_bound_down')) and finite(certificate.get('original_bound_up'))
            and certificate.get('original_bound_down') == certificate['original_bound']['down_binary64']
            and certificate.get('original_bound_up') == certificate['original_bound']['up_binary64'],
            'Certificate endpoint aliases disagree')
    require(certificate.get('model_hashes') == model.model_hashes(expected), 'Certificate is for a different projected matrix')
    digest = hashlib.sha256(np.asarray(row_dual, dtype='<f8').tobytes()).hexdigest()
    require(certificate.get('row_dual_sha256') == digest, 'Certificate is for a different solution snapshot')
    require(finite(certificate.get('actual_seconds')) and certificate['actual_seconds'] >= 0,
            'Invalid certificate cost receipt')
    return True

