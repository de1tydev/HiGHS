"""Exact weak-duality certificate for a binary64 continuous LP in sorted CSC.

No solver, network factorization, filesystem access, or global rational cache.
The caller owns native/model-readback/primal QA and all source-file receipts.
"""
from __future__ import annotations

import hashlib
import math
import time
from fractions import Fraction

import numpy as np

ARRAY_FIELDS = ('col_lower', 'col_upper', 'col_cost', 'row_lower', 'row_upper',
                'integrality', 'a_start', 'a_index', 'a_value')
SCALAR_FIELDS = ('num_col', 'num_row', 'num_nz', 'sense', 'offset')
INT_FIELDS = ('integrality', 'a_start', 'a_index')
ZERO, ONE = Fraction(0), Fraction(1)


class CertificateError(ValueError):
    """Fail-closed rejection, with JSON-safe evidence and elapsed wall time."""

    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.details = {} if details is None else details
        self.actual_seconds = 0.0


def _rat(value):
    return [str(value.numerator), str(value.denominator)]


def _enclosure(value):
    """Two finite binary64 endpoints enclosing an exact rational, or reject."""
    try:
        rounded = float(value)
    except (OverflowError, ValueError):
        rounded = math.inf
    if not math.isfinite(rounded):
        raise CertificateError('binary64_enclosure_overflow',
                               'Exact value has no finite binary64 enclosure',
                               details={'rational': _rat(value)})
    down = up = rounded
    exact_rounded = Fraction.from_float(rounded)
    if exact_rounded > value:
        down = math.nextafter(rounded, -math.inf)
    if exact_rounded < value:
        up = math.nextafter(rounded, math.inf)
    if not math.isfinite(down) or not math.isfinite(up):
        raise CertificateError('binary64_enclosure_overflow',
                               'Outward endpoint is outside finite binary64',
                               details={'rational': _rat(value)})
    if not Fraction.from_float(down) <= value <= Fraction.from_float(up):
        raise CertificateError('enclosure_direction', 'Outward enclosure verification failed')
    return {'rational': _rat(value), 'down_binary64': down,
            'up_binary64': up, 'direction_verified': True}


def _require(condition, message):
    if not condition:
        raise CertificateError('invalid_input', message)


