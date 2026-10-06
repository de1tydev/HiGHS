"""Pure continuous adapter around the immutable adaptive emitter.

Staging never edits a caller's model, metadata, or activation ledger. Adopt the
returned next_metadata/next_state only after native.apply_batch succeeds.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha

import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
from types import MappingProxyType

import numpy as np
from scipy.sparse import csc_matrix, hstack

ROOT = PACKAGE_ROOT
EMITTER_SHA = source_sha('adaptive-line-emitter-v1/emitter.py')
ADAPTER_SHA = source_sha('heldout-projected-binding-v2/family_model_adapter.py')
TOTAL_NNZ_CAP = 1756901


def _emitter():
    path = ROOT / 'science/emitter.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != EMITTER_SHA:
        raise ValueError('Local adaptive emitter changed')
    return load_module('emitter', path)


emitter = _emitter()
frozen = emitter.load_pinned('_adaptive_lp_frozen_model_adapter',
    'family_model_adapter.py', ADAPTER_SHA)
model, fp = frozen.model, frozen.fp
require = emitter.require
line_caps = frozen.line_caps
matrix_identity = frozen.matrix_identity


def _check_context(expected, metadata, state):
    """Check the continuous matrix, append-only map and growth accounting."""
    e = model.validate_model(expected)
    require(not np.any(e['integrality']), 'Adaptive LP must be all continuous')
    fp.verify_full_scope(metadata['full_scope'])
    require(metadata['full_scope_identity_sha256'] == metadata['full_scope']['identity_sha256']
            == metadata['scope_identity'] == state.scope_identity, 'Full-scope identity drift')
    require(metadata['source_identity'] == state.source_identity, 'Source identity drift')
    ids = np.asarray(metadata['retained_original_columns'])
    require(ids.dtype.kind in 'iu' and ids.shape == (state.nret,)
            and len(set(ids.tolist())) == len(ids)
            and np.all(ids >= 0) and np.all(ids < metadata['original_num_col']),
            'Invalid retained original map')
    require(metadata['original_to_retained'] == {int(j): i for i, j in enumerate(ids)},
            'Retained inverse map mismatch')
    inverse = np.full(metadata['original_num_col'], -1, dtype=np.int32)
    inverse[ids] = np.arange(len(ids), dtype=np.int32)
    require(np.array_equal(metadata['original_to_projected'], inverse)
            and np.array_equal(metadata['removed_columns'], np.flatnonzero(inverse < 0)),
            'Original restoration map drift')
    require(metadata['hours'] == state.hours
            and tuple(metadata['rated']) == state.rated
            == tuple(metadata['full_scope']['ordered_monitored_indices'])
            and tuple(metadata['fixed_columns']) == state.fixed
            and tuple(metadata['balance_columns']) == state.fixed,
            'Activation map dimensions drift')
    require(len(set(state.active)) == len(state.active)
            and set(state.active).issubset(state.rated)
            and len(state.active) <= emitter.ACTIVE_CAP, 'Active-line cap/map drift')
    require(0 <= state.admitted <= emitter.MAX_BATCHES
            and state.admitted <= state.evaluations <= emitter.MAX_EVALUATIONS,
            'Activation count drift')
    require(metadata['base_num_col'] == state.nret + 2
            and metadata['projected_num_col'] == state.num_col == e['num_col'],
            'Dynamic column map mismatch')
    require(metadata['balance_nnz'] == metadata['balance_nonzeros']
            and metadata['retained_matrix_nnz'] == metadata['retained_matrix_nonzeros'],
            'Nonzero metadata aliases drift')
    require(len(metadata['lineage']) == state.admitted
            and sum(item['nnz'] for item in metadata['lineage']) == state.cut_nnz,
            'Activation lineage/count drift')
    require(e['num_row'] == metadata['base_row_count'] + sum(item['rows'] for item in metadata['lineage'])
            and e['num_row'] <= metadata['base_row_count'] + emitter.MAX_BATCHES * state.hours * emitter.ACTIVE_CAP,
            'Total row growth guard')
    require(e['num_nz'] == metadata['retained_matrix_nnz'] + metadata['balance_nnz'] + metadata.get('fixed_family_nnz', 0) + state.cut_nnz
            and metadata['balance_nnz'] + state.cut_nnz <= emitter.NNZ_CAP
            and e['num_nz'] <= TOTAL_NNZ_CAP, 'Total nonzero growth guard')
    if 'first_start_family' in metadata:
        import current_scuc.first_start as first_start
        family = metadata['first_start_family']
        require(metadata['fixed_family_nnz'] == family['nonzeros'] and
                metadata['base_row_count'] == family['row_start'] + family['row_count'], 'Fixed-family accounting drift')
        require(family['source_sha256'] == metadata['source_identity'] and
                family['source_object_sha256'] == metadata['full_scope']['source_object_sha256'], 'Fixed-family source drift')
        first_start.validate(e, family, model)
    else:
        require(metadata.get('fixed_family_nnz', 0) == 0 and e['num_nz'] <= 1656515, 'Uninstalled fixed-family accounting')
    require(metadata['map_hash'] == state.map_hash
            and metadata['matrix_identity'] == matrix_identity(e, metadata, state),
            'Current matrix/map identity mismatch')
    return e


def make_base(original, source, hours, pairs, lodf, source_identity, full_scope):
    """Return the empty, explicitly continuous adaptive base and fresh ledger."""
    fp.verify_full_scope(full_scope)
    rebuilt = fp.build_full_scope(source, original, hours, lodf,
        full_scope['subset_mapping_scope'], pins=full_scope['pins'],
        production_scope=full_scope['production_scope'])
    require(rebuilt == full_scope, 'Adaptive source/full-scope mismatch')
    intended, metadata = frozen.make_base(original, source, hours, pairs, lodf,
        source_identity, full_scope['identity_sha256'])
    ids = metadata['retained_original_columns']
    state = emitter.Activation(len(ids), hours, metadata['rated'], source_identity,
        full_scope['identity_sha256'])
    # Frozen make_base intentionally restores original types. This wrapper is LP only.
    original_retained_hash = metadata['retained_integrality_sha256']
    original_retained_count = metadata['retained_integer_count']
    intended['integrality'] = np.zeros(intended['num_col'], dtype=np.int32)
    inverse = np.full(metadata['original_num_col'], -1, dtype=np.int32)
    inverse[ids] = np.arange(len(ids), dtype=np.int32)
    metadata.update(schema='adaptive-line-continuous-lp-adapter/v1',
        hours=hours, exact_pairs=tuple(tuple(pair) for pair in pairs),
        full_scope=copy.deepcopy(full_scope), full_scope_identity_sha256=full_scope['identity_sha256'],
        original_num_row=original['num_row'], original_to_projected=inverse,
        removed_columns=np.flatnonzero(inverse < 0).astype(np.int32),
        balance_columns=state.fixed, balance_nonzeros=metadata['balance_nnz'],
        retained_matrix_nonzeros=metadata['retained_matrix_nnz'],
        projected_num_col=intended['num_col'], projected_hashes=model.model_hashes(intended),
        original_integer_columns_cleared=int(np.count_nonzero(original['integrality'])),
        original_integer_count=int(np.count_nonzero(original['integrality'])),
        original_retained_integer_count=original_retained_count,
        original_retained_integrality_sha256=original_retained_hash,
        retained_integer_count=0, retained_integrality_sha256=model.digest(intended['integrality'][:state.nret]),
        all_continuous=True, subset_mapping_readback_only=True,
        full_mps_readback_claimed=False, physical_dc_lower_bound_certified=False)
    metadata['matrix_identity'] = matrix_identity(intended, metadata, state)
    _check_context(intended, metadata, state)
    return intended, metadata, state


def restore_retained(x, metadata):
    """Restore original order, retaining every binary64 bit at dynamic sizes."""
    point = np.asarray(x)
    require(point.dtype == np.float64 and point.shape == (metadata['projected_num_col'],)
            and np.all(np.isfinite(point)), 'Invalid dynamic projected point')
    ids = np.asarray(metadata['retained_original_columns'], dtype=np.int32)
    require(len(set(ids.tolist())) == len(ids) and np.all(ids >= 0)
            and np.all(ids < metadata['original_num_col'])
            and len(ids) + 2 <= len(point), 'Invalid retained restoration map')
    restored = np.full(metadata['original_num_col'], np.nan, dtype=np.float64)
    restored[ids] = point[:len(ids)]
    require(restored[ids].tobytes() == point[:len(ids)].tobytes(), 'Retained mapping changed bits')
    return restored


def stage_batch(expected, metadata, state, token, rows, caps):
    """Validate a full edit on copies; return intermediate/final models and CSR."""
    before = copy.deepcopy(_check_context(expected, metadata, state))
    prior_metadata, prior_state = copy.deepcopy(metadata), copy.deepcopy(state)
    require(isinstance(token, MappingProxyType), 'Mutable/unissued activation token')
    require(token['admit'], 'Terminal evaluation cannot append columns/rows')
    rows, caps = copy.deepcopy(list(rows)), dict(caps)
    slots = tuple(token['positive_slots'])
    require(len(set(slots)) == len(slots)
            and all(type(l) is int and l in state.rated and type(t) is int and 0 <= t < state.hours
                    for l, t in slots), 'Malformed positive support slots')
    require(tuple(token['new']) == tuple(sorted({l for l, t in slots} - set(state.active))),
            'Partial positive-line activation forbidden')
    for row in rows:
        require(type(row['line']) is int and type(row['hour']) is int
                and all(type(j) is int or isinstance(j, np.integer) for j in row['original_indices'])
                and math.isfinite(row['upper']), 'Malformed support serialization')
    next_state = copy.deepcopy(state)
    final, next_metadata = frozen.append_batch(before, copy.deepcopy(metadata), next_state,
        token, rows, caps)
    next_metadata['projected_num_col'] = final['num_col']
    next_metadata['projected_hashes'] = model.model_hashes(final)
    _check_context(final, next_metadata, next_state)
    added = final['num_col'] - before['num_col']
    intermediate = dict(before)
    for key in ('col_lower', 'col_upper', 'col_cost', 'integrality'):
        intermediate[key] = final[key].copy()
    intermediate['col_names'] = list(final['col_names'])
    intermediate = frozen._install_matrix(intermediate,
        hstack([model.matrix(before), csc_matrix((before['num_row'], added))], format='csc'))
    require(intermediate['num_nz'] == before['num_nz'], 'New columns must have zero nonzeros')
    bottom = model.matrix(final)[before['num_row']:, :].tocsr()
    batch = dict(lower=final['row_lower'][before['num_row']:].copy(),
        upper=final['row_upper'][before['num_row']:].copy(),
        starts=bottom.indptr.astype(np.int32), index=bottom.indices.astype(np.int32),
        value=bottom.data.copy(), names=final['row_names'][before['num_row']:])
    return dict(schema='adaptive-line-staged-edit/v1', before=before,
        metadata=prior_metadata, state=prior_state, token=token, rows=rows, caps=caps,
        intermediate=intermediate, final=final, next_metadata=next_metadata,
        next_state=next_state, batch=batch)


def _same(left, right):
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        return (isinstance(left, np.ndarray) and isinstance(right, np.ndarray)
                and left.dtype == right.dtype and left.shape == right.shape
                and left.tobytes() == right.tobytes())
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same(left[key], right[key]) for key in left)
    if isinstance(left, (tuple, list)) and isinstance(right, (tuple, list)):
        return type(left) is type(right) and len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def verify_edit(current, edit):
    """Reconstruct and compare every precomputed model, ledger, map and CSR."""
    require(edit.get('schema') == 'adaptive-line-staged-edit/v1', 'Invalid edit schema')
    require(model.model_hashes(model.validate_model(current)) == model.model_hashes(edit['before']),
            'Stale native edit model')
    rebuilt = stage_batch(edit['before'], edit['metadata'], edit['state'], edit['token'],
        edit['rows'], edit['caps'])
    for key in ('intermediate', 'final'):
        require(model.model_hashes(model.validate_model(edit[key])) == model.model_hashes(rebuilt[key]),
                'Precomputed edit model mismatch: ' + key)
    require(_same(edit['next_metadata'], rebuilt['next_metadata']), 'Precomputed next metadata mismatch')
    require(_same(vars(edit['next_state']), vars(rebuilt['next_state'])), 'Precomputed next state mismatch')
    require(_same(edit['batch'], rebuilt['batch']), 'Precomputed CSR batch mismatch')
    return rebuilt
