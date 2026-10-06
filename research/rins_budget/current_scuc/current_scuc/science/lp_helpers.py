#!/usr/bin/env python3
"""One fresh adaptive per-line continuous full-scope LP gate.

The actual subset mapping model is distinct from the complete virtual row model.
The parent owns the watchdog, resource guards, durable stages and final admission.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import time
PROCESS_STARTED = time.monotonic()  # before parsing, hashing or scientific imports
import argparse
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True

ROOT = PACKAGE_ROOT
PAIRS = ((1201, 830), (1378, 274))
HOURS = 36
WALL_CAP = 300.
NATIVE_CAP = 240.
FINAL_RESERVE = 10.
MAX_BATCHES = 4
MAX_NEW_NNZ = 1048576
CERTIFICATE_CALL_CAP = 20.
CERTIFICATE_TOTAL_CAP = 120.
STATIONARITY_FAILURE = 'independent stationarity residual'
ENVIRONMENT = {
    'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
    'NUMEXPR_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def strict_json(path, *, compressed=False):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key: ' + key)
            result[key] = value
        return result
    with (gzip.open(path, 'rt') if compressed else open(path)) as stream:
        return json.load(stream, object_pairs_hook=unique)


def clean_json(value):
    """Nonfinite scalar info remains explicitly unavailable, never zero."""
    if isinstance(value, Fraction):
        return [str(value.numerator), str(value.denominator)]
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {'available': False, 'nonfinite': repr(value)}
    if isinstance(value, Path):
        return str(value)
    if value is None or type(value) in (str, int, float, bool):
        return value
    # NumPy scalars are small; arrays must have been moved to an NPZ artifact.
    if type(value).__module__.startswith('numpy') and hasattr(value, 'item') and not hasattr(value, '__len__'):
        return clean_json(value.item())
    raise TypeError('Unsupported JSON value ' + type(value).__name__)


def write_json(out, name, value, costs):
    tick = time.monotonic()
    require(Path(name).name == name, 'Artifact name must be a basename')
    path = Path(out) / name
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('w') as stream:
        json.dump(clean_json(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    temporary.replace(path)
    receipt = {'path': path.name, 'sha256': sha256(path), 'bytes': path.stat().st_size}
    costs['serialization_seconds'] = costs.get('serialization_seconds', 0.) + time.monotonic() - tick
    return receipt


def bundle(out, stem, value, costs):
    """Persist every ndarray separately and verify dtype/shape/all stored bits."""
    import numpy as np
    tick = time.monotonic()
    arrays = {}
    def split(item, key='root'):
        if isinstance(item, np.ndarray):
            require(item.dtype.kind in 'biuf', 'Object or nonnumeric artifact array')
            name = 'a' + str(len(arrays))
            arrays[name] = np.array(item, copy=True, order='C')
            return {'npz_array': name, 'field': key, 'dtype': item.dtype.str, 'shape': list(item.shape)}
        if isinstance(item, dict):
            return {str(k): split(v, key + '.' + str(k)) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [split(v, key + '[' + str(i) + ']') for i, v in enumerate(item)]
        return item
    document = split(value)
    receipt = {'bit_roundtrip_verified': True}
    if arrays:
        require(Path(stem).name == stem, 'Artifact stem must be a basename')
        path = Path(out) / (stem + '.npz')
        require(not path.exists(), 'Refuse to replace NPZ artifact')
        with path.open('xb') as stream:
            np.savez(stream, **arrays)
        with np.load(path, allow_pickle=False) as stored:
            require(set(stored.files) == set(arrays), 'NPZ array names drifted')
            for key, expected in arrays.items():
                actual = stored[key]
                require(actual.dtype == expected.dtype and actual.shape == expected.shape and actual.tobytes() == expected.tobytes(), 'NPZ bit readback mismatch: ' + key)
        receipt['arrays'] = {'path': path.name, 'sha256': sha256(path), 'bytes': path.stat().st_size,
                             'count': len(arrays), 'array_sha256': {key: hashlib.sha256(arr.tobytes()).hexdigest() for key, arr in arrays.items()}}
    costs['serialization_seconds'] = costs.get('serialization_seconds', 0.) + time.monotonic() - tick
    receipt['document'] = write_json(out, stem + '.json', document, costs)
    return receipt


def budget_gate(deadline, native_elapsed=0., *, now=None, reserve=FINAL_RESERVE):
    now = time.monotonic() if now is None else now
    require(finite(deadline) and finite(now) and finite(native_elapsed), 'Nonfinite budget state')
    require(0 <= native_elapsed <= NATIVE_CAP, 'Native cumulative ceiling exceeded')
    require(finite(reserve) and reserve >= 0, 'Invalid budget reserve')
    if now + reserve >= deadline or native_elapsed >= NATIVE_CAP:
        return False
    return True









FULL_COUNTS = ('signed_normal_rows', 'signed_security_rows', 'unsigned_security_pair_hours')











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


def persist_lower_certificate(out, current, certificate, costs):
    receipt = bundle(out, f'round-{current["round"]:02d}-exact-lower', certificate, costs)
    stored = strict_json(Path(out) / receipt['document']['path'])
    require(stored == clean_json(certificate), 'Exact lower certificate persistence readback mismatch')
    return receipt


def measured_lower_certificate(expected, solution, deadline, *, certified_lower, model, record, current, out, binding=None):
    """Proof, validation, persistence/readback and every failed attempt are charged."""
    costs = record['actual_stage_costs']
    used = costs.get('exact_lower_certificate_seconds', 0.)
    require(finite(used) and 0 <= used <= CERTIFICATE_TOTAL_CAP, 'Invalid certificate aggregate cost')
    tick = time.monotonic()
    certificate_deadline = min(deadline - FINAL_RESERVE, tick + CERTIFICATE_CALL_CAP,
                               tick + CERTIFICATE_TOTAL_CAP - used)
    current['lower_certificate_passed'] = False
    current['lower_certificate_deadline_monotonic'] = certificate_deadline
    current['lower_certificate_aggregate_before_seconds'] = used
    if certificate_deadline <= tick:
        current['lower_certificate_error'] = 'Certificate budget exhausted before attempt'
        return None
    require(record['certificate_attempts'] < 5, 'Maximum exact lower attempts exceeded')
    record['certificate_attempts'] += 1
    certificate = None
    try:
        certificate = certified_lower.certify(expected, solution['row_dual'],
                                              deadline_monotonic=certificate_deadline)
        if binding is not None:
            certificate['adaptive_binding'] = dict(binding)
        current['lower_certificate'] = certificate
        lower_certificate_gate(certificate, expected, solution['row_dual'], model=model)
        current['lower_certificate_artifact'] = persist_lower_certificate(out, current, certificate, costs)
        current['lower_certificate_persistence_readback_verified'] = True
    except Exception as error:
        current['lower_certificate_error'] = type(error).__name__ + ': ' + str(error)
        current['lower_certificate_failure_type'] = type(error).__name__
        current['lower_certificate_failure_message'] = str(error)
        current['lower_certificate_failure_code'] = getattr(error, 'code', None)
        current['lower_certificate_failure_details'] = getattr(error, 'details', None)
        current['lower_certificate_failure_helper_actual_seconds'] = getattr(error, 'actual_seconds', None)
        certificate = None
    finally:
        finished = time.monotonic()
        elapsed = finished - tick
        costs['exact_lower_certificate_seconds'] = used + elapsed
        current['lower_certificate_measured_seconds'] = elapsed
        current['lower_certificate_aggregate_after_seconds'] = used + elapsed
    if (finished >= certificate_deadline or elapsed > CERTIFICATE_CALL_CAP
            or costs['exact_lower_certificate_seconds'] > CERTIFICATE_TOTAL_CAP):
        current['lower_certificate_error'] = 'Certificate measured deadline or aggregate ceiling exceeded'
        certificate = None
    if certificate is not None and certificate['actual_seconds'] > elapsed:
        current['lower_certificate_error'] = 'Certificate internal time exceeds measured attempt'
        certificate = None
    current['lower_certificate_passed'] = certificate is not None
    return certificate
















