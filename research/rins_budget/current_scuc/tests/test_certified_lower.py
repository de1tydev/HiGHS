"""Tiny/adversarial exact tests only; no solver, model files, or native calls."""
import copy
import hashlib
import json
import math
import sys
import time
import unittest
from fractions import Fraction as Q
from unittest.mock import patch

import numpy as np

from current_scuc.science import certified_lower as cert


def model(c, A=(), rl=(), ru=(), cl=None, cu=None, *, sense=1, offset=0.0):
    n, m = len(c), len(A)
    cl = [0.0]*n if cl is None else cl
    cu = [10.0]*n if cu is None else cu
    starts, indices, values = [0], [], []
    for j in range(n):
        for i in range(m):
            if A[i][j]:
                indices.append(i)
                values.append(A[i][j])
        starts.append(len(values))
    return dict(num_col=n, num_row=m, num_nz=len(values), sense=sense, offset=offset,
                col_cost=list(c), col_lower=list(cl), col_upper=list(cu),
                row_lower=list(rl), row_upper=list(ru), integrality=[0]*n,
                a_start=starts, a_index=indices, a_value=values,
                col_names=['x'+str(j) for j in range(n)],
                row_names=['r'+str(i) for i in range(m)])


def exact(enclosure):
    return Q(*map(int, enclosure['rational']))


def run(e, y):
    return cert.certify(e, y, deadline_monotonic=time.monotonic()+20)