def _validate(expected, row_dual, check):
    """Validate before integer coercion, without accepting ragged/object data."""
    _require(isinstance(expected, dict), 'Expected model must be a dictionary')
    for key in (*SCALAR_FIELDS, *ARRAY_FIELDS, 'col_names', 'row_names'):
        _require(key in expected, 'Missing model field ' + key)
    for key in ('num_col', 'num_row', 'num_nz'):
        value = expected[key]
        _require(type(value) is int and 0 <= value < 2**31, 'Invalid dimension ' + key)
    n, m, nz = (expected[k] for k in ('num_col', 'num_row', 'num_nz'))
    _require(n > 0, 'Expected at least one column')
    sense = expected['sense']
    _require(not isinstance(sense, (bool, np.bool_)) and
             isinstance(sense, (int, np.integer)) and sense in (1, -1),
             'Objective sense must be integer +1 or -1')
    offset = expected['offset']
    _require(not isinstance(offset, (bool, np.bool_)) and
             isinstance(offset, (int, float, np.integer, np.floating)), 'Invalid offset')
    offset = float(offset)
    _require(math.isfinite(offset), 'Nonfinite objective offset')
    e = dict(num_col=n, num_row=m, num_nz=nz, sense=int(sense), offset=offset)
    sizes = dict(col_lower=n, col_upper=n, col_cost=n, row_lower=m, row_upper=m,
                 integrality=n, a_start=n+1, a_index=nz, a_value=nz)
    for key, size in sizes.items():
        check()
        a = np.asarray(expected[key])
        _require(a.shape == (size,), 'Invalid shape ' + key)
        integer = key in INT_FIELDS
        # Empty Python integer lists have float dtype, but contain no bad indices.
        _require((a.dtype.kind in 'iu' or size == 0) if integer else
                 a.dtype.kind in 'fiu' and (a.dtype.kind != 'f' or a.dtype.itemsize <= 8),
                 'Invalid numeric dtype ' + key)
        for start in range(0, size, 65536):
            check()
            part = a[start:start+65536]
            if integer:
                _require(bool(np.all(part >= 0) and np.all(part < 2**31)),
                         'Invalid integer array ' + key)
            elif key in ('col_cost', 'a_value'):
                _require(bool(np.all(np.isfinite(part))), 'Nonfinite ' + key)
        e[key] = np.array(a, dtype='<i4' if integer else '<f8', order='C', copy=True)
        check()
        if not integer and key in ('col_cost', 'a_value'):
            _require(bool(np.all(np.isfinite(e[key]))), 'Nonfinite converted ' + key)
    _require(bool(np.all(e['integrality'] == 0)), 'Certificate requires continuous LP columns')
    _require(bool(np.all(e['a_value'] != 0)), 'Explicit zero CSC coefficient')
    for prefix in ('col', 'row'):
        lo, up = e[prefix + '_lower'], e[prefix + '_upper']
        for start in range(0, len(lo), 65536):
            check()
            l, u = lo[start:start+65536], up[start:start+65536]
            _require(bool(np.all(~np.isnan(l)) and np.all(~np.isnan(u)) and
                          np.all(l <= u) and np.all(l != math.inf) and
                          np.all(u != -math.inf)), 'Invalid ' + prefix + ' bounds')
    starts, indices = e['a_start'], e['a_index']
    _require(starts[0] == 0 and starts[-1] == nz, 'Invalid CSC endpoints')
    for start in range(0, n, 65536):
        check()
        stop = min(n, start + 65536)
        _require(bool(np.all(starts[start+1:stop+1] >= starts[start:stop])),
                 'Decreasing CSC starts')
    for start in range(0, nz, 65536):
        check()
        _require(bool(np.all(indices[start:start+65536] < m)), 'CSC row index out of range')
    # Check adjacent rows per column; duplicate entries are not silently summed.
    for j in range(n):
        if j % 256 == 0:
            check()
        a, b = int(starts[j]), int(starts[j+1])
        if b-a > 1:
            _require(bool(np.all(indices[a+1:b] > indices[a:b-1])),
                     'Unsorted or duplicate CSC row indices')
    for key, size in (('col_names', n), ('row_names', m)):
        names = expected[key]
        _require(isinstance(names, (list, tuple)) and len(names) == size, 'Invalid ' + key)
        seen = set()
        for i, name in enumerate(names):
            if i % 256 == 0:
                check()
            _require(isinstance(name, str) and name and len(name) < 4096 and
                     '\x00' not in name and len(name.encode('utf-8')) < 4096,
                     'Unsafe name in ' + key)
            _require(name not in seen, 'Duplicate name in ' + key)
            seen.add(name)
        e[key] = list(names)
    check()
    dual = np.asarray(row_dual)
    _require(dual.shape == (m,) and dual.dtype.kind in 'fiu' and
             (dual.dtype.kind != 'f' or dual.dtype.itemsize <= 8), 'Invalid row-dual shape or dtype')
    dual = np.array(dual, dtype='<f8', order='C', copy=True)
    for start in range(0, m, 65536):
        check()
        _require(bool(np.all(np.isfinite(dual[start:start+65536]))), 'Nonfinite row dual')
    return e, dual


def _array_hash(array, check):
    data = memoryview(array).cast('B')
    digest = hashlib.sha256()
    for start in range(0, len(data), 1024*1024):
        check()
        digest.update(data[start:start+1024*1024])
    check()
    return digest.hexdigest()


def _model_hashes(e, check):
    result = {k: e[k] for k in SCALAR_FIELDS}
    result.update({k: _array_hash(e[k], check) for k in ARRAY_FIELDS})
    for key in ('col_names', 'row_names'):
        digest = hashlib.sha256()
        for i, name in enumerate(e[key]):
            if i % 256 == 0:
                check()
            if i:
                digest.update(b'\n')
            digest.update(name.encode('utf-8'))
        result[key] = digest.hexdigest()
    return result


def _bound_counts(lower, upper, check):
    result = dict(fixed=0, finite_ranged=0, lower_only=0, upper_only=0, free=0,
                  finite_lower=0, finite_upper=0, negative_infinite_lower=0,
                  positive_infinite_upper=0)
    for i, (lo, up) in enumerate(zip(lower, upper)):
        if i % 256 == 0:
            check()
        fl, fu = math.isfinite(lo), math.isfinite(up)
        result['finite_lower' if fl else 'negative_infinite_lower'] += 1
        result['finite_upper' if fu else 'positive_infinite_upper'] += 1
        kind = ('fixed' if lo == up else 'finite_ranged') if fl and fu else (
            'lower_only' if fl else 'upper_only' if fu else 'free')
        result[kind] += 1
    return result


