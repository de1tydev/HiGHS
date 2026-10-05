"""Synthetic-only full oracle and eta tests. No source files or native LP calls."""
import copy
from fractions import Fraction as Q
import importlib.util
import math
from pathlib import Path
import sys
import time
import unittest
from unittest import mock
import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import oracle as o
import full_projection as fp
from fixtures import fixture, prepare_tiny, tiny_exact_flow, exact_scoped_value


def all_pairs(p):
    return tuple((l, k) for l in p.rated for k in p.outages if l != k)


def full_value(flow, p, t=0):
    # Explicit signed-row matrix evaluation, with one common slack per line.
    required = [Q(0)]*len(p.lines)
    signed = 0
    for l in p.rated:
        if math.isfinite(p.normal[t, l]):
            for s in (-1, 1):
                required[l] = max(required[l], s*flow[l]-o.exact(p.normal[t, l])); signed += 1
        for k in p.outages:
            if k != l and math.isfinite(p.emergency[t, l]):
                for s in (-1, 1):
                    required[l] = max(required[l], s*flow[l]+s*o.exact(p.lodf[l, k])*flow[k]-o.exact(p.emergency[t, l])); signed += 1
    return sum(required, Q(0)), required, signed


class FullOracleTests(unittest.TestCase):
    def test_scope_counts_zero_lodf_multiplicity_and_self_exclusion(self):
        p, x, _, _ = prepare_tiny(hours=2, lodf=np.zeros((3, 3)))
        c = p.full_scope['counts']
        self.assertEqual(c['allowed_pairs_per_hour'], 4)
        self.assertEqual(c['unsigned_security_pair_hours'], 8)
        self.assertEqual(c['signed_security_rows'], 16)
        self.assertEqual(c['signed_normal_rows'], 8)
        self.assertEqual(p.scope['seed_signed_rows'], 8)
        self.assertNotEqual(p.scope['row_scope_sha256'], p.full_scope_identity_sha256)
        result = p.evaluate(x)
        self.assertEqual(result['certificate']['signed_security_rows'], 16)
        self.assertEqual(result['certificate']['coverage_by_hour'][0]['self_excluded_pairs'], 2)
        self.assertTrue(p.check_lift(result['original_network_lift']['values'])['passed'])

    def test_full_includes_cross_pairs_and_retains_zero_pair_identity(self):
        d = np.array([[-1., 0., 100.], [100., -1., 0.], [0., 0., -1.]])
        p, x, _, _ = prepare_tiny(hours=1, lodf=d)
        scan, _ = p._scan_hour([Q(1), Q(2), Q(3)], Q(0), 0, None)
        subset = o.base.row_scan([Q(1), Q(2), Q(3)], Q(0), p.rated, p.pairs, p.lodf, p.normal[0], p.emergency[0])
        self.assertGreater(sum(scan['upper']), sum(subset['upper'])+390)
        self.assertEqual(p.full_scope['counts']['unsigned_security_pair_hours'], 4)
        p2, _, _, _ = prepare_tiny(hours=1, lodf=d, pairs=((0, 1),))
        self.assertEqual(p2.full_scope['counts']['unsigned_security_pair_hours'], 4)
        self.assertNotEqual(p2.full_scope_identity_sha256, p.full_scope_identity_sha256)

    def test_missing_normal_emergency_and_no_eligible_outage(self):
        d, e, g = fixture(hours=2)
        # Scope/cap standalone handles varying masks and all absent limits.
        d['Transmission lines']['l0']['Normal flow limit (MW)'] = [math.inf, .25]
        d['Transmission lines']['l1']['Emergency flow limit (MW)'] = [math.inf, .25]
        d['Contingencies'] = {'only': {'Affected lines': ['l0']}}
        lines, rated, outages, normal, emergency = fp.source_scope_arrays(d, 2)
        records = fp.coverage_records(2, rated, outages, normal, emergency)
        self.assertEqual([r['signed_normal_rows'] for r in records], [2, 4])
        self.assertEqual([r['signed_security_rows'] for r in records], [0, 2])
        bounds, proof = fp.full_eta_caps(d, 2, g.lodf)
        item = next(r for r in proof['maximum_absolute_lodf'] if r['line'] == 0)
        self.assertFalse(item['has_eligible_outage'])
        d['Contingencies'] = {}
        _, proof = fp.full_eta_caps(d, 2, g.lodf)
        self.assertTrue(all(not r['has_eligible_outage'] for r in proof['maximum_absolute_lodf']))

    def test_shared_slack_full_matrix_interval_and_cut_grid(self):
        p, x, _, _ = prepare_tiny(hours=1)
        result = p.evaluate(x); rec = result['certificate']['hour_certificates'][0]
        q = [Q(*map(int, v)) for v in rec['qstar']]
        phi, _, signed = full_value(tiny_exact_flow(q, p.endpoints, p.weights), p)
        self.assertEqual(signed, p.full_scope['counts']['signed_soft_rows'])
        self.assertLessEqual(Q(*map(int, rec['value_lower_MW'])), phi)
        self.assertGreaterEqual(Q(*map(int, rec['value_upper_MW'])), phi)
        pi = list(map(o.exact, result['arrays']['pi'][0])); C = o.exact(result['arrays']['constant_up'][0])
        checked = 0
        for a in range(-6, 7):
            for b in range(-6, 7):
                q = [Q(a, 2), Q(b, 2), Q(-a-b, 2)]
                if sum((max(v, Q(0)) for v in q), Q(0)) > p.source_F[0]: continue
                phi, _, _ = full_value(tiny_exact_flow(q, p.endpoints, p.weights), p)
                support = sum((v*(z+load) for v, z, load in zip(pi, q, p.loads[0])), Q(0))-C
                self.assertLessEqual(support, phi); checked += 1
        self.assertGreater(checked, 100)
        self.assertEqual(rec['lambda_budget_max'], 1)
        self.assertEqual(len({r['monitored'] for r in rec['selected_rows']}), len(rec['selected_rows']))

    def test_full_caps_dominate_every_explicit_pair_and_shared_cost(self):
        data, _, g = fixture(hours=2)
        g.lodf[0, 2] = 21.; g.lodf[1, 0] = -17.
        bounds, proof = fp.full_eta_caps(data, 2, g.lodf)
        lines, rated, outages, normal, emergency = fp.source_scope_arrays(data, 2)
        for t in range(2):
            F = Q(3); brute = Q(0)
            for l in rated:
                brute += max([Q(0), F-o.exact(normal[t, l])] + [(1+abs(o.exact(g.lodf[l, k])))*F-o.exact(emergency[t, l]) for k in outages if k != l])
            self.assertEqual(Q(*map(int, proof['records'][t]['Ueta_exact'])), brute)
            self.assertGreaterEqual(o.exact(bounds[t]), brute)
            summed_outage_slacks = sum((max(Q(0), (1+abs(o.exact(g.lodf[l, k])))*F-o.exact(emergency[t, l])) for l in rated for k in outages if k != l), Q(0))
            self.assertLess(brute, summed_outage_slacks)
        # All corners of the source flow box satisfy the per-line shared cap.
        p, _, _, _ = prepare_tiny(hours=1, lodf=g.lodf)
        for f0 in (-3, 0, 3):
            for f1 in (-3, 0, 3):
                for f2 in (-3, 0, 3):
                    value, _, _ = full_value([Q(f0), Q(f1), Q(f2)], p)
                    self.assertLessEqual(value, o.exact(bounds[0]))

    def test_serialized_flow_lift_upper_covers_exact_virtual_rows(self):
        p, x, e, _ = prepare_tiny(hours=2)
        x[p.names.index('sc_g0_0')] = -0.
        result = p.evaluate(x); y = result['original_network_lift']['values']
        np.testing.assert_array_equal(x[p.retained_indices].view(np.uint64), y[p.retained_indices].view(np.uint64))
        self.assertEqual(result['original_network_lift']['recomputed_original_objective'], math.fsum(c*v for c, v in zip(e['col_cost'], y)))
        for t in range(p.hours):
            _, required, _ = full_value([o.exact(v) for v in y[p.flow_indices[t]]], p, t)
            for l, j in zip(p.rated, p.over_indices[t]): self.assertGreaterEqual(o.exact(y[j]), required[l])
        self.assertTrue(p.check_lift(y)['passed'])
        self.assertTrue(result['certificate']['full_scope_coverage_complete'])

    def test_arbitrary_exact_input_interval_covers_rounded_values(self):
        p, _, _, _ = prepare_tiny(hours=1)
        values = [Q(1, 3), Q(-2, 7), Q(11, 13)]
        scan, _ = p._scan_hour(values, Q(1, 10**14), 0, None)
        _, needs, _ = full_value([o.exact(float(v)) for v in values], p)
        for l in p.rated: self.assertGreaterEqual(o.exact(scan['upper'][l]), needs[l])

    def test_stored_lift_tamper_nan_and_missing_coverage_rejected(self):
        p, x, _, _ = prepare_tiny(hours=2)
        y = p.evaluate(x)['original_network_lift']['values']
        bad = y.copy(); bad[p.over_indices[0, 0]] -= .01
        check = p.check_lift(bad)
        self.assertFalse(check['passed']); self.assertGreater(check['conservative_violation_upper'], .009)
        self.assertEqual((check['worst_hour'], check['worst_line']), (0, 0))
        bad = y.copy(); bad[p.flow_indices[0, 0]] = math.nan
        with self.assertRaisesRegex(ValueError, 'Nonfinite'): p.check_lift(bad)
        scan_original = p._scan_hour
        def missing(*args):
            scan, receipt = scan_original(*args); receipt['unsigned_security_pairs'] -= 1
            return scan, receipt
        with mock.patch.object(p, '_scan_hour', missing):
            with self.assertRaisesRegex(ValueError, 'coverage'): p.check_lift(y)
            with self.assertRaisesRegex(ValueError, 'coverage'): p.evaluate(x)
        with self.assertRaisesRegex(ValueError, 'hour coverage'): p._check_coverage([])
        def nonfinite(*args):
            scan, receipt = scan_original(*args); scan['upper'][0] = math.inf
            return scan, receipt
        with mock.patch.object(p, '_scan_hour', nonfinite):
            with self.assertRaises(ValueError): p.check_lift(y)

    def test_deadline_coefficient_identity_and_scope_drift_rejected(self):
        p, x, _, _ = prepare_tiny(hours=1)
        y = p.evaluate(x)['original_network_lift']['values']
        with self.assertRaises(TimeoutError): p.check_lift(y, deadline=time.monotonic()-1)
        with self.assertRaises(TimeoutError): p.evaluate(x, deadline=time.monotonic()-1)
        with self.assertRaises(TimeoutError): fp.full_eta_caps(fixture()[0], 2, p.lodf, deadline=time.monotonic()-1)
        with mock.patch.object(p, 'outages', p.outages[:-1]):
            with self.assertRaisesRegex(ValueError, 'coverage identities'): p.check_lift(y)
        p.lodf.setflags(write=True); p.lodf[0, 2] += .1; p.lodf.setflags(write=False)
        with self.assertRaisesRegex(ValueError, 'coefficient mismatch'): p.check_lift(y)

    def test_finite_source_F_and_zero_shed_omission_charge_preserved(self):
        p, x, _, gen = prepare_tiny(hours=1, zero_shed=True)
        for value in (1e-12, -1e-12):
            x[p.shed_indices[0, 2]] = value
            result = p.evaluate(x); rec = result['certificate']['hour_certificates'][0]
            read = lambda k: Q(*map(int, rec[k]))
            self.assertEqual(read('fixed_zero_omission_constant_debit'), max(Q(0), -read('omitted_fixed_zero_shed_value')))
            self.assertLessEqual(read('emitted_cut_at_retained_MW'), read('v2_emitted_cut_at_qstar_MW'))
            self.assertEqual(read('F_certificate'), max(read('F_source'), read('Qplus')))
            self.assertNotIn(p.shed_indices[0, 2], result['cut_rows'][0]['original_indices'])
        self.assertEqual(gen.calls, 1)

    def test_unchanged_v2_scanner_equivalence_and_tie_order(self):
        p, _, _, _ = prepare_tiny(hours=1, lodf=np.zeros((3, 3)))
        f = [Q(3, 7), Q(-11, 5), Q(7, 9)]
        full, _ = p._scan_hour(f, Q(1, 101), 0, None)
        direct = o.v2.row_scan(f, Q(1, 101), p.rated, p.outages, p.lodf, p.normal[0], p.emergency[0])
        for k in direct: np.testing.assert_array_equal(full[k], direct[k])
        # Direct unchanged scanner tie test: normal wins equal emergency rows;
        # otherwise first source-listed nonself outage wins all equal zeros.
        normal = [.125, .25, math.inf]; emergency = [.125, .25, math.inf]
        scan = o.v2.row_scan([Q(1), Q(2), Q(3)], Q(0), p.rated, p.outages, p.lodf, normal, emergency)
        self.assertEqual(scan['kind'].tolist(), [1, 1, 0])
        scan = o.v2.row_scan([Q(1), Q(2), Q(3)], Q(0), p.rated, (2, 0, 1), p.lodf, [10., 10., math.inf], emergency)
        self.assertEqual(scan['outage'][:2].tolist(), [2, 2])

    def test_multi_hour_gap_is_actual_sparse_support_and_balance_failure_visible(self):
        p, x, _, _ = prepare_tiny(hours=3)
        x[p.p_indices[0, 0]] += .01
        result = p.evaluate(x)
        gap = Q(0)
        for record, cut in zip(result['certificate']['hour_certificates'], result['cut_rows']):
            support = sum((o.exact(a)*o.exact(x[j]) for j, a in zip(cut['original_indices'], cut['coefficients'])), Q(0))-o.exact(cut['upper'])
            self.assertEqual(support, Q(*map(int, record['emitted_cut_at_retained_MW'])))
            gap += 5000*(Q(*map(int, record['value_upper_MW']))-support)
        self.assertEqual(gap, Q(*map(int, result['certificate']['support_gap_dollars'])))
        self.assertFalse(result['original_network_lift']['network_residual_le_1e_5'])
        self.assertGreater(result['original_network_lift']['raw_balance_max_abs_upper'], .009)
        self.assertEqual(result['original_network_lift']['values'][p.p_indices[0, 0]], x[p.p_indices[0, 0]])

    def test_full_production_pin_rejected_on_tiny_bits(self):
        data, expected, gen = fixture(hours=1)
        p, _, _, _ = prepare_tiny(hours=1)
        with self.assertRaisesRegex(ValueError, 'full LODF hash mismatch'):
            fp.build_full_scope(data, expected, 1, gen.lodf, p.scope, production_scope=True)


