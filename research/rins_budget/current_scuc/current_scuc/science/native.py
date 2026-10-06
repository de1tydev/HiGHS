"""Same-object addCols/addRows LP edits using only pinned public C APIs."""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha

import ctypes as C
import time

import numpy as np

import current_scuc.family_adapter as adapter

core = adapter.emitter.load_pinned('_adaptive_lp_frozen_capi',
    'science/capi.py',
    source_sha('network-projection-lp-core-v1/capi.py'))
require, NativeError = adapter.require, core.NativeError


class PersistentLP(core.PersistentLP):
    def __init__(self, library_path, log_path, solver_random_seed=0):
        super().__init__(library_path, log_path, solver_random_seed)
        self._adaptive_binding = None
        self.partial_edit_failure = None
        try:
            fun = self.lib.Highs_addCols
            fun.restype = self.I
            fun.argtypes = [C.c_void_p, self.I, self.DP, self.DP, self.DP,
                           self.I, self.IP, self.IP, self.DP]
            provenance = core._helper().symbol_provenance(self.lib, ('Highs_addCols',))
            require(set(provenance) == {'Highs_addCols'}
                    and all(item['path'] == str(self.library_path)
                            and item['sha256'] == runtime_sha('library') for item in provenance.values()),
                    'Highs_addCols symbol DSO mismatch')
            self.identity['loaded_symbol_provenance'].update(provenance)
        except BaseException:
            self.destroy()
            raise

    def apply_batch(self, edit):
        """Preflight once, then apply both native edits without an interim solve.

        A partial edit, name failure, invalidation failure or readback mismatch
        destroys the handle. Caller ledger adoption is permitted only on return.
        """
        self._alive()
        require(self.expected is not None and self.last_run is not None
                and self.last_run['version'] == self.version
                and self.last_run['run_status'] == 0 and self.last_run['model_status'] == 7,
                'Composite edit requires a successfully solved current model')
        staged = adapter.verify_edit(self.expected, edit)
        before_binding = (staged['metadata']['matrix_identity'], staged['metadata']['map_hash'],
                          staged['state'].evaluations, staged['state'].admitted)
        require(self._adaptive_binding is None or self._adaptive_binding == before_binding,
                'Stale adaptive edit ledger')
        before, intermediate, final = (staged[key] for key in ('before', 'intermediate', 'final'))
        batch = staged['batch']
        ncol = final['num_col'] - before['num_col']
        nrow = final['num_row'] - before['num_row']
        old_version, handle, start = self.version, self.handle, time.monotonic()
        reads, statuses, calls = {}, {}, 0
        attempted = []
        stage = 'before_readback'
        self.partial_edit_failure = None
        try:
            # Verify the actual current matrix too, before the first mutation.
            reads['before'] = self._verify(before)
            if ncol:
                tails = [np.ascontiguousarray(intermediate[key][before['num_col']:], dtype=np.float64)
                         for key in ('col_cost', 'col_lower', 'col_upper')]
                starts = np.zeros(ncol + 1, dtype=np.int32)
                index, value = np.empty(0, dtype=np.int32), np.empty(0, dtype=np.float64)
                stage = 'add_columns'
                attempted.append('Highs_addCols')
                self._call('Highs_addCols', ncol, *(self._ptr(a) for a in tails),
                           0, self._ptr(starts), self._ptr(index), self._ptr(value))
                calls += 1
                self.version += 1
                self.last_run = None
                stage = 'name_columns'
                for j, name in enumerate(intermediate['col_names'][before['num_col']:]):
                    self._call('Highs_passColName', before['num_col'] + j, name.encode())
                stage = 'column_status_invalidation'
                statuses['after_columns'] = int(self.lib.Highs_getModelStatus(self.handle))
                require(statuses['after_columns'] == 0, 'Column addition failed to invalidate old model status')
                stage = 'intermediate_readback'
                reads['intermediate'] = self._verify(intermediate)
            if nrow:
                stage = 'add_rows'
                attempted.append('Highs_addRows')
                self._call('Highs_addRows', nrow, self._ptr(batch['lower']), self._ptr(batch['upper']),
                    len(batch['value']), self._ptr(batch['starts']), self._ptr(batch['index']),
                    self._ptr(batch['value']))
                calls += 1
                self.version += 1
                self.last_run = None
                stage = 'name_rows'
                for j, name in enumerate(batch['names']):
                    self._call('Highs_passRowName', before['num_row'] + j, name.encode())
                stage = 'row_status_invalidation'
                statuses['after_rows'] = int(self.lib.Highs_getModelStatus(self.handle))
                require(statuses['after_rows'] == 0, 'Row addition failed to invalidate old model status')
            stage = 'final_readback'
            reads['final'] = self._verify(final)
            if not calls:
                # Empty support batches change the ledger, not the native matrix.
                self.version += 1
                self.last_run = None
            self.expected = final
            self._adaptive_binding = (staged['next_metadata']['matrix_identity'],
                staged['next_metadata']['map_hash'], staged['next_state'].evaluations,
                staged['next_state'].admitted)
            require(self.handle == handle, 'Native object changed during composite edit')
        except BaseException as error:
            self.last_run = None
            self.partial_edit_failure = dict(stage=stage, error_type=type(error).__name__,
                error=str(error), attempted_structural_calls=attempted,
                successful_structural_calls=calls, previous_version=old_version,
                version=self.version, before_matrix_identity=staged['metadata']['matrix_identity'],
                intended_matrix_identity=staged['next_metadata']['matrix_identity'])
            try:
                self.destroy()
            finally:
                self.partial_edit_failure['handle_destroyed'] = not bool(self.handle)
            raise
        return dict(previous_version=old_version, version=self.version, same_handle=True,
            added_columns=ncol, added_rows=nrow, added_nonzeros=len(batch['value']),
            native_edit_calls=calls, old_solution_invalidated=True,
            native_status_invalidated=bool(calls), statuses=statuses, readbacks=reads,
            readback=reads['final'],
            matrix_identity=staged['next_metadata']['matrix_identity'],
            map_hash=staged['next_metadata']['map_hash'],
            composite_edit_and_readback_seconds=time.monotonic() - start,
            basis_reuse='supported automatic same-object basis extension; no preserved factorization claim')