def certify(expected_model_dict, row_dual, *, deadline_monotonic):
    """Return an exact LP bound; raise CertificateError or TimeoutError.

    Sense +1 returns an ORIGINAL LOWER bound; sense -1 returns an ORIGINAL
    UPPER bound, after normalizing cost, offset, and native row dual by sense.
    The caller passes min(now+20s, aggregate allowance, arm deadline), charges
    every attempted call, and retains independent numerical stationarity QA.
    """
    started = time.monotonic()

    def check():
        if time.monotonic() >= deadline_monotonic:
            raise TimeoutError('Exact projected-matrix certification deadline exhausted')

    try:
        _require(not isinstance(deadline_monotonic, bool) and
                 isinstance(deadline_monotonic, (int, float)) and
                 math.isfinite(deadline_monotonic), 'Deadline must be finite monotonic time')
        check()
        e, native_y = _validate(expected_model_dict, row_dual, check)
        hashes = _model_hashes(e, check)
        dual_hash = _array_hash(native_y, check)
        cache = {0.0: ZERO, 1.0: ONE}

        def exact(value):
            v = float(value)
            answer = cache.get(v)
            if answer is None:
                answer = Fraction.from_float(v)
                cache[v] = answer
            return answer

        s, n, m = e['sense'], e['num_col'], e['num_row']
        row_counts = dict(zero=0, lower_selected=0, upper_selected=0)
        projections = []
        y = []
        row_sum = ZERO
        for i in range(m):
            if i % 256 == 0:
                check()
            raw = s * exact(native_y[i])
            lo, up = e['row_lower'][i], e['row_upper'][i]
            projected = raw
            missing = 'lower' if raw > 0 and not math.isfinite(lo) else (
                'upper' if raw < 0 and not math.isfinite(up) else None)
            if missing:
                projected = ZERO
                projections.append({'index': i, 'name': e['row_names'][i],
                                    'native_input': _rat(exact(native_y[i])),
                                    'normalized_input': _rat(raw), 'projected': _rat(ZERO),
                                    'missing_required_endpoint': missing})
            y.append(projected)
            row_counts['lower_selected' if projected > 0 else
                       'upper_selected' if projected < 0 else 'zero'] += 1
            if projected:
                row_sum += projected * exact(lo if projected > 0 else up)

        costs, dots = [], []
        lam_lo, lam_hi = ZERO, ONE
        low_active, high_active, contradictions = [], [], []
        constraint_counts = dict(upper_missing=0, lower_missing=0, total=0,
                                 nonzero_coefficient=0, zero_coefficient_satisfied=0,
                                 zero_coefficient_contradiction=0)
        old_unsupported = []
        q_before_max = ZERO
        operations = 0
        for j in range(n):
            if j % 128 == 0:
                check()
            c = s * exact(e['col_cost'][j])
            d = ZERO
            for k in range(int(e['a_start'][j]), int(e['a_start'][j+1])):
                operations += 1
                if operations % 256 == 0:
                    check()
                yi = y[int(e['a_index'][k])]
                if yi:
                    d += exact(e['a_value'][k]) * yi
            costs.append(c)
            dots.append(d)
            q_before = c-d
            q_before_max = max(q_before_max, abs(q_before))
            fl, fu = math.isfinite(e['col_lower'][j]), math.isfinite(e['col_upper'][j])
            if (q_before > 0 and not fl) or (q_before < 0 and not fu):
                old_unsupported.append({'index': j, 'name': e['col_names'][j],
                                        'q': _rat(q_before),
                                        'missing_required_endpoint': 'lower' if q_before > 0 else 'upper'})
            # Every missing endpoint yields a*lambda <= b, including BOTH
            # constraints for free columns. No residual tolerance appears here.
            conditions = []
            if not fu:
                conditions.append(('upper_missing', d, c))
            if not fl:
                conditions.append(('lower_missing', -d, -c))
            for kind, a, b in conditions:
                constraint_counts[kind] += 1
                constraint_counts['total'] += 1
                witness = {'column': j, 'name': e['col_names'][j], 'kind': kind,
                           'a': _rat(a), 'b': _rat(b)}
                if not a:
                    if b < 0:
                        contradictions.append(witness)
                        constraint_counts['zero_coefficient_contradiction'] += 1
                    else:
                        constraint_counts['zero_coefficient_satisfied'] += 1
                    continue
                constraint_counts['nonzero_coefficient'] += 1
                ratio = b/a
                witness['ratio'] = _rat(ratio)
                if a > 0:
                    if ratio < lam_hi:
                        lam_hi, high_active = ratio, [witness]
                    elif ratio == lam_hi:
                        high_active.append(witness)
                else:
                    if ratio > lam_lo:
                        lam_lo, low_active = ratio, [witness]
                    elif ratio == lam_lo:
                        low_active.append(witness)
        check()
        interval = {'lower': _rat(lam_lo), 'upper': _rat(lam_hi),
                    'lower_active': low_active, 'upper_active': high_active,
                    'lower_domain_active': lam_lo == 0, 'upper_domain_active': lam_hi == 1,
                    'contradictions': contradictions, 'constraint_counts': constraint_counts,
                    'empty': bool(contradictions or lam_lo > lam_hi)}
        if interval['empty']:
            raise CertificateError('empty_lambda_interval', 'No admissible contraction in [0,1]',
                                   details={'lambda_interval': interval})
        if lam_hi <= 0:
            raise CertificateError('zero_only_lambda_interval', 'Only zero contraction is admissible',
                                   details={'lambda_interval': interval})
        lam = lam_hi  # Must remain Fraction even when float(lam) == 1.0.
        _require(ZERO <= lam_lo <= lam <= ONE, 'Internal contraction interval inconsistency')
        support_sum, q_max = ZERO, ZERO
        signs = dict(positive=0, negative=0, zero=0)
        support_counts = dict(lower_selected=0, upper_selected=0, zero=0)
        for j, (c, d) in enumerate(zip(costs, dots)):
            if j % 128 == 0:
                check()
            q = c-lam*d
            q_max = max(q_max, abs(q))
            signs['positive' if q > 0 else 'negative' if q < 0 else 'zero'] += 1
            if not q:
                support_counts['zero'] += 1
                continue
            side = 'lower' if q > 0 else 'upper'
            endpoint = e['col_' + side][j]
            if not math.isfinite(endpoint):
                raise CertificateError('negative_infinite_support',
                                       'Contracted column has no finite supporting endpoint',
                                       details={'column': j, 'name': e['col_names'][j],
                                                'q': _rat(q), 'missing_required_endpoint': side})
            support_counts[side + '_selected'] += 1
            support_sum += q * exact(endpoint)
        offset = s * exact(e['offset'])
        contracted_row_sum = lam * row_sum
        lower = offset + contracted_row_sum + support_sum
        original = lower if s == 1 else -lower
        check()
        original_enclosure = _enclosure(original)
        result = {
            'schema': 'network-projection-certified-lower-v2', 'passed': True,
            'status': 'finite_exact_projected_matrix_bound_certified',
            'scope': 'Exact rational interpretation of the supplied binary64 continuous projected matrix',
            'exact_projected_matrix_bound_certified': True,
            'physical_dc_lower_bound_certified': False, 'full_scuc_claim': False,
            'original_bound_direction': 'lower' if s == 1 else 'upper',
            'original_bound_label': 'ORIGINAL LOWER' if s == 1 else 'ORIGINAL UPPER',
            'original_bound': original_enclosure,
            'original_bound_down': original_enclosure['down_binary64'],
            'original_bound_up': original_enclosure['up_binary64'],
            'normalized_lower': _enclosure(lower), 'normalization_sense': s,
            'normalized_offset': _enclosure(offset), 'selected_lambda': _enclosure(lam),
            'one_minus_lambda': _enclosure(ONE-lam), 'lambda_interval': interval,
            'row_term_before_contraction': _enclosure(row_sum),
            'row_term': _enclosure(contracted_row_sum),
            'column_support_sum': _enclosure(support_sum),
            'row_sign_projection_count': len(projections), 'row_sign_projections': projections,
            'row_sign_counts': row_counts, 'q_sign_counts': signs,
            'column_support_counts': support_counts,
            'bound_counts': {'rows': _bound_counts(e['row_lower'], e['row_upper'], check),
                             'columns': _bound_counts(e['col_lower'], e['col_upper'], check)},
            'constraint_counts': constraint_counts,
            'uncontracted_unsupported_column_count': len(old_unsupported),
            'uncontracted_unsupported_columns': old_unsupported,
            'negative_infinity_column_count': 0, 'negative_infinity_columns': [],
            'uncontracted_q_max_abs': _enclosure(q_before_max),
            'contracted_q_max_abs': _enclosure(q_max),
            'stationarity': {'computed_here': False, 'required_from_caller': True,
                             'reason': 'Native column dual is not an input; q alone is not stationarity'},
            'model_hashes': hashes, 'row_dual_sha256': dual_hash,
            'source_and_artifact_receipts_required_from_caller': True,
            'new_native_calls': 0, 'new_network_factorizations': 0, 'new_model_bounds': 0,
        }
        check()
        result['actual_seconds'] = time.monotonic() - started
        return result
    except (CertificateError, TimeoutError) as exc:
        exc.actual_seconds = time.monotonic() - started
        raise
    except (TypeError, ValueError, OverflowError, IndexError, KeyError) as exc:
        failure = CertificateError('invalid_input', 'Malformed certificate input: ' + str(exc))
        failure.actual_seconds = time.monotonic() - started
        raise failure from exc
