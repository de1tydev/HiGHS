#!/usr/bin/env python3
"""One fresh charged candidate for the complete source-listed-outage LP gate.

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
PAIRS = ()
HOURS = 36
WALL_CAP = 300.
NATIVE_CAP = 240.
FINAL_RESERVE = 10.
MAX_BATCHES = 8
MAX_NEW_NNZ = 281319
CERTIFICATE_CALL_CAP = 20.
CERTIFICATE_TOTAL_CAP = 120.
STATIONARITY_FAILURE = 'independent stationarity residual'
import current_scuc.heldout as heldout
INPUT_PINS = heldout.LazyPins()

REQUIRED_PAYLOAD = ()
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



FULL_COUNTS = ('signed_normal_rows', 'signed_security_rows', 'unsigned_security_pair_hours')


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


def persist_lift(out, round_index, lift, costs):
    """Read the original primal back from disk; this vector alone enters upper QA."""
    import numpy as np
    receipt = bundle(out, f'round-{round_index:02d}-original-lift', {'values': lift}, costs)
    tick = time.monotonic()
    document = strict_json(Path(out) / receipt['document']['path'])
    field = document['values']
    with np.load(Path(out) / receipt['arrays']['path'], allow_pickle=False) as archive:
        stored = np.array(archive[field['npz_array']], copy=True)
    require(stored.dtype == lift.dtype and stored.shape == lift.shape
            and stored.tobytes() == lift.tobytes(), 'Original lift readback mismatch')
    stored.setflags(write=False)
    costs['serialization_seconds'] += time.monotonic() - tick
    receipt['readback_values_sha256'] = hashlib.sha256(stored.tobytes()).hexdigest()
    return stored, receipt


def point_components(original, values):
    """Cheap source-cost diagnostics; no replacement for full original QA."""
    names = original.get('col_names', [])
    if len(names) != len(values):
        return {'available': False}
    result = {'available': True}
    for label, prefix in (('source_shedding_mw_sum', 'shed_'),
                          ('source_shared_overflow_mw_sum', 'over_'),
                          ('source_reserve_shortfall_mw_sum', 'short_')):
        selected = [j for j, name in enumerate(names) if name.startswith(prefix)]
        result[label] = math.fsum(float(values[j]) for j in selected)
        result[label.replace('_mw_sum', '_cost_sum')] = math.fsum(
            float(original['col_cost'][j]) * float(values[j]) for j in selected)
    return result



















def load_modules():
    from current_scuc.science import model, capi, qa
    from current_scuc import full_projection, full_oracle
    return model, full_projection, capi, qa, full_oracle


def verify_loaded_runtime(identities):
    """Ensure numerical imports and actual BLAS DSOs are the pinned files."""
    from threadpoolctl import threadpool_info
    pinned = {item['path']: item['sha256'] for item in identities}
    loaded = {}
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] in ('numpy', 'scipy', 'threadpoolctl') and getattr(module, '__file__', None):
            path = str(Path(module.__file__).resolve())
            require(path in pinned and sha256(path) == pinned[path], 'Unpinned loaded numerical module: ' + name)
            loaded[path] = pinned[path]
    pools = threadpool_info()
    for pool in pools:
        path = str(Path(pool['filepath']).resolve())
        require(path in pinned and sha256(path) == pinned[path], 'Unpinned loaded numerical DSO')
        require(pool.get('num_threads') == 1, 'Numerical BLAS is not single-threaded')
        loaded[path] = pinned[path]
    return {'loaded_file_count': len(loaded), 'files': loaded, 'threadpools': pools}


def output_directory(path):
    out = Path(path).resolve()
    require(not out.is_relative_to(ROOT) and not out.exists(), 'Worker output must be fresh and outside source package')
    out.mkdir(parents=True)
    return out