class FullProjectionTests(unittest.TestCase):
    def test_only_eta_upper_changes_with_subset_signature_preserved(self):
        core_dir = HERE.parent/'network-projection-lp-core-v1'
        sys.path.insert(0, str(core_dir))
        spec = importlib.util.spec_from_file_location('_synthetic_core_helpers', core_dir/'test_core.py')
        helpers = importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
        data, expected, H, pairs, sparse_lodf = helpers.tiny_source()
        lodf = np.zeros((3, 3));
        for (l, k), v in sparse_lodf.items(): lodf[l, k] = v
        lodf[1, 0] = 22.; lodf[2, 1] = -17.
        core = fp._core(); old, oldmeta = core.transform_expected(expected, data, H, pairs, lodf)
        subset = dict(normal_signed_rows=oldmeta['network_row_counts']['normal'], seed_signed_rows=oldmeta['network_row_counts']['security'],
                      row_scope_sha256=oldmeta['network_row_signature_sha256'])
        scope = fp.build_full_scope(data, expected, H, lodf, subset)
        new, meta = fp.transform_expected(expected, data, H, pairs, lodf, full_scope=scope)
        self.assertEqual(meta['network_row_signature_sha256'], oldmeta['network_row_signature_sha256'])
        self.assertEqual(meta['network_row_counts'], oldmeta['network_row_counts'])
        self.assertTrue(np.all(new['col_upper'][meta['eta_columns']] > old['col_upper'][oldmeta['eta_columns']]))
        for k in old:
            if k == 'col_upper': continue
            if isinstance(old[k], np.ndarray): np.testing.assert_array_equal(old[k], new[k])
            else: self.assertEqual(old[k], new[k])
        self.assertEqual(meta['full_scope_identity_sha256'], scope['identity_sha256'])
        self.assertEqual(meta['projected_hashes']['col_upper'], core.model_hashes(new)['col_upper'])
        self.assertFalse(meta['full_mps_readback_claimed'])
        self.assertFalse(meta['physical_dc_lower_bound_certified'])
        drift = copy.deepcopy(scope); drift['counts']['signed_security_rows'] -= 2
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            fp.transform_expected(expected, data, H, pairs, lodf, full_scope=drift)
        with self.assertRaises(TimeoutError):
            fp.transform_expected(expected, data, H, pairs, lodf, full_scope=scope, deadline=time.monotonic()-1)


if __name__ == '__main__':
    start = time.monotonic()
    result = unittest.main(verbosity=2, exit=False).result
    elapsed = time.monotonic()-start
    print('Synthetic-only tests:', result.testsRun, 'seconds:', elapsed)
    if elapsed > 20: raise SystemExit('Synthetic test cap exceeded')
    raise SystemExit(0 if result.wasSuccessful() else 1)
