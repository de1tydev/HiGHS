"""Fresh, full source-listed-outage oracle over the frozen subset column map.

Reuse immutable v2 row_scan/selected_terms and exact cut certificate. The only
runtime factors come from the fresh generator call performed by the base class.
No real source factor/evaluation is permitted before independent release freeze.
"""
from __future__ import annotations
from current_scuc._paths import ROOT as PACKAGE_ROOT, source_path, source_sha, module as load_module, runtime_path, runtime_sha
import os
for _key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
             'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_key] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import sys
sys.dont_write_bytecode = True
from fractions import Fraction as Q
import hashlib
import importlib.util
import math
from pathlib import Path
import time
import numpy as np
from threadpoolctl import threadpool_limits, threadpool_info

ROOT = PACKAGE_ROOT
BASE_SHA = source_sha('heldout-projected-binding-v2/scope_oracle.py')

def _load(name, path, pin=None):
    if pin is not None and hashlib.sha256(path.read_bytes()).hexdigest() != pin:
        raise ValueError('Local source identity changed: ' + str(path))
    return load_module(name, path)

base = _load('_full_frozen_subset_oracle', ROOT/'scope_oracle.py', BASE_SHA)
full_projection = _load('_full_projection_adapter', Path(__file__).with_name('full_projection.py'))
v2 = base.v2
require, exact, up, down, rat = base.require, base.exact, base.up, base.down, base.rat
V2_SHA, GENERATOR_SHA, REQUIRED_PINS = base.V2_SHA, base.GENERATOR_SHA, base.REQUIRED_PINS
APPROVED_PAIRS, FULL_LODF_SHA = base.APPROVED_PAIRS, full_projection.FULL_LODF_SHA
deadline_check = full_projection.deadline_check