class CertificateTests(unittest.TestCase):
    def assert_enclosure(self, enclosure, wanted=None):
        value = exact(enclosure)
        if wanted is not None:
            self.assertEqual(value, wanted)
        self.assertTrue(enclosure['direction_verified'])
        self.assertLessEqual(Q.from_float(enclosure['down_binary64']), value)
        self.assertGreaterEqual(Q.from_float(enclosure['up_binary64']), value)

    def assert_certificate(self, e, y, wanted, exact_optimum=None):
        result = run(e, y)
        self.assertIs(result['passed'], True)
        self.assertIs(result['exact_projected_matrix_bound_certified'], True)
        self.assert_enclosure(result['original_bound'], wanted)
        self.assert_enclosure(result['normalized_lower'], e['sense']*wanted)
        self.assertGreaterEqual(result['actual_seconds'], 0)
        self.assertEqual(result['original_bound_down'], result['original_bound']['down_binary64'])
        self.assertEqual(result['original_bound_up'], result['original_bound']['up_binary64'])
        self.assertEqual(result['original_bound_direction'], 'lower' if e['sense'] == 1 else 'upper')
        if exact_optimum is not None:
            if e['sense'] == 1:
                self.assertLessEqual(wanted, exact_optimum)
                self.assertLessEqual(Q.from_float(result['original_bound_down']), exact_optimum)
            else:
                self.assertGreaterEqual(wanted, exact_optimum)
                self.assertGreaterEqual(Q.from_float(result['original_bound_up']), exact_optimum)
        # No Infinity/NaN, Fraction, NumPy scalars, or arrays leak into the API.
        json.loads(json.dumps(result, allow_nan=False))
        return result

    def test_row_bound_types_and_sign_projection(self):
        cases = [
            ('lower', [1], [2], [math.inf], [1], Q(2), Q(2), 0),
            ('lower_wrong_sign', [1], [2], [math.inf], [-3], Q(0), Q(2), 1),
            ('upper', [-1], [-math.inf], [2], [-1], Q(-2), Q(-2), 0),
            ('upper_wrong_sign', [-1], [-math.inf], [2], [3], Q(-10), Q(-2), 1),
            ('equality_positive', [1], [2], [2], [1], Q(2), Q(2), 0),
            ('equality_negative', [-1], [2], [2], [-1], Q(-2), Q(-2), 0),
            ('ranged_positive', [1], [2], [4], [1], Q(2), Q(2), 0),
            ('ranged_negative', [-1], [2], [4], [-1], Q(-4), Q(-4), 0),
            ('free_positive', [1], [-math.inf], [math.inf], [7], Q(0), Q(0), 1),
            ('free_negative', [1], [-math.inf], [math.inf], [-7], Q(0), Q(0), 1),
            ('free_zero', [1], [-math.inf], [math.inf], [0], Q(0), Q(0), 0),
        ]
        for label, c, rl, ru, y, wanted, optimum, projected in cases:
            with self.subTest(label=label):
                r = self.assert_certificate(model(c, [[1]], rl, ru), y, wanted, optimum)
                self.assertEqual(r['row_sign_projection_count'], projected)

    def test_column_bound_types_negative_zero_cost_and_offset(self):
        cases = [
            ('finite_positive', [3], [-2], [7], Q(-6)),
            ('finite_negative', [-3], [-2], [7], Q(-21)),
            ('fixed_negative', [-3], [2], [2], Q(-6)),
            ('fixed_positive', [3], [2], [2], Q(6)),
            ('lower_only', [3], [2], [math.inf], Q(6)),
            ('upper_only', [-3], [-math.inf], [2], Q(-6)),
            ('free_zero', [0], [-math.inf], [math.inf], Q(0)),
            ('finite_zero', [0], [-2], [7], Q(0)),
        ]
        for label, c, cl, cu, wanted in cases:
            with self.subTest(label=label):
                self.assert_certificate(model(c, cl=cl, cu=cu, offset=5.5), [], wanted+Q(11, 2), wanted+Q(11, 2))

    def test_maximization_normalizes_cost_offset_and_dual(self):
        r = self.assert_certificate(model([1], [[1]], [-math.inf], [2], sense=-1, offset=7.5), [1], Q(19, 2), Q(19, 2))
        self.assertEqual(r['original_bound_label'], 'ORIGINAL UPPER')
        self.assert_certificate(model([-1], [[1]], [2], [math.inf], sense=-1, offset=17), [-1], Q(15), Q(15))
        self.assert_certificate(model([3], cl=[-2], cu=[7], sense=-1, offset=-5), [], Q(16), Q(16))
        # A positive native max dual on a lower-only row normalizes negative,
        # so projection must occur AFTER normalization.
        r = self.assert_certificate(model([1], [[1]], [2], [math.inf], sense=-1), [3], Q(10), Q(10))
        self.assertEqual(r['row_sign_projection_count'], 1)
        self.assertEqual(r['row_sign_projections'][0]['normalized_input'], ['-3', '1'])

    def test_global_lambda_upper_lower_and_free_equalities(self):
        r = self.assert_certificate(model([1], [[2]], [2], [2], cu=[math.inf], offset=5), [1], Q(6), Q(6))
        self.assertEqual(exact(r['selected_lambda']), Q(1, 2))
        self.assertEqual(exact(r['normalized_offset']), Q(5))
        r = self.assert_certificate(model([1], [[2]], [2], [2], cl=[-math.inf], cu=[math.inf]), [1], Q(1), Q(1))
        self.assertEqual(r['lambda_interval']['lower'], ['1', '2'])
        self.assertEqual(r['lambda_interval']['upper'], ['1', '2'])
        self.assertEqual(r['constraint_counts']['total'], 2)
        r = self.assert_certificate(model([-1], [[-2]], [-4], [math.inf], cu=[math.inf]), [1], Q(-4), Q(-2))
        self.assertEqual(r['lambda_interval']['lower'], ['1', '2'])
        self.assertEqual(exact(r['selected_lambda']), Q(1))
        self.assert_certificate(model([1], [[2]], [2], [math.inf], cl=[-math.inf], cu=[10]), [1], Q(-8), Q(1))

    def test_all_constraints_including_late_column(self):
        e = model([1, 1], [[2, 4]], [0], [0], cu=[math.inf, math.inf])
        r = self.assert_certificate(e, [1], Q(0), Q(0))
        self.assertEqual(exact(r['selected_lambda']), Q(1, 4))
        self.assertEqual(r['constraint_counts']['upper_missing'], 2)
        self.assertEqual(r['lambda_interval']['upper_active'][0]['column'], 1)

    def test_empty_and_zero_intervals_fail_closed(self):
        cases = [
            ('zero_d_negative_upperfree', model([-1], cu=[math.inf]), [], 'empty_lambda_interval'),
            ('zero_d_positive_lowerfree', model([1], cl=[-math.inf]), [], 'empty_lambda_interval'),
            ('zero_only', model([0], [[1]], [0], [0], cu=[math.inf]), [1], 'zero_only_lambda_interval'),
            ('contradictory_columns', model([1, 1], [[4, 2]], [0], [0], cl=[0, -math.inf], cu=[math.inf, 10]), [1], 'empty_lambda_interval'),
            ('negative_free_equality', model([-1], [[2]], [0], [0], cl=[-math.inf], cu=[math.inf]), [1], 'empty_lambda_interval'),
            ('above_one_equality', model([2], [[1]], [0], [0], cl=[-math.inf], cu=[math.inf]), [1], 'empty_lambda_interval'),
        ]
        for label, e, y, code in cases:
            with self.subTest(label=label):
                with self.assertRaises(cert.CertificateError) as caught:
                    run(e, y)
                self.assertEqual(caught.exception.code, code)
                self.assertGreaterEqual(caught.exception.actual_seconds, 0)
                json.dumps(caught.exception.details, allow_nan=False)

    def test_rational_contraction_that_rounds_to_one(self):
        tiny = 2.0**-55
        e = model([1], [[1], [tiny]], [1, 0], [1, math.inf], cu=[math.inf])
        r = self.assert_certificate(e, [1, 1], Q(2**55, 2**55+1), Q(1))
        lam = exact(r['selected_lambda'])
        self.assertEqual(lam, Q(2**55, 2**55+1))
        self.assertEqual(float(lam), 1.0)
        self.assertLess(lam, 1)
        self.assertEqual(r['uncontracted_unsupported_column_count'], 1)
        self.assertEqual(r['q_sign_counts']['zero'], 1)
        self.assertEqual(r['selected_lambda']['down_binary64'], math.nextafter(1.0, 0.0))

    def test_tiny_exact_nonzero_residual_never_zeroed(self):
        tiny = math.ulp(0.0)
        r = self.assert_certificate(model([tiny], cl=[-1], cu=[0]), [], -Q.from_float(tiny), -Q.from_float(tiny))
        self.assertEqual(r['q_sign_counts']['positive'], 1)
        # Tiny negative q on a missing-upper column must contract exactly,
        # even though its magnitude is far below any numerical tolerance.
        e = model([1], [[1], [tiny]], [0, 0], [0, 0], cu=[math.inf])
        r = self.assert_certificate(e, [1, 1], Q(0), Q(0))
        self.assertLess(exact(r['selected_lambda']), Q(1))
        self.assertEqual(float(exact(r['selected_lambda'])), 1.0)
        self.assertEqual(r['uncontracted_unsupported_columns'][0]['q'], [str(-1), str(2**1074)])

    def test_directional_serialization(self):
        cases = [Q(1, 3), Q(-1, 3), Q(0), Q(2**55, 2**55+1), Q(1, 2**1075), -Q(1, 2**1075), Q.from_float(sys.float_info.max)]
        for value in cases:
            with self.subTest(value=value):
                r = cert._enclosure(value)
                self.assert_enclosure(r, value)
                json.dumps(r, allow_nan=False)
        self.assertEqual(cert._enclosure(Q(1, 2**1075))['down_binary64'], 0.0)
        self.assertEqual(cert._enclosure(-Q(1, 2**1075))['down_binary64'], -math.ulp(0.0))

    def test_overflow_rejects_with_exact_context(self):
        for value in (Q.from_float(sys.float_info.max)+1, -Q.from_float(sys.float_info.max)-1, Q(2)**2000):
            with self.subTest(sign=value > 0):
                with self.assertRaises(cert.CertificateError) as caught:
                    cert._enclosure(value)
                self.assertEqual(caught.exception.code, 'binary64_enclosure_overflow')
                self.assertEqual(caught.exception.details['rational'], [str(value.numerator), str(value.denominator)])
        with self.assertRaises(cert.CertificateError) as caught:
            run(model([sys.float_info.max], cl=[2], cu=[2]), [])
        self.assertEqual(caught.exception.code, 'binary64_enclosure_overflow')

    def test_hash_compatibility_and_input_immutability(self):
        e = model([1, -2], [[2, 3]], [-math.inf], [7], cl=[0, -1], cu=[math.inf, 3], offset=0.5)
        before = copy.deepcopy(e)
        y = np.array([0.25])
        r = run(e, y)
        self.assertEqual(e, before)
        self.assertEqual(y.tolist(), [0.25])
        for key in cert.ARRAY_FIELDS:
            dtype = '<i4' if key in cert.INT_FIELDS else '<f8'
            digest = hashlib.sha256(np.asarray(e[key], dtype=dtype).tobytes()).hexdigest()
            self.assertEqual(r['model_hashes'][key], digest)
        for key in ('col_names', 'row_names'):
            self.assertEqual(r['model_hashes'][key], hashlib.sha256('\n'.join(e[key]).encode()).hexdigest())
        for key in cert.SCALAR_FIELDS:
            self.assertEqual(r['model_hashes'][key], e[key])
        self.assertEqual(r['row_dual_sha256'], hashlib.sha256(y.astype('<f8').tobytes()).hexdigest())

    def test_invalid_models_and_duals(self):
        base = model([1], [[1]], [0], [1])
        bad_values = [
            ('num_col', True), ('num_row', -1), ('num_nz', 2**31),
            ('sense', 0), ('sense', True), ('sense', 1.0), ('offset', math.inf), ('offset', math.nan),
            ('col_cost', [math.inf]), ('col_cost', [math.nan]), ('col_cost', ['1']),
            ('a_value', [math.nan]), ('a_value', [0]), ('a_value', [[1]]),
            ('col_lower', [math.inf]), ('col_lower', [11]), ('col_lower', [math.nan]),
            ('col_upper', [-math.inf]), ('row_lower', [2]), ('row_upper', [-math.inf]),
            ('integrality', [1]), ('integrality', [0.0]),
            ('a_start', [0, 2]), ('a_start', [-1, 1]), ('a_start', [0.0, 1.0]),
            ('a_index', [1]), ('a_index', [-1]), ('a_index', [2**32]),
            ('col_names', []), ('row_names', ['']), ('row_names', ['bad\0name']),
        ]
        for key, value in bad_values:
            with self.subTest(key=key, value=value):
                e = copy.deepcopy(base)
                e[key] = value
                with self.assertRaises(cert.CertificateError):
                    run(e, [0])
        for dual in ([math.inf], [math.nan], [], [[0]], ['0'], [complex(1, 0)]):
            with self.subTest(dual=dual):
                with self.assertRaises(cert.CertificateError):
                    run(base, dual)
        e = copy.deepcopy(base)
        del e['row_upper']
        with self.assertRaises(cert.CertificateError):
            run(e, [0])
        e = model([1], [[1], [2]], [0, 0], [1, 1])
        for indices in ([0, 0], [1, 0]):
            e['a_index'] = indices
            with self.assertRaises(cert.CertificateError):
                run(e, [0, 0])

    def test_deadlines_before_and_during_work(self):
        e = model([1], [[1]], [0], [1])
        with self.assertRaises(TimeoutError) as caught:
            cert.certify(e, [0], deadline_monotonic=time.monotonic()-1)
        self.assertGreaterEqual(caught.exception.actual_seconds, 0)
        for deadline in (math.inf, math.nan, None, True):
            with self.subTest(deadline=deadline):
                with self.assertRaises(cert.CertificateError):
                    cert.certify(e, [0], deadline_monotonic=deadline)
        # Mock monotonic time, not a sleep. Each target independently proves a
        # deadline check inside validation, hashing, or exact arithmetic/output.
        for expire_after in (3, 20, 40, 55):
            state = [0]
            def tick():
                state[0] += 1
                return 0.0 if state[0] <= expire_after else 2.0
            with self.subTest(expire_after=expire_after), patch.object(cert.time, 'monotonic', tick):
                with self.assertRaises(TimeoutError):
                    cert.certify(e, [0], deadline_monotonic=1.0)

    def test_deadline_mid_sparse_dot_product(self):
        rows = 1024
        e = model([1], [[1] for _ in range(rows)], [0]*rows, [0]*rows)
        state = {'adds': 0}
        original_add = Q.__add__
        def counted_add(a, b):
            state['adds'] += 1
            return original_add(a, b)
        def tick():
            # The first 1,024 additions assemble row supports; expire after
            # 100 subsequent additions inside the single sparse column dot.
            return 2.0 if state['adds'] >= rows + 100 else 0.0
        with patch.object(Q, '__add__', counted_add), patch.object(cert.time, 'monotonic', tick):
            with self.assertRaises(TimeoutError) as caught:
                cert.certify(e, [1]*rows, deadline_monotonic=1.0)
        self.assertGreaterEqual(state['adds'], rows + 100)
        self.assertLess(state['adds'], 2*rows)
        self.assertEqual(caught.exception.actual_seconds, 2.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