class PreparedOracle(base.PreparedOracle):
    """Subset mapping validated independently from full virtual security scope."""
    def __init__(self, data, expected, pairs, generator, pins, *, production_scope, deadline=None):
        started = time.monotonic(); deadline_check(deadline)
        super().__init__(data, expected, pairs, generator, pins, production_scope=production_scope)
        deadline_check(deadline)
        den = self.factorization['minimum_outage_denominator']
        require(not self.outages or (den is not None and math.isfinite(den) and den > 1e-9), 'Listed outage denominator check failed')
        self.full_scope = full_projection.build_full_scope(data, expected, self.hours, self.lodf, self.scope,
            pins=pins, production_scope=production_scope, deadline=deadline)
        self.full_scope_identity_sha256 = self.full_scope['identity_sha256']
        self.factorization.update(full_scope_identity_sha256=self.full_scope_identity_sha256,
            full_scope=self.full_scope, subset_mapping_scope=self.scope,
            fresh_full_lodf_pin_checked=bool(production_scope), archived_factors_used=False)
        self.times['full_virtual_scope_identity_seconds'] = time.monotonic()-started-self.prepare_seconds
        self.prepare_seconds = time.monotonic()-started

    def _check_identity(self, deadline):
        deadline_check(deadline); full_projection.verify_full_scope(self.full_scope)
        require(self.full_scope['identity_sha256'] == self.full_scope_identity_sha256, 'Full-scope identity drift')
        require(hashlib.sha256(self.lodf.tobytes(order='C')).hexdigest() == self.full_scope['lodf_binary64_C_sha256'], 'Full LODF coefficient mismatch')
        require(full_projection._array_hash(self.normal) == self.full_scope['normal_limit_binary64_sha256'] and
                full_projection._array_hash(self.emergency) == self.full_scope['emergency_limit_binary64_sha256'], 'Full rating bits mismatch')
        require(list(self.rated) == self.full_scope['ordered_monitored_indices'] and list(self.outages) == self.full_scope['ordered_outage_indices'], 'Full scope coverage identities changed')
        deadline_check(deadline)

    def _scan_hour(self, flow, qres, hour, deadline):
        """One streamed hour; pinned v2 itself scans bounded monitored blocks."""
        deadline_check(deadline)
        require(0 <= hour < self.hours and len(flow) == len(self.lines), 'Invalid full scan hour/flow shape')
        require(all(math.isfinite(float(v)) for v in flow), 'Nonfinite full scan flow')
        scan = v2.row_scan(flow, qres, self.rated, self.outages, self.lodf, self.normal[hour], self.emergency[hour])
        m = len(self.lines)
        require(all(np.asarray(scan[k]).shape == (m,) for k in ('lower', 'upper', 'kind', 'outage', 'sign', 'nominal')), 'Missing full scan line coverage')
        require(all(np.all(np.isfinite(scan[k])) for k in ('lower', 'upper', 'nominal')), 'Nonfinite full scan result')
        require(np.all(scan['lower'] >= 0) and np.all(scan['lower'] <= scan['upper']), 'Invalid full scan enclosure')
        receipt = dict(self.full_scope['coverage_by_hour'][hour])
        receipt.update(full_scope_identity_sha256=self.full_scope_identity_sha256,
            complete=True, scan_implementation_sha256=V2_SHA,
            monitored_indices_sha256=full_projection._array_hash(self.rated, '<i8'),
            outage_indices_sha256=full_projection._array_hash(self.outages, '<i8'))
        deadline_check(deadline)
        return scan, receipt

    def _check_hour_receipt(self, receipt, hour):
        expected = self.full_scope['coverage_by_hour'][hour]
        require(receipt.get('complete') is True and receipt.get('full_scope_identity_sha256') == self.full_scope_identity_sha256,
                'Missing full scan coverage receipt')
        require(all(receipt.get(k) == v for k, v in expected.items()), 'Full scan coverage count mismatch')
        require(receipt.get('scan_implementation_sha256') == V2_SHA and
                receipt.get('monitored_indices_sha256') == full_projection._array_hash(self.rated, '<i8') and
                receipt.get('outage_indices_sha256') == full_projection._array_hash(self.outages, '<i8'), 'Full scan coverage identity mismatch')

    def _check_coverage(self, records):
        require(len(records) == self.hours, 'Missing full scan hour coverage')
        for t, receipt in enumerate(records): self._check_hour_receipt(receipt, t)
        for key in ('signed_normal_rows', 'signed_security_rows'):
            require(sum(r[key] for r in records) == self.full_scope[key], 'Full scan aggregate coverage mismatch')
        require(sum(r['unsigned_security_pairs'] for r in records) == self.full_scope['unsigned_security_pair_hours'], 'Full scan pair-hour coverage mismatch')

    def evaluate(self, retained_values, deadline=None):
        started = time.monotonic(); deadline_check(deadline)
        with threadpool_limits(limits=1):
            require(all(v.get('num_threads', 1) == 1 for v in threadpool_info()), 'BLAS thread limit ineffective')
            return self._evaluate(retained_values, started, deadline)

    def check_lift(self, stored_original_vector, deadline=None):
        """Check all virtual rows of read-back binary64 lift, with Qres=0.

        This supplements, never replaces, the runner's unchanged base-matrix QA.
        Uses exact differences only once per monitored line/hour, not per pair.
        """
        started = time.monotonic(); self._check_identity(deadline)
        x = np.asarray(stored_original_vector)
        require(x.dtype == np.float64 and x.shape == (len(self.names),) and np.all(np.isfinite(x)), 'Nonfinite/incomplete stored original lift')
        coverage = []; worst = Q(0); worst_hour = worst_line = None
        for t in range(self.hours):
            deadline_check(deadline)
            scan, receipt = self._scan_hour([exact(v) for v in x[self.flow_indices[t]]], Q(0), t, deadline)
            self._check_hour_receipt(receipt, t); coverage.append(receipt)
            for l, j in zip(self.rated, self.over_indices[t]):
                # Upper-lower subtraction is exact rational, including cancellation.
                excess = max(Q(0), exact(scan['upper'][l])-exact(x[j]))
                if excess > worst: worst, worst_hour, worst_line = excess, t, l
        self._check_coverage(coverage); deadline_check(deadline)
        return dict(schema='network-projection-full-stored-lift-qa-v1', passed=worst <= exact(1e-5),
            full_scope_identity_sha256=self.full_scope_identity_sha256, full_scope_coverage_complete=True,
            signed_normal_rows=self.full_scope['signed_normal_rows'], signed_security_rows=self.full_scope['signed_security_rows'],
            unsigned_security_pair_hours=self.full_scope['unsigned_security_pair_hours'], coverage_by_hour=coverage,
            conservative_violation_exact=rat(worst), conservative_violation_upper=up(worst),
            tolerance=1e-5, worst_hour=worst_hour, worst_line=worst_line,
            worst_line_id=None if worst_line is None else self.lines[worst_line],
            stored_lift_binary64_sha256=hashlib.sha256(x.tobytes(order='C')).hexdigest(),
            zero_radius=True, unchanged_base_matrix_qa_required=True,
            endpoint_scope='original_base_dc_plus_full_literal_virtual_rows',
            upper_qualification='numerical full-scope primal witness when unchanged base QA also passes',
            physical_dc_lower_bound_certified=False, seconds=time.monotonic()-started)

    def _evaluate(self, retained_values, started, deadline=None):
        self._check_identity(deadline)
        x = self._retained_vector(retained_values)
        retained_bits = x[self.retained_indices].view(np.uint64).copy()
        self.evaluation_count += 1
        H, n, m = self.hours, len(self.buses), len(self.lines)
        theta_rows, flow_rows, over_rows, hour_records, cuts = [], [], [], [], []
        pis, constants, line_lower, line_upper = [], [], [], []
        gap_total = Q(0)
        raw_max = Q(0)
        lift_balance_max = Q(0)
        flow_equation_max = Q(0)
        coverage = []
        for t in range(H):
            deadline_check(deadline)
            raw = [exact(x[j]) - load for j, load in zip(self.shed_indices[t], self.loads[t])]
            for j, bus in zip(self.p_indices[t], self.generator_bus):
                raw[int(bus)] += exact(x[j])
            q, imbalance, reference_delta = v2.balanced_probe(raw)
            raw_max = max(raw_max, abs(imbalance))
            Fcert = v2.certificate_bound(self.source_F[t], q)
            theta = np.zeros(n)
            theta[1:] = self.lu.solve(np.asarray([float(v) for v in q[1:]]))
            f, forward_residual, qres = v2.forward_certificate(q, theta, self.endpoints, self.weights)
            scan, receipt = self._scan_hour(f, qres, t, deadline)
            self._check_hour_receipt(receipt, t)
            coverage.append(receipt)
            c, lh, selected = v2.selected_terms(scan, self.lodf, self.normal[t], self.emergency[t], self.rated, self.outages)
            rhs = v2.incidence_transpose([exact(w) * cc for w, cc in zip(self.weights, c)], self.endpoints, n)
            pi = np.zeros(n)
            if selected:
                pi[1:] = self.lu.solve(np.asarray([float(v) for v in rhs[1:]]))
            cert = v2.cut_certificate(c, lh, pi, self.endpoints, self.weights, self.path_upper,
                                      Fcert, self.loads[t], q)
            vlo = sum((exact(v) for v in scan['lower']), Q(0))
            vhi = sum((exact(v) for v in scan['upper']), Q(0))
            # Omitted columns are exactly zero on the source domain, but a
            # numerical native snapshot may be slightly outside that bound.
            # Charge its exact omission value and, when negative, weaken the
            # constant enough that actual sparse support cannot exceed v2's.
            fixed_omission = sum((exact(cert['pi'][bus]) * exact(x[j]) for bus, j in enumerate(self.shed_indices[t]) if self.fixed_zero_shed[t, bus]), Q(0))
            omission_debit = max(Q(0), -fixed_omission)
            emitted_constant_exact = exact(cert['constant']) + omission_debit
            emitted_constant = up(emitted_constant_exact)
            full_support = cert['emitted_cut_at_qstar'] - (exact(emitted_constant) - exact(cert['constant']))
            actual_sparse_support = full_support - fixed_omission
            require(actual_sparse_support <= cert['emitted_cut_at_qstar'], 'Omission correction failed to preserve probe support')
            gap = v2.PRICE * (vhi - actual_sparse_support)
            require(gap >= 0, 'Cut exceeds certified upper value')
            gap_total += gap
            for r in selected:
                r['monitored_id'] = self.lines[r['monitored']]
                r['outage_id'] = None if r['outage'] < 0 else self.lines[r['outage']]
            # Serialize original flows to binary64, then cover THEIR literal rows
            # as well as the balanced-query value enclosure. Retained p/shed stay.
            fhat = np.asarray([float(v) for v in f])
            fe = [exact(v) for v in fhat]
            # The unchanged v2 elementary outward scan starts at down(f), up(f).
            # float(f) lies in this interval too, so its upper covers the emitted
            # flow bits without an exact all-pair/hour Fraction loop.
            require(all(down(v) <= fv <= up(v) for v, fv in zip(f, fhat)), 'Serialized flow escaped input enclosure')
            over = np.array(scan['upper'], dtype=np.float64, copy=True)
            actual_lhs = v2.incidence_transpose(fe, self.endpoints, n)
            residual = [a - b for a, b in zip(raw, actual_lhs)]
            lift_balance_max = max(lift_balance_max, max(map(abs, residual)))
            flow_equation_max = max(flow_equation_max, max(abs(a - b) for a, b in zip(fe, f)))
            x[self.theta_indices[t]] = theta
            x[self.flow_indices[t]] = fhat
            x[self.over_indices[t]] = over[list(self.rated)]
            indices, coefficients = [], []
            for j, bus in zip(self.p_indices[t], self.generator_bus):
                value = float(cert['pi'][bus])
                if value != 0:
                    indices.append(int(j)); coefficients.append(value)
            for bus, j in enumerate(self.shed_indices[t]):
                value = float(cert['pi'][bus])
                if value != 0 and not self.fixed_zero_shed[t, bus]:
                    indices.append(int(j)); coefficients.append(value)
            cut = dict(hour=t, original_indices=np.asarray(indices, dtype=np.int64),
                       coefficients=np.asarray(coefficients, dtype=np.float64), upper=emitted_constant,
                       eta_coefficient=-1., nnz=len(indices) + 1)
            cuts.append(cut)
            # Since pi(reference)=0, the cut at raw p/s equals the synthetic
            # query cut. Fixed-zero omissions are valid on the original boxes.
            emitted_at_retained = sum((exact(a) * exact(x[j]) for j, a in zip(indices, coefficients)), Q(0)) - exact(emitted_constant)
            require(emitted_at_retained == actual_sparse_support, 'Retained cut/source coefficient mapping mismatch')
            hour_records.append(dict(hour=t,
                probe_label='synthetic_exactly_balanced_evaluation_only_not_original_feasible_upper',
                qstar=[rat(v) for v in q], raw_imbalance=rat(imbalance), reference_delta=rat(reference_delta),
                source_lift_balance_residual=[rat(v) for v in residual],
                Qplus=rat(sum((max(v, Q(0)) for v in q), Q(0))), F_source=rat(self.source_F[t]),
                F_certificate=rat(Fcert), probe_domain_excess=rat(Fcert - self.source_F[t]),
                forward_residual=[rat(v) for v in forward_residual], Qres=rat(qres), selected_rows=selected,
                c_sparse=[dict(line=l, value=rat(v)) for l, v in enumerate(c) if v],
                lambda_budget_max=1 if selected else 0,
                dual_residual=[rat(v) for v in cert['residual']], delta=rat(cert['delta']),
                lambda_h=rat(lh), pi_load=rat(cert['pi_load']), zeroed_pi_count=cert['zeroed_count'],
                v2_constant_before_upward_round=rat(cert['constant_exact_before_round']),
                v2_constant_hex=cert['constant'].hex(), v2_constant_rounding_loss=rat(cert['constant_rounding_loss']),
                constant_before_upward_round=rat(emitted_constant_exact),
                constant_hex=emitted_constant.hex(), constant_rounding_loss=rat(exact(emitted_constant) - emitted_constant_exact),
                value_lower_MW=rat(vlo), value_upper_MW=rat(vhi),
                v2_emitted_cut_at_qstar_MW=rat(cert['emitted_cut_at_qstar']),
                emitted_cut_at_qstar_MW=rat(full_support),
                emitted_cut_at_retained_MW=rat(emitted_at_retained),
                omitted_fixed_zero_shed_value=rat(fixed_omission),
                fixed_zero_omission_constant_debit=rat(omission_debit),
                support_gap_dollars=rat(gap), support_gap_dollars_upper=up(gap),
                maximum_excess_upper_MW=float(max(scan['upper'])), actual_cut_nnz=cut['nnz']))
            theta_rows.append(theta); flow_rows.append(fhat); over_rows.append(over)
            pis.append(cert['pi']); constants.append(emitted_constant)
            line_lower.append(scan['lower']); line_upper.append(scan['upper'])
        self._check_coverage(coverage)
        deadline_check(deadline)
        require(np.array_equal(retained_bits, x[self.retained_indices].view(np.uint64)), 'Recovery mutated retained values')
        require(np.all(np.isfinite(x)), 'Incomplete/nonfinite original lift')
        objective = math.fsum(float(c) * float(v) for c, v in zip(self.cost, x)) + self.offset
        require(math.isfinite(objective), 'Nonfinite recomputed original objective')
        elapsed = time.monotonic() - started
        report = dict(schema='network-projection-full-oracle-evaluation-v1', evaluation=self.evaluation_count,
            pins=self.pins, frozen_v2_sha256=V2_SHA, **self.scope,
            subset_mapping_pairs=[list(p) for p in self.pairs], certificate_valid=True,
            full_scope=self.full_scope, full_scope_identity_sha256=self.full_scope['identity_sha256'],
            full_scope_coverage_complete=True, coverage_by_hour=coverage,
            signed_normal_rows=self.full_scope['signed_normal_rows'],
            signed_security_rows=self.full_scope['signed_security_rows'],
            unsigned_security_pair_hours=self.full_scope['unsigned_security_pair_hours'],
            subset_mapping_scope=self.scope, endpoint_scope='original_base_dc_plus_full_literal_virtual_rows',
            support_gap_dollars=rat(gap_total), support_gap_dollars_upper=up(gap_total),
            support_gap_le_100_dollars=(gap_total <= 100), passed=(gap_total <= 100),
            cut_validity_domain='declared_literal_lodf_row_model', physical_dc_lower_bound_certified=False,
            original_source_feasible_upper_claimed=False, source_checker_required=True,
            eta_objective_coefficient=v2.PRICE, value_unit='summed shared overload MW',
            certificate_bound_rule='max(exact F_source, exact Qplus(qstar)); original source boxes unchanged',
            fresh_factorizations_this_evaluation=0, reused_factorizations_this_evaluation=2,
            fresh_factorizations_at_preparation=2, preparation_seconds=self.prepare_seconds,
            factor_reuse_policy='immutable geometry and two fresh source-equivalent factors within one charged arm',
            actual_cut_nnz=sum(row['nnz'] for row in cuts),
            maximum_excess_upper_MW=max(r['maximum_excess_upper_MW'] for r in hour_records),
            timing={'evaluation_seconds': elapsed}, hour_certificates=hour_records)
        lift = dict(values=x, theta_hat=np.asarray(theta_rows), flow_hat=np.asarray(flow_rows),
                    overload_upper=np.asarray(over_rows),
                    recomputed_original_objective=objective,
                    raw_balance_max_abs=rat(raw_max), raw_balance_max_abs_upper=up(raw_max),
                    source_nodal_balance_max_abs=rat(lift_balance_max), source_nodal_balance_max_abs_upper=up(lift_balance_max),
                    source_flow_equation_max_abs=rat(flow_equation_max), source_flow_equation_max_abs_upper=up(flow_equation_max),
                    network_residual_le_1e_5=(max(lift_balance_max, flow_equation_max) <= exact(1e-5)),
                    retained_bits_unchanged=True, source_checker_required=True, original_feasibility_claimed=False,
                    full_virtual_row_checker_required=True,
                    full_scope_identity_sha256=self.full_scope['identity_sha256'],
                    full_scope_scan_upper_used=True)
        arrays = dict(pi=np.asarray(pis), constant_up=np.asarray(constants),
                      line_value_lower=np.asarray(line_lower), line_value_upper=np.asarray(line_upper))
        return dict(certificate=report, cut_rows=cuts, original_network_lift=lift, arrays=arrays)


def prepare(data, expected, pairs, *, generator, pins, deadline=None):
    """Production preparation must be charged; pins are checked read receipts."""
    deadline_check(deadline)
    import current_scuc.heldout as heldout
    heldout.check_inputs(pins, data=data, expected=expected)
    require(tuple(pairs) == (), 'Held-out original mapping must be empty')
    require(base._digest(generator.__file__) == GENERATOR_SHA, 'Frozen generator implementation mismatch')
    with threadpool_limits(limits=1):
        require(all(v.get('num_threads', 1) == 1 for v in threadpool_info()), 'BLAS thread limit ineffective')
        return PreparedOracle(data, expected, pairs, generator, pins, production_scope=True, deadline=deadline)
